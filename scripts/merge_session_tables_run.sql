-- Migration: Merge session_monitor columns into sessions table (safe / rerunnable)
-- Purpose: Consolidate duplicate session tracking into single source of truth
-- Date: 2025-12-12
-- Branch: feature/admin-fusion

SELECT 'merge_session_tables_run.sql: start' AS info;
SELECT DATABASE() AS db_name, VERSION() AS mysql_version;

-- Helper: does session_monitor exist?
SET @sm_exists := (
  SELECT COUNT(*)
  FROM information_schema.TABLES
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'session_monitor'
);

-- Step 1: Add new columns from session_monitor to sessions table (only if missing)
SET @col_exists := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'sessions' AND COLUMN_NAME = 'username'
);
SET @sql := IF(@col_exists = 0,
  'ALTER TABLE sessions ADD COLUMN username VARCHAR(100) AFTER user_id',
  'SELECT "sessions.username already exists" AS info'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @col_exists := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'sessions' AND COLUMN_NAME = 'user_agent'
);
SET @sql := IF(@col_exists = 0,
  'ALTER TABLE sessions ADD COLUMN user_agent TEXT AFTER ip_address',
  'SELECT "sessions.user_agent already exists" AS info'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @col_exists := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'sessions' AND COLUMN_NAME = 'device_type'
);
SET @sql := IF(@col_exists = 0,
  'ALTER TABLE sessions ADD COLUMN device_type VARCHAR(50) AFTER user_agent',
  'SELECT "sessions.device_type already exists" AS info'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @col_exists := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'sessions' AND COLUMN_NAME = 'browser'
);
SET @sql := IF(@col_exists = 0,
  'ALTER TABLE sessions ADD COLUMN browser VARCHAR(50) AFTER device_type',
  'SELECT "sessions.browser already exists" AS info'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @col_exists := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'sessions' AND COLUMN_NAME = 'app_name'
);
SET @sql := IF(@col_exists = 0,
  'ALTER TABLE sessions ADD COLUMN app_name VARCHAR(50) DEFAULT ''app'' AFTER browser',
  'SELECT "sessions.app_name already exists" AS info'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @col_exists := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'sessions' AND COLUMN_NAME = 'last_activity'
);
SET @sql := IF(@col_exists = 0,
  'ALTER TABLE sessions ADD COLUMN last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP AFTER expires_at',
  'SELECT "sessions.last_activity already exists" AS info'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @col_exists := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'sessions' AND COLUMN_NAME = 'status'
);
SET @sql := IF(@col_exists = 0,
  'ALTER TABLE sessions ADD COLUMN status ENUM(''active'',''expired'',''forced_logout'') DEFAULT ''active'' AFTER last_activity',
  'SELECT "sessions.status already exists" AS info'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- Step 2: Add indexes (only if missing)
SET @idx_exists := (
  SELECT COUNT(*) FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'sessions' AND INDEX_NAME = 'idx_username'
);
SET @sql := IF(@idx_exists = 0,
  'CREATE INDEX idx_username ON sessions(username)',
  'SELECT "idx_username already exists" AS info'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @idx_exists := (
  SELECT COUNT(*) FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'sessions' AND INDEX_NAME = 'idx_status'
);
SET @sql := IF(@idx_exists = 0,
  'CREATE INDEX idx_status ON sessions(status)',
  'SELECT "idx_status already exists" AS info'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @idx_exists := (
  SELECT COUNT(*) FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'sessions' AND INDEX_NAME = 'idx_app_name'
);
SET @sql := IF(@idx_exists = 0,
  'CREATE INDEX idx_app_name ON sessions(app_name)',
  'SELECT "idx_app_name already exists" AS info'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @idx_exists := (
  SELECT COUNT(*) FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'sessions' AND INDEX_NAME = 'idx_last_activity'
);
SET @sql := IF(@idx_exists = 0,
  'CREATE INDEX idx_last_activity ON sessions(last_activity)',
  'SELECT "idx_last_activity already exists" AS info'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- Step 3: Populate username from users table for existing sessions
UPDATE sessions s
JOIN users u ON s.user_id = u.user_id
SET s.username = u.username
WHERE s.username IS NULL;

-- Step 4: Copy data from session_monitor to sessions (only if session_monitor exists)
SET @sql := IF(@sm_exists > 0,
  'UPDATE sessions s JOIN session_monitor sm ON BINARY s.session_id = BINARY sm.session_id SET s.user_agent = COALESCE(s.user_agent, sm.user_agent), s.device_type = COALESCE(s.device_type, sm.device_type), s.browser = COALESCE(s.browser, sm.browser), s.app_name = COALESCE(s.app_name, sm.app_name), s.last_activity = COALESCE(s.last_activity, sm.last_activity), s.status = COALESCE(s.status, sm.status) WHERE BINARY s.session_id = BINARY sm.session_id',
  'SELECT "session_monitor does not exist: skipping overlay update" AS info'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- Step 5: Insert orphaned session_monitor records (only if session_monitor exists)
SET @sql := IF(@sm_exists > 0,
  'INSERT INTO sessions (session_id, user_id, username, created_at, expires_at, ip_address, user_agent, device_type, browser, app_name, last_activity, status) SELECT sm.session_id, u.user_id, sm.username, sm.login_time, sm.expires_at, sm.user_ip, sm.user_agent, sm.device_type, sm.browser, sm.app_name, sm.last_activity, sm.status FROM session_monitor sm JOIN users u ON BINARY sm.username = BINARY u.username WHERE NOT EXISTS (SELECT 1 FROM sessions s WHERE BINARY s.session_id = BINARY sm.session_id)',
  'SELECT "session_monitor does not exist: skipping orphan insert" AS info'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- Step 6: Verification
SELECT
  'sessions' AS table_name,
  COUNT(*) AS row_count,
  COUNT(DISTINCT session_id) AS unique_sessions,
  COUNT(DISTINCT username) AS unique_users
FROM sessions;

SET @sql := IF(@sm_exists > 0,
  'SELECT ''session_monitor'' AS table_name, COUNT(*) AS row_count, COUNT(DISTINCT session_id) AS unique_sessions, COUNT(DISTINCT username) AS unique_users FROM session_monitor',
  'SELECT "session_monitor" AS table_name, 0 AS row_count, 0 AS unique_sessions, 0 AS unique_users'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SELECT 'merge_session_tables_run.sql: end' AS info;

-- Optional follow-up (manual, after verifying everything):
-- RENAME TABLE session_monitor TO session_monitor_old;
