# Decision Log — Miolingo Desktop

Append-only. Newest at the bottom. Each entry: date, decision, reasoning,
alternatives considered. Phase 1 adds to this whenever it makes a non-trivial
choice (see the autonomy convention in `CLAUDE.md`).

---

### 2026-05-23 — Target stack: PySide6/Qt + PyInstaller
**Decision:** Build the native app with PySide6 and package with PyInstaller.
**Reasoning:** The business logic (Whisper ASR, scoring, TTS, materials) is
already Python and largely decoupled from Streamlit, so this keeps the entire
core and rewrites only the UI shell + storage. Fully offline, headlessly
testable, one codebase ports to Win/Linux later.
**Alternatives:** pywebview+web UI (frontend rewrite + bridge), Tauri+Python
sidecar (Rust + most moving parts), Flutter (full Dart rewrite, loses Python
core), BeeWare/Toga (immature for torch/whisper). **Chosen by Matthew in Phase 0.**

### 2026-05-23 — Storage: local SQLite, local-first, sync-ready
**Decision:** All user data in a local SQLite DB under
`~/Library/Application Support/Miolingo/`. Schema uses UUID PKs,
`created_at`/`updated_at`, soft-delete — sync-ready but no sync built in v1.
**Reasoning:** Matthew can't host custom backends; desktop app must be offline
and self-contained. Sync-ready schema avoids a painful migration later.
**Alternatives:** keep remote MySQL+SSH (retains the latency/hosting coupling
we're escaping); build sync now (mechanism unresolved — see QUESTIONS).
**Chosen by Matthew (local-first + optional later sync).**

### 2026-05-23 — No auth in v1 (single local user)
**Decision:** Drop Argon2 login / multi-user. One implicit local user.
**Reasoning:** A distributed single-user desktop app doesn't need server-side
auth; removing it cuts large surface area (`app_mysql` auth, sessions, cookies).
**Alternatives:** keep accounts (only needed if multi-user/sync, both deferred).
**Implied by Matthew's data-model choice.**

### 2026-05-23 — Default offline TTS: Piper; espeak demoted
**Decision:** Bundle Piper neural voices as the default offline TTS; Google
Cloud TTS optional/online; espeak last-resort fallback only.
**Reasoning:** Matthew: espeak quality is "unspeakably bad." Piper is local,
fast, good quality, MIT-licensed, covers the target languages. Keeps offline.
**Alternatives:** online-only TTS (no offline audio); keep espeak (rejected on
quality). **Chosen by Matthew.**

### 2026-05-23 — ASR: Whisper local (`base`), wav2vec2 dropped
**Decision:** Whisper running locally, default model `base`, ffmpeg bundled.
Drop wav2vec2.
**Reasoning:** Whisper covers all languages and already works; wav2vec2 is
Portuguese-only and heavy. Local = offline.
**Alternatives:** keep wav2vec2 (Portuguese-only, not worth the footprint).

### 2026-05-23 — Platform: macOS only for v1
**Decision:** Ship macOS first; keep code cross-platform-clean. Win/Linux are
non-goals for v1.
**Reasoning:** Focus polish; PyInstaller makes later Win/Linux cheap.
**Chosen by Matthew.**

### 2026-05-23 — Performance bar: snappy UI, scoring best-effort
**Decision:** UI < 100 ms / no full reruns / never freezes (work off-thread);
transcription latency best-effort with progress + cancel.
**Reasoning:** The Streamlit pain is the full-script rerun, not raw model speed.
Fixing responsiveness is the win; Whisper latency is inherent.
**Chosen by Matthew.**

### 2026-05-23 — Distribution: signed/notarized .dmg, manual updates
**Decision:** Direct-download notarized `.dmg`; no auto-update, no App Store.
Signing gated on Apple Developer ID availability (see QUESTIONS).
**Reasoning:** Simplest credible distribution for v1; Sparkle/Store are later.
**Chosen by Matthew.**

### 2026-05-23 — Docs & app live under `desktop/`; source app untouched
**Decision:** All migration docs and the new app live under `desktop/`. The
existing Streamlit app (`src/`, root `CLAUDE.md`, `AGENTS.md`) is read-only
reference during migration.
**Reasoning:** Keeps the working app intact as a reference/fallback; gives
Phase 1 a clean, self-contained working directory; avoids clobbering the
critical Streamlit/DB rules in the root `CLAUDE.md`.
**Made by planning agent (Phase 0).**

### 2026-05-23 (rev) — Whisper default = `medium`, downloaded on first run
**Decision:** Default Whisper model is **`medium`** (not `base`). Not bundled
(~1.5 GB); downloaded on first run with progress and cached locally so the app
is offline thereafter. Model size adjustable in settings (down to `base`).
**Reasoning:** Matthew uses `medium` — `base` accuracy is not good enough, and
an inaccurate transcript compromises the whole practice/scoring cycle. Accuracy
beats size/speed here. Bundling 1.5 GB would bloat the `.dmg`, so
download-on-first-run is the better trade. Use Apple-Silicon accel where
possible to offset the slower model.
**Alternatives:** bundle `medium` (huge `.dmg`); keep `base` (rejected on
accuracy). **Supersedes the earlier `base` decision; chosen by Matthew.**

### 2026-05-23 (rev) — Cloud sync target = Matthew's own DB, end-of-session push
**Decision:** Sync (a fast-follow, not core v1) pushes local data to Matthew's
own existing remote DB as a **batch at the end of a session**, not live. v1
keeps the schema sync-ready and may stub a session-end export.
**Reasoning:** Matthew confirmed syncing to his own DB at session end is
feasible — resolves the "no custom backend" concern (he already has the DB).
Batch-at-session-end is simpler and avoids per-write coupling.
**Alternatives:** live sync (more complex); BaaS/WordPress endpoint (unneeded —
he has his own DB). **Chosen by Matthew.**

### 2026-05-23 (rev) — Apple Developer ID expected to be available
**Decision:** Plan for a signed/notarized `.dmg`; build scripts assume an Apple
Developer ID is provided. Keep an unsigned-build fallback + documented signing
steps if the cert isn't present at build time.
**Reasoning:** Matthew says he can likely obtain a signed Apple ID.
**Chosen by Matthew (tentative — "possibly").**

### 2026-05-23 (M0) — Use the shared repo venv; Python 3.12 baseline
**Decision:** Use the existing shared repo venv at
`/Users/matthew/Software/working/miolingo/venv` (Python 3.12, per `pip3.12`)
rather than a dedicated `desktop/.venv`. Target Python 3.12 in `pyproject.toml`.
**Reasoning:** The shared venv already has numpy/openai-whisper/soundfile/gtts
installed (visible in `venv/bin/`), so most desktop deps are present; a separate
venv would duplicate ~GBs of torch/whisper. Desktop-only deps (PySide6,
piper-tts, pytest-qt) are added via `pip install -e "desktop[dev]"`.
**Alternatives:** dedicated `desktop/.venv` (cleaner isolation but heavy
duplication and slower to provision autonomously). Reversible — switching to a
private venv later is just a re-create + reinstall.

### 2026-05-23 (M0) — Tooling config: ruff + mypy in desktop/pyproject.toml
**Decision:** Scope ruff and mypy to `desktop/miolingo_desktop` and
`desktop/tests` via config in `desktop/pyproject.toml`. Line length 100.
mypy runs in non-strict-but-typed mode initially (warn on untyped defs off for
ported third-party-touching code) to keep early milestones unblocked.
**Reasoning:** Keeps gates meaningful for new code without forcing full strict
typing on logic ported from an untyped Streamlit app on day one.
**Alternatives:** full strict mypy (too much churn up front, reversible to
tighten later).

### 2026-05-23 (M1) — Core defaults: Whisper `medium`, TTS engine `piper`
**Decision:** `core/config.DEFAULT_SETTINGS` sets `whisper_model_size="medium"`
and `tts_engine="piper"` (the source app defaulted to `base` / `google_cloud`).
**Reasoning:** Matches ratified Phase-0 decisions (accuracy-first ASR; offline
neural TTS default). Dispatcher order: Piper -> Google Cloud (only if an api_key
is supplied) -> espeak.
**Alternatives:** keep source defaults (contradicts Phase-0 rulings).

### 2026-05-23 (M1) — Drop wav2vec2; drop `format_ipa` HTML helper from core
**Decision:** The ported `asr.py` is Whisper-only (wav2vec2 removed).
`phonemes.format_ipa` (returned an HTML `<span>`) is NOT ported into `core/` —
IPA markup is a UI concern for the Qt layer.
**Reasoning:** wav2vec2 was Portuguese-only/heavy (Phase-0). Keeping HTML out of
`core/` preserves the UI-framework-free guarantee.
**Alternatives:** keep `format_ipa` (leaks presentation into core).

### 2026-05-23 (M1) — Replace Streamlit caching/session with plain mechanisms
**Decision:** `@st.cache_data` -> `functools.lru_cache`; Whisper model
`st.session_state` cache -> a module-level dict with `clear_model_cache()`;
`st.spinner` -> optional `progress_fn`; `st.warning`/`st.error` -> optional
`warn_fn`/`error_fn` (default `logging`); `st.secrets[...]` -> an explicit
`api_key` argument (no global secrets in core).
**Reasoning:** Removes Streamlit coupling while preserving behaviour; callbacks
let the Qt worker thread report progress without core importing PySide6.
**Alternatives:** custom cache class (unneeded).

### 2026-05-23 (M1) — Materials dir via env override + repo walk-up
**Decision:** `materials.get_data_dir()` returns `$MIOLINGO_MATERIALS_DIR` if
set, else walks up to the repo-root `language_materials/`. lru_cached; tests
`cache_clear()` around overrides.
**Reasoning:** Dev reads the real bundled content unchanged; packaging (M8)
points the env var at bundled resources without code changes.
**Alternatives:** hardcode a path (breaks under PyInstaller).

### 2026-05-23 (M1) — Scoring parity proven at the pure-scoring layer
**Decision:** The parity regression locks the ported edit-distance scoring via
(a) hardcoded JSON fixtures with certain expected values and (b) a cross-check
against an independent reference Levenshtein over multi-edit/unicode strings.
The audio->phoneme stage is a manual test (needs espeak + a recording).
**Reasoning:** `comparison.py` is copied byte-for-byte, so identical output is
guaranteed and provable headlessly; the audio stage can't run in CI without a
mic/model, so it's marked manual rather than faked.
**Alternatives:** bundle a real audio fixture + model (huge, still needs a
Mac/mic to capture) — deferred to M3's manual acceptance.

### 2026-05-23 — Story Reader deferred to post-v1
**Decision:** Story Reader (full + scene-by-scene) is not a v1 must-keep; slot
it in only if cheap after M3, else post-v1.
**Reasoning:** Matthew's must-keep selection in Phase 0 was Quick Practice,
Vocabulary, History+Statistics — Story Reader was not selected.
**Flagged for confirmation in QUESTIONS.md.**
