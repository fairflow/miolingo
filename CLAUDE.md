# Miolingo — Claude Code Instructions

## Python Environment

**Always activate the project virtual environment before running any Python, pip, or related command.**

The venv holds all installed packages — running outside it means those packages are invisible to Python, regardless of which binary you invoke.

- Look for `venv/` or `.venv/` at the project root (check both)
- Activate with `source venv/bin/activate` or `source .venv/bin/activate` before running anything
- If neither exists, **stop and ask the user for help** — do not attempt to recreate it

---

## Project Overview
Streamlit pronunciation trainer for Portuguese, French, Dutch, Flemish and other languages.
- **Main app:** `src/app.py` (~4000 lines), runs at `localhost:8501`
- **Admin:** `localhost:8505`
- **Stack:** Streamlit 1.39+, OpenAI Whisper (ASR), Google Cloud TTS / eSpeak NG / gTTS, MySQL over SSH tunnel, Argon2 auth

## CRITICAL: Database Connection Rule
**Never create new DB tunnels or connections.** Always reuse the session connection via `app_mysql.get_connection()`. Creating new tunnels exhausts server resources (past production outage). One tunnel per session, always.

```python
# ✅ CORRECT
conn = app_mysql.get_connection()

# ❌ WRONG — never do this
new_conn = mysql.connector.connect(...)
new_tunnel = SSHTunnelForwarder(...)
```

## Current Debug Mode
The app is running in active debug mode. The following are **intentional** — do not report as new bugs:
- `Missing cookie_password in st.secrets` warning banner
- State-change banners (e.g. "State changed: story_mode: None → Scene by Scene")
- Connection Info panel showing tunnel details, SQL connection string, MySQL ID — this is for developer/tester use

## Known Issues (already tracked — do not duplicate)
- Statistics tab: charts/breakdowns not yet implemented (missing feature, not regression)
- Scene title encoding: accented characters stripped in dropdown/heading (Streamlit limitation under investigation)
- Scoring/ASR accuracy: needs full refactor, not a simple fix
- Input red border: default Streamlit behaviour on touched fields, may be configurable

---

## Testing Protocol

When asked to test the app, follow this standard approach:

### Classification
Every issue must have **both**:

| Field | Options |
|-------|---------|
| **Type** | `Warning` · `Bug` · `Missing Feature` |
| **Severity** | `Critical` · `High` · `Medium` · `Low` |

- *Warning* — something shown to users that shouldn't be (config leakage, internal messages)
- *Bug* — incorrect behaviour: wrong output, broken interaction, data error, encoding failure
- *Missing Feature* — expected functionality absent (no charts, no filter, no export)

**Severity calibration in debug mode:** Lower severity by one level for debug-message leakage compared to production — the app banner explicitly warns users about this.

### Report Format
Use this template for each issue:

```
### ISSUE-N [Type] [Severity] — Short descriptive title

**Steps to reproduce:**
1. ...
2. ...

**Expected:** ...
**Actual:** ...
**Notes:** (optional context, workaround, related issues)
```

Include at the top of the report:
- App version (from sidebar)
- Environment (browser, OS, TTS engine, logged-in user)

### Depth
Cover **all** of the following before writing up:
- Every tab: Quick Practice, Story Reader, Statistics, History
- Sidebar: language settings, TTS engine, slow speech, Scoring Algorithm, Audio Processing, CCS Testing, Connection Info
- Within each tab: every expander, every sub-mode, at least one complete primary action

**Widget State Rule:** For every interactive widget encountered (toggle, checkbox, radio button, dropdown, selector), test **all** states — not just the default. Binary widgets: test both on and off. Multi-value selectors: test at least one non-default value. An untested state is an untested feature. This is the browser-test equivalent of ISTQB State Transition Testing, and is what the CCS framework's port matching is built to catch.

### Interleaving
Claude may (and should) pause to ask the user to log in, record audio, or perform any action requiring human input. This is expected and collaborative — not an error.

Use `docs/TESTING_CHECKLIST.md` as a structured guide.

---

## Key Files
- `src/app.py` — main Streamlit app
- `src/app_mysql.py` — MySQL DB module (use `get_connection()`)
- `src/ccs_test_framework.py` — CCS dual-agent test framework (available for structured testing)
- `docs/TESTING_CHECKLIST.md` — structured UI test checklist
- `.github/ISSUE_TEMPLATE/bug_report.md` — GitHub issue template
- `.streamlit/config.toml` — Streamlit theme and server config
- `APP_CHANGELOG.md` — version history
