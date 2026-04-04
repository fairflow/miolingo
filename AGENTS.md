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
| `src/app.py` | 4,034 | Main Streamlit app — all UI, audio, scoring, practice logic |
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

## Key Configuration

| File | Purpose |
|------|---------|
| `.streamlit/secrets_template.toml` | Template for DB, API keys, SSH config |
| `.streamlit/config.toml` | Streamlit theme and server settings |
| `config/.miolingo.config` | App-specific configuration |
| `requirements.txt` | Python dependencies |
| `docker-compose.yml` | Container deployment (port 8601) |

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
