# Logout Debug Instrumentation

## Overview
Comprehensive debug tracking system to identify the exact code path causing iOS 5-minute logout issue.

## Implementation Date
2025-01-08

## Problem
Users were being logged out after 5 minutes on iOS despite:
- Increasing validation interval from 5 to 60 minutes
- Removing periodic validation entirely
- Adding session recovery logic

The logout is programmatic (some code sets `authenticated=False` or clears session state), so we need to track WHERE it happens.

## Solution Architecture

### 1. Debug Info Storage
All logout events store debug information in `st.session_state['logout_debug_info']` with this structure:

```python
{
    'username': str,              # Last logged-in username
    'logout_type': str,           # 'voluntary' | 'forced' | 'recovery_failed' | 'recovery_error'
    'forced_reason': str | None,  # Machine-readable reason code (if forced)
    'forced_message': str | None, # User-friendly message (if forced)
    'timestamp': str,             # ISO format timestamp
    'code_location': str,         # Function name and line number
    'last_connection': dict | None,  # Connection state at logout
    'session_state_snapshot': dict   # Relevant session_state keys
}
```

### 2. Instrumented Code Paths

#### A. Voluntary Logout (User Clicks Button)
**Location:** `app.py` line ~1128

**Trigger:** User clicks "🚪 Logout" button

**Debug Info Captured:**
- `logout_type`: 'voluntary'
- `code_location`: 'Logout button handler (app.py line ~1128)'
- Connection state before cleanup
- Session snapshot: had_session_id, session_id (truncated), had_authenticated, had_user

#### B. Session Recovery Failed
**Location:** `check_authentication()` line ~948

**Trigger:** `validate_session()` returns None (session_id invalid in database)

**Debug Info Captured:**
- `logout_type`: 'recovery_failed'
- `forced_reason`: 'session_invalid_in_database'
- `forced_message`: 'Session recovery attempted but session_id not valid in database'
- `code_location`: 'check_authentication() line ~948: validate_session() returned None'
- Connection state (if available)
- Session snapshot: had_session_id, session_id (truncated), had_authenticated, had_user

#### C. Session Recovery Error
**Location:** `check_authentication()` line ~970

**Trigger:** Exception during `validate_session()` call (database error, connection issue)

**Debug Info Captured:**
- `logout_type`: 'recovery_error'
- `forced_reason`: 'database_error_during_recovery'
- `forced_message`: Exception details
- `code_location`: Full traceback from exception
- Session snapshot: had_session_id, had_authenticated, exception message

### 3. Debug Info Display

**Location:** `show_login_page()` line ~654

**UI Element:** Expandable section "🔍 Debug Info: Last Logout Details" (collapsed by default)

**Display Sections:**
1. **Last User**: Username of user who was logged out
2. **Logout Path**: Type with color coding (✅ voluntary, ❌ forced, ⚠️ recovery_failed)
3. **Code Location**: Exact function and line number in code block
4. **Timestamp**: ISO format timestamp
5. **Last Connection Data**: JSON snapshot of connection state at logout
6. **Current Connection Data**: Live query of current connection state
7. **Session State Snapshot**: Relevant keys from session_state at logout
8. **Clear Button**: Removes debug info from session_state

## Usage

### For Testing
1. Login to app
2. Trigger logout (click button or wait for timeout)
3. After redirect to login page, expand "🔍 Debug Info" expander
4. Examine `code_location` to see exactly where logout occurred
5. Check connection and session snapshots for state at logout

### For iOS 5-Minute Logout Issue
1. Login on iOS device
2. Keep app open for 5+ minutes
3. When logout occurs, check debug info on login page
4. `code_location` will reveal:
   - If it's recovery_failed: session_id became invalid
   - If it's recovery_error: database connection issue
   - If it's something else: new code path discovered

## Code Locations Reference

| Logout Path | File | Line | Function |
|-------------|------|------|----------|
| Voluntary | app.py | ~1128 | Logout button handler |
| Recovery Failed | app.py | ~948 | check_authentication() |
| Recovery Error | app.py | ~970 | check_authentication() (exception block) |
| Debug Display | app.py | ~654 | show_login_page() |

## Next Steps

After capturing debug info from iOS 5-minute logout:

1. **If `recovery_failed`**: Session is expiring/invalidating prematurely
   - Check MySQL server `wait_timeout` setting
   - Check if something is manually invalidating sessions
   - Verify session sliding window logic

2. **If `recovery_error`**: Database connection issues
   - Check SSH tunnel stability
   - Check MySQL connection pool health
   - Check network connectivity on iOS

3. **If new code path**: Previously unknown logout trigger discovered
   - Add instrumentation to that path
   - Investigate root cause

## Testing Checklist

- [x] Voluntary logout captures debug info
- [ ] Recovery failed path captures debug info (test by manually invalidating session)
- [ ] Recovery error path captures debug info (test by killing database)
- [ ] Debug expander displays all info correctly
- [ ] Clear button removes debug info
- [ ] Debug info persists across page refreshes
- [ ] iOS 5-minute logout captured (CRITICAL - in production)

## Related Documentation

- `docs/dev-docs/AUTH_LOGOUT_ANALYSIS.md` - Original analysis of logout issue
- `docs/dev-docs/PHRASE_SELECTOR_STATE_FIX.md` - State management patterns
- `.github/copilot-instructions.md` - Database connection rules (CRITICAL: never create multiple tunnels)

## Notes

- Debug info is stored in `st.session_state`, so it survives `st.rerun()` but NOT browser refresh
- This is intentional - we want to see info immediately after logout but not clutter state forever
- Connection snapshots are kept small to avoid session state bloat
- All instrumentation uses try/except to ensure logout still works if debug capture fails
