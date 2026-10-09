# Realised-phone: status, test results, and what approval needs

Companion to [`HANDOFF.md`](../../HANDOFF.md) and the [spec](REALISED_PHONE_SPEC.md).
Beads: `miolingo-6vo` (.2 data model, .3 slice, .4 golden).

## What is built (en → es, /r/ slice)

| Handoff item | Where | State |
|---|---|---|
| Candidate inventory (§1a) | `src/realised_phone/data/pairs/en-es.yaml` | Draft for review. /r/ and /ɾ/ are active; VOT, spirants and vowels are data only. |
| Source 1, extended-inventory alignment | — | Experimental track, not started (proposal below). |
| Source 2, recognizer on the aligned window | `realised_phone/recognizer.py` | Works with xlsr-53. Candidates the model can't name are reported as `unsupported`. |
| Source 3, contrast detector | `realised_phone/detectors/rhotic.py` | Rhotic detector (occlusions + F3). Thresholds calibrated on Common Phone dev. |
| Combination (§1c) | `realised_phone/combine.py` | Sources agree → confident; they disagree → uncertain. |
| Forced alignment | `realised_phone/align.py` | Calls MFA 3.x via `align_one` subprocess. |
| Whisper gate | `realised_phone/gate.py` | Word recall of the target words, accent-insensitive. In practice it reuses the transcript already in the result. |
| Model registry + approval gate (§5) | `realised_phone/registry.py`, `data/model_registry.yaml` | **Nothing is approved.** Candidates only run with `allow_candidates`, and their output is marked not learner-visible. |
| See / hear (§2) | `realised_phone/view.py`, `src/ui/realised_phone_panel.py` | Debug-only panel: learner word/sound/slowed audio, native exemplar, spectrogram, occlusion and F3 plots. |
| Native exemplar bank | `scripts/realised_phone/build_native_bank.py` | Script ready. The bank still has to be built on the M4 from Common Phone es. |
| Coaching ladder (§3) | `realised_phone/coaching.py`, `data/coaching/en-es.yaml` | Draft content for r→tap, r→english_r, ɾ→english_r and ɾ→trill. Refused unless reviewed. |
| Learner model (§4) | `realised_phone/learner.py`, `data/priors/en-es.yaml` | Beta per (phone, context), escalation, improvement feedback. The priors are a draft and the citations are unverified. |
| Golden tests (step 4) | `tests/golden/realised_phone/manifest.yaml`, `scripts/realised_phone/run_golden.py` | 24 Common Phone clips plus 2 LibriSpeech: 0 confident-wrong. Learner entries are still TODO. |
| Calibration | `scripts/realised_phone/calibrate_rhotic.py` | Run on Common Phone dev. The calibrated thresholds are shipped: `calibrated: true`. |
| Evaluation for approval | `scripts/realised_phone/eval_rhotics.py`, `eval_alignment.py` | Common Phone test results are below. The registry `results` point to them. |
| Common Phone data | `scripts/realised_phone/extract_cp_parquet.py` | Pulls Spanish and English from the Hugging Face Parquet release, a way round the 13 GB Zenodo tarball. |
| Batch alignment | `realised_phone/align.py` `mfa_align_batch` | One MFA run per corpus, with a cache. Utterances MFA can't align are remembered and not retried. |

Tests: `venv/bin/python -m pytest tests/realised_phone` has 58 unit tests. The golden tests
run only when MFA and the clips are present.

## Common Phone results (2026-09-30) — the evidence for your review

This run used Common Phone from the author's Hugging Face release (`pklumpp/CommonPhoneDataset`,
CC0, 16 kHz), extracted with `scripts/realised_phone/extract_cp_parquet.py`. At most 3
utterances were taken per speaker.

- **Calibration** used the dev split: 400 Spanish utterances (136 speakers) and 400 English
  (202 speakers).
- **Evaluation** used the test split: 400 Spanish (138 speakers) and 400 English (192 speakers).
- **Labels** are the aligner's dictionary phones. Spanish [r] counts as trill and [ɾ] as tap;
  English [ɹ] counts as English r, and English codas are excluded.
- **Checking the labels:** Common Phone's own IPA alignment agrees with MFA on tap vs trill for
  612 of 614 non-coda rhotics. Every disagreement is in a coda, where the MFA dictionary writes
  a trill and the contrast is neutralised anyway.

**Combined verdicts, non-coda, test split, with the dev-calibrated thresholds now shipped**
(`results/rhotics_cp-test-cal-dev.json`):

| label | tokens | confident | confident & correct | confident & wrong |
|---|---|---|---|---|
| tap (native es) | 613 | 362 (59%) | 360 (**99.4%**) | 1 as trill, 1 as English r |
| trill (native es) | 153 | 38 (25%) | 31 (**81.6%**) | 6 as tap, 1 as English r |
| English [ɹ] (English speakers) | 437 | 170 (39%) | 167 (**98.2%**) | 2 as trill, 1 as tap |
| **all** | 1203 | 570 (47.4%) | **97.9%** | 12 |

With the shipped *default* thresholds the result was 96.9% at 48.5% coverage
(`results/rhotics_cp-test-shipped.json`). The calibrated thresholds improved held-out accuracy,
so they were adopted in `calibration/rhotic.yaml`. Only two values changed: occlusion depth went
from 5 to 8 dB, and the trill contact interval from 25–75 to 25–60 ms.

What each source contributes (non-coda test tokens where the source reached a decision):
- **Recognizer, xlsr-53 restricted to the candidates:**
  - taps 560 of 581 right, trills 84 of 98, English [ɹ] 391 of 408;
  - it abstains on about 8% of tokens.
  - It is the strong source.
- **Detector, occlusions + F3:**
  - weak on its own: dev balanced accuracy 0.66 at 68% coverage;
  - it confuses English [ɹ] with tap (stop releases next to the r look like contacts) and misreads trills.
  - Its value is as an independent second vote. A confident verdict needs both sources to
    agree, so each of the 12 confident errors is a case where both were wrong together.

**Alignment** (`results/align_cp-es-test.json`): MFA against Common Phone's alignment.
- Rhotic midpoint difference: median 11 ms, 90th percentile 44 ms.
- 73% of rhotics are within 20 ms.
- 80 of 400 utterances had a different number of rhotics in the two alignments and were skipped.

**Golden clips** (`tests/golden/realised_phone/manifest.yaml`, 24 Common Phone test clips):
- Chosen at random with a fixed seed from tokens both aligners agree on, one speaker per clip,
  **not** filtered on our own output.
- Results: 19 pass, 5 abstain (uncertain), 2 soft failures (tentative and wrong), **0 confident
  wrong**.
- The two LibriSpeech clips also pass.

**Against the acceptance bar proposed below:**
- Confident accuracy ≥ 95%: **met** (97.9%).
- Coverage ≥ 50% per class: **not met.** Tap 59%, trill 25%, English r 39%.
- No English-r claims on native speech: **not met strictly.** There were 2 confident English-r
  verdicts among 766 native tokens.
- **The trill class is the weak point.**
  - Confident trill verdicts are wrong 18% of the time, and the errors are mostly "tap". In a
    learner that would mean telling someone their correct trill was a tap.
  - Some of these may be label noise: native read speech sometimes reduces a trill, and the
    labels are dictionary forms, not what was actually heard. Listening to the 6 cases would
    settle it. They're in the JSON with speaker, word and time.
  - A cheap mitigation, if you want one (your call; I haven't changed anything):
    1. Only show a "you made an error" verdict when it's confident *and* the recognizer's margin
       is above a higher threshold.
    2. Treat trill→tap verdicts as tentative until learner data exists.

**What the Common Phone data can't show:** English-L1 learners speaking Spanish. English [ɹ]
here comes from English speech, and learner recordings (including [ʁ]) are still needed. They
are the `-TODO` entries in the golden manifest.

## English ↔ French (2026-09-30)

The same method was used: Common Phone test split, non-coda tokens, both sources combined.
- **Native French [ʁ]:** 400 utterances from 136 speakers.
- **Native English [ɹ]:** the same 400 English test utterances as above.
- **Error stand-ins:** each language's r is judged against the *other* language's target. This
  is not learner speech; learners speaking the target language are still needed.

| Pair | Tokens | Confident & correct | Coverage | The main error, caught confidently |
|---|---|---|---|---|
| **French → English** (target [ɹ]) | 1022 | **98.3%** | 35% | French r (uvular): 31% of tokens, 98.4% right |
| **English → French** (target [ʁ]), xlsr-53 | 1022 | **98.3%** | 35% | English r: 39% of tokens, 98.2% right |
| English → French, Cnam French recognizer | 1022 | 97.8% | 22% | English r: **5%**. Cnam calls English r "uvular" 275/437 times |

**Recognizer choice for French:**
- Cnam is the app's French specialist and is excellent on native French, but it knows only
  French sounds. As a source of evidence for *which* sound a learner made, a model that also knows
  the learner's L1 sounds is needed.
- So xlsr-53 is now listed first for `fr` in the registry. Cnam keeps its role in the app's
  existing accuracy scoring; that part is unchanged.

**Uvular cue** (new, in `calibration/rhotic.yaml`):
- The rule: F3 not lowered, and (F2 backed or mostly devoiced), and ≥ 70 ms.
- Picked on dev, where it had 5% false alarms on Spanish tap/trill. On the Spanish **test**
  split it fires on 20% of trills (taps 2%), which confirms the caveat that part of what it learned
  is French-vs-Spanish speaker differences.
- It does no harm to Spanish: the recognizer never agrees on "uvular" there, so those tokens
  become uncertain. English → Spanish went from 97.9% at 47% to **98.2% at 46%**.
- It shouldn't be relied on alone.

**Golden clips:** 24 new ones, chosen the same way as the Spanish ones. Results: 15 pass,
9 uncertain, **0 confidently wrong**. Across the whole manifest (50 clips): 34 pass, 14 uncertain,
2 tentative-and-wrong, 0 confidently wrong.
- **Next detector fix:** 4 of the 9 uncertain cases are French [ʁ] straight after a stop
  (*trente*, *précis*, *crabiers*, *projets*). The stop's closure and release look like a
  tongue-tip contact, so the detector says "tap" while the recognizer says "uvular".
- English [ɹ] in *grave*/*principles* had the same issue. Ignoring a dip at the very start of an
  r that follows a stop should fix both.

Result files: `results/rhotics_cp-test-fr-en.json`, `rhotics_cp-test-en-fr-xlsr.json`,
`rhotics_cp-test-en-fr.json` (Cnam), `rhotics_cp-test-en-es-uvcue.json`.

## Stop-release fix (2026-09-30)

When an r follows a stop, the detector now ignores dips in the first 10 ms of the r. Those dips
are the stop's closure and release, not a tongue contact. The window was chosen on dev and checked
on the test split:

| Pair | Before | After | English r, confident & correct |
|---|---|---|---|
| English → Spanish | 98.2% at 46% | **98.8% at 47%** | 98.2% → **100%** |
| English → French | 98.3% at 35% | **99.1% at 34%** | 98.2% → **100%** |
| French → English | 98.3% at 35% | **99.1% at 34%** | 98.2% → **100%** |

It doesn't fix French [ʁ] after a stop, which is still sometimes read as a tap: that dip is part of
the uvular sound itself. Result files: `results/rhotics_cp-test-*-stopfix.json`.

## Dutch (Netherlands) and Flemish (2026-09-30)

These are **distinct models** (`en-nl`, `en-nl-be`):

| | Netherlands | Flemish |
|---|---|---|
| r | trill, tap and uvular accepted; the English-like r is accepted in codas (native "Gooise r") | trill, tap and uvular only |
| g | voiceless and voiced both fine | voiced soft g; a Netherlands-style g is an **accent** (penalty 0.3), not an error |

**Data:**
- **Netherlands:** FLEURS `nl_nl` test (364 utterances; FLEURS has no speaker IDs).
- **Flemish:** the only open multi-utterance source is **one male speaker** (400 utterances, cut
  from Common Voice). The Flemish rows below are a **sanity check, not validation**.
- **Error stand-ins:** Common Phone English test ([ɹ] for r; [k ɡ] and [h] for g/ch).
- **Aligner:** MFA `dutch_cv` 2.0.0, whose dictionary is rule-generated and crude (*een* → [eːn]).
  It's shared by both varieties.

**r** (non-coda):

| | Recognizer | Confident & correct | Coverage | English r caught |
|---|---|---|---|---|
| Netherlands | **xlsr-53** | 99.6% | 20% | 38% of tokens, all right |
| Netherlands | Clementapa | 100% | 2% | **0%**: it calls English r "trill" 311/437 |
| Flemish (1 speaker) | xlsr-53 | 100% | 25% | 38%, all right |

**g/ch**, with the new dorsal detector (stop vs fricative) plus a recognizer. Each native token
is judged against its own target (ch /x/ or g /ɣ/):

| | Recognizer | Confident & correct | Coverage | English k/g caught | Native g confirmed |
|---|---|---|---|---|---|
| Netherlands | **xlsr-53** | 99.1% | 19% | 46%, all right | 12% |
| Netherlands | Clementapa | 98.9% | 14% | 35% | 11% |
| Flemish (1 speaker) | xlsr-53 | 99.2% | 15% | 46% | **0%**: it never names voiced [ɣ] |
| Flemish (1 speaker) | **Clementapa** | 98.5% | 16% | 35% | **13%** (37/38 right) |

**Choices:**
- xlsr-53 for everything in Netherlands Dutch and for the Flemish r.
- **Clementapa for the Flemish g**, via a per-target `recognizer:` field in `en-nl-be.yaml`.
  Judging soft vs harsh g needs a model that can name the voiced [ɣ]. Clementapa is testing-only
  (licence undeclared).

**Known gaps:**
- English [h] for g/ch is never confident. The recognizer hears it (109/123), but the detector
  deliberately doesn't decide [h] vs [x], because on this data that only separates on recording
  differences.
- Coverage is lower than for Spanish or French (15–25%) because native Dutch r and g vary so much.
- The Flemish voiced/voiceless thresholds are uncalibrated.
- **Flemish needs multi-speaker data** to be validated: Common Voice nl, which has Belgian accent
  tags, or CGN.

Result files: `results/rhotics_test-en-nl-r-*.json`, `dorsal_test-en-nl-*.json`,
`rhotics_vl1spk-en-nlbe-r.json`, `dorsal_vl1spk-en-nlbe-*.json`.

## English ↔ French vowels and aspiration (2026-10-01)

### Aspiration (English p t k vs French short-lag p t k): no detector shipped — negative result

I tried a voice-onset-time (VOT) measurement: the time from the burst to the start of voicing, inside the
MFA window for word-initial p/t/k. Data: Common Phone dev, 859 French and 486 English stops.

| | French (unaspirated) | English (aspirated) |
|---|---|---|
| median VOT | 24 ms | 32 ms |
| inter-quartile range | 5–40 ms | 5–63 ms |

Textbook values are about 15 ms for French and 60–80 ms for English. On crowd-sourced phone audio the two
distributions overlap almost completely. The **best single threshold (55 ms) gets 59% balanced accuracy**, and
even the extremes only reach 62–70%. Two causes:

- voicing onset is smeared by pitch-tracker lag;
- low-band hum and noise read as "voicing" during the aspiration.

That is not good enough to vote, so **there is no VOT detector**. Aspiration stays a recognizer-only target
(fr-en `pʰ tʰ kʰ`, en-fr `p t k`): its verdicts can be at most *tentative*. Tentative verdicts are never shown as
errors and never escalate coaching. A usable VOT detector would need cleaner audio (learner recordings in the
app) or a learned burst/voicing model. Scratch script: `vot_vowel_feats.py` (not committed).

### French /y/ vs /u/ (tu / tout) and English "goose": vowel detector

`detectors/vowel.py` models each vowel as a diagonal Gaussian over the F1/F2/F3 ratios measured at the middle half of
the vowel. Each ratio is divided by the speaker's own median over voiced frames, which normalises for vocal-tract
length without needing other utterances. Calibration (`scripts/realised_phone/calibrate_vowel.py` →
`calibration/vowel.yaml`) uses Common Phone dev:

- French y: n 321;
- French u: n 189;
- French i: n 797;
- English goose [ʉ]: n 202.

Mean F2 ratio: y 1.15, u 0.78, i 1.28, English goose 1.03. Note that English "goose" lies between French y and u.

**First attempt: four-way posterior over y / i / u / goose with all three ratios. Too weak.** On Common Phone test
native French [y] was named y only 43/120 times, against goose 34, i 32 and u 11. The detector then *disagreed* with
a correct recognizer on 42 native tokens, so only 4/164 native [y] were confirmed. Kept as
`vowel4way_cp-test-en-fr-{y,u}.json`.

**Shipped: a backness-only vote.** F2 ratio alone separates front [y] (1.16) from back [u] (0.85). The detector now
says only "front" or "back" (calibration `vote`). A "front" vote is *compatible* with [y], [i] and goose. So when the
recognizer hears [i], the combiner does not count it as a disagreement: the verdict is tentative [i]. That is the
new `Evidence.compatible` / `combine._narrow` rule. A real disagreement, front vs [u], is still *uncertain*.

Common Phone test, non-coda tokens (xlsr-53 recognizer plus vowel detector):

| target y (*tu*) | tokens | confident | confident and right |
|---|---|---|---|
| native French [y] | 164 | 109 | **109** (all), up from 4 |
| French [u] as the error (*tu → tout*) | 34 | 22 | **21** |
| French [i] as the error | 178 | 1 | 0 (171 tentative [i]) |
| English goose [ʉ] as the error | 35 | 3 | 0 (2 said back, 1 said y) |
| **all** | | 33% coverage | **96.3%** confident accuracy |

| target u (*tout*) | tokens | confident | confident and right |
|---|---|---|---|
| native French [u] | 34 | 21 | **21** (no false alarms) |
| English goose [ʉ] as the error | 35 | 13 | 0 (all called back [u]) |

How to read this:

- *Tu → tout*, the main English-L1 error, is caught confidently 62% of the time.
- Native [y] is confirmed 66% of the time, with no false confirmations.
- [i] for [y] is only ever *tentative*, because the recognizer alone separates rounding. Tentative verdicts never
  count as errors.
- **English goose for French u is not detected.** All 13 confident "goose" misses say back [u], meaning "correct".
  The failure is safe: it never accuses a learner wrongly, it just lets the error through. The goose labels are also
  weak ground truth: Common Phone writes English /uː/ as ʉː by convention, whatever the speaker's accent, and the
  detector itself heard 15 of the 35 as back. Measuring this properly needs real English-L1 learners.
- A confident [y] means two sources rule out [u], but only the recognizer rules out [i].

Results:

- `vowel_cp-test-en-fr-y.json`
- `vowel_cp-test-en-fr-u.json`.

## Smoke results (2026-09-29, cloud container) — *not* approval evidence

`research/phonetics/realised_phone/results/rhotics_smoke-minds14es8-libri8.json`

- **Native Spanish:** 8 MINDS-14 es-ES utterances. This is phone-band audio (8 kHz upsampled),
  giving 27 [ɾ] and 11 [r] tokens.
- **English [ɹ]:** 8 LibriSpeech utterances, 33 [ɹ] tokens. This is English speech, so it
  stands in for "English r" but is not learner Spanish.
- Alignment used MFA 3.4.2 with `spanish_mfa` 3.2.0 and `english_mfa` / `english_us_mfa`.

Findings (non-coda tokens unless stated):
- **Combined verdicts: 22 of 22 confident verdicts were correct**, at 52% coverage. The rest are
  tentative or uncertain, never a wrong claim.
- **Recognizer (xlsr-53, constrained to candidates):**
  - It names English [ɹ] in 32 of 33 windows.
  - On native Spanish it never favours [ɹ]; the highest [ɹ] share was 0.03.
  - It gets tap vs trill right on 34 of 38 native tokens. Trills are often near-ties with tap,
    so they fall below the margin and don't vote.
- **Detector:**
  - Taps: good (12 right, 3 abstain).
  - Native trills: weak on this audio (2 of 8). Real trills in phone-band casual speech often
    show only one clear contact.
  - English [ɹ]: 23 of 33 before calibration.
  - F3 is unreliable on narrowband audio, so the detector refuses to assert English r there.
    It checks the energy above 4.1 kHz: LibriSpeech measures −9 to −14 dB, phone audio
    −37 to −48 dB, and the cut-off is −30 dB.
- **Real-data corrections to the design:**
  - F3 lowering is checked before occlusion counting, because stop closures next to [ɹ]
    (*grave*, *principles*) produce false dips.
  - Tap and trill are both accepted in codas.
  - A floor on the recognizer's raw posterior stops it deciding on near-silent windows.
- Calibration on the same smoke tokens gives balanced accuracy 0.88 at 82% coverage. This
  was **not** adopted: the set is too small and the audio is mismatched.

## What approval needs (per source; your call)

1. ~~Build the evaluation set from Common Phone es~~. Done from the cloud (above). Still needed:
   **learner recordings** (English-L1 Spanish, from `$MIO_AUDIO_DUMP_DIR` or new ones), and the
   native exemplar bank for the see/hear panel. The bank can also be built from the Common Phone
   extract:
   ```bash
   export MIO_MFA_CMD="conda run -n mfa mfa"      # see install notes in HANDOFF.md
   # Common Phone es from the HF Parquet shards (dev-00002 holds es; test-00001/2 hold es):
   venv/bin/python scripts/realised_phone/extract_cp_parquet.py dev-00002-of-00004.parquet --lang es --split dev --out ~/datasets/cp_hf --n 2000 --per-speaker 10
   venv/bin/python scripts/realised_phone/build_native_bank.py --tsv ~/datasets/cp_hf/es/dev/list.tsv --bank ~/datasets/miolingo_native_bank
   # re-run the evaluation after adding learner clips (lists: wav<TAB>text<TAB>speaker):
   venv/bin/python scripts/realised_phone/eval_rhotics.py --native-tsv ~/datasets/cp_hf/es/test/list.tsv --english-tsv <learner or English list> --cache ~/.cache/mio_align --post-cache ~/.cache/mio_post --label <name> --out research/phonetics/realised_phone/results/rhotics_<name>.json
   ```
2. **Golden manifest:** the Common Phone clips are done. Add **learner clips** (English-L1
   Spanish, including an [ʁ] attempt) in place of the `-TODO` entries, then run
   `scripts/realised_phone/run_golden.py --allow-candidates`.
3. **Review** the inventory, priors (check each citation), coaching drafts and the
   calibration output. Set `status: reviewed` or `status: approved` with `approved_by` and
   `approved_on` in the YAML files.
4. **Suggested acceptance bar** (a proposal; you decide): on CP-es + learner clips, confident
   verdicts ≥ 95% correct, with trill/tap/english_r coverage ≥ 50% each, and no English-r
   claims on native speech. Status on Common Phone: accuracy met (97.9%); coverage and the
   no-English-r rule not yet met (see above). Trill is the weak class.

## Experimental track: extended-inventory alignment (§1b source 1, §5)

This is not on the critical path. It is proposed here so the pass/fail criteria are agreed
**before** anything is run:

- **Idea:** adapt the MFA Spanish model on pooled Spanish and English Common Voice audio,
  using a merged IPA phone set so that [ɹ] exists as a unit. Then add variant pronunciations
  (e.g. `perro  p e ɹ o`) and let the aligner choose between them.
- **Comparison:** the same eval set as `eval_rhotics.py`. The aligner's variant choice is
  treated as a third evidence source.
- **Proposed pass criteria:**
  - variant-choice accuracy ≥ the detector's accuracy on trill/tap/english_r;
  - it must add confident coverage without lowering confident accuracy below the bar above;
  - boundary error vs the CP MAU tier must not be worse than stock `spanish_mfa`.
- **Proposed fail criteria:** any of the above missed; or GMM adaptation can't be trained
  reproducibly on the M4 in a day. This matches your doubt that GMM training will be good
  enough.

## Environment notes

- MFA is conda-forge only. `MIO_MFA_CMD` sets how it's invoked; if you give the env's `mfa`
  path directly, that env's `bin/` must also be on `PATH` (for openfst and kaldi).
  `MIO_MFA_MODELS` points at a models directory if you don't use `mfa model download`.
- The xlsr-53 espeak tokenizer needs `phonemizer` and a system `espeak-ng`
  (`requirements-wav2vec2.txt`).
- Alignment latency is about 11 s per `align_one` call on a cloud container, including cold
  start. Measure it on the M4; a long-lived aligner process is the obvious optimisation.
