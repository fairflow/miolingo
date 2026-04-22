# Changelog - Miolingo Multi-Language Pronunciation Trainer

All notable changes to the Miolingo pronunciation trainer application will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Entries are written by `scripts/bump_version.py`; the `--notes` flag is
required for any non-tooling bump so the log captures *what* changed, not
just that something changed.


## [7.8.2-claude-dev] - 2026-04-22

### Changed

- docs: make AGENTS.md the canonical project reference; slim CLAUDE.md to Claude-operational content only (git recipe, venv, testing protocol)


## [7.8.1-claude-dev] - 2026-04-21

### Added

- Add GOLDEN.md — the human-readable contract for how Matthew and Claude work together (division of labour, branch model, 8-step golden path, port convention, venv, settings layers, common failure modes).
- Document the vocab search mini-language in USER_GUIDE.md: plain text, anchor/bracket regex triggers, field:value, has:/none:, combining clauses, errors, and explicit non-goals.
- SCRIPTS_WORKFLOW.md: add step 7 — boot the worktree preview on 8701 after each PR push so the IDE Preview button serves the branch-under-review.


## [7.8.0-claude-dev] - 2026-04-21

### Added

- Vocabulary search mini-language: plain text still works; new operators are ^prefix, suffix$, [bracket-class-regex], field:value (word/translation/ipa/source/url/note/context), has:FIELD and none:FIELD. All AND-combined, any order.
- Regex triggers conservatively (^ at start, unescaped $ at end, or [...] present) so natural punctuation like 'saudade?' or 'e.g.' still searches as plain text.
- Whitespace around ':' is collapsed outside quotes; only the first ':' splits field from value so URLs work.
- Invalid queries surface as non-fatal warnings in the UI rather than crashing.


## [7.7.1-claude-dev] - 2026-04-21

### Changed

- bump_version.py now requires --notes "TEXT" for any real bump; --kind selects section heading; --no-notes for emergency re-tags only.
- APP_CHANGELOG.md backfilled for 7.6.8 / 7.6.9 / 7.7.0 from their PR bodies.
- SCRIPTS_WORKFLOW.md golden path updated to reflect the new --notes requirement.


## [7.7.0-claude-dev] - 2026-04-21

### Added

- Post-capture edit form on every vocabulary entry: ✏️ Edit opens an inline form covering display_word (casing only), translation, IPA, source_name, url, and the three context fields. Empty strings clear to NULL; lookup key stays immutable. (PR #87)
- ✨ Auto-fill action — visible only when translation or IPA is missing — fills gaps via the existing LLM + eSpeak enrichment and never overwrites existing values.

### Changed

- Per-entry Streamlit session keys are pruned after deletes and logout/re-login to prevent orphan widget state.


## [7.6.9-claude-dev] - 2026-04-20

### Changed

- `scripts/create-pr.sh` version check now compares HEAD against `origin/$BASE_BRANCH:src/config.py` instead of `git describe`; the old check gave false positives because `bump_version.py --tag` places the new tag at HEAD. (PR #86)
- `scripts/create-pr.sh` push uses explicit `HEAD:refs/heads/<branch>` form so it stays safe regardless of inherited upstream tracking, and sets the upstream cleanly so subsequent tag pushes don't trip the PreToolUse hook.
- New authoritative workflow doc at `docs/dev-docs/SCRIPTS_WORKFLOW.md` + CLAUDE.md preamble pointing at it, so fresh sessions stop rediscovering the release workflow from scratch.


## [7.6.8-claude-dev] - 2026-04-20

### Fixed

- Personal vocabulary sync: `vocab_entries` table was missing from `scripts/sync_db.py`'s `SYNC_TABLES`, so local captures never replicated to the remote MySQL. Added the table with an idempotent merge strategy (GREATEST/COALESCE/NULLIF) that preserves per-row history across both sides. (PR #85)
- New `scripts/test_vocab_sync.py` round-trip harness (17 assertions) proves L→R, R→L, counter-merge, NULL-fill, and idempotency.


## [7.6.7] - 2026-04-20

### Added

- Vocabulary bulk import: 250-word limit per upload. Files over the limit show an error immediately and block the Import button. (`vocab.IMPORT_LINE_LIMIT = 250`)
- Test suite: 36 unit tests for the import parser + fixture files covering all 8 field-combination patterns + a Comet browser test plan (`tests/fixtures/vocab-import/`).

## [7.6.6] - 2026-04-20

### Changed

- Vocabulary bulk import: new 5-field positional format `word | translation | ipa | source | url` (context field removed — impractical in plain text). Use `||` to skip a field while keeping later ones in the correct position (e.g. `word || [atˈɛ] | src`). IPA `[]` brackets stripped automatically.
- Enrichment is now additive: LLM/eSpeak only fills fields missing from the file — pre-enriched files import instantly with no redundant API calls.
- "Auto-fetch translation + IPA" checkbox relabelled to "Auto-fetch **missing** translation + IPA" to reflect the above.

## [7.6.5] - 2026-04-19

### Changed

- Vocabulary tab: paste/upload controls now appear above the entry list (no more scrolling past entries to add a word).
- Vocabulary tab: optional URL field on paste capture and bulk import (`word | source | context | url`); clickable 🔗 Source link shown in expanded entry rows; URL column in CSV export.
- Migration: run `python scripts/amend_db.py --file scripts/add_vocab_url.sql --execute` against local and remote MySQL.

## [7.6.4] - 2026-04-19

### Fixed

- Vocabulary bulk import: show word count + estimated time before import starts; replace silent spinner with a live progress bar (N/total).

## [7.6.3] - 2026-04-19

### Fixed

- Vocabulary tab: fix SyntaxError in empty-search message (curly quotes broke f-string).

## [7.6.2] - 2026-04-19

### Fixed

- Vocabulary tab: empty search results now show "not in your vocabulary — add it below" instead of the misleading "no vocabulary yet" message.

## [7.6.1] - 2026-04-19

### Fixed

- Vocabulary tab paste capture: passage and source label are now optional; only "Word to add" is required.

## [7.6.0] - 2026-04-18

### Added

- **Personal Vocabulary Tracker** (F2): a new "📚 Vocabulary" tab that holds a
  per-user, per-language dictionary of single words captured from everywhere
  they appear in Miolingo. Each entry stores the source (poem title,
  practice material, paste label) plus ±2 lines of context around the word,
  so you can jog your memory of where you learned it. Sortable
  alphabetically or by recency; searchable; with per-entry notes, TTS
  playback, and CSV export.
- Capture routes:
  - **Story Reader**: "Add a word from this phrase" input beside the
    displayed line; ±2 surrounding phrases captured as context.
  - **Quick Practice**: auto-capture on a perfect match for single-word
    practice targets; "Add a word" input for multi-word phrases.
  - **Paste + click**: paste a passage into the Vocabulary tab and pick a
    word from it; the containing line + ±2 neighbours become its context.
  - **Bulk upload**: pipe-delimited `word | source | context` `.txt` file
    imported in one go; multi-word rows are reported and skipped.
- Auto-enrichment: translation (via the existing cached LLM provider) and
  IPA (via espeak) are fetched at capture time. TTS is on-demand per entry.
- Practice-from-vocab: a new "📚 My Vocab" source in Quick Practice loads
  your vocab list as a practice queue.
- New `vocab_entries` table. Apply `scripts/add_vocab_entries.sql` to each
  environment before deploying. Unique index on
  `(user_id, language_code, word)` enforces one-entry-per-word dedup;
  re-captures bump `times_seen` / `last_seen_at` and fill previously-NULL
  fields without overwriting existing values (first encounter wins).
- Integration test coverage: 11 new tests in `tests/integration/test_vocab.py`.


## [7.5.2] - 2026-04-18

### Fixed

- Quick Practice: navigating to another phrase via Previous/Next/Jump-to
  with a recording still in the widget no longer leaves Streamlit's
  `st.audio_input` showing "An error occurred. Please try again." The
  audio_input widget is now remounted (key rotation) and the stale
  result cleared on every navigation event, mirroring what the Remove
  Recording button already did. Also prevents a recording made for
  phrase N from being submittable against phrase N+1.


## [7.5.1] - 2026-04-18

### Fixed

- Logout: clicking Logout no longer leaves the user auto-re-logged-in or
  on a blank page. Two related races are closed:
  - `st.session_state.clear()` used to drop the `cookie_manager`
    reference, forcing a fresh `EncryptedCookieManager` to be built mid-
    logout. That new instance could read the pre-logout cookie state
    before the just-queued `cookies.save()` had committed to the
    browser. The manager is now preserved across the clear.
  - `check_authentication()` could run `resolve_session()` on the very
    next rerun and re-attach the still-present session cookie. It now
    short-circuits when `voluntary_logout` is set, deferring cookie
    reads until the browser has had a chance to catch up.

Logging in as a different user in the same browser now works without
incognito. Tab-independent logout is not addressed — cookies are shared
per-domain and would need a separate identity mechanism.


## [7.5.0] - 2026-04-17

### Added

- Statistics tab: four compact charts + breakdown, replacing the previous
  metrics-only view. Window is the last 90 days:
  - Accuracy trend (per-practice score + rolling-10 average overlay)
  - Practices per day (bar)
  - Score distribution (histogram, 20 bins)
  - Weakest phrases table (min 3 attempts, lowest average score first)
- `app_mysql.get_user_progress_timeseries()` — time-series rows for charts
- `app_mysql.get_user_weakest_phrases()` — GROUP BY target_phrase
  aggregate for the breakdown table

Charts use Streamlit's native Altair (no new dependency). Heights are
fixed at 220px to keep the tab scrollable.


## [7.4.2] - 2026-04-17

### Changed

- Dockerfile: use Debian's prebuilt `espeak-ng` package instead of a
  multi-stage source build. Cuts Docker cold-start build time by several
  minutes, drops the build-tooling stage entirely, and produces a smaller
  final image. No runtime behaviour change — `get_espeak_path()` already
  resolves `espeak-ng` on Debian.


## [7.3.11] - 2026-04-15

### Changed

- Version bump


## [7.3.10] - 2026-04-15

### Changed

- Version bump


## [7.3.9] - 2026-04-15

### Changed

- Version bump


## [7.3.8-claude-dev] - 2026-04-14

### Changed

- Version bump


## [7.3.7-claude-dev] - 2026-04-14

### Changed

- Version bump


## [7.2.0-claude-dev] - 2026-04-06

### Added

- **Bi-directional language selection**: Users now choose both a source language (what
  they know) and a target language (what they practise) on the login page. Source language
  is locked for the session and persisted to the database. Returning users see their
  saved preference pre-filled.
- Login page shows two side-by-side language selectboxes instead of one.
- Sidebar shows source language as a read-only badge ("fixed until logout").
- Free-text practice mode shows the translation direction in the input label.
- `SOURCE_LANGUAGE_OPTIONS` and `source_language` default added to `config.py`.
- `tests/test_bilingual.py` — 10 tests covering the new config exports and UI contracts.


## [7.1.11-claude-dev] - 2026-04-06

### Fixed

- **Bootstrap connection generator bug**: `get_connection()` pre-auth path called
  `pool.get_bootstrap_connection()` without `with`, storing a `_GeneratorContextManager`
  in session state instead of a real MySQL connection. Every subsequent `.cursor()` call
  failed. Fixed by adding `ConnectionPool.get_direct_connection()` which returns a real
  connection object, reusing existing tunnels when available.
- **`write_debug_log` crash on missing SSH secrets**: On environments without `[ssh]` in
  `st.secrets` (e.g. Streamlit Cloud), `write_debug_log()` raised `KeyError` inside its
  own error handler, creating log noise. Added a guard that returns early when SSH secrets
  are absent, plus a `None` check on the connection.
- Added `tests/test_connection.py` covering both fixes.


## [7.1.10-claude-dev] - 2026-04-06

### Fixed

- **Logout crash (`StreamlitDuplicateElementKey`)**: `on_logout()` previously called
  `set_logged_out_flag()` then `clear_cookie_session_id()` separately, each invoking
  `cookies.save()`.  The cookie component renders with the hardcoded key
  `'CookieManager.sync_cookies.save'`; two renders in one Streamlit run raised
  `StreamlitDuplicateElementKey`, crashing logout for any user whose previous session
  ended without an explicit logout click.  Fixed by adding `SessionManager.logout()`
  which applies both cookie mutations and calls `save()` exactly once.
- Added `tests/test_session_manager.py` (9 tests) asserting the single-save invariant.


## [7.1.9-claude-dev-phase6] - 2026-04-06

### Changed

- Version bump


## [7.1.8-claude-dev-phase5] - 2026-04-05

### Changed

- Version bump


## [7.1.7-claude-dev-phase4] - 2026-04-05

### Changed

- Version bump


## [7.1.6-claude-dev-phase2] - 2026-04-05

### Changed

- Version bump


## [7.1.2] - 2026-01-01

### Changed

- Version bump



## [7.1.0] - 2025-12-27

### Changed

- Version bump



## [7.0.2] - 2025-12-21

### Changed

- Version bump



## [7.0.1] - 2025-12-21

### Changed

- Version bump



## [7.0.0] - 2025-12-21

### Added

- User-uploaded practice materials workflow: upload → preview → enrich → save
- Remote saving to server into `incoming/{username}/{language_code}/`
- WYSIWYG editing for uploaded/enriched materials (what you see is what gets saved)

### Changed

- Session architecture for saving: reuse the in-memory SSH tunnel/connection for the whole Streamlit session (no tunnel reconstruction)
- Parsing/normalisation of pipe-delimited lines to consistently handle `phrase | translation | ipa`

### Fixed

- Upload UX/state stability (source selection and loaded content persist across reruns)
- Practice-mode display regressions caused by ordering/parsing of enriched content
- Pronunciation scoring and “identical phonemes” messaging use consistent normalisation
- Restored phoneme diff colour-highlighting and improved iOS/Safari reward sound triggering



## [6.4.0] - 2025-12-19

### Changed

- Version bump



## [6.3.0] - 2025-12-15

### Changed

- Version bump



## [6.2.5] - 2025-12-15

### Changed

- Version bump



## [6.2.5] - 2025-12-14

### Changed

- Version bump



## [6.2.4] - 2025-12-11

### Changed

- Version bump



## [6.2.3] - 2025-12-11

### Changed

- Version bump



## [6.2.2] - 2025-12-11

### Changed

- Version bump



## [6.2.1] - 2025-12-10

### Changed

- Version bump



## [6.2.0] - 2025-12-09

### Changed

- Version bump



## [6.0.0] - 2025-12-08

### Changed

- Version bump



## [5.0.0] - 2025-12-08

### Changed

- Version bump



## [4.3.0] - 2025-12-07

### Changed

- Version bump



## [4.2.2] - 2025-12-07

### Changed

- Version bump



## [4.2.1] - 2025-12-07

### Changed

- Version bump



## [4.2.0] - 2025-12-06

### Changed

- Version bump



## [4.1.0] - 2025-12-06

### Changed

- Version bump



## [3.2.3] - 2025-12-05

### Changed

- Version bump



## [3.2.2] - 2025-12-04

### Changed

- Version bump



## [3.2.1] - 2025-12-04

### Changed

- Version bump



## [3.2.0] - 2025-12-04

### Changed

- Version bump



## [3.1.9] - 2025-12-04

### Changed

- Version bump



## [3.1.8] - 2025-12-04

### Changed

- Version bump



## [3.1.7] - 2025-12-04

### Changed

- Version bump



## [3.1.6] - 2025-12-04

### Changed

- Version bump



## [3.1.5] - 2025-12-04

### Changed

- Version bump



## [3.1.4] - 2025-12-04

### Changed

- Version bump



## [3.1.3] - 2025-12-03

### Changed

- Version bump



## [3.1.0] - 2025-11-29

### Changed

- Version bump



## [3.0.3] - 2025-11-28

### Changed

- Version bump



## [3.0.2] - 2025-11-28

### Changed

- Version bump



## [3.0.1] - 2025-11-28

### Changed

- Version bump



## [2.2.4] - 2025-11-28

### Changed

- Version bump



## [3.0.0] - 2025-11-28

### Changed

- **Repository Reorganization**: Major restructuring for better maintainability
  - Created `docs/dev-docs/` with categorized developer documentation and README
  - Created `docs/archive/` for historical documentation
  - Created `scripts/language-generation/` for resource generation scripts and intermediate data
  - Created `data/practice-sets/` for legacy practice data files
  - Moved 24 developer documentation files to `docs/dev-docs/`
  - Moved 17 language generation scripts from `src/` to `scripts/language-generation/`
  - Moved French resource generation JSON files to `scripts/language-generation/`
  - Moved 12 practice data files to `data/practice-sets/`
  - Cleaned up root directory (10 essential files remain)
- **Language Materials**: Fixed path resolution for `language_materials/` directory
- **Documentation**: Added comprehensive README in `docs/dev-docs/` with categorization

### Fixed

- **Phrasebook Topics**: Now properly loads from `language_materials/*/phrasebook-topics/`
- **Cache Invalidation**: Bumped cache version to 1.8.1 to refresh language materials

## [2.2.3] - 2025-11-23

### Fixed

- **History Reload**: History now reloads from database when viewing History tab
- **Session Display**: All saved practices now visible after logout/login
- Previous sessions were saved but not displayed due to stale session state

### Changed

- History tab refreshes data from database on every view
- Ensures users always see their latest practice sessions


## [2.2.2] - 2025-11-23

### Changed

- **Database-Backed Settings**: All user settings now saved to database instead of local JSON files
- **Settings Persistence**: Settings persist across devices and sessions for authenticated users
- **Simplified Storage**: Removed redundant local JSON history storage, database is single source of truth
- **Guest Warning**: Clear warning for guest users about temporary session data

### Fixed

- **Function Definition Order**: Fixed NameError by moving load_settings() before authentication functions
- **History Format**: Fixed KeyError by properly grouping database practices into sessions by date
- **Cross-Device Sync**: Settings now sync automatically across all user sessions

### Technical

- Settings auto-load from user_settings table on login
- Practice history grouped by date for compatibility with UI
- All authenticated users use database exclusively
- Non-authenticated users still use local JSON as fallback


## [2.2.1] - 2025-11-23

### Fixed

- **Guest Mode Cloud Deployment**: Removed `st.error()` call from `app_mysql.py` that caused AttributeError on Streamlit Cloud
- **Error Handling**: Made `log_activity()` non-critical in guest user creation (swallows errors gracefully)
- **Resource Cleanup**: Improved exception handling and cursor/connection cleanup in `create_guest_user()`

### Technical

- Guest mode now returns `None` silently on failure, letting caller handle UI error messages
- Better exception handling catches generic `Exception` instead of just `Error`


## [2.2.0] - 2025-11-23

### Added

- **Guest Mode**: Frictionless onboarding - users can try app without registration
- **Guest User System**: Creates temporary accounts with unique usernames (`guest_timestamp_random`)
- **Guest UI Tab**: Third tab on login page for instant access
- **Guest Indicator**: Sidebar shows guest status and session warnings

### Fixed

- **Language Initialization**: Fixed banner/dropdown mismatch (Portuguese vs French)
- **Default Language**: Consistent French default throughout app
- **Session State**: Early initialization of `material_language` and `language` prevents AttributeError

### Changed

- **Admin Dashboard**: Fixed deprecation warnings (`use_container_width` → `width='stretch'`)

### Technical

- Guest sessions are temporary (24h expiration)
- Guest progress not saved after logout
- All 6 languages available to guests


## [2.1.0] - 2025-11-22

### Changed

- **Language Selection Simplified**: Training language now directly derived from material language selection
- **Unified Language Control**: Single language dropdown controls both materials and speech
- **Sidebar Reorganization**: Improved layout with version at top, cleaner hierarchy
- **Removed Complexity**: Eliminated auto-sync race conditions and widget state conflicts

### Removed

- **Training Language Dropdown**: Temporarily disabled in Fun section (marked as TODO for future enhancement)
- Complex auto-sync logic that caused synchronization issues

### Fixed

- Language selection now updates banner, materials, and speech consistently
- Eliminated widget state conflicts between multiple language selectors


## [2.0.5] - 2025-11-22

### Added

- **Fun Section**: New "Fun" section in sidebar with experimental features
- **Mix Up Languages**: Hidden feature to speak one language's materials in a different language's voice (easter egg)

### Changed

- **Language Selection**: Simplified main language selector - now just "Language" (previously "Materials Language")
- **Auto-sync**: Training language automatically syncs with main language selection
- **Language Order**: Reordered training languages to match materials (German, Spanish, French, Italian, Dutch, Portuguese)
- **Sidebar Layout**: Improved version display at top, better visual hierarchy


## [2.0.4] - 2025-11-22

### Changed

- **Story Links**: Removed "Coming soon" labels from all language story links in sidebar (Portuguese, Dutch, German, Italian, Spanish)
- All 6 languages now fully available with complete story materials


## [2.0.3] - 2025-11-22

### Fixed

- **Story Practice Mode Session State**: Fixed radio button reverting to "Scene by Scene" after saving session - now maintains "Practice Mode" selection correctly
- Added session state persistence for story mode selection to prevent UI state desync on rerun

### Added

- **VERSION_CHECKLIST.md**: Comprehensive documentation of all files containing version numbers
- Version markers in key files (app.py, VERSION_WORKFLOW.md) for easier version management


## [2.0.2] - 2025-11-22

### Fixed

- **IPA Typography**: Standardized IPA formatting across all display locations with consistent fonts, sizes, and delimiters
- **Layout**: Fixed phoneme analysis section to span full width instead of being constrained to column layout
- **Font Consistency**: Applied IPA-optimized fonts (Doulos SIL, Charis SIL, Gentium Plus, DejaVu Sans) throughout app
- **Display Formatting**: Normalized phoneme display uses consistent 1.05em sizing and standard weight

### Changed

- Created `format_ipa()` function for centralized IPA typography management
- Moved detailed phoneme analysis outside two-column layout for better readability
- Standardized IPA delimiters to square brackets `[ipa]` format consistently


## [2.0.1] - 2025-11-22

### Fixed

- **Dictionary Quality**: Regenerated all language dictionaries with improved filtering
  - Removed English word leakage from target language dictionaries
  - Filtered IPA notation artifacts from word lists
  - Removed numeric entries
- **Dictionary Format**: All dictionaries now have complete format `word | English | [IPA]`
- **Script Improvements**: Enhanced `generate_all_materials.py` with better word extraction

### Technical

- Added comprehensive English word filtering (600+ common words)
- Added IPA character detection to prevent notation leakage
- Improved phrase file parsing to only extract target language column
- Dictionary word counts optimized (removed ~30-40% noise per language)

## [2.0.0] - 2025-11-22

### Added

- **Complete Story-Based Learning System**: 16-scene immersive story across all 6 languages
  - Full story.md narrative files for each language
  - 96 JSON scene files (16 scenes × 6 languages) with bilingual text and IPA
  - Story Reader with full story and scene-by-scene modes
  - Practice Mode integration with story content
- **Comprehensive Dictionaries**: Generated complete word lists for all languages
  - French: 1255 words
  - Portuguese: 1186 words
  - Spanish: 1343 words
  - German: 1399 words
  - Dutch: 1115 words
  - Italian: 1418 words
- **IPA Throughout**: All phrases and dictionary entries include espeak-generated IPA
- **Unified Generation Script**: `generate_all_materials.py` processes all 6 languages

### Changed

- Enhanced language materials structure with story-scenes-json directories
- Updated phrase files to include IPA for all languages (4 files per language)
- Improved JSON loading to support multi-language story scenes

## [1.8.0] - 2025-11-16

### Added

- **German Language Support**: Complete practice materials with 103 phrases and IPA transcriptions
- **Italian Language Support**: Complete practice materials with 103 phrases and IPA transcriptions
- **Spanish Language Support**: Complete practice materials with 103 phrases and IPA transcriptions
- Multi-language TTS support: all 3 TTS engines (Google Cloud, gTTS, eSpeak) now fully support German, Italian, and Spanish

### Fixed

- Voice mapping for German, Italian, and Spanish across all TTS engines
- Language selection now correctly applies to TTS audio generation


## [1.7.0] - 2025-11-16

### Added

- **German Language Support**: Complete German practice materials with 103 phrases
  - Full phonetic transcriptions (IPA)
  - 12 topic-based practice files (greetings, numbers, time, etc.)
  - TTS support for google_cloud, gtts, and espeak engines
  - Flag emoji 🇩🇪 integration
- **Italian Language Support**: Complete Italian practice materials with 103 phrases
  - Full phonetic transcriptions (IPA)
  - 12 topic-based practice files (greetings, numbers, time, etc.)
  - TTS support for google_cloud, gtts, and espeak engines
  - Flag emoji 🇮🇹 integration
- **Spanish Language Support**: Complete Spanish practice materials with 103 phrases
  - Full phonetic transcriptions (IPA)
  - 12 topic-based practice files (greetings, numbers, time, etc.)
  - TTS support for google_cloud, gtts, and espeak engines
  - Flag emoji 🇪🇸 integration
- **Enhanced Language Display**: Full language names with flag emojis in practice materials section
  - Updated format: "🇫🇷 French", "🇩🇪 German", "🇮🇹 Italian", "🇪🇸 Spanish"
  - Consistent display across all 6 supported languages

### Changed

- App now supports 6 languages: Portuguese, French, Dutch, German, Italian, Spanish
- Total practice materials expanded to 618 phrases (6 languages × 103 phrases)
- Language selection dropdown now includes German, Italian, and Spanish options

### Technical

- Updated `LANGUAGE_CONFIG` with voice codes for all TTS engines
- Updated `flag_emojis` dictionary with 🇩🇪, 🇮🇹, 🇪🇸
- Updated `format_language_name()` in `app_language_materials.py`
- Automation scripts updated to support all 6 languages


## [1.3.1] - 2025-11-13

### Added
- **SSH Tunnel Encryption**: All database traffic now encrypted via SSH tunnel
  - Port 722 SSH connection to miolingo.io
  - ED25519 key-based authentication
  - Automatic port selection to avoid conflicts
  - Connection persistence across Streamlit reruns using `st.session_state`
  - Dual-mode key support: file path (local) or direct content (Streamlit Cloud)

### Changed
- **Session Save Behavior**: Added `st.rerun()` after saving session for immediate UI sync
  - Eliminates double-click issue on "Save Session Now" button
  - Sidebar state updates immediately after save

### Fixed
- SSH tunnel lifecycle management to prevent duplicate tunnels on Streamlit reruns
- Port binding conflicts resolved by auto-selecting available ports
- SSH port configuration (722 instead of default 22 for Krystal hosting)
- Debug logging suppressed (paramiko, gtts, urllib3, fsevents now at WARNING level)

### Security
- Database connections now fully encrypted end-to-end via SSH tunnel
- Private SSH keys kept secure (never committed to git)
- Supports both local development (key file) and cloud deployment (key content in secrets)

### Technical
- New dependencies: `paramiko<3.0` (downgraded for sshtunnel compatibility), `sshtunnel>=0.4.0`
- SSH tunnel managed in `app_mysql.py` module
- Connection uses SSH key at `~/.ssh/miolingo/mysql_tunnel_key` (local) or secrets (cloud)
- Cleanup handler registered via `atexit` to properly close tunnel on shutdown

## [1.3.0] - 2025-11-13

### Added
- **Multi-User Authentication**: Complete user authentication system with secure login/registration
  - Argon2id password hashing (100MB memory, 4 iterations, 8 threads)
  - 32-byte secure session tokens with 24-hour expiration
  - Per-user, per-language settings and progress tracking
  - Rate limiting for abuse prevention (no CAPTCHA by design)
- **MySQL Database Integration**: External database on Krystal hosting (miolingo.io)
  - 6-table schema: users, sessions, user_settings, user_progress, rate_limits, activity_log
  - Modular architecture: `app_mysql.py` module keeps all database logic separate
  - Connection pooling optimized for Krystal Emerald plan (10 connections)
- **Per-User Progress**: Practice sessions saved per-user and per-language
  - Individual statistics for each user and language combination
  - Real-time database saving after each practice
  - Recent average (last 10 practices) tracking
- **Security Features**:
  - All SQL queries parameterized to prevent injection attacks
  - Session IP validation to detect hijacking
  - Activity logging with timestamps and IP addresses
  - Secure secrets management via Streamlit secrets.toml

### Changed
- **Statistics Display**: Now pulls from database instead of local JSON files
  - Shows per-language stats dynamically based on selected language
  - Real-time updates when switching languages
  - Current session stats + all-time stats from database
- **Punctuation Handling**: Removed punctuation before audio generation
  - Prevents comma/pause detection from affecting similarity scores
  - Cleaner transcription matching
- **UI Improvements**:
  - Normalized phonemes display changed from `st.code()` to `st.markdown()` for better mobile rendering
  - Sidebar shows username, email, and logout button when authenticated
  - Login/registration forms with validation

### Fixed
- Total Perfect statistic now uses correct `exact_match` key (was showing 0%)
- Compare Phoneme Sounds buttons reference fixed (deferred for later testing)

### Technical
- Branch: `feature/multi-user-auth-v1.3.0`
- Database: MariaDB 10.6.23 on miolingo.io:3306
- New dependencies: `mysql-connector-python==9.4.0`, `argon2-cffi==25.1.0`
- All credentials git-ignored via updated `.gitignore`

---

## [1.2.1] - 2025-11-13

### Changed
- **Documentation**: Updated all documentation to be language-agnostic instead of Portuguese-specific
  - Changed app name from "Portuguese Pronunciation Trainer" to "Miolingo - Multi-Language Pronunciation Trainer"
  - Updated README.md, USER_GUIDE.md, DEVELOPER_GUIDE.md, TESTING_GUIDE.md, and app-docs/README.md
  - Replaced Portuguese-specific language with generic "pronunciation practice" or "language learning"
  - Updated primary app URL to https://miolingo.io/ with backup https://miolingo.streamlit.app/
  - Emphasized multi-language support (Portuguese, French, Dutch, Flemish) throughout docs
  - Clarified wav2vec2 is Portuguese-only, Whisper supports all languages

---

## [1.1.3] - 2025-11-13

### Fixed
- Mobile UX: removed separator line between audio and recording sections for more compact layout
- Recording instructions now dynamically display the selected language (Portuguese/French/Dutch) instead of hardcoded "Portuguese"

---

## [1.1.2] - 2025-11-13

### Fixed
- Mobile UX: reduced phrase heading size further (h3 → h4) for better screen space on phones
- Mobile UX: moved recording instructions info box below the recording widget to maximize phrase visibility
- Removed redundant "automatically selected phrase" caption that consumed screen space

---

## [1.1.1] - 2025-11-13

### Fixed
- eSpeak TTS auto-play bug: now uses `--stdout` to capture audio bytes instead of auto-playing
- Mobile UX improvements: changed phrase heading from h1 to h3 for better visibility
- Mobile layout: moved emoji inline with phrase and translation above phrase for better recording visibility

### Added
- French language materials infrastructure (phrases A-D levels)
- Helper script for French phrase setup

---

## [1.0.0] - 2025-11-11

### Added
- Multi-language support: Portuguese, French, Dutch, Flemish
- Language and voice/dialect selection in sidebar
- Dynamic phrase lists and session tracking per language
- All practice modes, scoring, and feedback now work for every supported language

### Changed
- Updated documentation for language/voice selection
- Phrase files reorganized for multi-language support

---

## [0.9.0] - 2025-11-10

### Added
- iOS Safari audio compatibility with WAV conversion feature
- User-configurable WAV audio format toggle in settings
- Edit distance (Levenshtein) scoring algorithm for pronunciation comparison
- User-selectable scoring algorithm (edit distance vs positional matching)
- User-adjustable silence trimming threshold slider (0.001-0.1)
- Version number display in sidebar
- Comprehensive version management system
- Git tags synchronized with version numbers
- CCS testing framework integration improvements

### Fixed
- Audio generation deadlock caused by ffmpeg pipe buffer overflow
- Used `subprocess.DEVNULL` to prevent ffmpeg output buffering issues
- iOS Safari "Error" on MP3 audio playback (grey player, no sound)
- Silence trimming potentially cutting off speech ends
- 0% scoring issue with pronunciation misalignment

### Changed
- Renamed application file from `streamlit_app_v2.py` to `app.py`
- Enhanced phoneme analysis to work with edit distance algorithm
- Improved results display with edit distance metrics

### Technical Details
- ffmpeg MP3→WAV conversion for iOS compatibility
- PCM 16-bit WAV format at 22050Hz sample rate
- Spinner + subprocess deadlock resolution via `DEVNULL`
- Levenshtein distance algorithm for flexible scoring

---

## Version History Summary

- **0.9.0** (2025-11-10) - iOS audio fix, edit distance scoring, version system
- Future versions will be documented here as they are released
- Version 1.0.0 will mark the first stable production release

---

## Versioning Scheme

This project uses [Semantic Versioning](https://semver.org/):
- **MAJOR.MINOR.PATCH** (e.g., `0.9.0`)
- Version progression: `0.9.0` → `0.9.1` → ... → `0.9.9` → `1.0.0`
- **PATCH**: Bug fixes only
- **MINOR**: New features (backward compatible)
- **MAJOR**: Breaking changes or stable release milestone (0.x.x → 1.0.0)

Git tags match version numbers: `v0.9.0`, `v0.9.1`, `v1.0.0`, etc.

## How to Update Version

1. Update `__version__` in `app.py`
2. Update this CHANGELOG.md with changes
3. Commit changes: `git commit -m "Bump version to X.Y.Z"`
4. Create matching git tag: `git tag -a vX.Y.Z -m "Version X.Y.Z"`
5. Push with tags: `git push myfork main --tags`

## Version 0.9.1 (2025-11-10)

### Bug Fixes
- **WAV Audio Setting Persistence**: Fixed issue where "Use WAV audio format" checkbox setting would not persist after page reload
  - Setting now auto-saves immediately when toggled
  - Added visual confirmation message when saved
  - Ensures iOS Safari users don't lose their audio format preference

