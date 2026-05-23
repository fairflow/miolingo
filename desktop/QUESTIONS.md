# Open Questions for Matthew — Miolingo Desktop

Append-only. Phase 1 adds questions here when it wants Matthew's ruling but must
**not block** — it makes a reasonable call (logged in DECISIONS.md) and keeps
going. Matthew answers async; answers may redirect later work.

Format: date, question, why it matters, the interim assumption Phase 1 is
proceeding under.

---

### 2026-05-23 — How should optional cloud sync work, given no custom backend?
**Why it matters:** You want local-first + *optional* sync, but you can't host
custom server code (only packaged tools like WordPress). v1 won't build sync,
but the eventual mechanism affects nothing structurally except confirming the
sync-ready schema is enough.
**Candidates:** (a) file-based sync via your own cloud drive (iCloud/Dropbox
folder holding the SQLite file or an export); (b) a managed BaaS free tier
(Supabase/Firebase) — no self-hosting; (c) a small WordPress plugin/REST
endpoint as the sync server. **Interim assumption:** schema is sync-ready
(UUID PK, timestamps, soft-delete); sync deferred entirely to post-v1.

### 2026-05-23 — Do you have an Apple Developer ID for signing/notarization?
**Why it matters:** Determines whether v1 ships a properly notarized `.dmg` or
an unsigned bundle (users must right-click-open past Gatekeeper).
**Interim assumption:** packaging scripts support signing/notarization but, if
no cert is available in the build environment, Phase 1 produces an **unsigned**
bundle and documents the exact signing steps in `packaging/SIGNING.md`.

### 2026-05-23 — Confirm Story Reader is deferred (not dropped) for v1.
**Why it matters:** It was not in your must-keep selection. Confirming lets
Phase 1 either skip it cleanly or slot it after M3 if cheap.
**Interim assumption:** deferred to post-v1; built only if it falls out cheaply
once the practice-rendering scaffolding exists.

### 2026-05-23 — Is bundling Whisper `base` (~140 MB) acceptable for app size?
**Why it matters:** Bundling guarantees true offline first-run but inflates the
`.dmg`. The alternative is download-on-first-run (needs network once).
**Interim assumption:** bundle Whisper `base` for guaranteed offline; expose
model size in settings.

### 2026-05-23 — Which Piper voice per language meets your quality bar?
**Why it matters:** Piper offers multiple voices per language at different
quality/size tiers; you have strong opinions on TTS quality.
**Interim assumption:** Phase 1 picks a reasonable medium-quality voice per
language and produces sample clips (M7) for you to spot-check; weak ones get
flagged here for replacement.
