# Miolingo Architecture Overview

**Version:** 3.1.3  
**Date:** December 3, 2025

## System Architecture

### High-Level Components

```diagram
┌─────────────────────────────────────────────────────────────┐
│                     Streamlit Cloud                         │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  Main App (app.py) - Port 8501                        │  │
│  │  - User sessions (one per browser)                    │  │
│  │  - Session state (isolated per user)                  │  │
│  │  - Global SSH tunnel (shared across ALL sessions)     │  │
│  └───────────────────────────────────────────────────────┘  │
│                            │                                │
│                            │ SSH Tunnel                     │
│                            │ (sshtunnel library)            │
│                            ↓                                │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  MySQL Connection Pool                                │  │
│  │  - 10 connections per session_state                   │  │
│  │  - Health validation via ping()                       │  │
│  │  - Auto-recovery on stale connections                 │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ Port 722 (SSH)
                            │ Ed25519 key auth
                            ↓
┌─────────────────────────────────────────────────────────────┐
│              Krystal Hosting (miolingo.io)                  │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  SSH Server (port 722)                                │  │
│  │  - Keepalive: 30 seconds                              │  │
│  │  - fail2ban protection (rate limiting)                │  │
│  └───────────────────────────────────────────────────────┘  │
│                            │                                │
│                            │ Localhost forward              │
│                            ↓                                │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  MySQL/MariaDB 10.6.23 (localhost:3306)               │  │
│  │  - wait_timeout: 28800s (8 hours)                     │  │
│  │  - interactive_timeout: 28800s (8 hours)              │  │
│  │  - Database: fairtlou_miolingo                        │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## Critical Design Patterns

### 1. Global SSH Tunnel (Fixed in v3.1.2)

**Problem:** Originally used `st.session_state.ssh_tunnel`, creating one tunnel per user session. This caused:

- 125+ stale tunnels accumulating
- Server connection limit exhaustion
- fail2ban rate limiting blocks

**Solution:** Global module-level variable `_global_ssh_tunnel`

```python
# src/app_mysql.py
_global_ssh_tunnel = None  # Shared across ALL users

def get_ssh_tunnel():
    global _global_ssh_tunnel
    
    # Health check existing tunnel
    if _global_ssh_tunnel and tunnel_is_healthy():
        return _global_ssh_tunnel
    
    # Create new tunnel if needed
    _global_ssh_tunnel = SSHTunnelForwarder(
        ('miolingo.io', 722),
        ssh_pkey=key,
        remote_bind_address=('127.0.0.1', 3306),
        set_keepalive=30.0  # Prevent idle timeout
    )
    return _global_ssh_tunnel
```

**Key Points:**

- ONE tunnel serves ALL users
- Survives across Streamlit reruns
- Cleaned up only on app shutdown (atexit)
- 30-second keepalive prevents idle disconnect

### 2. Connection Pool Per Session State

Each user has their own connection pool in `st.session_state.mysql_pool`:

- 10 connections per user (increased from 5 for Emerald plan)
- Shares the global SSH tunnel
- Isolated per user session

```python
def get_connection_pool():
    if "mysql_pool" not in st.session_state:
        tunnel = get_ssh_tunnel()  # Get shared tunnel
        st.session_state.mysql_pool = pooling.MySQLConnectionPool(
            pool_name=f"miolingo_pool_{id(st.session_state)}",
            pool_size=10,
            host='127.0.0.1',
            port=tunnel.local_bind_port,  # Tunnel's dynamic port
            # ... MySQL credentials ...
            init_command="SET SESSION wait_timeout=28800, interactive_timeout=28800"
        )
    return st.session_state.mysql_pool
```

### 3. Connection Health Validation (Added in v3.1.3)

Every connection from pool is validated before use:

```python
def get_connection():
    conn = pool.get_connection()
    
    # Ping to validate connection is alive
    try:
        conn.ping(reconnect=True, attempts=3, delay=1)
    except Error:
        # Connection dead - clear pool and recreate
        conn.close()
        del st.session_state.mysql_pool
        return get_connection()  # Recursive retry
    
    return conn
```

**This handles:**

- Stale connections that timed out
- Dead SSH tunnel
- MySQL server restart
- Network interruptions

### 4. Streamlit Session State vs Global State

**Session State (`st.session_state`):**

- Isolated per browser tab/user
- Persists across reruns (button clicks, widget changes)
- Cleared on page reload or tab close
- Examples: `mysql_pool`, `settings`, `authenticated`, `language`

**Global State (module-level variables):**

- Shared across ALL users
- Persists across ALL reruns
- Only cleared on app restart
- Example: `_global_ssh_tunnel`

**Widget State (key="name"):**

- Managed automatically by Streamlit
- Stored in `st.session_state.name`
- **NEVER manually set** - causes race conditions
- Examples: `material_language`, `story_mode`, `active_tab`

## Common Failure Modes

### 1. MySQL Connection Timeout

**Symptoms:**

- "Lost connection to MySQL server during query"
- "Can't connect to MySQL server" (Error 2003)
- Operations hang then fail

**Causes:**

- MySQL `wait_timeout` expired (default 8 hours, we set this)
- SSH tunnel died
- Network interruption
- Server maintenance

**Auto-Recovery:**

1. `get_connection()` pings connection
2. Detects failure
3. Closes stale connection
4. Deletes connection pool
5. `get_connection_pool()` recreates pool
6. `get_ssh_tunnel()` recreates tunnel if needed
7. Returns fresh connection

**Manual Recovery:**

- Refresh page (triggers new connection)
- Wait 30 seconds (auto-recovery may succeed)

### 2. SSH Tunnel Failures

**Symptoms:**

- "Connection refused" on 127.0.0.1:xxxxx
- Authentication errors
- Timeout on database operations

**Causes:**

- fail2ban blocked IP (too many attempts)
- SSH server restart
- Network routing issues
- Key authentication failure

**Prevention:**

- Global tunnel reduces connection attempts
- 30-second keepalive prevents idle timeout
- Auto-reconnect on tunnel death

**Recovery:**

- Global tunnel health check recreates automatically
- Streamlit Cloud uses different IP than your local machine

### 3. Streamlit Cloud App Restart

**When it happens:**

- Code deployment (git push) NO THIS DOESN'T USUALLY HAPPE
- Extended inactivity (no users for ~15 minutes) MAY NEED WAKING, DOES NOT RESTART
- Streamlit Cloud maintenance ONLY BY ADMIN
- Resource limits exceeded NOT YET OBSERVED TO HAPPEN
- THE APP CAN FAIL FOR THOSE REASONS BUT IS NOT AUTOMATICALLY RESTARTED

**What gets reset:**

- Global SSH tunnel (recreated on first use)
- All session states (users must re-login)
- Connection pools (recreated per session)

**What persists:**

- MySQL database content
- User credentials
- Practice history
- Settings (in database for authenticated users)

## Concurrent User Scaling

### Current Capacity

**SSH Tunnel:** 1 global tunnel handles all users efficiently

**MySQL Connections:**

- 10 connections per user session
- Emerald plan likely supports 100+ connections THIS MUST BE CHECKED
- Connection validation prevents stale accumulation

**Streamlit Resources:**

- Free tier: Limited RAM/CPU
- Community Cloud: Shared resources
- May need upgrade for >50 concurrent users

### Load Testing Recommendations

1. **Simulate Multiple Users:**

   ```python
   # Use Locust or similar for load testing
   # Test scenarios:
   # - 10 users practicing simultaneously
   # - 50 users browsing stories
   # - 100 users logging in within 5 minutes
   ```

2. **Monitor Key Metrics:**
   - SSH tunnel stability
   - MySQL connection count: `SHOW PROCESSLIST;`
   - Response times
   - Error rates
   - Streamlit memory usage

3. **Failure Scenarios to Test:**
   - Kill SSH tunnel during practice session
   - Restart MySQL during login
   - Simulate fail2ban IP block
   - Extended idle periods (overnight)
   - Rapid login/logout cycles

4. **Expected Limits:**
   - SSH: Single tunnel, unlimited users
   - MySQL: ~100 connections (10 per user = 10 concurrent users max on current plan)
   - Streamlit: RAM/CPU limits on free tier

### Scaling Strategy

**For 10-50 Users:**

- Current architecture sufficient
- Monitor connection pool usage
- May need MySQL plan upgrade for >10 concurrent sessions

**For 50-200 Users:**

- Upgrade Streamlit hosting (Team or Enterprise) DOES THIS EXIST??
- Connection pool size optimization
- Consider read replicas for statistics/history

**For 200+ Users:**

- Multiple Streamlit instances (load balancer)
- Connection pooling optimization
- Dedicated MySQL server
- Redis for session caching

## Database Schema

### Key Tables

**users:**

- `user_id` (primary key)
- `username`, `email`, `password_hash`
- Authentication data

**user_settings:**

- User-specific preferences
- TTS engine, voice, speed, pitch
- Material language (new in v3.1.3)

**practice_history:**

- Practice session records
- Phrases, results, timestamps
- Used for statistics

**announcements:**

- System-wide messages
- Admin-managed via miolingo-admin.py

## Security Considerations

### Authentication

- Password hashing (bcrypt/similar)
- Session secrets in `secrets.toml`
- JWT or session-based auth

### SSH Tunnel

- Ed25519 key authentication (no password)
- Key stored in Streamlit secrets
- No key exposed in code/git

### Database

- Localhost-only access (not exposed to internet)
- SSH tunnel encrypts all traffic
- User-specific permissions

### Secrets Management

- `secrets.toml` (local development)
- Streamlit Cloud secrets (deployment)
- Never committed to git

## Debugging Tools

### Check SSH Tunnel Status

```bash
# Local machine
ps aux | grep "ssh.*miolingo.io"
lsof -ti:3333  # Check if tunnel listening

# On Krystal server (jailshell)
who  # See active SSH sessions
```

### Check MySQL Connection

```bash
# Via tunnel
mysql -h 127.0.0.1 -P 3333 -u fairtlou_miolingo_matthew -p

# Check connections
SHOW PROCESSLIST;
SHOW STATUS LIKE 'Threads_connected';
```

### Streamlit Debugging

```python
# In app.py - State change tracking (already implemented)
st.warning(f"🔍 State changed: {changes}")

# Connection pool info
st.write(f"Pool size: {len(st.session_state.mysql_pool._cnx_queue.queue)}")

# Tunnel info
st.write(f"Tunnel port: {_global_ssh_tunnel.local_bind_port}")
st.write(f"Tunnel active: {_global_ssh_tunnel.is_active}")
```

## Recent Fixes Timeline

### v3.1.2 (Dec 2, 2025)

- Fixed SSH tunnel leak (per-session → global)
- Fixed eSpeak binary path
- Separated quick/story result storage
- Added MySQL connection health validation

### v3.1.3 (Dec 3, 2025)

- Fixed tab bouncing (st.tabs → radio buttons)
- Settings persistence (language saved/loaded)
- Language/voice alignment on login
- Story mode preservation across tabs
- Clean debug output (no false changes)

## Next Steps for Production

1. **Load Testing:**
   - Simulate 10+ concurrent users
   - Monitor SSH tunnel stability
   - Check MySQL connection limits
   - Measure response times

2. **Monitoring Setup:**
   - Application logging (errors, warnings)
   - Database query performance
   - SSH tunnel health checks
   - User session metrics

3. **Capacity Planning:**
   - MySQL connection limit: Current vs needed
   - Streamlit hosting tier evaluation
   - Cost analysis for scaling

4. **Backup Strategy:**
   - Database backup schedule
   - Practice history retention policy
   - User data export capability

5. **Documentation:**
   - User onboarding guide
   - Admin operations manual
   - Incident response playbook

## Questions to Answer

1. **Current MySQL connection limit?**
   - Check with Krystal hosting plan details
   - Test with: `SHOW VARIABLES LIKE 'max_connections';`

2. **Streamlit Cloud resource limits?**
   - Free tier vs Team tier comparison
   - Memory/CPU allocation

3. **Expected user concurrency?**
   - Peak usage patterns
   - Growth projections

4. **Acceptable downtime tolerance?**
   - SLA requirements
   - Maintenance windows

## Contact & Support

- **Hosting:** Krystal (miolingo.io)
- **Database:** MySQL/MariaDB 10.6.23
- **Platform:** Streamlit Cloud
- **Repository:** <https://github.com/fairflow/miolingo>
- **Support Email:** <io@miolingo.io>

---

**Document Maintained By:** Development Team  
**Last Updated:** December 3, 2025  
**Version:** 3.1.3
