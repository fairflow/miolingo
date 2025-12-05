# Connection Monitor - Experimental Architecture

**Status:** Experimental (Development Branch: `feature/connection-monitor`)  
**Version:** 0.1.0  
**Purpose:** Explore robust connection pool architecture before integrating into main apps

---

## Overview

This standalone monitoring app explores a new architecture for managing SSH tunnels, database connections, and user sessions. It replaces the single global tunnel approach with a pool-based system that provides better visibility, control, and resource management.

## Key Design Decisions

### 1. **Pool of 10 SSH Tunnels** (not 1 global tunnel)
- **Why:** Distribute load, isolate failures, enable selective cleanup
- **Current:** Single `_global_ssh_tunnel` shared across ALL users
- **New:** 10 independent tunnels, load-balanced by connection count
- **Benefit:** If one tunnel dies, only affects 25 connections (not all users)

### 2. **25 DB Connections per Tunnel** (250 total capacity)
- **Why:** Stay under MySQL Emerald plan limit (300) with safety margin
- **Math:** 10 tunnels × 25 connections = 250 capacity
- **Monitoring:** Track active connections, prevent exceeding capacity
- **Action on limit:** Block new logins/registrations when approaching 250

### 3. **Comprehensive Session Tracking**
Each user session stores:
- **session_id:** Unique identifier
- **username:** User account name
- **user_ip:** IP address (for security/debugging)
- **user_agent:** Full user agent string
- **device_type:** iOS, Android, macOS, Windows, Linux
- **browser:** Safari, Chrome, Firefox, Edge
- **login_time:** When session started
- **expires_at:** 7 days from login
- **last_activity:** Updated on each action
- **status:** active, expired, forced_logout

### 4. **Process ID Tracking**
- SSH tunnels run in threads (not separate processes in Python)
- Store parent process PID: `os.getpid()`
- Future: Could spawn actual subprocesses for true isolation
- Benefit: Can monitor process health, kill if needed

### 5. **Connection Handle Registry**
Each connection tracked with:
- **connection_id:** UUID-based identifier (e.g., `conn_a3b5c7d9`)
- **conn_obj:** Actual `mysql.connector` connection object (the handle)
- **mysql_conn_id:** MySQL's internal `CONNECTION_ID()` from `SHOW PROCESSLIST`
- **tunnel_id:** Which tunnel this connection uses
- **session_id:** Which user session owns this connection
- **created_at, last_activity:** Timestamps for idle detection
- **status:** active, idle, closed

---

## Database Schema

### `tunnel_monitor` Table
Tracks SSH tunnel lifecycle and health.

```sql
CREATE TABLE tunnel_monitor (
    id INT AUTO_INCREMENT PRIMARY KEY,
    tunnel_id VARCHAR(50) UNIQUE NOT NULL,          -- tunnel_0, tunnel_1, ...
    pid INT,                                         -- Process ID
    local_port INT,                                  -- Local bind port
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    status ENUM('active', 'idle', 'dead') DEFAULT 'active',
    connection_count INT DEFAULT 0,
    INDEX idx_tunnel_id (tunnel_id),
    INDEX idx_status (status)
);
```

### `connection_monitor` Table
Tracks database connection lifecycle.

```sql
CREATE TABLE connection_monitor (
    id INT AUTO_INCREMENT PRIMARY KEY,
    connection_id VARCHAR(100) UNIQUE NOT NULL,     -- conn_abc123...
    mysql_connection_id INT,                        -- MySQL SHOW PROCESSLIST ID
    tunnel_id VARCHAR(50),
    session_id VARCHAR(100),
    username VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    status ENUM('active', 'idle', 'closed') DEFAULT 'active',
    INDEX idx_connection_id (connection_id),
    INDEX idx_tunnel_id (tunnel_id),
    INDEX idx_session_id (session_id),
    INDEX idx_status (status),
    FOREIGN KEY (tunnel_id) REFERENCES tunnel_monitor(tunnel_id) ON DELETE SET NULL
);
```

### `session_monitor` Table
Tracks user sessions with device/browser info.

```sql
CREATE TABLE session_monitor (
    id INT AUTO_INCREMENT PRIMARY KEY,
    session_id VARCHAR(100) UNIQUE NOT NULL,
    username VARCHAR(100) NOT NULL,
    user_ip VARCHAR(45),                            -- IPv4 or IPv6
    user_agent TEXT,                                -- Full user agent string
    device_type VARCHAR(50),                        -- iOS, Android, macOS, etc.
    browser VARCHAR(50),                            -- Safari, Chrome, etc.
    login_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,                           -- 7 days from login
    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    status ENUM('active', 'expired', 'forced_logout') DEFAULT 'active',
    INDEX idx_session_id (session_id),
    INDEX idx_username (username),
    INDEX idx_status (status),
    INDEX idx_expires_at (expires_at)
);
```

---

## Architecture Components

### Data Structures (Python)

```python
@dataclass
class TunnelInfo:
    tunnel_id: str              # tunnel_0, tunnel_1, ...
    tunnel_obj: SSHTunnelForwarder  # Actual tunnel object
    pid: int                    # Process ID
    local_port: int             # Local bind port
    created_at: datetime
    last_used: datetime
    status: str                 # active, idle, dead
    connection_count: int       # Current connections using this tunnel

@dataclass
class ConnectionInfo:
    connection_id: str          # conn_uuid
    conn_obj: mysql.connector   # Connection handle
    mysql_conn_id: int          # MySQL's CONNECTION_ID()
    tunnel_id: str              # Which tunnel
    session_id: str             # Which user session
    username: str
    created_at: datetime
    last_activity: datetime
    status: str                 # active, idle, closed

@dataclass
class SessionInfo:
    session_id: str
    username: str
    user_ip: str
    user_agent: str
    device_type: str            # Parsed from user agent
    browser: str                # Parsed from user agent
    login_time: datetime
    expires_at: datetime        # 7 days from login
    last_activity: datetime
    connection_ids: List[str]   # All connections this session uses
```

### Global Registries (In-Memory)

```python
TUNNEL_POOL: Dict[str, TunnelInfo] = {}
CONNECTION_REGISTRY: Dict[str, ConnectionInfo] = {}
SESSION_REGISTRY: Dict[str, SessionInfo] = {}
```

---

## Resource Management

### Tunnel Management

**Creating Tunnels:**
```python
def get_or_create_tunnel() -> Tuple[str, TunnelInfo]:
    # 1. Find tunnel with lowest connection count
    # 2. If all at capacity, create new tunnel (if under 10 limit)
    # 3. If pool exhausted, raise exception
```

**Closing Tunnels:**
```python
def close_tunnel(tunnel_id: str) -> bool:
    # 1. Close all connections using this tunnel
    # 2. Stop SSH tunnel process
    # 3. Update database status to 'dead'
    # 4. Remove from TUNNEL_POOL
```

### Connection Management

**Getting Connections:**
```python
def get_connection(session_id, username) -> Tuple[str, connection]:
    # 1. Check if at capacity (250 connections)
    # 2. Get or create tunnel
    # 3. Create MySQL connection via tunnel
    # 4. Register in CONNECTION_REGISTRY
    # 5. Record in database
```

**Closing Connections:**
```python
def close_connection(connection_id: str) -> bool:
    # 1. Close MySQL connection (conn.close())
    # 2. Decrement tunnel connection count
    # 3. Update database status to 'closed'
    # 4. Remove from CONNECTION_REGISTRY
```

**Cleanup Idle Connections:**
```python
def cleanup_idle_connections(idle_threshold_minutes: int = 10):
    # 1. Find connections idle > threshold
    # 2. Close each one
    # 3. Return count of closed connections
```

### Session Management

**Registering Sessions:**
```python
def register_session(username, session_id, user_ip, user_agent, expires_at):
    # 1. Parse user agent → device_type, browser
    # 2. Create SessionInfo
    # 3. Store in SESSION_REGISTRY
    # 4. Record in database
```

**Parsing User Agent:**
```python
def parse_user_agent(user_agent: str) -> Tuple[str, str]:
    # Device detection: iOS, Android, macOS, Windows, Linux
    # Browser detection: Safari, Chrome, Firefox, Edge
    # Returns: (device_type, browser)
```

---

## UI Pages

### 📊 Dashboard
- Active tunnels (current / max 10)
- Active connections (current / max 250)
- Active sessions (count)
- Pool capacity percentage
- Resource usage chart

### 🔌 Tunnels
- List all tunnels in pool
- For each tunnel:
  - PID, local port
  - Created/last used timestamps
  - Connection count (current / 25)
  - Status (active, idle, dead)
  - **Action:** Close tunnel button

### 🔗 Connections
- List all active connections
- For each connection:
  - MySQL connection ID
  - Tunnel ID it uses
  - Session ID (if linked to user)
  - Username
  - Created/last activity timestamps
  - **Action:** Close connection button

### 👥 Sessions
- Statistics:
  - Active session count
  - Breakdown by device type
  - Breakdown by browser
- Detailed session list:
  - Username, IP address
  - Device type, browser
  - Login time, last activity
  - **Time remaining** until expiry (hours:minutes:seconds)

### ⚙️ Controls
- **Close Idle Connections:** Configurable idle threshold (minutes)
- **Close All Tunnels:** Nuclear option (closes everything)
- **Configuration Display:** Max tunnels, connections per tunnel, total capacity

---

## What We Can Do with Handles

### Connection Handles
```python
# Close specific connection
conn_obj.close()

# Check if connection still alive
conn_obj.is_connected()

# Get MySQL's internal connection ID
cursor.execute("SELECT CONNECTION_ID()")
mysql_conn_id = cursor.fetchone()[0]

# Force-close from server side (if we have admin privileges)
cursor.execute("KILL CONNECTION %s", (mysql_conn_id,))
```

### Tunnel Process Handles
```python
# Stop SSH tunnel
tunnel_obj.stop()

# Check if tunnel is active
tunnel_obj.is_active

# Kill process (if we spawn as subprocess in future)
os.kill(pid, signal.SIGTERM)
os.kill(pid, signal.SIGKILL)  # Force kill
```

---

## Current Limitations vs Main Apps

### What This App Does NOT Do Yet:
1. **No authentication:** Direct access, no login (local-only)
2. **No integration:** Doesn't connect to `app.py` or `miolingo-admin.py`
3. **No real user tracking:** Mock data only (until integrated)
4. **No automatic cleanup:** Requires manual trigger in Controls page
5. **No alerts:** Doesn't warn when approaching capacity limits

### Differences from Current Architecture:
| Aspect | Current (`app_mysql.py`) | New (Connection Monitor) |
|--------|-------------------------|--------------------------|
| Tunnels | 1 global tunnel | Pool of 10 tunnels |
| Connections | Created on-demand, no registry | Full registry with handles |
| Session tracking | Basic (username, expires_at) | Comprehensive (IP, device, browser) |
| Monitoring | Debug logs only | Real-time dashboard |
| Cleanup | None (connections leak) | Manual + idle timeout |
| Capacity limits | No enforcement | Hard limits with prevention |

---

## Next Steps for Integration

### Phase 1: Testing & Validation
- [ ] Test tunnel pool under load (simulate multiple users)
- [ ] Verify connection cleanup works correctly
- [ ] Test idle connection timeout (10-minute threshold)
- [ ] Ensure database tables don't leak space
- [ ] Monitor for memory leaks in registries

### Phase 2: Authentication Integration
- [ ] Add login system (copy from `app.py`)
- [ ] Require authentication to access monitor
- [ ] Admin-only access (not for regular users)

### Phase 3: Main App Integration
- [ ] Refactor `app_mysql.py` to use tunnel pool
- [ ] Replace `_global_ssh_tunnel` with `get_or_create_tunnel()`
- [ ] Add session registration calls in `create_session()`
- [ ] Integrate connection registry into `get_connection()`
- [ ] Add automatic cleanup on session logout

### Phase 4: Alerting & Automation
- [ ] Email/log alerts when capacity > 80%
- [ ] Auto-reject logins when capacity > 90%
- [ ] Automatic idle connection cleanup (background thread)
- [ ] Automatic dead tunnel removal
- [ ] Health check endpoint for external monitoring

---

## Questions & Design Decisions

### Q: Can we actually kill tunnel processes?
**A:** Python's `SSHTunnelForwarder` uses threads, not separate processes. We store the parent process PID (`os.getpid()`), but can't kill individual tunnels this way. To get true process isolation:
- Option 1: Spawn tunnels as subprocesses (`subprocess.Popen`)
- Option 2: Use `multiprocessing` module
- Current: Thread-based (good enough for now)

### Q: What happens to dropped connections?
**A:** MySQL will timeout idle connections server-side. Our cleanup function (`cleanup_idle_connections`) will:
1. Detect connections idle > threshold
2. Try to close them gracefully (`conn.close()`)
3. If already dead, just remove from registry
4. Decrement tunnel connection count

### Q: How do we prevent login when at capacity?
**A:** In main app integration:
```python
def can_create_session() -> Tuple[bool, str]:
    active = sum(1 for c in CONNECTION_REGISTRY.values() if c.status == 'active')
    if active >= MAX_TOTAL_CONNECTIONS * 0.9:  # 90% threshold
        return False, "Server at capacity. Please try again later."
    return True, ""
```

### Q: Should we use connection pooling?
**A:** We're already doing our own pooling:
- `CONNECTION_REGISTRY` is essentially a connection pool
- `mysql.connector.pooling` would add another layer
- Current approach gives us more control and visibility
- Decision: Stay with manual registry for now

---

## Running the Monitor

### Local Development
```bash
# Create/switch to feature branch
git checkout -b feature/connection-monitor

# Run on port 8503 (avoids conflicts)
streamlit run src/connection_monitor.py --server.port 8503
```

### Access
- Local: http://localhost:8503
- Network: http://192.168.178.40:8503 (your local network IP)

### Requirements
- Same as main app (`requirements.txt`)
- `.streamlit/secrets.toml` with SSH and MySQL credentials
- MySQL Emerald plan access

---

## Security Notes

⚠️ **This app has FULL database access:**
- Can close any connection
- Can kill any tunnel
- Can view all user sessions and IPs
- **DO NOT deploy publicly without authentication**
- Keep on `feature/connection-monitor` branch until secured

---

## Changelog

### v0.1.0 (2025-12-05)
- Initial experimental implementation
- Pool of 10 SSH tunnels
- 25 connections per tunnel (250 total)
- Database tables: `tunnel_monitor`, `connection_monitor`, `session_monitor`
- Basic Streamlit UI with 5 pages
- Manual cleanup controls
- Device and browser detection from user agent

---

## References
- Main app: `src/app.py`
- Database module: `src/app_mysql.py`
- Admin app: `src/miolingo-admin.py`
- SSH tunnel docs: https://github.com/pahaz/sshtunnel
- MySQL connector: https://dev.mysql.com/doc/connector-python/en/
