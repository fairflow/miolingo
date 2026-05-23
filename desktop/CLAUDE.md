# Miolingo Desktop — Agent Instructions (Phase 1: Autonomous Migration)

This file governs the **native desktop port** of Miolingo. It is the operating
manual for the autonomous Phase 1 agent. Read it fully before doing anything.

> The desktop app lives entirely under `desktop/`. The existing Streamlit app
> (repo root, `src/`) is the **reference implementation** — read it, port from
> it, but **do not modify it** during this migration.

---

## 0. What you are building

A native **macOS** desktop app (PySide6/Qt, packaged with PyInstaller) that
replaces the Streamlit pronunciation trainer. It reuses the existing Python
business logic (ASR, scoring, TTS, materials) and replaces only the Streamlit
UI shell and the remote-MySQL storage layer.

Read these before coding, in order:
1. `desktop/SPEC.md` — the PRD: requirements, chosen stack, acceptance criteria.
2. `desktop/MIGRATION_PLAN.md` — the milestone/PR sequence to execute.
3. `desktop/DECISIONS.md` — decisions already made (don't re-litigate these).
4. `desktop/QUESTIONS.md` — open questions for Matthew (don't block on them).
5. Repo root `AGENTS.md` — architecture of the source app you're porting from.

---

## 1. HARD GUARDRAILS (never violate)

These are absolute. Violating them is a failure regardless of outcome.

- **NEVER push to `main`.** Never push to `claude/dev`, `claude/dev-swept`, or
  `claude/dev-minimal-pairs` either. Those are integration branches.
- **Always work on a feature branch.** One branch per milestone/PR.
- **Always open a PR** for every shippable chunk. Never land work without a PR.
- **Run the test suite before opening any PR.** A PR may not be opened if tests
  fail. See §4.
- **Never modify the existing Streamlit app** (`src/`, root `app.py`, root
  `CLAUDE.md`, `AGENTS.md`). Port *from* it; leave it working.
- **Never commit secrets.** No API keys, DB creds, Apple certs, or
  `secrets.toml` content. Use `.gitignore` and environment/keychain.
- **Never create remote DB tunnels or connections.** The desktop app is
  local-first (SQLite). There is no SSH tunnel in this app.

---

## 2. Autonomy convention (how to make progress without Matthew)

Phase 1 runs unattended. Matthew is unavailable. Therefore:

> **When you hit a decision point, choose the most reasonable option, record it
> in `desktop/DECISIONS.md` (with reasoning + alternatives considered), and
> continue. Never block waiting for input. Put anything you'd want Matthew's
> ruling on into `desktop/QUESTIONS.md` and keep working.**

Rules of thumb for the autonomy convention:
- Prefer the option that (a) preserves offline-first behaviour, (b) keeps the
  Python core reusable, (c) is simplest to test headlessly, (d) is reversible.
- If a choice is cheap and reversible, just make it and note it in DECISIONS.md.
- If a choice is expensive/irreversible (e.g. a schema you'll build a lot on top
  of, a dependency that's hard to remove), pick the conservative option, build
  behind it, and log the trade-off in both DECISIONS.md and QUESTIONS.md.
- If blocked by something you genuinely cannot decide or fake (e.g. an Apple
  signing certificate you don't have), stub/skip that step, document it in
  QUESTIONS.md, and continue with everything else. Do not stall the whole plan.

Keep DECISIONS.md and QUESTIONS.md append-only and dated.

---

## 3. Project layout (target)

```
desktop/
├── CLAUDE.md            # this file
├── SPEC.md              # PRD
├── MIGRATION_PLAN.md    # milestone/PR sequence
├── DECISIONS.md         # decision log (append-only)
├── QUESTIONS.md         # open questions for Matthew (append-only)
├── pyproject.toml       # desktop app deps + tooling (created in M1)
├── miolingo_desktop/    # the app package
│   ├── __init__.py
│   ├── main.py          # PySide6 entry point
│   ├── core/            # ported, UI-free business logic (asr, tts, scoring, ...)
│   ├── data/            # SQLite storage layer + migrations
│   ├── ui/              # Qt widgets/views (Practice, Vocabulary, History, Stats)
│   └── resources/       # bundled models/voices/content references
├── tests/               # pytest suite for the desktop app
└── packaging/           # PyInstaller spec, .dmg build, notarization scripts
```

The ported business logic in `miolingo_desktop/core/` must be **UI-framework
free** — no `import streamlit`, no `import PySide6`. It takes plain args and
returns plain values, so it stays testable headlessly. (The source modules
`src/scoring/`, `src/audio/asr.py`, `src/audio/tts.py`, `src/config.py`,
`src/app_language_materials.py` are already close to this — strip the
`st.session_state`/`@st.cache_data`/`st.spinner` coupling when porting.)

---

## 4. Build / test / run commands

All commands run from `desktop/` unless noted. Use the repo venv at
`/Users/matthew/Software/working/miolingo/venv` (created in Phase 0) or a
dedicated `desktop/.venv`; record which in DECISIONS.md.

```bash
# Activate environment (decide & document which venv in M1):
source /Users/matthew/Software/working/miolingo/venv/bin/activate

# Install desktop deps (after pyproject.toml exists):
pip install -e ".[dev]"

# Run the app (dev):
python -m miolingo_desktop.main

# Run the FULL test suite — REQUIRED green before any PR:
pytest -q

# Run only fast/headless unit tests:
pytest tests/unit -q

# Lint / type-check (configure in M1; treat failures as blocking):
ruff check .
mypy miolingo_desktop

# Build the macOS app + .dmg (after packaging exists):
python packaging/build_macos.py
```

Qt GUI tests must run headlessly in CI/cloud. Use `pytest-qt` with the
`offscreen` platform: `QT_QPA_PLATFORM=offscreen pytest -q`. Any test that
needs a display, a microphone, or network must be marked
`@pytest.mark.manual` and excluded from the required pre-PR run.

---

## 5. Git workflow (per PR)

```bash
git fetch origin
git switch -c claude/desktop-<milestone-slug> origin/claude/dev-minimal-pairs

# ... do the work, keep core/ UI-free, add tests ...

pytest -q                      # MUST be green
git add desktop/<changed files>
git commit -m "feat(desktop): <what and why>"

# First push — explicit refspec (avoids inheriting the base branch upstream):
git push -u origin HEAD:refs/heads/claude/desktop-<milestone-slug>

gh pr create --base claude/dev-minimal-pairs \
  --title "desktop(Mn): <title>" --body "<summary + test plan>"
```

- PRs target **`claude/dev-minimal-pairs`** (the repo's integration branch),
  never `main`.
- One PR per milestone in MIGRATION_PLAN.md. Each PR must be independently
  reviewable and leave the desktop app in a working (if incomplete) state.
- Before the first push on a branch, verify upstream matches the local name
  (`git rev-parse --abbrev-ref @{u}`); if not, use the `HEAD:refs/heads/<name>`
  refspec form.

---

## 6. Definition of done (every PR)

A PR is done only when **all** hold:
- [ ] Code for the milestone's acceptance criteria (see SPEC.md) is implemented.
- [ ] `pytest -q` is green (headless), including new tests for the new behaviour.
- [ ] `ruff` and `mypy` pass (or new violations are documented and justified).
- [ ] No `import streamlit` anywhere under `desktop/`.
- [ ] No secrets committed.
- [ ] DECISIONS.md updated for any non-trivial choice made in the PR.
- [ ] The app still launches (`python -m miolingo_desktop.main`) and the
      milestone's vertical slice works.
- [ ] PR description lists what changed and a test plan.
