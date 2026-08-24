# Miolingo web — design of record

Full approved plan: see the port plan (2026-07-12). This file tracks the
as-built architecture; DECISIONS.md carries the why.

## Shape

```
browser (one origin)                      localhost
┌─────────────────────────────┐          ┌──────────────────────────┐
│ Svelte 5 SPA (app/)         │  /api/*  │ FastAPI oracle (oracle/) │
│  ui/        thin components │ ───────► │  espeak G2P              │
│  app/model  τ-channel wiring│          │  Whisper ASR       (M3)  │
│  domain/    pure TS agents  │ /materials│ A2P recognizers   (M3)  │
│  store/     Dexie + prefs   │ ───────► │  weighted scoring  (M3)  │
│  oracle/    HTTP client     │          │  language_materials mount│
└─────────────────────────────┘          └──────────────────────────┘
   all state lives here                     stateless (model caches only)
```

- **domain/** ports the CCS spec's five agents (PS, Helm, Vocab, VocabTable,
  StoryReader) as pure functions `(state, args) → state` plus `readySet` and
  `*View` projections — the same mapping the Swift port proved. No framework
  imports allowed in this directory.
- **app/model.svelte.ts** is the composition root: the spec's restricted τ
  channels (goPractice, langRead, vocabRead, vocabUpsert) become direct calls
  between $state slices. Language is *borrowed* from Helm at point of use;
  the vocab collection is *owned* by the VocabTable slice and written through
  to Dexie.
- **oracle/** answers with everything displayed about an attempt (ASR text,
  both IPA channels, scores, per-phone ops) in ONE round trip — the TS side
  never recomputes displayed numbers (single source of truth; golden-parity
  tests cover the few pure functions ported for the spec test table).

## Ports

Vite dev :8330 (proxies /api + /materials) · oracle :8331 · prod-local: the
oracle serves `app/dist/` at / so everything is one process, one origin.

## Invariants (from the spec — do not violate)

1. UI renders **view projections only**, never raw agent state.
2. Control enablement comes from **readySet functions only**.
3. Own it → store it; borrow it → fetch fresh (no cached language, no vocab
   snapshots crossing component boundaries).
4. capture_vocab · vocabUpsert is atomic — one state transition, no flicker.
5. Story mode-switch preserves (scene, pos); select_scene resets pos.
