# Miolingo — round plan: "specify & port Practice Mode, grow the rig, skin & Help"

Approved 2026-06-07. A **methodology-driven** round: build the flow **L1 spec (`.wl`)
→ L2 rig (a language-neutral grammar) → L3 skin (loft + styling)**, deriving the
Swift from the spec/rig rather than copying the existing Swift (previous files are
reference only). Each L1 change is verified by walk sequences, which become the
Swift test plan.

## Decisions (locked)
1. Sequencing: **0 → 1 → 2 → 4(practice display) → 3(JSON rig + sidebar) → 5 → 6**.
2. Externalise the rig to **JSON now** (this round).
3. Help: **both** an in-app Help window and a (simpler) Apple Help Book.
   In-app help is **user-facing only — no methodology content**.
4. Phoneme colours: **keep the app's** (sub = blue, ins = green, del = pink, equal = plain).
5. **Leave history/stats out** until the next run.

## Phase 0 — quick fixes (DONE)
- Autofill stores the translation **lower-case** (recovered app behaviour).
- ASR robustness: retain the `SFSpeechRecognitionTask`; keep the best partial and
  return it on a late error (fixes "100% once, then 0%").
- "heard /…/" now always shows after an attempt — empty → an explicit
  "(nothing recognised …)" note, so failures are visible/diagnosable.

## Phase 1 — Spec: Practice Mode scoring (Wolfram)
Recovered from `src/scoring/comparison.py` (`get_edit_operations`) + `practice_tab.py`.
- `alignPhonemes[user, correct]` → Levenshtein backtrace: list of `{op, target, user}`,
  `op ∈ {equal, sub, ins, del}`.
- `normalisePhonemes[ipa]` → strip spaces/pause markers (clean IPA; never espeak `-x`).
- Enrich `evaluate` / `sessionView` / `storyView` to publish `recognised`, `targetIpa`,
  `userIpa`, `similarity`, `alignment`. Ports unchanged — value-functions only.

## Phase 2 — Wolfram: tests + walk sequences
- Headless `.wls` unit tests for the new functions.
- New `walkTests` sequences exercising record→attempt→score→(alignment in view).
- These sequences are the spec-of-record → transcribed into the Swift test plan.

## Phase 3 — Rigging: JSON grammar + variety
- `berth.*.json` (typed cleats), `rig.*.json` (cleat→fitting), `deckplan.*.json` (layout).
- Capabilities: `ingest` (paste/file/hint), constraint resolution `swap`, projection
  sub-rig (the alignment panel).
- The Swift loft reads JSON. Show variety: top-level switch → **sidebar**;
  story mode → radio; sort → menu; tts → segmented; languages → menu (+swap).

## Phase 4 — Build Swift to the new spec
- Port `alignPhonemes` + enriched projection into `MiolingoCore`.
- Practice results: recognised phrase, target/user IPA, **colour-coded phoneme diff**, similarity.
- Sidebar navigation from the deck-plan. Swift tests transcribed from Phase 2.

## Phase 5 — Styling (a swappable skin)
- Theme: typography, spacing, palette, phoneme colours, score viz, app icon.

## Phase 6 — macOS Help
- In-app Help window (bundled Markdown, `⌘?`) + a simple Apple Help Book.
- User-facing docs only (no methodology).

## Out of scope this round
History / Statistics (external store), espeak internal codes, per-attempt history.
