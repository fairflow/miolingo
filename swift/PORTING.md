# Miolingo → Swift / native macOS — porting notes & decisions

A native macOS (SwiftUI) rebuild of miolingo, driven by the **formal CCS
specification** in `spec/*.wl` as the source of truth for the user-facing ports
and the pure value-functions. Only the *oracles* ("outside the model": TTS, ASR,
translation/IPA enrichment) and a few in-transition functions are taken from the
Python implementation, and those sit behind protocols.

Built and verified on: macOS 15.7.7 (Sequoia), Xcode 16.4, Swift 6.1.2, arm64.

---

## What "done" means here (per Matthew's brief)
The spec's **user-interaction surface** is treated as finished: the ports exposed
to the user for each component are complete (incomplete wrt the original app, but
self-contained). So the Swift app implements exactly those ports — no more.

## Decisions taken in your absence (each with its default + why)

| # | Question | Decision | Why |
|---|----------|----------|-----|
| 1 | Build system | **SwiftPM** package (`swift/Miolingo`), library `MiolingoCore` + app target `Miolingo` + tests; a `Scripts/make_app.sh` assembles the `.app` bundle. | Builds **offline & headlessly** (`swift build`, `swift test`); no Xcode GUI needed; the project is plain text, reviewable. An `.xcodeproj` is generated only for signing/distribution later. |
| 2 | External dependencies | **None.** System `SQLite3`, `AVFoundation`, `Speech`, `SwiftUI`, (optional `Translation`). | Network-fetching SPM deps (GRDB etc.) can't be assumed in a sandbox; system libs guarantee a reproducible build. |
| 3 | Database tech | Raw **SQLite** via the SDK's `SQLite3` module, thin Swift wrapper. | Zero deps; bundles cleanly; matches the app's SQL store (`vocab_entries`). |
| 4 | "Helm as a local-only DB, distributable" | Helm settings **and** the language reference table live in a **bundled seed DB** (`miolingo-seed.sql` schema + seed), copied to `~/Library/Application Support/Miolingo/miolingo.sqlite` on first launch (writable). | "Local only" = offline, no service; "distributed with the app" = shipped as a Resource and materialised on first run. |
| 5 | TTS engine | **`AVSpeechSynthesizer`** (native, offline, multilingual) as default; protocol `TTSEngine` keeps espeak/Google pluggable. | The app offered google/espeak; AVSpeech needs no API key and works offline. |
| 6 | ASR / `recognisePhonemes` | **`SFSpeechRecognizer`** (on-device) → text; optional espeak phonemes; behind `SpeechScorer`. Fallback: compare recognised text. | Whisper/wav2vec2 are heavy Python; SFSpeech is native on-device. The spec's `comparePhonemes`/Levenshtein (pure) is ported verbatim and scores whatever the recogniser returns. |
| 7 | `enrichOracle` (translation + IPA) | **Implemented**: `DictionaryEnrichOracle` = translation from a bundled offline lexicon (`lexicon.json`, target→native) + IPA via **espeak**. Autofill now fills both, offline. Upgrade path: swap the lexicon for the Apple `Translation` framework (`TranslationSession` via `.translationTask`, macOS 15+) or an API — same `EnrichOracle` signature. | Keeps autofill working offline with no keys; real translation is a drop-in swap (per `co-development.md`). Direction resolved as target→native (the spec's source→target is ambiguous for a stored vocab translation). |
| 8 | Signing / notarisation | **Deferred** (last, per brief). App is unsigned; `make_app.sh` builds a runnable local `.app`. | Explicitly requested last. |
| 9 | Components implemented | PS (Practice), Helm (Settings), Vocab + VocabTable (Vocabulary), StoryReader (Story). | Exactly `mioComponents` in `MioCore.wl`. |

## Spec → Swift mapping
- Each CCS agent → a **pure value type** in `MiolingoCore` whose methods are the
  agent's *ports* (each returns the successor state), mirroring the `.wl`
  transitions one-for-one. The restricted cross-component channels
  (`vocabUpsert`, `goPractice`, `langRead`, `vocabRead`) become **direct calls**
  between component models inside `AppModel` (the τ's the walk harness auto-fires).
- The pure value-functions (`levenshtein`, `comparePhonemes`, `addEntry`,
  `sortEntries`, `applyFilter`, `practiseList`, `importInto`, `exportCsv`,
  `validateWord`, `targetOf`, `selectPos`, `evaluate`, `*View`) are ported
  **verbatim in behaviour** and covered by tests transcribed from the `.wl` test
  suites.
- The `*View` projections become the SwiftUI view-models (what each pane renders).

## Open items left for you (non-blocking)
- Real translation provider (decision 7) — swap behind `EnrichOracle`.
- StoryLibrary as a real store (the spec defers `sceneOf` to a fixture; mirrored
  here as a bundled JSON/seed).
- History/Statistics tabs — out of the current spec surface (external store), so
  not built.
- Signing/notarisation (decision 8).
