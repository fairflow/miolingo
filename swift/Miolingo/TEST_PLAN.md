# Miolingo (Swift) — test plan

The Swift port is checked at two levels, both run headlessly with `swift test`.

## 1. Value-function unit tests (`MiolingoCoreTests.swift`)
Behaviour transcribed from `spec/tests/*.wls`. The Swift result must match the
`.wl` behaviour.

| test | spec source | checks |
|---|---|---|
| `testValidateWord` | VocabFunctions.wl | trim/punct/whitespace/length rules |
| `testAddEntryDedupAndBump` | VocabFunctions.wl | upsert dedup, times_seen bump, display kept |
| `testAddEntryCoalesceFillNeverOverwrite` | VocabFunctions.wl | fill-but-never-overwrite |
| `testDeleteAndUpdate` | VocabFunctions.wl | delete; editable-field update; unknown-field + key-change rejection |
| `testSortAndFilter` | VocabFunctions.wl | alpha/recent/oldest via logical clock; substring filter |
| `testImportRoundTripAndTargetGuard` | VocabFunctions.wl | header parse, []-IPA strip, target/none-header guards |
| `testExportCsvHeaderAndQuoting` | VocabFunctions.wl | 13-col header, RFC-4180 quoting |
| `testPractiseListShape` | VocabFunctions.wl | entries → practice phrase shape |
| `testLevenshteinAndCompare` | comparison.py | edit distance; similarity; empty-correct case |
| `testTargetOfAndSelectPos` | PracticeSessionFunctions.wl | range guard; select no-op (interleaving bug) |
| `testPracticeSessionFlow` | PracticeSessionRecovered.wl | load→select(guard)→record→score→capture→next |
| `testStoryModeSwitchPreservesPosition` | StoryReaderRecovered.wl | set_mode preserves (scene,pos); select_scene resets |
| `testStoryPracticeCaptureWord` | StoryReaderRecovered.wl | practice score + capture word |
| `testHelmViewAndSpeedGuard` | HelmFunctions.wl | trainingName; espeak-only speed guard |
| `testStoreRoundTrip` | (SQLite store) | vocab + Helm persist/reload; languages seeded |

## 2. Sequence tests (`ComponentSequenceTests.swift`)
The Swift analogue of `spec/walk-tests.wl`'s `walkTests` — named plans replayed
through the components + the cross-component channels (the τ's), asserting the
end state. Names mirror the spec batch.

| sequence | spec `walkTests` analogue | checks the channel(s) |
|---|---|---|
| `test_vs_capture` | `vs-capture` | add → vocabUpsert |
| `test_vs_import` | `vs-import` | import_bulk → vocabImport (target guard) |
| `test_ps_score` | `ps-score` | recording_made → attempt_made (langRead+ASR) |
| `test_sync_practise` | `sync-practise` | practise_vocab → goPractice → PS pull (vocabRead) |
| `test_full_roundtrip` | `full-roundtrip` | load→record→score→capture → vocabUpsert |
| `test_story_capture_roundtrip` | (story reader) | story practice → vocabUpsert; position preserved |
| `test_dictionary_enrich_oracle` | (enrich oracle) | offline lexicon translation lookup |
| `test_autofill_fills_only_empty` | autofill (vocab.py:411) | fills empty, never overwrites |

## Running
```bash
cd swift/Miolingo && swift test          # all of the above
```

## Not covered (and why)
- **GUI rendering** — SwiftUI views can't be exercised headlessly (same caveat as
  the spec's `walkUI`). Verified by running the app.
- **Live oracles** — the actual AVSpeech voice, SFSpeech transcription, and espeak
  process output depend on installed assets / permissions; the *pure* scoring and
  *enrich* logic they feed is covered above with injected inputs.
- **History / Statistics** — outside the current spec surface (external store).
