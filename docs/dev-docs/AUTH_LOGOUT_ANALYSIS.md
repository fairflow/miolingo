# Authentication and Logout Analysis

**Date:** 3 January 2026  
**Issue:** Users experiencing forced logout after ~5 minutes of inactivity on iOS via app.miolingo.io  
**Branch:** main (7.1.3)  
**Status:** Research completed - potential causes identified

---

## Problem Statement

Despite increasing the session validation interval from 5 minutes to 60 minutes (commit 3cf4f4f), users are still being logged out after approximately 5 minutes of inactivity. This suggests the issue is NOT the periodic validation check in `check_authentication()`.

---

## Key Findings

### 1. Session Validation Mechanism (app.py, lines 840-906)

**Current behavior:**
- Checks session validity every 60 minutes (recently changed from 5 minutes)
- Uses `app_mysql.validate_session()` to check database
- On validation failure: forces logout with reason "session_invalid"
- On database error: shows warning but KEEPS user logged in

**This is NOT the source of 5-minute logouts** because:
- Interval is now 60 minutes
- Database errors don't cause logout
- Only explicit session expiry triggers logout

### 2. Session Expiration in Database (app_mysql.py, lines 746-780, 908-1050)

**Session expiry settings:**
```python
get_session_inactivity_days() -> int  # Default: 7 days
```

**Sources (priority order):**
1. `MIOLINGO_SESSION_INACTIVITY_DAYS` environment variable
2. `st.secrets.session_inactivity_days`
3. `st.secrets.session.inactivity_days`
4. Default: 7 days

**Sliding expiration behavior:**
- `validate_session()` refreshes `expires_at` on every check
- Sets: `expires_at = NOW() + 7 days` (or configured value)
- Database query: `WHERE s.expires_at > NOW() AND s.status = 'active'`

**This is NOT the source** because:
- 7 days is much longer than 5 minutes
- Expiry is refreshed on validation (every 60 minutes)
- Database doesn't have 5-minute timeout

### 3. MySQL Connection Timeouts (app_mysql.py, line 233)

**MySQL session configuration:**
```python
init_command="SET SESSION wait_timeout=28800, interactive_timeout=28800"  # 8 hours
```

**This is NOT the source** because:
- 8 hours = 28800 seconds (not 5 minutes)
- Connection timeouts don't trigger automatic logout
- Connection errors show warning, don't force logout

### 4. Connection Pool Cleanup (connection_pool.py, lines 95-97)

**Background cleanup settings:**
```python
AUTO_CLEANUP_INTERVAL_MINUTES = 10  # How often to run background cleanup
IDLE_CONNECTION_THRESHOLD_MINUTES = 60 * 24 * 7  # 7 days before closing idle connections
```

**Cleanup process:**
- Runs every 10 minutes in background
- Only closes connections idle for 7+ days
- Uses `cleanup_dead_connections()` to verify with `SHOW PROCESSLIST`
- Marks dead connections as 'closed' in database

**This is NOT the direct source** because:
- 10-minute cleanup interval doesn't match 5-minute logout pattern
- 7-day idle threshold is much longer than 5 minutes
- Closing a connection doesn't automatically trigger logout

### 5. **POTENTIAL CULPRIT: Streamlit Rerun Behavior**

**Hypothesis:** iOS Safari/Mobile browsers may have aggressive background tab suspension.

When iOS puts browser tab in background:
1. **JavaScript execution pauses** → Streamlit websocket disconnects
2. **When user returns:** Streamlit reconnects and triggers full rerun
3. **Rerun calls `check_authentication()`** 
4. **If 5 minutes elapsed since last validation:**
   - Old logic: would validate immediately (every 5 min)
   - New logic: only validates if 60 min elapsed
5. **CRITICAL: Validation uses database connection**
   - If connection was idle, MySQL might have closed it
   - **Connection attempt fails** during rerun
   - Failure during validation could cause logout

**Evidence:**
- Only happening on iOS (aggressive tab suspension)
- Timing aligns with typical mobile browser background timeouts
- Local Mac testing doesn't show issue (no tab suspension)

### 6. SSH Tunnel State During Inactivity

**Tunnel configuration:**
- One tunnel shared across all connections for a session
- Stored in `st.session_state.ssh_tunnel`
- Connection pool tracks tunnel state in memory and database

**Potential issue:**
- If Mac sleeps (before caffeinate), tunnel dies
- If tunnel dies, connection fails
- Connection failure during validation could trigger logout

**Current mitigation:**
- `caffeinate` keeps Mac awake
- Should prevent tunnel death

---

## Logout Trigger Points (Documented in app.py, lines 602-615)

### Voluntary Logout
- User clicks "🚪 Logout" button
- Sets `voluntary_logout` flag
- Calls `app_mysql.delete_session()`
- Closes all connections
- No warning shown (expected behavior)

### Forced Logout - Session Invalid
- `validate_session()` returns `None`
- Sets `forced_logout_reason = "session_invalid"`
- Sets `forced_logout_message` with explanation
- Shows warning on next login page

---

## Theories for 5-Minute Logout

### Theory 1: Database Query During Rerun Fails ⭐ MOST LIKELY
**What happens:**
1. User idle for 5+ minutes on iOS
2. iOS suspends browser tab
3. User returns, Streamlit reconnects
4. Rerun triggers, hits some database query BEFORE authentication check
5. Database connection is stale (idle too long at MySQL level, not our timeout)
6. Query fails with connection error
7. Error handling somewhere forces logout

**Why this fits:**
- Timing matches (5 minutes)
- Only on iOS (tab suspension)
- MySQL has its own timeouts independent of our settings

**Investigation needed:**
- Check MySQL server's `wait_timeout` setting (might be 300 seconds = 5 minutes!)
- Our client sets 8 hours, but server might override
- Look for database queries BEFORE `check_authentication()` in main app flow

### Theory 2: Streamlit Session State Loss
**What happens:**
1. iOS suspends tab
2. Streamlit session state partially cleared
3. Missing `session_id` or `authenticated` flag
4. Triggers logout on reconnect

**Why this might fit:**
- Mobile browsers clear memory aggressively
- Streamlit session state stored in browser memory

**Investigation needed:**
- Add logging to track session state persistence
- Log `session_id`, `authenticated`, `last_session_check` values on each rerun

### Theory 3: Connection Pool Eviction
**What happens:**
1. Connection idle for 5 minutes
2. Connection pool or MySQL evicts it
3. Next query attempts to use dead connection
4. Failure triggers logout

**Why this might fit:**
- Could be internal MySQL timeout
- Connection pool might have additional logic not documented

**Investigation needed:**
- Check for undocumented timeouts in connection pool
- Verify MySQL server-side timeout settings

---

## Recommended Actions (For refactor-auth Branch)

### Immediate Testing (No Code Changes)

1. **Check MySQL server timeout settings:**
   ```sql
   SHOW VARIABLES LIKE '%timeout%';
   ```
   Look for:
   - `wait_timeout` (might be 300 seconds = 5 minutes!)
   - `interactive_timeout`
   - These override client settings if server value is lower

2. **Add diagnostic logging:**
   - Log every rerun with timestamp
   - Log `session_id`, `authenticated`, `last_session_check` values
   - Log database query attempts and results
   - Track iOS vs desktop behavior

3. **Test with different devices:**
   - Desktop browser (should work fine)
   - iOS Safari
   - iOS Chrome
   - Android browser

### Code Changes to Consider (refactor-auth branch)

#### Option A: Remove Periodic Validation Entirely ⭐ RECOMMENDED

**Rationale:** Session validation might be unnecessary complexity.

**Current:** Check every 60 minutes
**Proposed:** Only validate on login, never during active session

**Implementation:**
```python
def check_authentication():
    # Initialize session state
    if 'authenticated' not in st.session_state:
        st.session_state['authenticated'] = False
    
    # Check if authenticated
    if not st.session_state['authenticated']:
        show_login_page()
        st.stop()
    
    # NO PERIODIC VALIDATION
    # Trust browser session state until user logs out or session expires on server
    # If database connection fails, show error but don't logout
```

**Benefits:**
- Eliminates validation-related logouts
- Reduces database queries
- Simpler code
- Session still expires on server after 7 days (database enforces)

**Risks:**
- Expired sessions won't be detected until next login
- Session hijacking window longer (but still limited by 7-day server expiry)

#### Option B: Make Validation Failures Non-Fatal

**Keep validation but don't logout on failure:**
```python
if now - last_check > 3600:
    try:
        user = app_mysql.validate_session(st.session_state['session_id'], "127.0.0.1")
        if not user:
            # Show warning but DON'T logout
            st.warning("⚠️ Session validation failed. You may need to re-login soon.")
        else:
            st.session_state['last_session_check'] = now
    except Exception as e:
        # Already shows warning, doesn't logout
        pass
```

#### Option C: Add Connection Retry Logic

**Retry failed database operations before giving up:**
```python
def validate_session_with_retry(session_id, ip, retries=3):
    for attempt in range(retries):
        try:
            return app_mysql.validate_session(session_id, ip)
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(1)  # Wait 1 second
                continue
            raise  # Final attempt failed
```

#### Option D: Remove Connection Pool Complexity

**Simplify to basic connection-per-request:**
- Eliminate connection pooling
- Create fresh connection for each query
- Simpler, more reliable (but slightly slower)

---

## Additional Observations

### Mac Sleep Issue (RESOLVED)
- Previously: Mac sleeping killed tunnel and connections
- Solution: `caffeinate` script (scripts/keep_alive.sh) keeps Mac awake
- No longer a source of logouts

### Cloudflare Tunnel Stability
- Tunnel connector runs continuously via Cloudflare
- Appears stable during testing
- No evidence of tunnel disconnections causing logouts

### iOS-Specific Behavior
- iOS Safari aggressively suspends background tabs
- May lose websocket connection
- Streamlit reconnects on tab resume
- This rerun might trigger the logout

---

## Next Steps

1. **Check MySQL server timeout:** Most likely culprit is server-side 5-minute timeout
2. **Add diagnostic logging:** Track exact sequence of events during logout
3. **Test Option A:** Remove periodic validation entirely on refactor-auth branch
4. **Monitor results:** Test with iOS for 10-15 minutes idle
5. **If still fails:** Investigate Streamlit session state persistence on iOS

---

## References

- `src/app.py` lines 840-906: Authentication check and validation
- `src/app_mysql.py` lines 746-780: Session inactivity configuration
- `src/app_mysql.py` lines 908-1050: Session validation logic
- `src/connection_pool.py` lines 90-110: Connection pool timeouts
- `src/connection_pool.py` lines 786-830: Connection cleanup logic
- Issue #12: iOS microphone permissions (related to HTTPS requirement)
- PR #14: refactor-auth merge with connection pool improvements

---

**Conclusion:** The 5-minute logout issue is likely caused by MySQL server-side timeout settings (300 seconds = 5 minutes) overriding our 8-hour client timeout. When iOS suspends the tab, the connection becomes idle. On resume, Streamlit reruns, attempts a database query with the now-stale connection, fails, and triggers logout logic somewhere in the flow.

**Primary recommendation:** Check MySQL server `wait_timeout` and either increase it server-side or implement robust connection retry logic. Consider removing periodic validation entirely as it adds complexity without clear benefit for this use case.
