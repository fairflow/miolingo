# Open Questions for Matthew — Miolingo Desktop

Append-only. Phase 1 adds questions here when it wants Matthew's ruling but must
**not block** — it makes a reasonable call (logged in DECISIONS.md) and keeps
going. Matthew answers async; answers may redirect later work.

Format: date, question, why it matters, the interim assumption Phase 1 is
proceeding under.

---

### 2026-05-23 — [RESOLVED] Cloud sync mechanism
**Answer (Matthew):** Sync to **his own existing DB**, feasible as a **batch
push at the end of each session**. Resolves the "no custom backend" worry — he
already has the DB. Full sync is a fast-follow; v1 stays sync-ready (schema with
UUID PK / timestamps / soft-delete) and may stub a session-end export.
**Open sub-question for Phase 1:** the exact DB endpoint/credentials and whether
to reuse the source app's remote MySQL. Phase 1 needs these to build the actual
push — keep them out of version control (env/keychain).

### 2026-05-23 — [RESOLVED, tentative] Apple Developer ID
**Answer (Matthew):** Can likely obtain a signed Apple ID ("possibly"). Plan
for a signed/notarized `.dmg`; keep the unsigned-build fallback + documented
signing steps in `packaging/SIGNING.md` if the cert isn't present at build time.

### 2026-05-23 — Confirm Story Reader is deferred (not dropped) for v1.
**Why it matters:** It was not in your must-keep selection. Confirming lets
Phase 1 either skip it cleanly or slot it after M3 if cheap.
**Interim assumption:** deferred to post-v1; built only if it falls out cheaply
once the practice-rendering scaffolding exists.

### 2026-05-23 — [RESOLVED] Whisper model — use `medium`
**Answer (Matthew):** `base` accuracy isn't good enough — he uses `medium`, and
an inaccurate transcript compromises the whole practice cycle. So default to
`medium`. Since it's ~1.5 GB it's **not bundled**; downloaded on first run with
progress, cached locally (offline thereafter). Size adjustable in settings.
**Residual note for Phase 1:** confirm `medium` latency is tolerable on
Matthew's Mac; lean on Apple-Silicon acceleration. If too slow, expose an easy
`small`/`base` toggle (no ruling needed — just make it adjustable).

### 2026-05-23 — Which Piper voice per language meets your quality bar?
**Why it matters:** Piper offers multiple voices per language at different
quality/size tiers; you have strong opinions on TTS quality.
**Interim assumption:** Phase 1 picks a reasonable medium-quality voice per
language and produces sample clips (M7) for you to spot-check; weak ones get
flagged here for replacement.
