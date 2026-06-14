# Miolingo — Swift / native macOS (agent instructions)

Scope: everything under `swift/`. The repo-root `CLAUDE.md` + `AGENTS.md` still
apply (git workflow, etc.); this file adds the Swift-specific conventions.

> This app is **built from the formal CCS spec** in `../spec/*.wl`, NOT from the
> Streamlit app. The spec's user-interaction surface is the contract. Read
> **`swift/PORTING.md`** (decisions), **`swift/RIG.md`** (the rig/skin design),
> **`swift/PLAN.md`** (round plan), **`swift/TEST_PLAN.md`** before non-trivial work.

## Layering (keep these separate)
- **L1 spec** → `../spec/*.wl` (Wolfram). The source of truth. Ports + pure
  value-functions. Change behaviour here FIRST, test it (`wolframscript -file
  spec/tests/*.wls`), then mirror in Swift.
- **MiolingoCore** (`Sources/MiolingoCore/`): pure domain ported from the spec —
  value-functions (levenshtein/comparePhonemes/alignPhonemes, addEntry, sort/
  filter/import/export, evaluate, the `*View` projections), the agents as value
  types (PracticeSession/Helm/VocabTable/Vocab/StoryReader), oracle protocols,
  SQLite store, and the rig model (Plimsoll/Cleat/Fitting/Berth/DeckPlan + RigJSON).
  Foundation + system SQLite3 only. Builds & tests **headlessly** (`swift test`).
- **MiolingoOracles** (`Sources/MiolingoOracles/`): the live "outside-the-model"
  services — AVSpeech/espeak TTS, SFSpeech + WhisperKit ASR. Shared by the app
  AND the harness.
- **Miolingo** (`Sources/Miolingo/`): the SwiftUI app (L3 skin). `AppModel` wires
  the restricted cross-component channels (vocabUpsert/goPractice/langRead/
  vocabRead) as direct calls — the τ's the walk harness auto-fires. The rig loft
  renders from the JSON grammar.
- **MiolingoHarness** (`Sources/MiolingoHarness/`): headless closed-loop speech
  test — espeak GENERATES audio → ASR transcribes → pure scorer evaluates.

## Discipline
- **Derive from the spec; don't copy old Swift.** The pure logic must match the
  `.wl` behaviour (the tests are transcribed from `spec/tests/*.wls`).
- **Honesty about oracles.** Never feed the recogniser the answer (no target as
  `contextualStrings`/prompt) — that produces performative, constant scores. Match
  comments to the actual wiring.
- **Held-until-concrete** mirrors the spec: an uninterpreted/empty input must not
  compute garbage (e.g. don't `ToString` an unevaluated oracle term).
- **Add a test with each behaviour change** (`Tests/MiolingoCoreTests/`), and where
  it's a spec behaviour, the corresponding `.wl` test too.
- **GUI + live oracles can't be verified headlessly** — say so; use the harness
  (`swift run MiolingoHarness [--whisper model]`) and Matthew's eyes/screenshots.

## Build · sign · run
```
cd swift/Miolingo
swift test                 # MiolingoCore behaviour (must stay green)
swift build                # core + oracles + app + harness
./Scripts/make_app.sh      # → signed Miolingo.app (ad-hoc; MIOLINGO_SIGN_ID=… for a stable cert)
open ./Miolingo.app        # first launch: right-click → Open (unsigned-dev)
```
- **Signing matters for permissions**: macOS keys Microphone + Speech-Recognition
  TCC to the code signature; an unsigned bundle won't keep the Speech grant.
- **Build version**: `appBuild()` and `make_app.sh`'s plist carry it; the git
  short-hash is **compiled in** via `BuildInfo.swift` (make_app rewrites then
  restores it). Bump the minor on each functional commit (Settings → Build shows it).
- **WhisperKit** is the one external dependency — `swift build` fetches it
  (network once), and it's gated on the `WHISPERKIT` define; dropping the
  Package.swift dependency + define keeps an offline build compiling (Whisper
  shows unavailable).

## Gotchas
- It's a **git worktree** (`…/miolingo-swift/`), not a normal clone — paths differ.
- espeak binary: `/opt/local/bin/espeak` (not espeak-ng locally).
- wolframscript: `/Applications/Wolfram.app/Contents/MacOS/wolframscript`
  (license errors are transient — retry).
- PR target / push discipline: see the repo-root `CLAUDE.md`.
