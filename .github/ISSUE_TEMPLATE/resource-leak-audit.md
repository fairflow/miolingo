---
name: Resource Leak Audit
about: Comprehensive audit of all resource cleanup across codebase
title: '[AUDIT] Resource Leak Prevention - Database Connections, SSH Tunnels, Files'
labels: 'bug, performance, technical-debt'
assignees: ''
---

## Problem
Connection pool exhaustion occurred in admin app due to database connections not being closed. Need comprehensive audit of ALL resource cleanup across entire codebase.

## Scope
Audit all code for proper resource cleanup with try/finally blocks:

### 1. Database Connections
- [ ] `src/app.py` - All `app_mysql.get_connection()` calls
- [ ] `src/app_mysql.py` - Internal connection management
- [x] `src/miolingo-admin.py` - **FIXED** in commit [hash]
- [ ] `src/practice_app.py` - If uses database
- [ ] `src/*` - Any other files using database

**Pattern to check:**
```python
conn = get_connection()
try:
    # ... use connection ...
finally:
    if conn:
        conn.close()
```

### 2. SSH Tunnels
- [ ] `src/app_mysql.py` - `_global_ssh_tunnel` lifecycle
- [ ] Verify tunnel is stopped on app shutdown
- [ ] Check for leaked tunnels in error paths

**Questions:**
- When/how is global tunnel cleaned up?
- What happens on Streamlit Cloud restart?
- Are there zombie tunnels accumulating?

### 3. File Handles
- [ ] `src/app_language_materials.py` - File reading operations
- [ ] `src/*` - Any file I/O operations
- [ ] Audio file generation/cleanup
- [ ] Temp file cleanup

**Pattern to check:**
```python
with open(file_path) as f:
    # Automatically closed
```

### 4. Audio Resources
- [ ] `soundfile` operations
- [ ] `ffmpeg` subprocess cleanup
- [ ] Temp audio file deletion
- [ ] Memory cleanup for large audio buffers

### 5. Model Resources  
- [ ] Whisper model loading/unloading
- [ ] Wav2Vec2 model cleanup
- [ ] GPU/CPU memory management

### 6. Guest User Cleanup
- [ ] No limits on concurrent guests (can exhaust connections!)
- [ ] Old guest accounts never deleted
- [ ] Need automated cleanup job

**Proposed solution:**
```python
def cleanup_old_guests():
    """Delete guest users older than 7 days"""
    DELETE FROM users 
    WHERE username LIKE 'guest_%' 
    AND created_at < DATE_SUB(NOW(), INTERVAL 7 DAY)
```

### 7. Session Cleanup
- [ ] Expired sessions not automatically removed
- [ ] Need periodic cleanup job
- [ ] Currently manual via admin panel

## Connection Pool Math
- MySQL Emerald: **25 concurrent connections**
- App pool size: **10 connections per session**
- Theoretical max: **2-3 simultaneous users**
- Current: **NO GUEST LIMITS** = potential DoS

## Priority Fixes
1. **CRITICAL**: Limit concurrent guests (check count, max 3)
2. **HIGH**: Add guest cleanup job (run daily)
3. **HIGH**: Audit main app.py for connection leaks
4. **MEDIUM**: Add connection pool monitoring/alerts
5. **LOW**: Audit other resource types

## Testing
- [ ] Load test with multiple concurrent users
- [ ] Monitor connection pool usage
- [ ] Verify cleanup jobs run successfully
- [ ] Check for zombie processes/tunnels

## Related Issues
- Pool exhaustion in admin: [describe incident]
- Session validation causing logouts: [link if exists]

## Notes
- Admin app fixes completed but main app not yet audited
- Need to distinguish critical (connection) vs nice-to-have (file) leaks
- Consider adding connection pool health metrics to admin dashboard
