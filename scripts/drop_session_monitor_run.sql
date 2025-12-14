-- Drop obsolete session_monitor table
-- Date: 2025-12-12
-- Branch: feature/admin-fusion

SELECT 'drop_session_monitor_run.sql: start' AS info;
SELECT DATABASE() AS db_name, VERSION() AS mysql_version;

-- Pre-check
SELECT TABLE_NAME
FROM information_schema.TABLES
WHERE TABLE_SCHEMA = DATABASE()
  AND TABLE_NAME IN ('session_monitor', 'session_monitor_old');

-- Drop (idempotent)
DROP TABLE IF EXISTS session_monitor;
DROP TABLE IF EXISTS session_monitor_old;

-- Post-check
SELECT TABLE_NAME
FROM information_schema.TABLES
WHERE TABLE_SCHEMA = DATABASE()
  AND TABLE_NAME IN ('session_monitor', 'session_monitor_old');

SELECT 'drop_session_monitor_run.sql: end' AS info;
