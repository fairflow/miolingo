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

### 2026-05-23 — Story Reader deferred to post-v1
**Decision:** Story Reader (full + scene-by-scene) is not a v1 must-keep; slot
it in only if cheap after M3, else post-v1.
**Reasoning:** Matthew's must-keep selection in Phase 0 was Quick Practice,
Vocabulary, History+Statistics — Story Reader was not selected.
**Flagged for confirmation in QUESTIONS.md.**
