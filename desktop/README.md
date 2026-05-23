# Miolingo Desktop

Native macOS desktop port of the Miolingo pronunciation trainer (PySide6/Qt +
local Whisper ASR + Piper TTS, local SQLite storage). This replaces the
Streamlit web app's UI shell and remote-MySQL storage while reusing the Python
business logic. The existing Streamlit app under the repo root remains the
reference implementation and is unchanged.

See `SPEC.md` (requirements), `MIGRATION_PLAN.md` (milestones), `DECISIONS.md`,
and `QUESTIONS.md`. `CLAUDE.md` is the agent operating manual.

## Develop

Use the shared repo venv (see `DECISIONS.md`):

```bash
source /Users/matthew/Software/working/miolingo/venv/bin/activate
pip install -e "desktop[dev]"     # run from the repo root
```

Run the app:

```bash
python -m miolingo_desktop.main
```

Run tests headlessly (required green before any PR):

```bash
cd desktop
QT_QPA_PLATFORM=offscreen pytest -q
```

Lint / type-check:

```bash
cd desktop
ruff check .
mypy miolingo_desktop
```

## Layout

```
miolingo_desktop/
  main.py        # PySide6 entry point (QMainWindow)
  core/          # UI-framework-free ported business logic (no streamlit, no PySide6)
  data/          # SQLite storage layer + migrations
  ui/            # Qt widgets/views
  resources/     # bundled voices / content references
tests/           # pytest suite (unit + integration)
packaging/       # PyInstaller spec, .dmg build, notarization scripts
```
