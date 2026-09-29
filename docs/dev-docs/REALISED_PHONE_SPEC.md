# Realised-phone data model — spec (miolingo-6vo.2)

Step 2 of [`HANDOFF.md`](../../HANDOFF.md). Code: `src/realised_phone/`. Data: `src/realised_phone/data/`.
Tests: `tests/realised_phone/`. IPA is the only phone notation anywhere in this package.

## Flow for one attempt

```
wav + target text + (L1, L2)
  → gate        Whisper transcript must cover the target words (gate only, never the error signal)
  → align       MFA forced alignment of the KNOWN text → words + phones with times
  → for each aligned phone that the pair inventory lists as a target:
       candidates = inventory(L1, L2, phone)
       evidence  += detector(s) on the segment        (source 3, Parselmouth)
       evidence  += recognizer on the segment window   (source 2, CTC posteriors, constrained)
       verdict    = combine(evidence)                  (agree → confident, disagree → uncertain)
  → AttemptAnalysis {gate, alignment, verdicts, sources used + their registry status}
  → handed to existing scoring / UI / learner model (no parallel scorer)
```

Every step that uses a model goes through the **registry**. A source whose status is not
`approved` is refused unless the caller passes `allow_candidates=True` (debug/testing only).
The resulting analysis then carries `learner_visible = False`, and the UI must not show it to learners.

## Records

### Pair inventory — `data/pairs/<l1>-<l2>.yaml`

```yaml
pair: {l1: en, l2: es}
status: draft | reviewed          # reviewed_by / reviewed_on filled by Matthew
targets:
  r:                              # canonical target phone (IPA, as the aligner labels it)
    name: alveolar trill
    detector: rhotic              # contrast detector id, or null
    candidates:
      - {phone: r, class: trill, kind: canonical}
      - {phone: ɾ, class: tap,   kind: l1_transfer, note: ...}
      - {phone: ɹ, class: english_r, kind: l1_transfer}
      - {phone: ɻ, class: english_r, kind: l1_transfer}
      - {phone: ʁ, class: uvular,    kind: other}
```

- `class` groups phones that the evidence sources cannot reliably tell apart and that get the
  same feedback (e.g. [ɹ] and [ɻ] are both "English r"). Verdicts are decided at class level
  first. The phone within the class is reported only if some source separates the two.
- `kind`: `canonical` | `l1_transfer` | `dialect` | `other`.

### Evidence

| field | meaning |
|---|---|
| `source` | `alignment` \| `recognizer` \| `detector` |
| `source_id`, `version`, `status` | registry identity at the time of use |
| `scores` | `{phone: 0..1}` over the candidates this source can name (normalised) |
| `unsupported` | candidates this source cannot name (e.g. aligner has no [ɹ]) |
| `margin` | class-level top − second |
| `decisive` | `margin ≥` the source's calibrated margin |
| `measurements` | raw numbers (dip count, F3 ratio, window…) so a verdict can be traced |
| `window` | `(start, end)` seconds analysed |

### Verdict

| field | meaning |
|---|---|
| `target` | canonical phone, `word`, `word_index`, `phone_index`, `start`, `end`, `context` |
| `status` | `confident` \| `tentative` \| `uncertain` \| `no_evidence` |
| `realised_class`, `realised_phone` | decided class; phone if resolved within class, else `null` |
| `between` | for `uncertain`: the top classes, e.g. `["tap", "trill"]` |
| `correct` | `realised_class` ∈ accepted classes for the context (canonical, or tap+trill in codas); also true when `uncertain` only between accepted classes; else null unless confident/tentative |
| `confidence` | mean decisive-source probability for the decided class |
| `evidence` | list of Evidence |

### Combination rule

1. Only **decisive** evidence votes, and it votes for its top class.
2. Decisive votes disagree → `uncertain` (between the voted classes). We never pick one of them.
3. All votes agree and `n_votes ≥ min_agreeing_sources` (default 2) → `confident`.
4. All votes agree but there are fewer than required → `tentative`. It is shown in debug and
   only nudges the learner model.
5. No decisive vote → `uncertain` between the top two pooled classes, or `no_evidence` if
   there was no evidence at all.

Accuracy of what the learner sees outranks coverage. Only `confident` verdicts from
learner-visible analyses are shown to learners.

### Context — computed from the alignment

`word_initial`, `post_nls` (after /n l s/), `intervocalic`, `onset_cluster` (after a stop or /f/ in the
same word, e.g. *tres*), `coda`, `other`. This is used for keying learner state and choosing drills.

### Model registry — `data/model_registry.yaml`

```yaml
- id: mfa-spanish_mfa          # stable id
  kind: aligner | recognizer | detector
  version: "3.2.0"
  languages: [es]
  phones: [...]                 # optional inventory
  results: [research/phonetics/phone_poc/results/cp_eval_es.json]   # test evidence
  status: candidate | approved | retired
  approved_by: null
  approved_on: null
  params: {margin: 0.25}        # source-specific tunables
```

`Registry.require(id, allow_candidates)` raises `ModelNotApproved` for anything that is not
`approved`, unless candidates are explicitly allowed. **Nothing is seeded as `approved`**, and
only Matthew changes that field.

### Learner state — `realised_phone.learner`

- Key: `(l2, target_phone, context)`.
- A Beta(α, β) over P(correct production), seeded from `data/priors/<l1>-<l2>.yaml`.
  Priors are qualitative difficulty levels with citations, mapped to pseudo-counts by a
  documented rule, and need Matthew's review before use.
- Update weights: confident 1.0, tentative 0.25, uncertain or no_evidence 0.
- Attempt history per key: `(timestamp, correct, status)`. Improvement feedback compares the last
  N confident outcomes against the N before them. It is reported only when both windows are full
  and P(p_recent > p_before) ≥ 0.9 under the Beta posteriors. Evidence it doesn't support is never claimed.
- Escalation per `(target, realised_class)`. The rung goes up after N consecutive failures and
  down after 2 consecutive successes. N = 3 by default, and 2 when P(correct) < 0.3.
- Serialised as JSON (`to_dict`/`from_dict`). DB persistence is a follow-up. The proposal is a
  `phone_verdicts` table (attempt_id, target, context, realised_class, status, confidence,
  evidence_json, sources_json) next to `user_progress`, with the same fields in the web Dexie
  store.

### Coaching ladder — `data/coaching/<l1>-<l2>.yaml`

Keyed by `(target, realised_class)`. Rungs: `contrast`, `articulation`, `perception`,
`drills`, `stabilisation`. Each file and entry has `status: draft | reviewed`. The loader
refuses draft content unless `allow_draft=True` (debug). The contrast rung is generated from
PanPhon feature differences plus an authored manner note, because PanPhon does not encode
trill vs tap.

## Thresholds and calibration

Detector thresholds live in `data/calibration/<detector>.yaml`, with `calibrated: false` until
`scripts/realised_phone/calibrate_rhotic.py` has been run on labelled clips. That script writes
suggested values plus a provenance record, and a human commits them. The seeded defaults come
from phonetics literature and synthetic tests. They are not tuned on learner data.

## Golden tests

- `tests/realised_phone/` runs everywhere. It covers synthetic trill, tap and [ɹ] signals
  (source-filter synthesis), the combination rule (including disagreement → `uncertain`),
  registry refusal, the learner model and coaching gating.
- `tests/golden/realised_phone/manifest.yaml` lists real clips (Common Phone es natives, plus
  learner and English-[ɹ] recordings from the M4). `scripts/realised_phone/run_golden.py` runs
  the full pipeline on them, and the matching pytest module skips when the clips aren't present.
