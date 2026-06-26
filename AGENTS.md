# Miolingo — AI Agent Instructions

This is the canonical project reference for all AI assistants working on Miolingo.
Tool-specific files (`CLAUDE.md`, `.github/copilot-instructions.md`) extend this with
environment-specific instructions. If they conflict, this file wins.

---

## Project Overview

Streamlit-based multi-language pronunciation trainer with real-time AI feedback.

- **Main app:** `src/app.py` (4,034 lines), runs at `localhost:8501`
- **Admin dashboard:** `src/miolingo-admin.py`, runs at `localhost:8505`
- **Stack:** Python 3.10+, Streamlit 1.39+, OpenAI Whisper (ASR), Google Cloud TTS / eSpeak NG / gTTS, MySQL over SSH tunnel, Argon2 auth
- **Languages:** Portuguese (BR/PT), French, Dutch, Flemish, German, Italian, Spanish

---

## CRITICAL: Database Connection Rule

**Never create new DB tunnels or connections.** Always reuse the session connection
via `app_mysql.get_connection()`. Creating new tunnels exhausts server resources
(caused a production outage). One tunnel per session, always.

```python
# CORRECT
conn = app_mysql.get_connection()

# WRONG — never do this
new_conn = mysql.connector.connect(...)
new_tunnel = SSHTunnelForwarder(...)
```

---

## Active Source Files

### Core Application

| File | Lines | Role |
|------|-------|------|
| `src/app.py` | ~2,800 | Main Streamlit app — UI, routing, session orchestration |
| `src/config.py` | ~190 | Constants, LANGUAGE_CONFIG, settings load/save |
| `src/translation.py` | ~260 | Translation providers + LLM translation |
| `src/scoring/comparison.py` | ~130 | Levenshtein, edit operations, scoring algorithms |
| `src/scoring/phonemes.py` | ~130 | IPA extraction, phoneme processing via espeak |
| `src/scoring/practice.py` | ~170 | Practice orchestration: silence trim, ASR, scoring pipeline |
| `src/audio/tts.py` | ~280 | TTS engines: eSpeak, Google Cloud, gTTS + fallback dispatcher |
| `src/audio/asr.py` | ~180 | ASR: Whisper, Wav2Vec2 transcription + model loaders |
| `src/app_mysql.py` | 1,890 | Database layer — auth, progress, sessions, data persistence |
| `src/app_language_materials.py` | 373 | Language material loading (phrases, words, stories by language/level) |
| `src/session_manager.py` | 272 | Streamlit session state management |
| `src/translation_providers.py` | 107 | Translation API interfaces (DeepL, OpenAI) |
| `src/pronunciation_trainer.py` | 550 | IPA/phoneme extraction via espeak (CLI tool) |

### Admin & Monitoring

| File | Lines | Role |
|------|-------|------|
| `src/miolingo-admin.py` | 1,066 | Admin dashboard — analytics, user stats, sessions |
| `src/admin_mysql.py` | 1,644 | Admin DB operations — user management, schema, monitoring |
| `src/unified_admin.py` | 207 | Admin interface router |

### Infrastructure

| File | Lines | Role |
|------|-------|------|
| `src/connection_pool.py` | 922 | MySQL connection pooling with SSH tunnel lifecycle |
| `src/connection_monitor.py` | 2,821 | Advanced connection monitoring, health checks, session tracking |
| `src/remote_storage.py` | 219 | Cloud storage integration |

### Observability

| File | Lines | Role |
|------|-------|------|
| `src/cost_monitor.py` | 203 | API usage and cost tracking |
| `src/api_usage_logger.py` | 189 | API call logging for monitoring/billing |

### Testing

| File | Lines | Role |
|------|-------|------|
| `src/ccs_test_framework.py` | 567 | CCS dual-agent test framework for UI state testing |
| `src/ccs_test_integration.py` | 467 | CCS framework integration into the app |

### Utilities

| File | Lines | Role |
|------|-------|------|
| `src/update_version.py` | 149 | Version bumping utility |
| `src/record_audio.py` | 130 | Audio recording utilities |
| `src/practice_sentences.py` | 163 | Sentence-level practice data |

---

## app.py Layout (line ranges)

```
  1–222     Imports, constants, LANGUAGE_CONFIG, version metadata
223–289     Settings: load_settings(), save_settings()
290–620     Translation & IPA utilities: providers, espeak, LLM translation, material enrichment
622–670     Announcements system
672–1125    Authentication: show_login_page(), check_authentication(), role checks
1126–1245   History: load_history(), save_history(), initialize_session_state()
1248–1298   ASR model loading: get_whisper_model(), get_wav2vec2_model(), get_espeak_path()
1299–1390   Phoneme/IPA processing: get_phonemes(), get_ipa(), format_ipa()
1391–1675   TTS engines: speak_text() (pyttsx3), speak_text_google_cloud(), speak_text_gtts(), generate_target_audio()
1676–1802   ASR transcription: transcribe_audio_whisper(), transcribe_audio_wav2vec2(), transcribe_audio()
1803–1942   Scoring: levenshtein_distance(), edit operations, compare_phonemes (positional & edit-distance)
1943–2080   Practice flow: practice_word_from_audio() — orchestrates record → transcribe → score
2081–2456   UI rendering: save_current_session(), render_practice_interface(), render_practice_results()
2457–2597   Story practice: render_scene_practice_mode()
2598–2796   Story reader: render_story_reader(), render_full_story(), render_scene_by_scene()
2797–4034   main(): entry point, sidebar config, tab routing (Quick Practice / Story Reader / Statistics / History)
```

---

## Module Dependency Graph

```
app.py ──→ app_mysql (DB)
       ──→ session_manager (state)
       ──→ translation_providers (optional, runtime)
       ──→ pronunciation_trainer (espeak CLI wrapper)
       ──→ app_language_materials (content loading)

app_mysql ──→ connection_pool ──→ SSH tunnel + MySQL
admin_mysql ──→ connection_pool

miolingo-admin.py ──→ app_mysql

ccs_test_integration ──→ ccs_test_framework

connection_monitor ──→ connection_pool (extends with health checks)
```

Nothing imports upward — `app.py` is the top of the dependency tree.

---

## Language Materials Structure

Each language lives in `language_materials/<code>/`:
```
language_materials/
├── pt/          Portuguese (phrases, words, stories, phrasebook)
├── fr/          French
├── de/          German
├── es/          Spanish
├── it/          Italian
└── nl/          Dutch
    ├── phrasebook_complete.json    # Full phrase database
    ├── phrasebook-topics/          # Topic-organised phrase files
    ├── phrases/                    # Individual phrase JSON files
    ├── story.md                    # Full story narrative
    └── story-scenes-json/          # Scene-by-scene JSON for practice
```

---

## Key Configuration & Reference Files

| File | Purpose |
|------|---------|
| `.streamlit/secrets_template.toml` | Template for DB, API keys, SSH config |
| `.streamlit/config.toml` | Streamlit theme and server settings |
| `config/.miolingo.config` | App-specific configuration |
| `requirements.txt` | Python dependencies |
| `docker-compose.yml` | Container deployment (port 8601) |
| `docs/TESTING_CHECKLIST.md` | Structured manual UI test checklist (used during testing sessions) |
| `.github/ISSUE_TEMPLATE/bug_report.md` | GitHub issue template for bug reports |
| `APP_CHANGELOG.md` | Version history — updated by `scripts/bump_version.py` |

---

## Scripts & Automation

| Directory | Purpose |
|-----------|---------|
| `scripts/bump_app.py`, `scripts/bump_admin.py` | Version bumping |
| `scripts/language-generation/` | 27 scripts for generating IPA, translations, phrasebooks |
| `scripts/clean_restart.py` | Full DB/session cleanup |
| `scripts/deep_mysql_diagnostic.py` | MySQL diagnostics |

---

## Known Issues (do not duplicate)

- Statistics tab: charts/breakdowns not yet implemented
- Scene title encoding: accented characters stripped (Streamlit limitation)
- Scoring/ASR accuracy: needs full refactor
- Input red border: default Streamlit behaviour on touched fields

---

## Current Debug Mode

The app runs in debug mode. These are intentional:
- `Missing cookie_password in st.secrets` warning banner
- State-change banners (e.g. "State changed: story_mode: None → Scene by Scene")
- Connection Info panel showing tunnel/SQL details

<!-- BEGIN BEADS INTEGRATION v:1 profile:minimal hash:970c3bf2 -->
## Beads Issue Tracker

This project uses **bd (beads)** for issue tracking. Run `bd prime` to see full workflow context and commands.

### Quick Reference

```bash
bd ready              # Find available work
bd show <id>          # View issue details
bd update <id> --claim  # Claim work
bd close <id>         # Complete work
```

### Rules

- Use `bd` for ALL task tracking — do NOT use TodoWrite, TaskCreate, or markdown TODO lists
- Run `bd prime` for detailed command reference and session close protocol
- Use `bd remember` for persistent knowledge — do NOT use MEMORY.md files

**Architecture in one line:** issues live in a local Dolt DB; sync uses `refs/dolt/data` on your git remote; `.beads/issues.jsonl` is a passive export. See https://github.com/gastownhall/beads/blob/main/docs/SYNC_CONCEPTS.md for details and anti-patterns.

## Agent Context Profiles

The managed Beads block is task-tracking guidance, not permission to override repository, user, or orchestrator instructions.

- **Conservative (default)**: Use `bd` for task tracking. Do not run git commits, git pushes, or Dolt remote sync unless explicitly asked. At handoff, report changed files, validation, and suggested next commands.
- **Minimal**: Keep tool instruction files as pointers to `bd prime`; use the same conservative git policy unless active instructions say otherwise.
- **Team-maintainer**: Only when the repository explicitly opts in, agents may close beads, run quality gates, commit, and push as part of session close. A current "do not commit" or "do not push" instruction still wins.

## Session Completion

This protocol applies when ending a Beads implementation workflow. It is subordinate to explicit user, repository, and orchestrator instructions.

1. **File issues for remaining work** - Create beads for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **Handle git/sync by active profile**:
   ```bash
   # Conservative/minimal/default: report status and proposed commands; wait for approval.
   git status

   # Team-maintainer opt-in only, unless current instructions forbid it:
   git pull --rebase
   bd dolt push
   git push
   git status
   ```
5. **Hand off** - Summarize changes, validation, issue status, and any blocked sync/commit/push step

**Critical rules:**
- Explicit user or orchestrator instructions override this Beads block.
- Do not commit or push without clear authority from the active profile or the current user request.
- If a required sync or push is blocked, stop and report the exact command and error.
<!-- END BEADS INTEGRATION -->

<!-- BEGIN BEADS CODEX SETUP: generated by bd setup codex -->
## Beads Issue Tracker

Use Beads (`bd`) for durable task tracking in repositories that include it. Use the `beads` skill at `.agents/skills/beads/SKILL.md` (project install) or `~/.agents/skills/beads/SKILL.md` (global install) for Beads workflow guidance, then use the `bd` CLI for issue operations.

### Quick Reference

```bash
bd ready                # Find available work
bd show <id>            # View issue details
bd update <id> --claim  # Claim work
bd close <id>           # Complete work
bd prime                # Refresh Beads context
```

### Rules

- Use `bd` for all task tracking; do not create markdown TODO lists.
- Run `bd prime` when Beads context is missing or stale. Codex 0.129.0+ can load Beads context automatically through native hooks; use `/hooks` to inspect or toggle them.
- Keep persistent project memory in Beads via `bd remember`; do not create ad hoc memory files.

**Architecture in one line:** issues live in a local Dolt DB; sync uses `refs/dolt/data` on your git remote; `.beads/issues.jsonl` is a passive export. See https://github.com/gastownhall/beads/blob/main/docs/SYNC_CONCEPTS.md for details and anti-patterns.
<!-- END BEADS CODEX SETUP -->
