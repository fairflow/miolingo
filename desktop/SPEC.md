# Miolingo Desktop — Product Requirements (SPEC)

**Status:** Phase 0 (approved direction, ready for autonomous build)
**Owner:** Matthew Fairtlough
**Last updated:** 2026-05-23

---

## 1. Problem & goal

Miolingo is a multi-language pronunciation trainer. The current implementation
is a Streamlit web app backed by remote MySQL over an SSH tunnel. Streamlit
re-runs the whole script on every interaction, which is **unacceptably slow**,
especially on the shared community server. Matthew cannot host custom server
code (hosting only supports packaged tools like WordPress).

**Goal:** ship a **native macOS desktop app** that delivers the same core
training experience with a snappy, no-full-reload UI, works offline, and stores
user data locally — distributed as a downloadable app rather than a hosted site.

---

## 2. Chosen target stack (decision)

**PySide6 (Qt for Python) + PyInstaller**, packaged as a signed/notarized macOS
`.dmg`.

**Why this stack:**
- The expensive, correctness-critical logic (Whisper ASR, espeak/Piper TTS,
  Levenshtein/phoneme scoring, translation, materials loading) is **already
  Python and already largely decoupled** from Streamlit. PySide6 keeps 100% of
  that core — the migration is "replace the UI shell + storage," not a rewrite.
- Fully offline-capable; no JS/Python bridge or Rust toolchain to maintain.
- One Python codebase ports cleanly to Windows/Linux later (PyInstaller targets
  all three) without rewriting business logic.
- Headlessly testable (`pytest-qt` + `QT_QPA_PLATFORM=offscreen`), which the
  autonomous Phase 1 needs.

**Alternatives considered:** pywebview + web UI (rejected: frontend rewrite in
JS + bridge complexity); Tauri + Python sidecar (rejected: Rust + packaged-
Python sidecar = most moving parts, hardest to run autonomously); Flutter
(rejected: full Dart rewrite, loses the Python ASR core); BeeWare/Toga
(rejected: immature for heavy deps like torch/whisper). See DECISIONS.md.

---

## 3. Target users & platforms

- **v1: macOS only** (Apple Silicon + Intel if feasible from one build).
- Keep the codebase cross-platform-clean so Windows/Linux are a cheap later
  follow-up. **Windows/Linux are explicit non-goals for v1.**
- Single local user per install (see §6).

---

## 4. Feature requirements

### 4.1 Must-keep (v1)

| Feature | Source reference | Notes |
|---|---|---|
| **Quick Practice** | `render_quick_practice_tab`, `practice_word_from_audio` (`src/app.py`), `src/scoring/`, `src/audio/asr.py` | Core loop: pick phrase/word → hear target audio → record → transcribe → score → show feedback. This is the product. |
| **Vocabulary** | personal-vocabulary feature in `src/app.py` + `src/app_mysql.py` | Per-language word tracker: add, edit, source context, autofill, CSV export, practice-from-vocab. |
| **History** | `load_history`/`save_history` (`src/app.py`), progress tables in `src/app_mysql.py` | List of past practice attempts with scores. |
| **Statistics** | `render_statistics_tab` (`src/app.py`) | Currently mostly unimplemented in Streamlit. v1 should ship at least basic charts (per-language accuracy over time, attempts count). This is the chance to actually build it. |
| **Bundled language content** | `language_materials/` (static JSON/MD) | Portuguese (BR/PT), French, German, Spanish, Italian, Dutch, English. Ships with the app; no network needed. |
| **ASR scoring** | `src/audio/asr.py`, `src/scoring/` | Whisper (local). Phoneme/IPA comparison via espeak. |
| **Offline neural TTS** | new (Piper) + `src/audio/tts.py` | See §5. |
| **Settings** | `src/config.py` | Language, voice, Whisper model size, scoring algorithm, etc. Persisted locally. |

### 4.2 Nice-to-have (v1 if cheap, else fast-follow)

- **Story Reader** (full story + scene-by-scene). Deferred to post-v1 unless it
  falls out cheaply once Quick Practice + the rendering scaffolding exist.
  *(Confirm deferral — see QUESTIONS.md.)*
- **Online premium TTS** (Google Cloud TTS) as an optional upgrade over Piper.
- **LLM/DeepL translation** (`src/translation*.py`) as an optional online aid.

### 4.3 Non-goals (v1)

- Multi-user accounts / login / Argon2 auth (single local user — see §6).
- Remote MySQL, SSH tunnels, connection pooling/monitoring
  (`src/connection_pool.py`, `src/connection_monitor.py`, `src/app_mysql.py`'s
  remote paths).
- The admin dashboard (`src/miolingo-admin.py`, `src/admin_mysql.py`) — server
  ops, not relevant to a distributed desktop app.
- wav2vec2 ASR (Portuguese-only, heavy) — Whisper covers all languages.
- Full cloud-sync **implementation** is a fast-follow, not core v1 (schema must
  be sync-ready; target is Matthew's own DB via end-of-session batch push — see
  §6 and QUESTIONS.md). v1 may stub a session-end export.
- Auto-update (manual download for v1).
- Windows/Linux builds.

---

## 5. Audio (TTS) requirements

- **Default offline TTS: Piper** (neural, local, fast, MIT-licensed). Bundle
  one good voice per supported language. espeak quality is unacceptable and is
  demoted to a last-resort fallback only.
- **Optional online TTS: Google Cloud TTS** as a quality upgrade when the user
  supplies credentials and is online. Off by default.
- The TTS dispatcher must degrade gracefully: Piper (offline) → Google Cloud
  (if configured + online) → espeak (last resort).
- **ASR: Whisper**, default model **`medium`**, running locally. Transcription
  accuracy is load-bearing — an inaccurate transcript compromises the entire
  practice/scoring cycle, so we favour accuracy over model size/speed. Model
  size is user-adjustable in settings (down to `base` for slow machines).
  Requires `ffmpeg` bundled. Use Apple-Silicon acceleration where available.
  wav2vec2 dropped. (`medium` is ~1.5 GB → handled via download-on-first-run,
  not bundled — see §8.)

---

## 6. Data, state & accounts

- **Local-first.** All user data — settings, practice history, progress,
  vocabulary — lives in a **local SQLite database** in the macOS app-support
  directory (`~/Library/Application Support/Miolingo/`). No network needed.
- **No login/auth in v1.** Single implicit local user.
- **Sync-ready schema:** design tables with stable UUID primary keys,
  `created_at`/`updated_at` timestamps, and soft-delete flags. Sync target is
  **Matthew's own (existing remote) database**, as a **batch push at the end of
  a session** (not live per-write). v1 keeps the schema sync-ready and may stub
  a session-end export; the full sync push is a fast-follow, not core v1 — see
  QUESTIONS.md for the exact endpoint/credentials.
- **No in-app state framework reruns.** UI state is held in Qt
  models/view-state, not by re-executing the whole program. Settings persist to
  SQLite (mirrors `config.load_settings`/`save_settings`, DB path).

---

## 7. Performance requirements

Target profile: **snappy UI, scoring best-effort.**

- **UI interactions feel instant** — any click/keypress/tab-switch responds in
  **< 100 ms**; there is **no full-page rerun** (the Streamlit failure mode).
- **No UI freezes:** Whisper transcription, TTS synthesis, and file IO run off
  the UI thread (Qt worker threads / `QThreadPool`). The UI always remains
  responsive and shows clear progress during transcription.
- **Transcription latency is best-effort** (no hard SLA) but must show a
  determinate-or-spinner progress indicator and be cancellable.
- **Cold start** (app launch to interactive) target **< 5 s**; first
  transcription may be slower due to model load (show a one-time "loading
  model" state).

---

## 8. Distribution & updates

- **Signed and notarized `.dmg`**, direct download. Requires Matthew's Apple
  Developer ID (see QUESTIONS.md — if unavailable, Phase 1 produces an unsigned
  build + documents the signing/notarization steps to run later).
- **Manual updates** for v1 (download new version). No Sparkle/auto-update, no
  App Store.
- Packaging scripts live in `desktop/packaging/` and must be runnable as a
  single command.

---

## 9. Acceptance criteria (agent-verifiable "done")

Phase 1 is **v1-complete** when all of the following are objectively true. Each
is checkable without Matthew.

**Core loop**
- [ ] `python -m miolingo_desktop.main` launches a PySide6 window on macOS with
      no Streamlit imports anywhere under `desktop/`.
- [ ] User can select a language and a phrase/word from bundled
      `language_materials/` content.
- [ ] User can play target audio generated by **Piper**, offline.
- [ ] User can record audio, have it transcribed by Whisper, and see a
      pronunciation score + edit-level feedback. The UI never freezes during
      transcription (verified by a test that runs scoring off-thread).
- [ ] The score produced by the ported scoring code matches the source app's
      output for a fixed (audio, reference) fixture set (regression test).

**Persistence**
- [ ] Practice attempts are saved to local SQLite and appear in **History**
      across app restarts.
- [ ] **Vocabulary** add/edit/delete/CSV-export works and persists locally.
- [ ] **Settings** persist locally and are restored on relaunch.
- [ ] DB schema uses UUID PKs + `created_at`/`updated_at` + soft-delete.

**Statistics**
- [ ] **Statistics** shows at least: attempts count and accuracy trend over
      time, per language. Renders from local data with no network.

**Offline**
- [ ] After the one-time Whisper-model download, with networking disabled the
      full core loop (select → Piper audio → record → Whisper score → save →
      History → Stats) works end to end.

**Quality gates**
- [ ] `pytest -q` green headless (`QT_QPA_PLATFORM=offscreen`), including unit
      tests for ported core logic and at least one Qt smoke test per view.
- [ ] `ruff` and `mypy` pass.

**Packaging**
- [ ] `python packaging/build_macos.py` produces a launchable `.app`/`.dmg`
      bundling Python, Qt, ffmpeg, Piper voices, and `language_materials/`. The
      Whisper `medium` model is fetched on first run (with progress UI) and
      cached locally; offline works after that one-time download.
      (Signing/notarization gated on Apple ID — Matthew expects to provide one;
      if absent at build time, an unsigned bundle + documented signing steps
      satisfy this.)

**Non-goals respected**
- [ ] No login UI, no remote DB/tunnel code, no admin dashboard, no Windows/
      Linux build scripts in v1.
