-- Migration: Merge session_monitor columns into sessions table
-- Purpose: Consolidate duplicate session tracking into single source of truth
-- Date: 2025-12-11
-- Branch: feature/admin-fusion

-- Step 1: Add new columns from session_monitor to sessions table
ALTER TABLE sessions
ADD COLUMN IF NOT EXISTS username VARCHAR(100) AFTER user_id,
ADD COLUMN IF NOT EXISTS user_agent TEXT AFTER ip_address,
ADD COLUMN IF NOT EXISTS device_type VARCHAR(50) AFTER user_agent,
ADD COLUMN IF NOT EXISTS browser VARCHAR(50) AFTER device_type,
ADD COLUMN IF NOT EXISTS app_name VARCHAR(50) DEFAULT 'app' AFTER browser,
ADD COLUMN IF NOT EXISTS last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP AFTER expires_at,
ADD COLUMN IF NOT EXISTS status ENUM('active','expired','forced_logout') DEFAULT 'active' AFTER last_activity;

-- Step 2: Add indexes for new columns
ALTER TABLE sessions
ADD INDEX IF NOT EXISTS idx_username (username),
ADD INDEX IF NOT EXISTS idx_status (status),
ADD INDEX IF NOT EXISTS idx_app_name (app_name),
ADD INDEX IF NOT EXISTS idx_last_activity (last_activity);

-- Step 3: Populate username from users table for existing sessions
UPDATE sessions s
JOIN users u ON s.user_id = u.user_id
SET s.username = u.username
WHERE s.username IS NULL;

-- Step 4: Copy data from session_monitor to sessions (for overlapping session_ids)
-- Only update fields that are NULL in sessions
UPDATE sessions s
JOIN session_monitor sm ON s.session_id = sm.session_id
SET 
    s.user_agent = COALESCE(s.user_agent, sm.user_agent),
    s.device_type = COALESCE(s.device_type, sm.device_type),
    s.browser = COALESCE(s.browser, sm.browser),
    s.app_name = COALESCE(s.app_name, sm.app_name),
    s.last_activity = COALESCE(s.last_activity, sm.last_activity),
    s.status = COALESCE(s.status, sm.status)
WHERE s.session_id = sm.session_id;

-- Step 5: Insert orphaned session_monitor records that don't exist in sessions
-- (These are sessions that were logged to session_monitor but not in sessions table)
INSERT INTO sessions (session_id, user_id, username, created_at, expires_at, ip_address, 
                      user_agent, device_type, browser, app_name, last_activity, status)
SELECT 
    sm.session_id,
    u.user_id,
    sm.username,
    sm.login_time,
    sm.expires_at,
    sm.user_ip,
    sm.user_agent,
    sm.device_type,
    sm.browser,
    sm.app_name,
    sm.last_activity,
    sm.status
FROM session_monitor sm
JOIN users u ON sm.username = u.username
WHERE NOT EXISTS (SELECT 1 FROM sessions s WHERE s.session_id = sm.session_id);

-- Step 6: Verify migration
SELECT 
    'sessions' as table_name,
    COUNT(*) as row_count,
    COUNT(DISTINCT session_id) as unique_sessions,
    COUNT(DISTINCT username) as unique_users
FROM sessions
UNION ALL
SELECT 
    'session_monitor' as table_name,
    COUNT(*) as row_count,
    COUNT(DISTINCT session_id) as unique_sessions,
    COUNT(DISTINCT username) as unique_users
FROM session_monitor;

-- Step 7: After verification, rename session_monitor to session_monitor_old
-- (Don't drop yet - keep as backup for a while)
-- RENAME TABLE session_monitor TO session_monitor_old;

-- Notes:
-- - Run verification query first
-- - Check that all sessions have been migrated
-- - Keep session_monitor_old as backup for rollback
-- - Update all code to use sessions table only
-- - After successful deployment, can DROP TABLE session_monitor_old
