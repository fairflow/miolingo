# Miolingo — native macOS (Swift / SwiftUI)

A native rebuild of miolingo, driven by the **formal CCS specification**
(`../spec/*.wl`). The spec's user-interaction surface is the contract; the pure
value-functions are ported verbatim, and the "outside the model" oracles (TTS,
ASR, translation/IPA) sit behind protocols with native macOS backends.

See **[PORTING.md](PORTING.md)** for the full spec→Swift mapping and every
decision taken (build system, DB, oracles, signing).

## Layout
```
Miolingo/
  Package.swift                  SwiftPM (no external deps; uses system SQLite3)
  Sources/MiolingoCore/          pure domain ported from the spec (Foundation+SQLite)
    Model, VocabFunctions, VocabImportExport, PracticeFunctions,
    HelmFunctions, StoryFunctions, VocabView, Components, Oracles, Store
  Sources/Miolingo/              the SwiftUI app + native oracles
    MiolingoApp, ContentView, Views, AppModel, NativeOracles, Recorder,
    BundledStoryLibrary, Resources/stories.json
  Tests/MiolingoCoreTests/       behaviour transcribed from spec/tests/*.wls
  Scripts/make_app.sh            assemble a runnable (unsigned) Miolingo.app
```

## Build & test
```bash
cd Miolingo
swift test            # 15 tests — the ported spec behaviour
swift build           # core + app
./Scripts/make_app.sh # → Miolingo.app  (unsigned; first launch: right-click → Open)
open ./Miolingo.app
```

## Spec → app, component by component
| spec agent (`*Recovered.wl`) | Swift type | UI |
|---|---|---|
| `PS` / `PSActive` | `PracticeSession` | Practice tab |
| `Helm` | `Helm` | Settings tab |
| `Vocab` + `VocabTable` | `Vocab` + `VocabTable` (SQLite) | Vocabulary tab |
| `StoryReader` | `StoryReader` | Story tab |

The restricted cross-component channels (`vocabUpsert`, `goPractice`,
`langRead`, `vocabRead`) — the τ's the walk harness auto-fires — are wired as
direct calls inside `AppModel`.

## Oracles (native, offline-first)
- **TTS** → `AVSpeechSynthesizer`
- **ASR** (`recognisePhonemes`) → `SFSpeechRecognizer` (on-device) → espeak IPA
- **enrich** (autofill IPA) → espeak; translation provider deferred

## Local database (Helm, distributable)
SQLite at `~/Library/Application Support/Miolingo/miolingo.sqlite`, created on
first launch from the embedded schema/seed (settings + `languages` reference).
The vocab collection persists here; the seed ships with the app.
