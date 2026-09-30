# Handoff: Miolingo — realised-phone identification, corrective coaching, adaptive practice

> Source: Matthew's handover artifact (claude.ai), imported 2026-09-29. It supersedes both
> earlier versions of this handover. The step-1 inventory is in
> [`docs/dev-docs/REALISED_PHONE_INVENTORY.md`](docs/dev-docs/REALISED_PHONE_INVENTORY.md).
> **Implementation status, test results and the approval checklist:**
> [`docs/dev-docs/REALISED_PHONE_RESULTS.md`](docs/dev-docs/REALISED_PHONE_RESULTS.md);
> data model: [`docs/dev-docs/REALISED_PHONE_SPEC.md`](docs/dev-docs/REALISED_PHONE_SPEC.md).

## Goal

Extend Miolingo, whose primary purpose is **pronunciation training**, so that for each learner
utterance of a known target sentence it:

1. identifies, as accurately as possible, **the phone the learner actually produced** — including
   phones foreign to the target language (e.g. English [ɹ] for Spanish trilled [r]);
2. lets the learner **see and hear** the discrepancy against a native model;
3. escalates to **detailed articulatory coaching** if the error persists;
4. **adapts** to the learner: error profile and practice strategy, starting from research-based
   L1→L2 error models, and reports improvements as feedback whenever possible.

## Scope boundaries

- **Scoring is out of scope.** Miolingo already scores pronunciation. This work produces
  *realised-phone evidence* (what was said, where, with what confidence) and hands it to the
  existing scoring. Do not write a parallel scorer.
- **Build on the existing test infrastructure.** Miolingo contains a large body of test code and
  results for recognition models. Inventory and reuse it before writing anything new.
- **Model approval gate (hard rule).** No recognition, alignment or detector model is deployed
  or enabled for learners until Matthew has reviewed its test results and approved it.

## Settled

- Framing: **text-dependent verification**. Target text, target language (L2) and learner's
  source language (L1) are all known at recognition time.
- Word and phone boundaries come from **forced alignment of the known text** (Montreal Forced
  Aligner 3.x as the baseline aligner).
- **Universal/interlingual phone recognisers are rejected** as the front end (tested extensively
  on the European languages Miolingo handles: unreliable, not universal, oversized, poor word
  boundaries).
- **Large per-language recognition models are allowed** where test results justify them, used
  inside aligned segments, not as open recognisers.
- **ASR (Whisper) = gate only**: confirms the learner attempted the target words in the target
  language before analysis. Its free transcript is never the error signal.
- Tones/stress/intonation: separate Parselmouth F0/intensity/duration channel.
- Serving: local on Matthew's M4 Pro. For a handful of external users, controlled exposure from
  that machine (port forwarding, or preferably an authenticated tunnel such as Tailscale or
  Cloudflare Tunnel — Matthew's decision). Krystal shared hosting cannot run FastAPI/ASGI.

## 1. Foreign phones: identifying what was actually uttered

The core difficulty: a target-language model only knows target-language phones, so it cannot
name [ɹ] in Spanish. The design is a **pair-specific candidate inventory** and **three
independent evidence sources**, combined conservatively.

### 1a. Candidate inventory per (L1, L2) pair

For each target phone, candidates = canonical phone ∪ known L1-transfer substitutes ∪ dialect
variants. Example (L1 English → L2 Spanish, target /r/ trill): {[r], [ɾ], [ɹ], [ɻ], [ʁ]}.
Stored as data (YAML), with IPA as the single canonical notation everywhere.

### 1b. Evidence sources

1. **Extended-inventory alignment.** MFA only accepts dictionary variants using phones in its
   acoustic model. So train or adapt a model on pooled L2 + L1 speech (e.g. Spanish + English
   Common Voice) with a merged IPA phone set, so [ɹ] exists as a unit. Then variant dictionaries
   can include L1 phones and the aligner chooses among them. (Experimental track — see §5.)
2. **Approved per-language recognition models**, run only on the aligned segment. Compare the
   model's evidence for each candidate within that window (constrained, not open, recognition).
   Reuse the existing Miolingo model test code.
3. **Contrast-specific acoustic detectors** (Parselmouth), small and interpretable, for the most
   frequent error contrasts. Thresholds are calibrated on data, not hard-coded:
   - rhotics: trill = ≥2 brief occlusions (periodic intensity dips ~20–30 Hz); tap = one short
     occlusion; English [ɹ] = strongly lowered F3 and no occlusion;
   - aspiration: voice onset time for /p t k/ (English-style long-lag VOT in Spanish/French/Italian);
   - vowel quality: F1/F2 (plot on a vowel chart), F3 for rounding (e.g. French /y/);
   - length: geminate vs singleton duration ratios (Italian);
   - fricative place: spectral centre of gravity (e.g. /x/ vs [k] vs [h]).

### 1c. Combination rule

If sources agree → report the realised phone with high confidence. If they disagree → report
"uncertain between X and Y" rather than a wrong claim. Accuracy of what the learner is shown
outranks coverage. Every verdict carries its evidence, so errors can be traced in testing.

## 2. See and hear the discrepancy

For each flagged segment (cut by alignment boundaries):

- **See:** target IPA vs realised IPA; waveform and spectrogram side by side with a native
  exemplar; the relevant measurement visualised (F3 track for rhotics, VOT marker, learner's vowel
  on an F1/F2 chart against the native target region, pitch contour for tone/stress).
- **Hear:** learner segment ↔ native segment, whole word and isolated sound, with slowed playback.
- Native exemplars: Miolingo's existing native audio if present, otherwise a bank cut
  automatically from aligned Common Voice.

## 3. Corrective coaching (escalation ladder)

Keyed by (target phone, realised phone) pair. Content is data, authored and reviewed by Matthew
(Claude may draft; nothing ships unreviewed):

1. Short contrast statement: what differs (place, manner, voicing, rounding), via PanPhon features.
2. Articulatory instructions: tongue, lips, airflow, with a mid-sagittal diagram.
3. Perception training: minimal pairs and same/different discrimination of native audio.
4. Progressive production drills — for trill: tap in *pero* → fast repeated taps → "tr"/"dr"
   onsets (*tres*, *drama*) → trill in isolation → trill in words.
5. Stabilisation in phrases, then in free sentences.

Escalate after N unsuccessful attempts on the same pair; de-escalate once corrected. N is a
tunable parameter informed by the learner model.

## 4. Adaptive learner model

- **Priors from research:** initialise each learner's expected error profile from published L1→L2
  error patterns (contrastive/transfer literature; Flege's Speech Learning Model and Best's PAM-L2
  as a basis for predicting difficulty). Claude Code compiles these per pair **with citations**;
  Matthew reviews before use.
- **Per-learner state:** for each (target phone, context, error type) a probability of correct
  production, e.g. Beta–Bernoulli or Bayesian knowledge tracing, updated from each verdict (only
  high-confidence verdicts update strongly).
- **Practice strategy:** prioritise weak and high-impact contrasts; spaced repetition with
  interleaving; minimal pairs targeted at the learner's actual confusions; escalation per §3.
- **Improvement feedback:** show gains whenever evidence supports it ("trill produced in 6 of your
  last 10 attempts, up from 1 of 10 last week"; F3 now in native range). Never claim improvement
  the evidence doesn't support.
- Feeds and reads from Miolingo's existing scoring rather than replacing it.

## 5. Model governance and training experiments

- **Model registry:** each model/detector has an ID, version, languages, phone inventory, test
  results (from the existing harness) and status `candidate → approved → retired`. Approval is
  recorded by Matthew; the app refuses to load anything not `approved`.
- **Experimental track (not critical path):** train/adapt MFA acoustic models with extended
  phone sets to reduce dependence on third-party pretrained models. Matthew doubts GMM-based
  training will be good enough, so this is framed as a comparative experiment against existing
  results, with explicit pass/fail criteria agreed before running.

## Installation (macOS, Apple Silicon)

**Package-manager policy:** Matthew prefers **MacPorts** to Homebrew. For any system package, use
the MacPorts port if it offers the same version (`port info <name>` vs the upstream/brew version);
fall back to another source only if the port is missing or older, and say so. Python packages go
in the project venv via `uv pip`, not as `py3xx-*` ports. MFA itself is only distributed via
conda-forge, so it needs a conda installation whatever the system package manager.

```bash
sudo port selfupdate
port info ffmpeg uv miniforge          # confirm ports exist and versions are current
sudo port install ffmpeg uv
# conda: use the MacPorts miniforge port if present and current; otherwise the official
# Miniforge installer from the conda-forge GitHub releases (not Homebrew)
conda create -n mfa -c conda-forge montreal-forced-aligner   # MFA in its own env
conda run -n mfa mfa model download acoustic spanish_mfa
conda run -n mfa mfa model download dictionary spanish_mfa
# Miolingo env
uv pip install mlx-whisper praat-parselmouth panphon textgrid librosa soundfile numpy scipy
```

Check the mfa-models site for exact model names per language. Miolingo calls MFA by subprocess
(`mfa align_one … --output_format json`) at first; measure latency before optimising.

## Open questions (ask Matthew, don't assume)

Answered 2026-09-29:

- **First pair built: L1 English → L2 Spanish.** This is the first pair to *build*, not the learner
  population.
- **The source language is the learner's first language (L1)** (answered 2026-09-30). Learners can
  be assumed to have more mastery of it than of the target. **Every pair with source ≠ target is
  allowed.** Pairs without a specific file use the L1-agnostic `any-<l2>.yaml` inventory and
  coaching data.
- **Pairs needed now** (2026-09-30), added one at a time: English→Spanish (done), English→French,
  French→English, and English→Dutch **and** English→Flemish. Netherlands Dutch and Flemish are
  **distinct models**, keyed by dialect (`nl` vs `nl-be`) with their own inventories, coaching,
  priors and, where available, aligner/recognizer entries. They differ in the r (Netherlands:
  approximant coda r is native; Flanders: alveolar/uvular r) and the g (Netherlands [x]; Flanders
  softer [ɣ] or palatal), so the same learner sound can be correct in one and an error in the other.
- Open: whether the Clementapa Dutch recognizer (licence undeclared, "test-only") may be used
  for testing.
- **Native recordings:** some exist, for tests — probably French. They are not in the repo:
  the debug archive hook (`src/scoring/practice.py` ~L245, miolingo-0x9) writes takes to
  `$MIO_AUDIO_DUMP_DIR` on the M4 with a `log.jsonl` sidecar whose `voice` field gives the
  language. For native **Spanish** exemplars and golden clips, use Common Phone es
  (`~/datasets/common_phone/CP`, CC0), which the bake-off already reads.
- Existing harness/results: see the inventory.

Still open:

- Diagram/illustration source for articulatory content (licence).
- External serving choice (port forwarding vs authenticated tunnel) and user limits.
- Learner audio retention policy (default: discard after analysis).

## Next step — one vertical slice, one beads task per item

1. **Inventory** the existing recognition test code and results; write a short summary and map
   what can be reused. No new code before this.
2. **Data model** (spec first): phone inventory per pair, candidate sets, verdict-with-evidence,
   learner state, model registry with approval status. Then golden-test harness stubs.
3. **Slice: L1 English → L2 Spanish, /r/ trill** only: alignment → rhotic detector (source 3) +
   any existing approved model (source 2) → realised-phone verdict → see/hear view → coaching
   ladder content draft for Matthew's review.
4. Golden clips: native trill, tap, English [ɹ], [ʁ]; test that verdicts match and that
   disagreement produces "uncertain".
