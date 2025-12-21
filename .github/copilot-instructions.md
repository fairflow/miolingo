# Copilot Instructions for Portuguese Pronunciation Trainer (espeak-ng-pt-br)

## Project Overview
- This is a Streamlit web app for multi-language pronunciation practice (Portuguese, French, Dutch, Flemish) with real-time AI feedback.
- Core tech: Python (Streamlit), eSpeak NG (TTS), OpenAI Whisper (ASR), ffmpeg (audio), soundfile/numpy (processing).
- App logic is in `app.py`. Documentation and guides are in `app-docs/`.

## CRITICAL: Database Connection & Tunnel Management

**⚠️ NEVER CREATE NEW TUNNELS OR CONNECTIONS ⚠️**

This is the most critical rule in the codebase:

1. **ONE connection per session**: Each user session has exactly ONE database connection stored in `st.session_state.db_connection`
2. **ONE tunnel per session**: The SSH tunnel is managed by ConnectionPool and reused for the entire session
3. **ALWAYS use `app_mysql.get_connection()`**: This returns the cached connection - never create your own
4. **SSH commands must reuse the tunnel**: If you need to execute SSH commands, reuse credentials but do NOT create new paramiko tunnels
5. **Check session state first**: Before any database operation, ensure the session connection exists

**Why this matters:**
- Creating multiple tunnels exhausts server resources
- Orphaned tunnels don't close properly
- This was a critical bug that caused production outages
- Each tunnel uses a port; running out of ports crashes the app

**Correct patterns:**
```python
# ✅ CORRECT: Reuse session connection
conn = app_mysql.get_connection()
cursor = conn.cursor()

# ✅ CORRECT: Check session state
if st.session_state.get('db_connection'):
    conn = st.session_state.db_connection

# ❌ WRONG: Never do this
new_conn = mysql.connector.connect(...)  # NO!
new_tunnel = SSHTunnelForwarder(...)     # NO!
```

## Architecture & Data Flow
- User interacts via Streamlit UI (`app.py`).
- Practice session state: current phrase, user recordings, settings (language, voice/dialect).
- TTS: eSpeak NG (formant synthesis) and optionally gTTS.
- Audio is generated, possibly converted (MP3→WAV via ffmpeg), then played back.
- User records audio; recognition is performed using Whisper.
- Results and history are stored in `practice_history.json` (runtime, not in git).

## Key Files & Directories
- `app.py`: Main app logic, language/voice config, session state, UI.
- `app-docs/`: Contains `USER_GUIDE.md`, `TESTING_GUIDE.md`, `DEVELOPER_GUIDE.md`.
- `practice_config.json`, `practice_history.json`: User/session data (runtime only).
- `requirements.txt`: Python dependencies.
- `phsource/`, `dictsource/`, `espeak-ng-data/`: eSpeak NG data and sources.
- `APP_CHANGELOG.md`, `VERSION_WORKFLOW.md`: Versioning and workflow docs.

## Developer Workflow
- Use Python 3.8+ (3.10+ recommended), ffmpeg, portaudio, eSpeak NG (see DEVELOPER_GUIDE.md for install).
- Create a virtual environment and install dependencies with `pip install -r requirements.txt`.
- Run locally: `streamlit run app.py`.
- First run downloads Whisper model (base).
- Use VS Code with Python extension, Black for formatting, Pylint/Ruff for linting.
- Versioning follows semantic versioning; see `VERSION_WORKFLOW.md` for branch/tag conventions.

## Project-Specific Patterns
- Language/voice selection is dynamic; config is in `app.py`.
- Phrase files are organized per language.
- All user/session data is runtime-only and not committed.
- CCS testing framework is available for advanced UI state testing (`ccs_test_framework.py`).
- Documentation is kept in `app-docs/` and referenced from the UI and guides.

## Integration Points
- eSpeak NG binaries and data must be available; may require local build/install.
- Whisper model is downloaded at runtime.
- ffmpeg is required for audio conversion.
- App can be deployed on Streamlit Cloud or run locally.

## Example Commands
- Local run: `streamlit run app.py`
- Install dependencies: `pip install -r requirements.txt`
- Check eSpeak NG: `espeak-ng --version`

## References
- For user, tester, and developer guides, see `app-docs/`.
- For versioning and workflow, see `VERSION_WORKFLOW.md` and `APP_CHANGELOG.md`.
- For eSpeak NG details, see `docs/` and upstream eSpeak NG documentation.

---
If any section is unclear or missing, please provide feedback for further refinement.
