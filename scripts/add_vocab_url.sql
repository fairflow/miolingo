-- Add optional url column to vocab_entries.
-- Run with: python scripts/amend_db.py --file scripts/add_vocab_url.sql
-- Apply --execute flag to commit; default is dry-run.

ALTER TABLE `vocab_entries`
  ADD COLUMN `url` VARCHAR(2048) NULL AFTER `notes`;
