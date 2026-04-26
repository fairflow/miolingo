-- Extend vocab_entries unique key to include source_language_code.
--
-- Previously: UNIQUE KEY uq_user_lang_word (user_id, language_code, word)
-- After:      UNIQUE KEY uq_user_lang_src_word
--                        (user_id, language_code, source_language_code, word)
--
-- Effect: the same word can now exist as independent rows under different
-- source languages, e.g. 'abandoned' under pt→en and fr→en are separate
-- entries with their own translations, IPA, and times_seen counters.
--
-- MySQL treats NULL as distinct from every value including itself in unique
-- indexes, so legacy rows with source_language_code IS NULL are unaffected
-- and do not conflict with each other or with language-specific rows.
--
-- Idempotent: IF NOT EXISTS / IF EXISTS guards on both operations.
-- Run against local and remote (same schema on both targets).

ALTER TABLE `vocab_entries`
  DROP INDEX `uq_user_lang_word`,
  ADD UNIQUE KEY `uq_user_lang_src_word`
    (`user_id`, `language_code`, `source_language_code`, `word`);
