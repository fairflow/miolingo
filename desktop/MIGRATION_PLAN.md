# Miolingo Desktop — Migration Plan

Execution plan for Phase 1 (autonomous). Each milestone = **one PR** targeting
`claude/dev-minimal-pairs`, independently reviewable, leaving the app working.
Sequenced so the **vertical slice** (a real practice attempt, end to end) is
proven early — before breadth.

Conventions: see `desktop/CLAUDE.md`. Don't start a milestone until the prior
PR's acceptance checks pass. Record decisions in `DECISIONS.md` as you go.

---

## Milestone 0 — Scaffold & toolchain  → PR `desktop-m0-scaffold`

Stand up an empty-but-runnable PySide6 app and the test/lint/CI plumbing.

- `desktop/pyproject.toml` with deps (PySide6, openai-whisper, piper-tts,
  numpy, soundfile) and `[dev]` extras (pytest, pytest-qt, ruff, mypy).
- `miolingo_desktop/main.py`: opens an empty `QMainWindow` titled "Miolingo".
- `tests/unit/test_smoke.py`: imports the package; a `pytest-qt` test that the
  main window constructs under `QT_QPA_PLATFORM=offscreen`.
- Decide & document the venv (shared repo venv vs `desktop/.venv`).
- **Acceptance:** `python -m miolingo_desktop.main` shows a window; `pytest -q`
  green headless; `ruff`/`mypy` pass.

## Milestone 1 — Port the UI-free core  → PR `desktop-m1-core`

Move business logic into `miolingo_desktop/core/`, stripped of Streamlit.

- Port `config.py`, `scoring/` (comparison + phonemes), `audio/asr.py`,
  `audio/tts.py`, `app_language_materials.py`, `pronunciation_trainer.py`,
  `translation*.py` into `core/`. Remove `import streamlit`,
  `@st.cache_data`, `st.spinner`, `st.session_state` — replace caching with
  plain in-process caches/lru_cache; replace `st.*` callbacks with injected
  callables or return values.
- Model/voice loaders become plain functions (no session_state).
- **Tests:** unit tests for scoring against fixed (reference, hypothesis)
  inputs; a **regression fixture** capturing the source app's score for a known
  (audio, reference) pair so parity is provable. Materials-loading tests.
- **Acceptance:** `core/` has zero UI imports; scoring parity test passes;
  `pytest -q` green.

## Milestone 2 — Local storage layer  → PR `desktop-m2-storage`

SQLite persistence, sync-ready schema. No UI yet.

- `miolingo_desktop/data/`: SQLite at
  `~/Library/Application Support/Miolingo/miolingo.db`; schema migrations
  (e.g. simple versioned SQL or `yoyo`/`alembic` — pick one, document).
- Tables: `settings`, `practice_attempts`, `vocabulary`, (+ `progress` if
  needed). UUID PKs, `created_at`/`updated_at`, `deleted_at` soft-delete.
- Repository classes with typed methods (save attempt, list history, CRUD
  vocab, get/set settings). Mirror the data shapes used by the source
  `app_mysql.py` so ported logic fits.
- **Tests:** CRUD round-trips against a temp-file SQLite DB; migration applies
  cleanly to an empty DB; soft-delete hides rows.
- **Acceptance:** repo tests green; DB created on first run.

## Milestone 3 — VERTICAL SLICE: Quick Practice end-to-end  → PR `desktop-m3-practice`

The proof-of-concept PR. One language, the full loop, real audio, persisted.

- `ui/practice_view.py`: select language + phrase, play target audio (Piper —
  bundle at least one voice now, M5 completes coverage), record mic input,
  run Whisper transcription **off the UI thread**, show score + edit feedback,
  save the attempt to SQLite.
- Wire `core/` + `data/` together behind a small app controller.
- Threading: `QThreadPool`/worker for transcription + TTS; progress + cancel.
- **Tests:** Qt smoke test of the view (offscreen); an integration test that
  drives controller `record→transcribe(stub)→score→save` and asserts a row in
  SQLite; a test asserting transcription runs off the GUI thread.
- **Acceptance (this is the milestone that proves the whole approach):** on
  macOS, a human can pick a phrase, hear Piper audio, record, and get a score
  that persists to History — **with the UI staying responsive**. Offline.

## Milestone 4 — History + Settings  → PR `desktop-m4-history-settings`

- `ui/history_view.py`: list past attempts (score, phrase, language, date)
  from SQLite; restart-persistent.
- `ui/settings_view.py` + persistence: language, voice, Whisper model size,
  scoring algorithm, TTS engine. Restored on relaunch.
- **Tests:** history renders seeded rows; settings round-trip persist/restore.
- **Acceptance:** attempts from M3 show in History across restarts; settings
  persist.

## Milestone 5 — Vocabulary  → PR `desktop-m5-vocabulary`

- `ui/vocabulary_view.py`: per-language word list — add, edit, delete (soft),
  source context, autofill, **CSV export**, and "practice from vocab" (feeds a
  word into the M3 practice flow).
- **Tests:** CRUD via UI controller; CSV export content; practice-from-vocab
  hands a word to the practice controller.
- **Acceptance:** vocab CRUD + CSV export + practice-from-vocab work and persist.

## Milestone 6 — Statistics  → PR `desktop-m6-statistics`

Build what Streamlit never finished.

- `ui/statistics_view.py`: attempts count + accuracy-over-time trend, per
  language, computed from SQLite. Use Qt charts (`QtCharts`) or a matplotlib
  canvas — pick one, document.
- **Tests:** stat aggregation functions over seeded data (pure, headless);
  view smoke test.
- **Acceptance:** Statistics renders real charts from local data, offline.

## Milestone 7 — Full Piper voice coverage + TTS fallback  → PR `desktop-m7-tts`

- Bundle a vetted Piper voice for **every** supported language (pt, fr, de, es,
  it, nl, en). Implement the dispatcher: Piper → Google Cloud (optional/online)
  → espeak (last resort).
- Generate sample clips per language into `packaging/` artifacts for Matthew to
  spot-check quality (note in QUESTIONS.md if any voice is weak).
- **Tests:** dispatcher selection logic; each bundled voice synthesizes a clip
  offline.
- **Acceptance:** every language has offline Piper audio; fallback order works.

## Milestone 8 — macOS packaging  → PR `desktop-m8-packaging`

- `packaging/build_macos.py` + PyInstaller spec. Bundle Python, Qt, Whisper
  `base` model, ffmpeg, Piper voices, and `language_materials/`.
- Signing/notarization scripted but **gated on Apple Developer ID**: if absent,
  produce an unsigned `.app`/`.dmg` and document the exact signing/notarize
  steps in `packaging/SIGNING.md` + QUESTIONS.md.
- **Tests:** a build smoke check that the produced bundle launches and the DB
  initializes (best-effort in cloud; document if it must be verified on a Mac).
- **Acceptance:** `python packaging/build_macos.py` yields a launchable bundle;
  full offline core loop works from the packaged app.

---

## Deferred / fast-follow (not in v1 unless cheap)

- **Story Reader** (full + scene-by-scene) — slot after M3 if the rendering
  scaffolding makes it cheap; otherwise post-v1. Confirm with Matthew.
- **Online premium TTS** (Google Cloud) beyond the fallback hook in M7.
- **LLM/DeepL translation** aid.
- **Cloud sync** — schema is sync-ready (M2); mechanism unresolved (QUESTIONS).
- **Auto-update (Sparkle)**, **Windows/Linux builds**.

## Sequencing rationale

M0–M2 build the skeleton (UI shell, core, storage) with no user-visible
feature. **M3 is deliberately the first feature and is a full vertical slice** —
it exercises every layer (UI thread-safety, Piper, Whisper, scoring, SQLite) and
de-risks the entire approach before investing in breadth (M4–M7). Packaging is
last so it bundles a known-working app.
