# Realised-phone work — inventory of existing recognition code & results

Step 1 of [`HANDOFF.md`](../../HANDOFF.md): what already exists, and what can be reused, before
any new code. Surveyed on `claude/weighted-phone-scorer` @ 247f51c (2026-09-29), which contains
all merged phonetics branches (`phone-recognizer-bakeoff`, `a2p-es-it-specialists`,
`a2p-model-lifecycle-ui`, web port M1–M8).

## Headline

- There is a working **bake-off harness** and **results for 7 languages**, plus a per-language
  recognizer module with lazy load/unload, a UI override, and a PanPhon weighted scorer.
- **Missing entirely:** forced alignment (no MFA/CTC alignment/TextGrid code), Parselmouth
  (not a dependency), committed native audio, an L1→L2 transfer model, and a formal model
  approval status.
- **Hazard:** `research/phonetics/phone_poc/analyze.py:15,25` folds the whole r-family
  {ɹ ɾ ʁ r ʀ} → `r`. Fine for its original PER comparison, but it erases exactly the contrast the
  /r/ slice needs. Do not reuse that normalisation.

## 1. Test harnesses and results

| Path | What | Format / how run | Reuse |
|---|---|---|---|
| `research/phonetics/phone_poc/cp_eval.py` | Main bake-off. Common Phone audio, scored with the app's own `weighted_phone` metric vs espeak-G2P of the transcript (not the CP TextGrid gold — L13-15 notes that as a future refinement). Model table `MODELS` ~L51. | `results/cp_eval_<lang>.json` (`mean_weighted_error`, `n_scored`, `n_failed`, timing). `python research/phonetics/phone_poc/cp_eval.py --n 150 --lang es --models fb,fb-xlsr,cnam-es --cp-root ~/datasets/common_phone/CP` | **Adapt** — the harness for any new model/detector result |
| `research/phonetics/phone_poc/fleurs_pt_eval.py` | Same on FLEURS (pt-BR, nl) | `results/fleurs_*.json` | Adapt |
| `research/phonetics/phone_poc/bench.py`, `analyze.py`, `corpus.json` | Earlier PoC on synthetic espeak audio (wav2vec2 lv-60 vs allosaurus); includes 5 injected-error items. `bench.py` L115-136 extracts per-frame CTC posteriors. WAVs not committed. | `results/results.json`, `normalized_summary.json` | Reference; posterior code useful for source-2 candidate scoring |
| `docs/research/phonetics/phone_recognizer_survey_2026-07.md` | Survey, bake-off tables, licence status per model, final wiring | MD | Key reference |
| `docs/research/phonetics/FINDING_audio_to_ipa_gap.md` | Root cause: score used text-derived IPA; notes no alignment/GOP exists | MD | Reference |
| `docs/research/phonetics/common_phone_apostrophe_report.md` | CP-fr MAU tier wrong for U+2019 words | MD | Gold-data caveat |
| `research/phonetics/DESIGN_DIGEST.md` | Two-channel design, per-phone abstention, Whisper "phonic gate" (L96-104) | MD | Reference — aligns with this handoff |
| `web/oracle/tests/test_attempt.py`, `test_smoke.py` | Closed loop: espeak → `/api/attempt` (Whisper tiny + fr A2P) | pytest | Pattern for golden-clip tests |
| `tests/test_phone_distance.py`, `research/phonetics/{phone_distance,fold_map}/test_*.py` | Scorer / fold-map unit tests | pytest | Reuse |

## 2. Models with results (mean 1 − weighted_phone similarity, n=150, lower is better)

Verified against the JSON in `research/phonetics/phone_poc/results/`.

| Lang (corpus) | fb lv-60 | fb xlsr-53 | Specialist | Wired default |
|---|---|---|---|---|
| es (CP) | 0.0603 | **0.0364** | cnam-es 0.0708 | xlsr-53 fallback |
| it (CP) | 0.0849 | 0.0645 | **cnam-it 0.0461** | Cnam italian |
| fr (CP) | 0.0719 | — | **cnam 0.0126** (pklumpp: 0 scored) | Cnam french |
| de (CP) | 0.1141 | **0.0426** | hk-de 1.0 (empty output) | xlsr-53 fallback |
| ru (CP) | 0.1333 | 0.1400 | **pklumpp 0.0733** | pklumpp |
| nl (FLEURS) | 0.1447 | 0.1116 | **clementapa 0.086** | Clementapa (licence undeclared → "test-only") |
| pt-br (FLEURS) | 0.1542 | **0.1143** | caiocrocha 0.1156 | xlsr-53 fallback |

Not benched: en, pt-pt, ZIPA.

**Caveat for this work:** these numbers measure agreement with espeak's *canonical* IPA on native
speech. They say nothing yet about whether a model can *name a foreign phone* (e.g. emit [ɹ] on
Spanish audio from an English speaker). The xlsr-53 espeak vocabulary is multilingual, so [ɹ]
is probably in its output inventory, but that is untested.

**Lifecycle / approval today:** `src/audio/phone_recognizer.py` — `_VOICE_TO_MODEL` (L62-70),
`KNOWN_MODELS` labels "(default)" / "(benched: loses)" / "(legacy)" (L89-100), LRU cache with
`_MAX_LOADED=2`, `set_model_override`, `unload`. UI selector `src/ui/sidebar.py` ~L555-610. There
is no `candidate → approved → retired` field; that registry (handoff §5) is new work, and can
wrap this module rather than replace it.

## 3. Reuse map against the handoff

| Handoff element | Existing | Status |
|---|---|---|
| Whisper gate | `src/audio/asr.py` (openai-whisper, hallucination checks, `no_speech_threshold`), `web/oracle/engines.py:36-47`; Swift WhisperKit | Reuse; no mlx-whisper yet |
| Forced alignment (MFA) | none | **Build** |
| Source 2: per-language models on segment | `phone_recognizer.py` (greedy CTC decode ~L252-266), `bench.py` posteriors | Adapt: constrained candidate scoring within a window is new |
| Source 3: Parselmouth detectors | none (not in requirements) | **Build** |
| PanPhon contrast features | `src/scoring/phone_distance.py` (`score`, `segment`, `_feature_distance`); `panphon>=0.22` in requirements | Reuse |
| Candidate inventory per (L1,L2) | fold map `src/ipa/data/espeak_fold_map.json` + `src/ipa/fold_map.py` — intra-L2 allophony only, pt-br/pt-pt/fr/nl/en; **no es/it/de** | New data (YAML); fold map is a model for format, not content |
| L1→L2 transfer priors | none (only prose, `language_materials/learning_plan.md:1237`, es→pt) | **Build** (with citations, for review) |
| Native exemplars | no audio committed; TTS on the fly (`src/audio/tts.py`, `web/oracle/engines.py`, piper in desktop); target IPA in `language_materials/unified/**` | Open question stands — likely a Common Voice/CP cut bank |
| Minimal pairs | `src/ipa/minimal_pairs.py` (`find_minimal_pairs`, derived from vocab) | Reuse for perception drills |
| Per-learner state | MySQL `user_progress` (`src/app_mysql.py:1663`), desktop SQLite `practice_attempts`, web Dexie `PracticeLogRow` (`web/app/src/store/db.ts`) — store phrase-level scores and IPA strings only | Adapt: no per-phone verdicts, model id/version, or evidence stored |
| Dual-channel scoring (hand verdicts to it) | `web/oracle/pipeline.py:134-179` `score_attempt`; `src/scoring/comparison.py` weighted_phone | Integration point |
| Corpora | Common Phone at `~/datasets/common_phone/CP` (CC0), FLEURS via HF — on the M4, not in repo | Reuse for golden clips / native bank |

## 4. Related open beads (from the remote Dolt DB, which looks behind the M4's)

`miolingo-0x9` (decision gate: phone recognizer vs Whisper — in progress), `miolingo-7w3` (score
used text IPA — in progress), `miolingo-dsq` (verdict still reads text path), `miolingo-yjc`
(word-aware segmentation for the acoustic channel — forced alignment would close this),
`miolingo-8gw` (learning from use — overlaps handoff §4), `miolingo-oam` (Whisper small
non-words — relevant to the gate).
