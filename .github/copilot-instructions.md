# Copilot Instructions for Miolingo

**See `AGENTS.md` in the project root for the canonical project reference** — architecture,
module map, dependency graph, critical rules, and known issues. This file contains
Copilot-specific supplements only.

---

## Quick Context

- Main app: `src/app.py` (~4,000 lines), Streamlit at `localhost:8501`
- Admin: `src/miolingo-admin.py` at `localhost:8505`
- Stack: Python 3.10+, Streamlit 1.39+, Whisper (ASR), Google Cloud TTS / eSpeak NG / gTTS, MySQL over SSH tunnel, Argon2 auth

## CRITICAL: Database Connection Rule

**Never create new DB tunnels or connections.** Always use `app_mysql.get_connection()`.
See `AGENTS.md` for the full explanation and correct patterns.

## Developer Workflow

- Python 3.10+ with venv, ffmpeg, portaudio, eSpeak NG
- Install: `pip install -r requirements.txt`
- Run locally: `cd src && streamlit run app.py`
- Versioning: semantic versioning via `scripts/bump_app.py` (see `VERSION_WORKFLOW.md`)
- Formatting: Black. Linting: Ruff.

## Integration Points

- eSpeak NG must be installed system-wide (provides IPA extraction)
- Whisper model downloads at first run (base model)
- ffmpeg required for audio conversion
- Deployable on Streamlit Cloud or via Docker (`docker-compose.yml`)

## References

- `AGENTS.md` — full architecture and module reference
- `docs/dev-docs/REFACTOR_PLAN.md` — active refactor plan
- `docs/app-docs/` — user, tester, and developer guides
- `APP_CHANGELOG.md` — version history
