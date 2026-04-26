-- Audit log for migrations applied via the admin Migration Runner.
--
-- Every successful apply (local, remote, or both) inserts one row per
-- target. Admin can see history and avoid re-running the same migration.
-- Idempotent: CREATE TABLE IF NOT EXISTS guards both DBs.

CREATE TABLE IF NOT EXISTS `schema_migrations` (
  `id`         INT NOT NULL AUTO_INCREMENT,
  `filename`   VARCHAR(255) NOT NULL,
  `checksum`   CHAR(64)     NOT NULL,
  `target`     ENUM('local','remote') NOT NULL,
  `applied_at` TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `applied_by` VARCHAR(100) NULL,
  `notes`      TEXT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_file_target_checksum` (`filename`, `target`, `checksum`),
  INDEX `idx_filename` (`filename`),
  INDEX `idx_applied_at` (`applied_at`)
);
