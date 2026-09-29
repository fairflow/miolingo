# Realised-phone: status, test results, and what approval needs

Companion to [`HANDOFF.md`](../../HANDOFF.md) and the [spec](REALISED_PHONE_SPEC.md).
Beads: `miolingo-6vo` (.2 data model, .3 slice, .4 golden).

## What is built (en → es, /r/ slice)

| Handoff item | Where | State |
|---|---|---|
| Candidate inventory (§1a) | `src/realised_phone/data/pairs/en-es.yaml` | Draft for review. /r/ and /ɾ/ are active; VOT, spirants and vowels are data only. |
| Source 1, extended-inventory alignment | — | Experimental track, not started (proposal below). |
| Source 2, recognizer on the aligned window | `realised_phone/recognizer.py` | Works with xlsr-53. Candidates the model can't name are reported as `unsupported`. |
| Source 3, contrast detector | `realised_phone/detectors/rhotic.py` | Rhotic detector (occlusions + F3). Thresholds are in YAML, `calibrated: false`. |
| Combination (§1c) | `realised_phone/combine.py` | Sources agree → confident; they disagree → uncertain. |
| Forced alignment | `realised_phone/align.py` | Calls MFA 3.x via `align_one` subprocess. |
| Whisper gate | `realised_phone/gate.py` | Word recall of the target words, accent-insensitive. In practice it reuses the transcript already in the result. |
| Model registry + approval gate (§5) | `realised_phone/registry.py`, `data/model_registry.yaml` | **Nothing is approved.** Candidates only run with `allow_candidates`, and their output is marked not learner-visible. |
| See / hear (§2) | `realised_phone/view.py`, `src/ui/realised_phone_panel.py` | Debug-only panel: learner word/sound/slowed audio, native exemplar, spectrogram, occlusion and F3 plots. |
| Native exemplar bank | `scripts/realised_phone/build_native_bank.py` | Script ready. The bank still has to be built on the M4 from Common Phone es. |
| Coaching ladder (§3) | `realised_phone/coaching.py`, `data/coaching/en-es.yaml` | Draft content for r→tap, r→english_r, ɾ→english_r and ɾ→trill. Refused unless reviewed. |
| Learner model (§4) | `realised_phone/learner.py`, `data/priors/en-es.yaml` | Beta per (phone, context), escalation, improvement feedback. The priors are a draft and the citations are unverified. |
| Golden tests (step 4) | `tests/golden/realised_phone/manifest.yaml`, `scripts/realised_phone/run_golden.py` | Two real English-[ɹ] clips pass. The Common Phone and learner entries are TODO placeholders. |
| Calibration | `scripts/realised_phone/calibrate_rhotic.py` | Works; not yet run on a real calibration set. |
| Evaluation for approval | `scripts/realised_phone/eval_rhotics.py` | Produces the JSON the registry `results` point to. |

Tests: `venv/bin/python -m pytest tests/realised_phone` has 53 unit tests. The golden tests
run only when MFA and the clips are present.

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

1. **Build the Spanish exemplar bank and evaluation set on the M4** from Common Phone es
   (wideband, CC0), plus your own and other learners' English-L1 Spanish recordings
   (`$MIO_AUDIO_DUMP_DIR`):
   ```bash
   export MIO_MFA_CMD="conda run -n mfa mfa"      # see install notes in HANDOFF.md
   venv/bin/python scripts/realised_phone/build_native_bank.py --cp-root ~/datasets/common_phone/CP --lang es --n 2000 --bank ~/datasets/miolingo_native_bank
   venv/bin/python scripts/realised_phone/calibrate_rhotic.py --cp-root ~/datasets/common_phone/CP --n 300 --english-tsv <english r list> --out /tmp/rhotic.suggested.yaml
   venv/bin/python scripts/realised_phone/eval_rhotics.py --cp-root ~/datasets/common_phone/CP --n 300 --english-tsv <list> --label cp-es-300 --out research/phonetics/realised_phone/results/rhotics_cp-es-300.json
   ```
2. **Fill the golden manifest** with CP ids, and with learner clips covering a native trill, a
   tap, English [ɹ] and [ʁ]. Then run `scripts/realised_phone/run_golden.py --allow-candidates`.
3. **Review** the inventory, priors (check each citation), coaching drafts and the
   calibration output. Set `status: reviewed` or `status: approved` with `approved_by` and
   `approved_on` in the YAML files.
4. **Suggested acceptance bar** (a proposal; you decide): on CP-es + learner clips, confident
   verdicts ≥ 95% correct, with trill/tap/english_r coverage ≥ 50% each, and no English-r
   claims on native speech.

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
