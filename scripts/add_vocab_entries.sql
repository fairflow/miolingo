-- F2: Personal Vocabulary Tracker
--
-- One-time schema change: adds the `vocab_entries` table used by the
-- Vocabulary tab. Apply manually against both local MySQL and the remote
-- production database. See scripts/sync_db.py for how prior schema changes
-- have been rolled out.

CREATE TABLE IF NOT EXISTS `vocab_entries` (
  `vocab_id` BIGINT NOT NULL AUTO_INCREMENT,
  `user_id` INT NOT NULL,
  `language_code` VARCHAR(10) NOT NULL,
  `word` VARCHAR(100) NOT NULL,
  `display_word` VARCHAR(100) NOT NULL,
  `translation` TEXT NULL,
  `ipa` VARCHAR(512) NULL,
  `source_name` VARCHAR(255) NULL,
  `context_before` TEXT NULL,
  `context_line` TEXT NULL,
  `context_after` TEXT NULL,
  `times_seen` INT NOT NULL DEFAULT 1,
  `first_seen_at` DATETIME NOT NULL,
  `last_seen_at` DATETIME NOT NULL,
  `notes` TEXT NULL,
  PRIMARY KEY (`vocab_id`),
  UNIQUE KEY `uq_user_lang_word` (`user_id`, `language_code`, `word`),
  KEY `idx_user_lang_last_seen` (`user_id`, `language_code`, `last_seen_at`),
  CONSTRAINT `fk_vocab_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
