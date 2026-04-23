-- Tier 2: source language for personal vocabulary.
--
-- Adds `source_language_code` to `vocab_entries` so rows can record which
-- native/source language the user was working from when the entry was
-- captured. NULL means unspecified (legacy rows + rows captured before the
-- session had a well-defined source); queries filtering by source treat
-- NULL as "matches any source".
--
-- Apply against local MySQL and the remote production database. Option 2
-- backfill: leave existing rows NULL (do not assume English).

ALTER TABLE `vocab_entries`
  ADD COLUMN `source_language_code` VARCHAR(10) NULL AFTER `language_code`,
  ADD KEY `idx_user_lang_src` (`user_id`, `language_code`, `source_language_code`);
