# Neolingo lab: results (2026-10-14 10:23 BST)

Offline experiment bench (`lab/`) for Neolingo's analysis of a take: what counts as heard, costs and
curve, phone model, the "understood" rule.  Every variant is ONE change against the live pipeline (the baseline)
unless its name starts with "combo" or "rec".  All figures come from `var/lab/results/metrics.json`
(`python -m lab.run variants`); definitions and caveats are at the end.  The owner's notes on his takes are never
read by the lab; the tables below are aggregates.


## Recommendation

One configuration per language.  Common to all three: what counts as heard is the greedy decode, but a substitution or deletion at a target sound is KEPT only where Miolingo's sound check (target-conditioned) flags that sound as `check` or `off` (rule V2: the free reading and the check must agree); a pair the language's table makes free (tolerated, or accepted at full weight, e.g. German [r] for espeak's [ɾ]) is shown as the target sound; insertions are all kept; costs are the live raw panphon distances and the curve the live square root (B did not separate correct from wrong words); the phone models stay the live ones.

- **German**: `rec de`, xlsr-53.  ü/ö (y, yː, øː, œ, ɔø, the calibrated `unreliable` list) are judged by the free reading only when it hears a different full vowel of German (u, uː, i, iː, o, oː, e, ...) AND the likelihood ratio confirms it: log P(target with that vowel | audio) − log P(target | audio) ≥ 2; otherwise the sound is shown as not judged.  Understood: the live rule (the words of Whisper's free transcription equal the phrase's, or it has the same sounds, German respellings tried).
- **English**: `rec en`, xlsr-53; the check's unreliable sounds (a, eə, iə, ɒ, ɔɪ, əʊ, ʊə: mostly notation, espeak [a] against the recogniser's [æ]) are not judged.  Understood: the live rule (the words of Whisper's free transcription equal the phrase's, or it has the same sounds, German respellings tried).
- **French**: `rec fr`, Cnam (French has no unreliable sounds).  Understood: the live rule (the words of Whisper's free transcription equal the phrase's, or it has the same sounds, German respellings tried).

What it gives and what it gives up (baseline → recommended):

| | reference diff | natives diff | positives diff | near misses detected (costing) | on judged sounds | targets on the unreliable list | roles reversed detected | learner harsh: fewer diff | learner fair: changed |
|---|---|---|---|---|---|---|---|---|---|
| German | 1.25 → 0.62 | 5.21 → 3.25 | 1.28 → 0.80 | 80% → 89% | 95% → 90% | 0% → 83% | 97% → 91% | 8 of 18 | 10 of 19 |
| English | 2.40 → 0.35 | 9.02 → 1.60 | 1.21 → 0.41 | 75% → 68% | 90% → 81% | 0% → 0% | n/a | 2 of 2 | 4 of 5 |
| French | 0.42 → 0.33 | 1.52 → 1.31 | 0.62 → 0.58 | 96% → 96% | 96% → 96% | – | 99% → 99% | 0 of 3 | 1 of 9 |

Why these, from the tables below:

1. **Free differences are removed first** (`combo clean` = A-zero=equal + A5-unjudged, or for German the ü/ö rule):
   the commonest false differences on correct speech are pairs that already cost nothing (English [a] heard [æ],
   [ɒ] heard [ʌ] or [ɔ]; German [ɾ] heard [r], [yː] heard [uː]).  Showing them told the learner something the
   score had already ignored.  Removing them costs no near-miss detection that counts.
2. **V2 for what counts as heard.**  Of the verified rules, V1 (only `off`) removes most false differences but loses
   the most detection (German roles-reversed detection falls to about half); V3 and V4 sit on the same curve as V2
   on near misses, but V2 keeps far more of the German roles-reversed errors than V4 at the same false-difference
   level, and it needs nothing new: the flags the page already shows.  English V2 and V4 at τ = 2 are not separated:
   the simpler (V2) is chosen.
3. **German ü/ö**: "unjudged" detects none of the ü→u/i, ö→o/e near misses; the plain "phoneme" rule detects most
   but also penalises correct ü/ö (about one native token in five, and about half in the synthetic voices); with the
   likelihood-ratio confirmation (τ = 2, chosen on the distribution of the ratio, see caveats) the false
   differences on reference phrases and natives are practically those of "unjudged" while most ü/ö near misses are
   still caught.
   English is different: its unreliable sounds are notation mismatches, and the phoneme rule only adds false
   differences there.
4. **Insertions**: verifying extra heard sounds by the ratio (ins lr, τ = 2) removes a further 10 to 20% of the
   remaining false differences for 1 to 3 points of detection; not separated, so the simpler (keep all) stays.
   Dropping edge insertions loses 8 to 13 points of detection (single words end in real insertions) for no gain on
   phrases.  V2 applied to substitutions only (every deletion kept) gains up to 4 points of detection (German; 2 in
   English, none in French) for 5 to 10% more false differences in German and 80 to 90% more in English: not chosen.
5. **Costs and curve (B)**: they change the score, not what is shown.  The chance that a correct word scores above
   a near miss (AUC) moves by under 0.02 between raw/stretched and square-root/linear: not separated, so the live
   ones stay.  Length normalisation (linear) also hides a single changed sound in a long native sentence (the
   roles-reversed take scores lower than the same audio's correct reading far less often).
6. **Phone model (C)**: lv-60 is clearly worse for German and French (natives' weighted error 2 to 4 times
   xlsr-53's / Cnam's, as the priors said).  For English it is NOT separated on native speech (its free reading
   is slightly closer to espeak) but is worse on the synthetic reference phrases and near misses; the check was
   calibrated with xlsr-53, so the V2 comparison favours xlsr-53.  Keep xlsr-53 (the live model; simpler).
7. **The converse switch** (take the check's alternative where the free reading agrees) adds false differences and
   detects nothing more: rejected.  **E** (100 × mean p_ok, for comparison only) almost never gives 100 (0 to 8% of
   reference phrases); as a detector of near misses (the check's own flag at the place) it is worse than the free
   reading in German and English and slightly better in French (98% against 96%).
8. **French alternative**: V4 at τ = 2 (or V1) halves French false differences again (reference 0.33 → 0.21,
   natives 1.31 → 0.6 a sentence) for 5 points of near-miss detection; V2 is kept for French because it loses
   almost nothing and is the same rule as for the other languages.

9. **Understood (D)**: the live rule stays.  Figures as correct words understood / reference phrases understood / near misses wrongly understood (INFLATION):

| | live rule | free OR teacher-forced, m = 0 | m = 1 | phrase as prompt |
|---|---|---|---|---|
| German | 68% / 95% / 1.2% | 71% / 97% / 2.3% | 77% / 97% / 3.1% | 93% / 100% / 25.0% |
| English | 76% / 98% / 1.6% | 79% / 98% / 2.1% | 83% / 98% / 3.0% | 97% / 99% / 18.7% |
| French | 54% / 92% / 2.0% | 60% / 94% / 3.3% | 64% / 97% / 4.1% | 80% / 100% / 13.5% |

   The prompted transcription inflates heavily (as Miolingo's Swift port found for the hint).  The teacher-forced rule (understood also when Whisper finds the phrase at least as probable as its own transcription, within m nats) recovers some correct words but every margin raises the inflation; the smallest (m = 0) is the only alternative worth considering (on the learner takes it would turn 2 of the 4 harsh takes now "not understood" into understood, and change 1 fair take(s)).  Since inflation is the figure that matters and the gain is small, the simpler live rule is kept.


## Validation of the lab against the live code

- `var/lab/validate/replay.md`: 81 takes replayed (env.audible, env.hear, env.sounds answered live; the compiled engine `neolingo neohost` computed the result).  Equal in target, heard text, heard sounds, flags, score, understood and columns: **81**.  Different: **0** (of which not checked by the engine: 0).
- `var/lab/validate/stored.md` (the lab's baseline against the STORED archive lines, by the engine version that wrote them; older engines and reconstructed lines differ by design): engine 5629789 (host 3816056, page 0.33): 3 takes, 0 different; engine 5629789 (host abb6077, page 0.33): 18 takes, 9 different (9 of them equal with the target stored then); engine 83227a8 (host c21d6d9, page 0.29): 9 takes, 0 different; engine 83227a8 (host c7d1cb9, page 0.29): 2 takes, 0 different; engine 83227a8 (host fa79171, page 0.29): 3 takes, 0 different; engine c2ba086 (host 1ae73ec, page 0.28): 7 takes, 2 different; engine c2ba086 (host 42ee1f9, page 0.28): 4 takes, 0 different; engine e9ceb0f (host 699c767, page 0.30): 2 takes, 0 different; engine f752c90 (host 8ca91a0, page 0.34): 7 takes, 0 different; reconstructed: 26 takes, 14 different
- `var/lab/validate/engine-A-V4_tau2-archive-reference-nearmiss-positive-cp-cpflip.md`: Variant: **A-V4 tau=2** (config {"heard": "V4", "tau": 2.0}).  Sets: archive, reference, nearmiss, positive, cp, cpflip (every 5th item).  Compared: score, columns with their marks, flags kept, target; understood where the Whisper text is cached (not cached: 450 items, given the text "").  Equal: **1161**.  Different: **0**.
- `var/lab/validate/engine-B-linear-archive-reference-nearmiss-positive-cp-cpflip.md`: Variant: **B-linear** (config {"curve": "linear"}).  Sets: archive, reference, nearmiss, positive, cp, cpflip (every 5th item).  Compared: score, columns with their marks, flags kept, target; understood where the Whisper text is cached (not cached: 470 items, given the text "").  Equal: **1161**.  Different: **0**.
- `var/lab/validate/engine-B-stretched-archive-reference-nearmiss-positive-cp-cpflip.md`: Variant: **B-stretched** (config {"cost": "stretched"}).  Sets: archive, reference, nearmiss, positive, cp, cpflip (every 5th item).  Compared: score, columns with their marks, flags kept, target; understood where the Whisper text is cached (not cached: 490 items, given the text "").  Equal: **1161**.  Different: **0**.
- `var/lab/validate/engine-baseline-archive-reference-nearmiss-positive-cp-cpflip.md`: Variant: **baseline** (config {}).  Sets: archive, reference, nearmiss, positive, cp, cpflip (every 1th item).  Compared: score, columns with their marks, flags kept, target; understood where the Whisper text is cached (not cached: 3684 items, given the text "").  Equal: **5802**.  Different: **0**.
- `var/lab/validate/engine-baseline-archive.md`: Variant: **baseline** (config {}).  Sets: archive (every 1th item).  Compared: score, columns with their marks, flags kept, target; understood where the Whisper text is cached (not cached: 0 items, given the text "").  Equal: **81**.  Different: **0**.
- `var/lab/validate/engine-combo_clean+V2-archive-reference-nearmiss-positive-cp-cpflip.md`: Variant: **combo clean+V2** (config {"zero_equal": true, "unchecked": "unjudged", "heard": "V2"}).  Sets: archive, reference, nearmiss, positive, cp, cpflip (every 1th item).  Compared: score, columns with their marks, flags kept, target; understood where the Whisper text is cached (not cached: 3260 items, given the text "").  Equal: **5802**.  Different: **0**.
- `var/lab/validate/engine-combo_phoneme+lr2+zero+V2-archive-reference-nearmiss-positive-cp-cpflip.md`: Variant: **combo phoneme+lr2+zero+V2** (config {"zero_equal": true, "unchecked": "phoneme_lr", "tau_unrel": 2.0, "heard": "V2"}).  Sets: archive, reference, nearmiss, positive, cp, cpflip (every 1th item).  Compared: score, columns with their marks, flags kept, target; understood where the Whisper text is cached (not cached: 2812 items, given the text "").  Equal: **5802**.  Different: **0**.
- `var/lab/validate/engine-rec_de-archive-reference-nearmiss-positive-cp-cpflip.md`: Variant: **rec de** (config {"zero_equal": true, "unchecked": "phoneme_lr", "tau_unrel": 2.0, "heard": "V2", "understood": "free"}).  Sets: archive, reference, nearmiss, positive, cp, cpflip (every 1th item).  Compared: score, columns with their marks, flags kept, target; understood where the Whisper text is cached (not cached: 1391 items, given the text "").  Equal: **5802**.  Different: **0**.


## Headline


**German** (recommended: `rec de`)

| variant | reference =100 (mean of 3 voices) | reference diff | natives diff | positives diff | near misses detected (costing) | judged sounds | targets on the unreliable list | false elsewhere | roles reversed detected | harsh: fewer diff | fair: changed |
|---|---|---|---|---|---|---|---|---|---|---|---|
| baseline | 56% | 1.25 | 5.21 | 1.28 | 80% | 95% | 0% of 114 | 1.03 | 97% | 0 of 18 | 0 of 19 |
| A-V1 | 81% | 0.65 | 2.06 | 0.52 | 64% | 75% | 0% of 114 | 0.39 | 52% | 10 of 18 | 15 of 19 |
| A-V2 | 67% | 0.96 | 3.80 | 0.97 | 76% | 90% | 0% of 114 | 0.78 | 92% | 6 of 18 | 10 of 19 |
| A-V3 | 67% | 0.94 | 3.51 | 0.80 | 73% | 86% | 0% of 114 | 0.62 | 85% | 7 of 18 | 11 of 19 |
| A-V4 tau=0 | 59% | 1.15 | 4.43 | 1.07 | 78% | 92% | 0% of 114 | 0.83 | 86% | 2 of 18 | 3 of 19 |
| A-V4 tau=2 | 72% | 0.53 | 2.54 | 0.67 | 73% | 86% | 0% of 114 | 0.56 | 62% | 10 of 18 | 11 of 19 |
| A-ins lr tau=2 | 57% | 1.19 | 4.84 | 1.17 | 77% | 91% | 0% of 114 | 0.91 | 97% | 4 of 18 | 2 of 19 |
| A-ins edges | 56% | 1.25 | 5.20 | 1.21 | 69% | 82% | 0% of 114 | 0.95 | 97% | 1 of 18 | 0 of 19 |
| A-converse | 53% | 1.27 | 5.57 | 1.29 | 80% | 95% | 0% of 114 | 1.04 | 97% | 0 of 18 | 2 of 19 |
| A-zero=equal | 56% | 1.21 | 4.83 | 1.22 | 80% | 95% | 0% of 114 | 0.99 | 96% | 2 of 18 | 5 of 19 |
| A5-unjudged | 56% | 0.92 | 4.71 | 1.06 | 80% | 95% | 0% of 114 | 0.95 | 97% | 5 of 18 | 4 of 19 |
| A5-phoneme | 47% | 1.11 | 5.02 | 1.20 | 94% | 95% | 89% of 114 | 1.00 | 97% | 1 of 18 | 4 of 19 |
| A5-phoneme+lr tau=2 | 56% | 0.92 | 4.75 | 1.12 | 93% | 95% | 83% of 114 | 0.96 | 97% | 3 of 18 | 4 of 19 |
| B-stretched | 47% | 1.25 | 5.07 | 1.27 | 81% | 96% | 0% of 114 | 1.00 | 97% | 0 of 18 | 12 of 19 |
| B-linear | 69% | 1.25 | 5.21 | 1.28 | 80% | 95% | 0% of 114 | 1.03 | 97% | 0 of 18 | 12 of 19 |
| B-deletions | 58% | 1.28 | 5.54 | 1.36 | 80% | 95% | 0% of 114 | 1.15 | 97% | 0 of 18 | 2 of 19 |
| C-lv60 | 10% | 3.27 | 12.25 | 1.95 | 78% | 92% | 0% of 113 | 1.62 | 96% | 0 of 18 | 17 of 19 |
| C-xlsr-fr | 56% | 1.25 | 5.21 | 1.28 | 80% | 95% | 0% of 114 | 1.03 | 97% | 0 of 18 | 0 of 19 |
| E-check score | 0% | – | – | – | 76% | 93% | 0% of 114 | – | 95% | – | – |
| combo clean | 56% | 0.88 | 4.33 | 1.00 | 80% | 95% | 0% of 114 | 0.91 | 96% | 6 of 18 | 6 of 19 |
| combo clean+V2 | 67% | 0.62 | 3.21 | 0.74 | 76% | 90% | 0% of 114 | 0.70 | 91% | 9 of 18 | 10 of 19 |
| combo clean+V4 tau=2 | 72% | 0.52 | 2.41 | 0.56 | 73% | 86% | 0% of 114 | 0.52 | 61% | 11 of 18 | 13 of 19 |
| combo phoneme+lr2+zero+V2 | 67% | 0.62 | 3.25 | 0.80 | 89% | 90% | 83% of 114 | 0.71 | 91% | 8 of 18 | 10 of 19 |
| rec de | 67% | 0.62 | 3.25 | 0.80 | 89% | 90% | 83% of 114 | 0.71 | 91% | 8 of 18 | 10 of 19 |

**English** (recommended: `rec en`)

| variant | reference =100 (mean of 3 voices) | reference diff | natives diff | positives diff | near misses detected (costing) | judged sounds | targets on the unreliable list | false elsewhere | roles reversed detected | harsh: fewer diff | fair: changed |
|---|---|---|---|---|---|---|---|---|---|---|---|
| baseline | 38% | 2.40 | 9.02 | 1.21 | 75% | 90% | 0% of 124 | 0.91 | n/a | 0 of 2 | 0 of 5 |
| A-V1 | 64% | 1.33 | 4.40 | 0.61 | 63% | 75% | 0% of 124 | 0.50 | n/a | 1 of 2 | 3 of 5 |
| A-V2 | 60% | 1.47 | 5.37 | 0.80 | 68% | 82% | 0% of 124 | 0.65 | n/a | 1 of 2 | 3 of 5 |
| A-V3 | 62% | 1.42 | 5.10 | 0.73 | 66% | 79% | 0% of 124 | 0.59 | n/a | 1 of 2 | 3 of 5 |
| A-V4 tau=0 | 53% | 1.74 | 6.58 | 0.96 | 72% | 86% | 0% of 124 | 0.70 | n/a | 1 of 2 | 0 of 5 |
| A-V4 tau=2 | 65% | 1.10 | 4.33 | 0.61 | 68% | 82% | 0% of 124 | 0.47 | n/a | 1 of 2 | 4 of 5 |
| A-ins lr tau=2 | 38% | 2.34 | 8.88 | 1.11 | 72% | 86% | 0% of 124 | 0.82 | n/a | 0 of 2 | 0 of 5 |
| A-ins edges | 38% | 2.38 | 9.01 | 1.19 | 66% | 80% | 0% of 124 | 0.88 | n/a | 0 of 2 | 0 of 5 |
| A-converse | 38% | 2.40 | 9.07 | 1.22 | 75% | 90% | 0% of 124 | 0.92 | n/a | 0 of 2 | 0 of 5 |
| A-zero=equal | 38% | 2.14 | 7.98 | 1.09 | 75% | 90% | 0% of 124 | 0.81 | n/a | 0 of 2 | 2 of 5 |
| A5-unjudged | 53% | 1.38 | 5.63 | 0.85 | 74% | 89% | 0% of 124 | 0.64 | n/a | 2 of 2 | 2 of 5 |
| A5-phoneme | 25% | 2.07 | 7.80 | 1.07 | 84% | 90% | 56% of 124 | 0.80 | n/a | 1 of 2 | 2 of 5 |
| A5-phoneme+lr tau=2 | 32% | 1.87 | 7.35 | 1.02 | 83% | 90% | 48% of 124 | 0.77 | n/a | 1 of 2 | 2 of 5 |
| B-stretched | 35% | 2.35 | 8.71 | 1.21 | 75% | 90% | 0% of 124 | 0.89 | n/a | 0 of 2 | 4 of 5 |
| B-linear | 46% | 2.40 | 9.02 | 1.21 | 75% | 90% | 0% of 124 | 0.91 | n/a | 0 of 2 | 4 of 5 |
| B-deletions | 38% | 2.49 | 9.17 | 1.21 | 75% | 90% | 0% of 124 | 0.92 | n/a | 0 of 2 | 1 of 5 |
| C-lv60 | 30% | 2.47 | 9.01 | 1.45 | 73% | 88% | 0% of 124 | 1.09 | n/a | 1 of 2 | 4 of 5 |
| C-xlsr-fr | 38% | 2.40 | 9.02 | 1.21 | 75% | 90% | 0% of 124 | 0.91 | n/a | 0 of 2 | 0 of 5 |
| E-check score | 0% | – | – | – | 70% | 87% | 1% of 124 | – | n/a | – | – |
| combo clean | 53% | 1.23 | 4.77 | 0.76 | 74% | 89% | 0% of 124 | 0.57 | n/a | 2 of 2 | 4 of 5 |
| combo clean+V2 | 81% | 0.35 | 1.60 | 0.41 | 68% | 81% | 0% of 124 | 0.35 | n/a | 2 of 2 | 4 of 5 |
| combo clean+V4 tau=2 | 79% | 0.38 | 1.50 | 0.36 | 68% | 82% | 0% of 124 | 0.29 | n/a | 2 of 2 | 4 of 5 |
| combo phoneme+lr2+zero+V2 | 53% | 0.83 | 3.31 | 0.57 | 76% | 82% | 47% of 124 | 0.48 | n/a | 2 of 2 | 4 of 5 |
| rec en | 81% | 0.35 | 1.60 | 0.41 | 68% | 81% | 0% of 124 | 0.35 | n/a | 2 of 2 | 4 of 5 |

**French** (recommended: `rec fr`)

| variant | reference =100 (mean of 3 voices) | reference diff | natives diff | positives diff | near misses detected (costing) | judged sounds | targets on the unreliable list | false elsewhere | roles reversed detected | harsh: fewer diff | fair: changed |
|---|---|---|---|---|---|---|---|---|---|---|---|
| baseline | 77% | 0.42 | 1.52 | 0.62 | 96% | 96% | – | 0.40 | 99% | 0 of 3 | 0 of 9 |
| A-V1 | 83% | 0.25 | 0.70 | 0.35 | 91% | 91% | – | 0.23 | 99% | 1 of 3 | 1 of 9 |
| A-V2 | 79% | 0.35 | 1.37 | 0.59 | 96% | 96% | – | 0.38 | 99% | 0 of 3 | 1 of 9 |
| A-V3 | 80% | 0.32 | 1.16 | 0.54 | 94% | 94% | – | 0.34 | 99% | 0 of 3 | 1 of 9 |
| A-V4 tau=0 | 78% | 0.33 | 1.21 | 0.57 | 95% | 95% | – | 0.36 | 98% | 0 of 3 | 1 of 9 |
| A-V4 tau=2 | 84% | 0.21 | 0.63 | 0.34 | 91% | 91% | – | 0.22 | 98% | 2 of 3 | 1 of 9 |
| A-ins lr tau=2 | 79% | 0.38 | 1.44 | 0.60 | 95% | 95% | – | 0.37 | 99% | 0 of 3 | 0 of 9 |
| A-ins edges | 78% | 0.40 | 1.49 | 0.60 | 82% | 82% | – | 0.37 | 99% | 0 of 3 | 0 of 9 |
| A-converse | 76% | 0.48 | 1.64 | 0.63 | 95% | 95% | – | 0.45 | 99% | 0 of 3 | 0 of 9 |
| A-zero=equal | 77% | 0.40 | 1.47 | 0.61 | 96% | 96% | – | 0.39 | 99% | 0 of 3 | 0 of 9 |
| A5-unjudged | 78% | 0.42 | 1.50 | 0.62 | 96% | 96% | – | 0.40 | 99% | 0 of 3 | 0 of 9 |
| A5-phoneme | 78% | 0.42 | 1.50 | 0.62 | 96% | 96% | – | 0.40 | 99% | 0 of 3 | 0 of 9 |
| A5-phoneme+lr tau=2 | 78% | 0.42 | 1.50 | 0.62 | 96% | 96% | – | 0.40 | 99% | 0 of 3 | 0 of 9 |
| B-stretched | 76% | 0.41 | 1.49 | 0.62 | 96% | 96% | – | 0.40 | 99% | 0 of 3 | 1 of 9 |
| B-linear | 79% | 0.42 | 1.52 | 0.62 | 96% | 96% | – | 0.40 | 99% | 0 of 3 | 1 of 9 |
| B-deletions | 78% | 0.51 | 1.71 | 0.63 | 96% | 96% | – | 0.41 | 99% | 0 of 3 | 0 of 9 |
| C-lv60 | 19% | 2.28 | 6.88 | 1.76 | 91% | 91% | – | 1.27 | 99% | 0 of 3 | 8 of 9 |
| C-xlsr-fr | 19% | 2.25 | 5.42 | 1.55 | 95% | 95% | – | 1.09 | 99% | 0 of 3 | 7 of 9 |
| E-check score | 3% | – | – | – | 98% | 98% | – | – | 100% | – | – |
| combo clean | 78% | 0.40 | 1.46 | 0.61 | 96% | 96% | – | 0.39 | 99% | 0 of 3 | 0 of 9 |
| combo clean+V2 | 80% | 0.33 | 1.31 | 0.58 | 96% | 96% | – | 0.37 | 99% | 0 of 3 | 1 of 9 |
| combo clean+V4 tau=2 | 84% | 0.21 | 0.60 | 0.33 | 91% | 91% | – | 0.22 | 98% | 2 of 3 | 1 of 9 |
| combo phoneme+lr2+zero+V2 | 80% | 0.33 | 1.31 | 0.58 | 96% | 96% | – | 0.37 | 99% | 0 of 3 | 1 of 9 |
| rec fr | 80% | 0.33 | 1.31 | 0.58 | 96% | 96% | – | 0.37 | 99% | 0 of 3 | 1 of 9 |

`diff` = mean number of sounds shown different (near, off, missing, added) per phrase / utterance / word.  Near misses "detected (costing)": a difference at the place of the edit that costs something (a difference shown at no cost is not counted here; the full tables give both).  E (the check alone) counts a near miss as detected where the check flags the sound.  Learner takes: of the harsh takes, how many show FEWER differences than the baseline; of the fair takes, how many change at all.


## German


### Reference phrases (48 a voice): share of phrases at 100, at 95 or more, under 90; mean sounds shown different

| variant | Google =100 | Google ≥95 | Google <90 | Google diff | compact Mac =100 | compact Mac ≥95 | compact Mac <90 | compact Mac diff | Premium Mac =100 | Premium Mac ≥95 | Premium Mac <90 | Premium Mac diff |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| baseline | 60% | 79% | 17% | 1.15 | 56% | 69% | 27% | 1.33 | 50% | 77% | 21% | 1.27 |
| A-V1 | 83% | 90% | 8% | 0.60 | 75% | 83% | 17% | 0.75 | 83% | 92% | 6% | 0.58 |
| A-V2 | 71% | 85% | 12% | 0.83 | 67% | 77% | 21% | 1.04 | 62% | 81% | 17% | 1.00 |
| A-V3 | 73% | 85% | 12% | 0.79 | 67% | 77% | 21% | 1.04 | 62% | 81% | 17% | 0.98 |
| A-ins edges | 60% | 79% | 17% | 1.15 | 56% | 69% | 27% | 1.33 | 50% | 77% | 21% | 1.27 |
| A-ins lr tau=0 | 62% | 81% | 15% | 1.12 | 56% | 71% | 25% | 1.29 | 50% | 77% | 21% | 1.27 |
| A-ins lr tau=2 | 62% | 81% | 15% | 1.12 | 58% | 79% | 17% | 1.17 | 50% | 77% | 21% | 1.27 |
| A5-unjudged | 60% | 81% | 17% | 0.81 | 56% | 71% | 27% | 1.00 | 50% | 79% | 21% | 0.94 |
| A5-phoneme | 52% | 79% | 17% | 1.00 | 48% | 69% | 27% | 1.21 | 42% | 77% | 21% | 1.12 |
| A5-phoneme+lr tau=0 | 52% | 81% | 17% | 0.96 | 48% | 71% | 27% | 1.17 | 42% | 79% | 21% | 1.08 |
| A5-phoneme+lr tau=2 | 60% | 81% | 17% | 0.81 | 56% | 71% | 27% | 1.00 | 50% | 79% | 21% | 0.94 |
| A5-phoneme+lr tau=4 | 60% | 81% | 17% | 0.81 | 56% | 71% | 27% | 1.00 | 50% | 79% | 21% | 0.94 |
| A-converse | 58% | 77% | 19% | 1.17 | 54% | 67% | 29% | 1.35 | 48% | 75% | 23% | 1.29 |
| A-zero=equal | 60% | 79% | 17% | 1.10 | 56% | 69% | 27% | 1.27 | 50% | 77% | 21% | 1.25 |
| B-stretched | 50% | 65% | 27% | 1.15 | 48% | 60% | 33% | 1.33 | 42% | 54% | 38% | 1.27 |
| B-linear | 75% | 88% | 8% | 1.15 | 67% | 83% | 6% | 1.33 | 67% | 85% | 10% | 1.27 |
| B-stretched+linear | 54% | 75% | 15% | 1.15 | 50% | 71% | 12% | 1.33 | 46% | 71% | 19% | 1.27 |
| B-deletions | 62% | 81% | 12% | 1.17 | 58% | 71% | 25% | 1.40 | 52% | 81% | 17% | 1.29 |
| C-lv60 | 12% | 38% | 52% | 2.92 | 8% | 31% | 62% | 3.15 | 8% | 38% | 60% | 3.75 |
| C-xlsr-fr | 60% | 79% | 17% | 1.15 | 56% | 69% | 27% | 1.33 | 50% | 77% | 21% | 1.27 |
| rec de | 73% | 88% | 12% | 0.50 | 67% | 79% | 21% | 0.71 | 62% | 83% | 17% | 0.67 |
| rec en | 73% | 88% | 12% | 0.50 | 67% | 79% | 21% | 0.71 | 62% | 83% | 17% | 0.67 |
| rec fr | 73% | 88% | 12% | 0.50 | 67% | 79% | 21% | 0.71 | 62% | 83% | 17% | 0.67 |
| E-check score | 0% | 48% | 33% | – | 0% | 42% | 35% | – | 0% | 29% | 40% | – |
| A-V4 tau=0 | 62% | 85% | 15% | 1.04 | 58% | 73% | 25% | 1.25 | 56% | 83% | 17% | 1.17 |
| A-V4 tau=2 | 71% | 88% | 12% | 0.48 | 69% | 79% | 21% | 0.65 | 75% | 85% | 15% | 0.48 |
| combo clean | 60% | 81% | 17% | 0.77 | 56% | 71% | 27% | 0.94 | 50% | 79% | 21% | 0.92 |
| combo clean+V1 | 85% | 92% | 8% | 0.27 | 77% | 83% | 17% | 0.42 | 85% | 92% | 6% | 0.25 |
| combo clean+V2 | 73% | 88% | 12% | 0.50 | 67% | 79% | 21% | 0.71 | 62% | 83% | 17% | 0.67 |
| combo clean+V3 | 75% | 88% | 12% | 0.46 | 67% | 79% | 21% | 0.71 | 62% | 83% | 17% | 0.65 |
| combo clean+V4 tau=1 | 67% | 85% | 15% | 0.60 | 65% | 77% | 23% | 0.77 | 71% | 85% | 15% | 0.58 |
| combo clean+V4 tau=2 | 71% | 88% | 12% | 0.46 | 69% | 79% | 21% | 0.62 | 75% | 85% | 15% | 0.48 |
| combo clean+V2+ins tau=2 | 75% | 90% | 10% | 0.48 | 69% | 90% | 10% | 0.54 | 62% | 83% | 17% | 0.67 |
| combo clean+V2 keep deletions | 69% | 83% | 17% | 0.54 | 60% | 73% | 27% | 0.77 | 58% | 79% | 21% | 0.73 |
| combo phoneme+lr2+zero+V2 | 73% | 88% | 12% | 0.50 | 67% | 79% | 21% | 0.71 | 62% | 83% | 17% | 0.67 |
| combo phoneme+lr2+zero+V2 keep deletions | 69% | 83% | 17% | 0.54 | 60% | 73% | 27% | 0.77 | 58% | 79% | 21% | 0.73 |
| combo clean+V2 lv60 | 27% | 48% | 42% | 1.90 | 15% | 38% | 54% | 2.10 | 17% | 44% | 50% | 2.52 |
| combo phoneme+lr2+zero+V2 lv60 | 27% | 48% | 42% | 1.92 | 12% | 38% | 54% | 2.17 | 17% | 44% | 50% | 2.56 |
| rec de | 73% | 88% | 12% | 0.50 | 67% | 79% | 21% | 0.71 | 62% | 83% | 17% | 0.67 |
| rec en | 73% | 88% | 12% | 0.50 | 67% | 79% | 21% | 0.71 | 62% | 83% | 17% | 0.67 |
| rec fr | 73% | 88% | 12% | 0.50 | 67% | 79% | 21% | 0.71 | 62% | 83% | 17% | 0.67 |


### Near misses (voice says B, target A; one edit) and their positives (voice says A)

| variant | n | detected at the place | below 100 | mean score | false elsewhere | detected, sound judged | detected, sound unjudged (n) | positives below 100 | positives mean | positives diff |
|---|---|---|---|---|---|---|---|---|---|---|
| baseline | 745 | 96% | 95% | 75.7 | 1.03 | 95% | 100% (114) | 59% | 86.4 | 1.28 |
| A-V1 | 745 | 79% | 73% | 83.6 | 0.39 | 75% | 100% (114) | 23% | 93.4 | 0.52 |
| A-V2 | 745 | 92% | 90% | 78.4 | 0.78 | 90% | 100% (114) | 48% | 88.6 | 0.97 |
| A-V3 | 745 | 88% | 86% | 79.3 | 0.62 | 86% | 100% (114) | 43% | 89.3 | 0.80 |
| A-ins edges | 745 | 85% | 86% | 80.5 | 0.95 | 82% | 100% (114) | 59% | 87.9 | 1.21 |
| A-ins lr tau=0 | 745 | 96% | 94% | 77.0 | 0.98 | 95% | 100% (114) | 59% | 87.4 | 1.24 |
| A-ins lr tau=2 | 745 | 93% | 91% | 79.4 | 0.91 | 92% | 100% (114) | 58% | 89.1 | 1.17 |
| A5-unjudged | 745 | 81% | 95% | 75.8 | 0.95 | 95% | 0% (114) | 58% | 86.6 | 1.06 |
| A5-phoneme | 745 | 94% | 100% | 75.1 | 1.00 | 95% | 89% (114) | 63% | 86.2 | 1.20 |
| A5-phoneme+lr tau=0 | 745 | 94% | 100% | 75.2 | 0.97 | 95% | 89% (114) | 62% | 86.3 | 1.16 |
| A5-phoneme+lr tau=2 | 745 | 94% | 100% | 75.3 | 0.96 | 95% | 83% (114) | 60% | 86.4 | 1.12 |
| A5-phoneme+lr tau=4 | 745 | 93% | 99% | 75.3 | 0.96 | 95% | 78% (114) | 58% | 86.4 | 1.08 |
| A-converse | 745 | 96% | 95% | 75.1 | 1.04 | 95% | 100% (114) | 59% | 86.1 | 1.29 |
| A-zero=equal | 745 | 96% | 95% | 75.7 | 0.99 | 95% | 100% (114) | 59% | 86.4 | 1.22 |
| B-stretched | 745 | 97% | 95% | 57.4 | 1.00 | 97% | 100% (114) | 59% | 76.3 | 1.27 |
| B-linear | 745 | 96% | 94% | 82.5 | 1.03 | 95% | 100% (114) | 54% | 90.1 | 1.28 |
| B-stretched+linear | 745 | 97% | 95% | 68.6 | 1.00 | 97% | 100% (114) | 59% | 82.5 | 1.27 |
| B-deletions | 745 | 96% | 92% | 79.0 | 1.15 | 95% | 100% (114) | 58% | 88.4 | 1.36 |
| C-lv60 | 745 | 93% | 96% | 69.6 | 1.62 | 92% | 98% (113) | 81% | 78.6 | 1.95 |
| C-xlsr-fr | 745 | 96% | 95% | 75.7 | 1.03 | 95% | 100% (114) | 59% | 86.4 | 1.28 |
| rec de | 745 | 89% | 96% | 78.0 | 0.71 | 90% | 83% (114) | 49% | 88.6 | 0.80 |
| rec en | 745 | 76% | 90% | 78.5 | 0.70 | 90% | 0% (114) | 47% | 88.9 | 0.74 |
| rec fr | 745 | 76% | 90% | 78.5 | 0.70 | 90% | 0% (114) | 47% | 88.9 | 0.74 |
| E-check score | 745 | 76% | 100% | 57.0 | – | 93% | 0% (114) | 100% | 72.7 | – |
| A-V4 tau=0 | 745 | 94% | 93% | 77.5 | 0.83 | 93% | 99% (114) | 56% | 88.1 | 1.07 |
| A-V4 tau=2 | 745 | 87% | 88% | 79.7 | 0.56 | 87% | 89% (114) | 40% | 91.3 | 0.67 |
| combo clean | 745 | 80% | 95% | 75.8 | 0.91 | 95% | 0% (114) | 58% | 86.6 | 1.00 |
| combo clean+V1 | 745 | 64% | 73% | 83.8 | 0.31 | 75% | 0% (114) | 21% | 93.7 | 0.30 |
| combo clean+V2 | 745 | 76% | 90% | 78.5 | 0.70 | 90% | 0% (114) | 47% | 88.9 | 0.74 |
| combo clean+V3 | 745 | 73% | 86% | 79.5 | 0.54 | 86% | 0% (114) | 41% | 89.6 | 0.59 |
| combo clean+V4 tau=1 | 745 | 76% | 91% | 78.6 | 0.61 | 90% | 0% (114) | 46% | 89.8 | 0.69 |
| combo clean+V4 tau=2 | 745 | 73% | 88% | 79.8 | 0.52 | 86% | 0% (114) | 39% | 91.4 | 0.56 |
| combo clean+V2+ins tau=2 | 745 | 73% | 86% | 82.3 | 0.58 | 87% | 0% (114) | 45% | 91.6 | 0.64 |
| combo clean+V2 keep deletions | 745 | 80% | 93% | 76.5 | 0.73 | 94% | 0% (114) | 50% | 87.1 | 0.80 |
| combo phoneme+lr2+zero+V2 | 745 | 89% | 96% | 78.0 | 0.71 | 90% | 83% (114) | 49% | 88.6 | 0.80 |
| combo phoneme+lr2+zero+V2 keep deletions | 745 | 93% | 99% | 75.9 | 0.74 | 94% | 83% (114) | 52% | 86.9 | 0.85 |
| combo clean+V2 lv60 | 745 | 74% | 93% | 73.8 | 1.17 | 88% | 0% (113) | 71% | 82.4 | 1.28 |
| combo phoneme+lr2+zero+V2 lv60 | 745 | 85% | 97% | 73.2 | 1.18 | 88% | 68% (113) | 71% | 82.1 | 1.31 |
| rec de | 745 | 89% | 96% | 78.0 | 0.71 | 90% | 83% (114) | 49% | 88.6 | 0.80 |
| rec en | 745 | 76% | 90% | 78.5 | 0.70 | 90% | 0% (114) | 47% | 88.9 | 0.74 |
| rec fr | 745 | 76% | 90% | 78.5 | 0.70 | 90% | 0% (114) | 47% | 88.9 | 0.74 |


### Native speech (Common Phone test speakers) and the roles-reversed proxy

| variant | n | =100 | ≥95 | <90 | mean score | diff | roles reversed: n | detected | false elsewhere |
|---|---|---|---|---|---|---|---|---|---|
| baseline | 249 | 14% | 36% | 56% | 84.4 | 5.21 | 248 | 97% | 5.01 |
| A-V1 | 249 | 41% | 54% | 33% | 91.5 | 2.06 | 248 | 52% | 1.91 |
| A-V2 | 249 | 17% | 41% | 50% | 86.7 | 3.80 | 248 | 92% | 3.60 |
| A-V3 | 249 | 18% | 42% | 48% | 87.4 | 3.51 | 248 | 85% | 3.31 |
| A-ins edges | 249 | 14% | 36% | 55% | 84.5 | 5.20 | 248 | 97% | 5.00 |
| A-ins lr tau=0 | 249 | 15% | 39% | 53% | 85.8 | 5.06 | 248 | 97% | 4.82 |
| A-ins lr tau=2 | 249 | 16% | 48% | 45% | 87.9 | 4.84 | 248 | 97% | 4.61 |
| A5-unjudged | 249 | 15% | 37% | 54% | 84.9 | 4.71 | 248 | 97% | 4.67 |
| A5-phoneme | 249 | 14% | 36% | 56% | 84.4 | 5.02 | 248 | 97% | 4.93 |
| A5-phoneme+lr tau=0 | 249 | 14% | 36% | 55% | 84.6 | 4.82 | 248 | 97% | 4.72 |
| A5-phoneme+lr tau=2 | 249 | 14% | 36% | 55% | 84.6 | 4.75 | 248 | 97% | 4.70 |
| A5-phoneme+lr tau=4 | 249 | 14% | 36% | 55% | 84.6 | 4.75 | 248 | 97% | 4.70 |
| A-converse | 249 | 12% | 33% | 59% | 82.9 | 5.57 | 248 | 97% | 5.38 |
| A-zero=equal | 249 | 14% | 36% | 56% | 84.4 | 4.83 | 248 | 96% | 4.65 |
| B-stretched | 249 | 10% | 16% | 74% | 73.2 | 5.07 | 248 | 97% | 4.85 |
| B-linear | 249 | 33% | 78% | 4% | 96.7 | 5.21 | 248 | 97% | 5.01 |
| B-stretched+linear | 249 | 15% | 61% | 17% | 94.1 | 5.07 | 248 | 97% | 4.85 |
| B-deletions | 249 | 14% | 39% | 52% | 86.1 | 5.54 | 248 | 97% | 5.42 |
| C-lv60 | 249 | 1% | 4% | 94% | 59.0 | 12.25 | 248 | 96% | 11.86 |
| C-xlsr-fr | 249 | 14% | 36% | 56% | 84.4 | 5.21 | 248 | 97% | 5.01 |
| rec de | 249 | 18% | 41% | 49% | 86.9 | 3.25 | 248 | 91% | 3.21 |
| rec en | 249 | 19% | 42% | 48% | 87.3 | 3.21 | 248 | 91% | 3.17 |
| rec fr | 249 | 19% | 42% | 48% | 87.3 | 3.21 | 248 | 91% | 3.17 |
| E-check score | 249 | 0% | 6% | 57% | 86.3 | – | 248 | 95% | – |
| A-V4 tau=0 | 249 | 14% | 40% | 51% | 86.4 | 4.43 | 248 | 86% | 4.17 |
| A-V4 tau=2 | 249 | 30% | 52% | 36% | 90.3 | 2.54 | 248 | 62% | 2.50 |
| combo clean | 249 | 15% | 37% | 54% | 84.9 | 4.33 | 248 | 96% | 4.32 |
| combo clean+V1 | 249 | 43% | 55% | 31% | 92.0 | 1.52 | 248 | 52% | 1.53 |
| combo clean+V2 | 249 | 19% | 42% | 48% | 87.3 | 3.21 | 248 | 91% | 3.17 |
| combo clean+V3 | 249 | 20% | 43% | 47% | 87.9 | 2.92 | 248 | 84% | 2.89 |
| combo clean+V4 tau=1 | 249 | 23% | 47% | 43% | 88.6 | 3.02 | 248 | 75% | 2.98 |
| combo clean+V4 tau=2 | 249 | 30% | 52% | 36% | 90.3 | 2.41 | 248 | 61% | 2.39 |
| combo clean+V2+ins tau=2 | 249 | 23% | 56% | 35% | 90.7 | 2.84 | 248 | 91% | 2.77 |
| combo clean+V2 keep deletions | 249 | 18% | 38% | 52% | 85.8 | 3.38 | 248 | 92% | 3.34 |
| combo phoneme+lr2+zero+V2 | 249 | 18% | 41% | 49% | 86.9 | 3.25 | 248 | 91% | 3.21 |
| combo phoneme+lr2+zero+V2 keep deletions | 249 | 17% | 37% | 53% | 85.4 | 3.42 | 248 | 92% | 3.37 |
| combo clean+V2 lv60 | 249 | 2% | 8% | 88% | 68.9 | 8.04 | 248 | 93% | 7.89 |
| combo phoneme+lr2+zero+V2 lv60 | 249 | 2% | 7% | 89% | 68.4 | 8.16 | 248 | 93% | 7.96 |
| rec de | 249 | 18% | 41% | 49% | 86.9 | 3.25 | 248 | 91% | 3.21 |
| rec en | 249 | 19% | 42% | 48% | 87.3 | 3.21 | 248 | 91% | 3.17 |
| rec fr | 249 | 19% | 42% | 48% | 87.3 | 3.21 | 248 | 91% | 3.17 |


### Learner takes (German), by the owner's verdict

| variant | fair: n | mean | diff | changed | harsh: n | mean | diff | fewer diff | more diff | generous: n | mean | diff | unjudged: n | mean | diff |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| baseline | 19 | 90.9 | 1.79 | 0 | 18 | 88.2 | 2.22 | 0 | 0 | 0 | – | – | 18 | 79.5 | 2.83 |
| A-V1 | 19 | 94.0 | 0.74 | 15 | 18 | 91.1 | 1.56 | 10 | 0 | 0 | – | – | 18 | 87.4 | 1.06 |
| A-V2 | 19 | 93.1 | 1.16 | 10 | 18 | 90.3 | 1.89 | 6 | 0 | 0 | – | – | 18 | 83.2 | 1.94 |
| A-V3 | 19 | 93.3 | 1.05 | 11 | 18 | 90.8 | 1.78 | 7 | 0 | 0 | – | – | 18 | 84.2 | 1.61 |
| A-ins edges | 19 | 90.9 | 1.79 | 0 | 18 | 89.2 | 2.17 | 1 | 0 | 0 | – | – | 18 | 82.3 | 2.61 |
| A-ins lr tau=0 | 19 | 90.9 | 1.79 | 0 | 18 | 88.2 | 2.22 | 0 | 0 | 0 | – | – | 18 | 79.5 | 2.83 |
| A-ins lr tau=2 | 19 | 93.3 | 1.68 | 2 | 18 | 91.4 | 2.00 | 4 | 0 | 0 | – | – | 18 | 81.7 | 2.72 |
| A5-unjudged | 19 | 90.9 | 1.63 | 4 | 18 | 88.2 | 1.94 | 5 | 0 | 0 | – | – | 18 | 79.5 | 2.78 |
| A5-phoneme | 19 | 90.9 | 1.68 | 4 | 18 | 87.8 | 2.17 | 1 | 0 | 0 | – | – | 18 | 79.4 | 2.83 |
| A5-phoneme+lr tau=0 | 19 | 90.9 | 1.68 | 4 | 18 | 87.8 | 2.17 | 1 | 0 | 0 | – | – | 18 | 79.4 | 2.83 |
| A5-phoneme+lr tau=2 | 19 | 90.9 | 1.63 | 4 | 18 | 88.0 | 2.06 | 3 | 0 | 0 | – | – | 18 | 79.5 | 2.78 |
| A5-phoneme+lr tau=4 | 19 | 90.9 | 1.63 | 4 | 18 | 88.0 | 2.06 | 3 | 0 | 0 | – | – | 18 | 79.5 | 2.78 |
| A-converse | 19 | 89.0 | 1.90 | 2 | 18 | 86.2 | 2.33 | 0 | 2 | 0 | – | – | 18 | 78.4 | 2.89 |
| A-zero=equal | 19 | 90.9 | 1.53 | 5 | 18 | 88.2 | 2.11 | 2 | 0 | 0 | – | – | 18 | 79.5 | 2.56 |
| B-stretched | 19 | 81.9 | 1.79 | 12 | 18 | 76.9 | 2.22 | 0 | 0 | 0 | – | – | 18 | 65.3 | 2.67 |
| B-linear | 19 | 96.2 | 1.79 | 12 | 18 | 94.8 | 2.22 | 0 | 0 | 0 | – | – | 18 | 88.8 | 2.83 |
| B-stretched+linear | 19 | 90.7 | 1.79 | 15 | 18 | 87.7 | 2.22 | 0 | 0 | 0 | – | – | 18 | 80.8 | 2.67 |
| B-deletions | 19 | 92.9 | 1.95 | 2 | 18 | 89.2 | 2.22 | 0 | 0 | 0 | – | – | 18 | 80.8 | 2.78 |
| C-lv60 | 19 | 82.9 | 2.53 | 17 | 18 | 80.3 | 3.39 | 0 | 9 | 0 | – | – | 18 | 76.9 | 3.17 |
| C-xlsr-fr | 19 | 90.9 | 1.79 | 0 | 18 | 88.2 | 2.22 | 0 | 0 | 0 | – | – | 18 | 79.5 | 2.83 |
| rec de | 19 | 93.1 | 0.95 | 10 | 18 | 90.1 | 1.72 | 8 | 0 | 0 | – | – | 18 | 83.2 | 1.83 |
| rec en | 19 | 93.1 | 0.95 | 10 | 18 | 90.3 | 1.61 | 9 | 0 | 0 | – | – | 18 | 83.2 | 1.83 |
| rec fr | 19 | 93.1 | 0.95 | 10 | 18 | 90.3 | 1.61 | 9 | 0 | 0 | – | – | 18 | 83.2 | 1.83 |
| E-check score | 19 | 83.2 | – | – | 18 | 82.1 | – | – | – | 0 | – | – | 18 | 72.9 | – |
| A-V4 tau=0 | 19 | 91.1 | 1.63 | 3 | 18 | 89.6 | 2.06 | 2 | 0 | 0 | – | – | 18 | 83.2 | 2.28 |
| A-V4 tau=2 | 19 | 91.5 | 1.10 | 11 | 18 | 89.9 | 1.56 | 10 | 0 | 0 | – | – | 18 | 85.4 | 1.33 |
| combo clean | 19 | 90.9 | 1.37 | 6 | 18 | 88.2 | 1.83 | 6 | 0 | 0 | – | – | 18 | 79.5 | 2.50 |
| combo clean+V1 | 19 | 94.0 | 0.58 | 15 | 18 | 91.1 | 1.28 | 13 | 0 | 0 | – | – | 18 | 87.4 | 1.00 |
| combo clean+V2 | 19 | 93.1 | 0.95 | 10 | 18 | 90.3 | 1.61 | 9 | 0 | 0 | – | – | 18 | 83.2 | 1.83 |
| combo clean+V3 | 19 | 93.3 | 0.90 | 11 | 18 | 90.8 | 1.50 | 10 | 0 | 0 | – | – | 18 | 84.2 | 1.56 |
| combo clean+V4 tau=1 | 19 | 91.4 | 1.00 | 12 | 18 | 89.9 | 1.50 | 11 | 0 | 0 | – | – | 18 | 84.9 | 1.72 |
| combo clean+V4 tau=2 | 19 | 91.5 | 0.95 | 13 | 18 | 89.9 | 1.44 | 11 | 0 | 0 | – | – | 18 | 85.4 | 1.28 |
| combo clean+V2+ins tau=2 | 19 | 95.4 | 0.84 | 11 | 18 | 93.5 | 1.39 | 10 | 0 | 0 | – | – | 18 | 85.4 | 1.72 |
| combo clean+V2 keep deletions | 19 | 91.2 | 1.05 | 10 | 18 | 89.3 | 1.67 | 9 | 0 | 0 | – | – | 18 | 82.2 | 1.89 |
| combo phoneme+lr2+zero+V2 | 19 | 93.1 | 0.95 | 10 | 18 | 90.1 | 1.72 | 8 | 0 | 0 | – | – | 18 | 83.2 | 1.83 |
| combo phoneme+lr2+zero+V2 keep deletions | 19 | 91.2 | 1.05 | 10 | 18 | 89.1 | 1.78 | 8 | 0 | 0 | – | – | 18 | 82.2 | 1.89 |
| combo clean+V2 lv60 | 19 | 86.5 | 1.58 | 17 | 18 | 82.8 | 2.44 | 6 | 5 | 0 | – | – | 18 | 80.1 | 2.56 |
| combo phoneme+lr2+zero+V2 lv60 | 19 | 86.4 | 1.63 | 17 | 18 | 82.7 | 2.50 | 6 | 6 | 0 | – | – | 18 | 80.1 | 2.56 |
| rec de | 19 | 93.1 | 0.95 | 10 | 18 | 90.1 | 1.72 | 8 | 0 | 0 | – | – | 18 | 83.2 | 1.83 |
| rec en | 19 | 93.1 | 0.95 | 10 | 18 | 90.3 | 1.61 | 9 | 0 | 0 | – | – | 18 | 83.2 | 1.83 |
| rec fr | 19 | 93.1 | 0.95 | 10 | 18 | 90.3 | 1.61 | 9 | 0 | 0 | – | – | 18 | 83.2 | 1.83 |


### V4: the likelihood-ratio threshold τ (keep an edit iff log P(edited target) − log P(target) ≥ τ)

| τ | near miss detected | near miss below 100 | false elsewhere | positives below 100 | reference diff (G/M/P) | native diff | roles reversed detected | harsh: fewer diff | fair: changed |
|---|---|---|---|---|---|---|---|---|---|
| greedy (baseline) | 96% | 95% | 1.03 | 59% | 1.15/1.33/1.27 | 5.21 | 97% | 0 | 0 |
| -6 | 96% | 95% | 0.98 | 59% | 1.15/1.29/1.21 | 4.89 | 96% | 1 | 2 |
| -4 | 96% | 95% | 0.95 | 58% | 1.12/1.29/1.21 | 4.78 | 95% | 1 | 2 |
| -2 | 95% | 94% | 0.91 | 58% | 1.10/1.29/1.21 | 4.65 | 95% | 1 | 2 |
| -1 | 94% | 94% | 0.88 | 58% | 1.08/1.29/1.21 | 4.53 | 91% | 2 | 2 |
| 0 | 94% | 93% | 0.83 | 56% | 1.04/1.25/1.17 | 4.43 | 86% | 2 | 3 |
| 1 | 91% | 91% | 0.67 | 46% | 0.71/0.90/0.65 | 3.35 | 77% | 8 | 10 |
| 2 | 87% | 88% | 0.56 | 40% | 0.48/0.65/0.48 | 2.54 | 62% | 10 | 11 |
| 4 | 76% | 75% | 0.35 | 26% | 0.29/0.50/0.29 | 1.57 | 44% | 13 | 15 |
| 6 | 57% | 58% | 0.25 | 17% | 0.17/0.31/0.12 | 1.02 | 27% | 14 | 15 |
| 10 | 16% | 23% | 0.16 | 9% | 0.06/0.21/0.02 | 0.55 | 3% | 14 | 15 |



## English


### Reference phrases (48 a voice): share of phrases at 100, at 95 or more, under 90; mean sounds shown different

| variant | Google =100 | Google ≥95 | Google <90 | Google diff | compact Mac =100 | compact Mac ≥95 | compact Mac <90 | compact Mac diff | Premium Mac =100 | Premium Mac ≥95 | Premium Mac <90 | Premium Mac diff |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| baseline | 35% | 52% | 44% | 2.02 | 35% | 46% | 54% | 2.71 | 42% | 56% | 38% | 2.48 |
| A-V1 | 65% | 75% | 23% | 1.23 | 60% | 75% | 25% | 1.42 | 67% | 83% | 15% | 1.33 |
| A-V2 | 58% | 73% | 25% | 1.35 | 58% | 73% | 27% | 1.60 | 62% | 79% | 19% | 1.44 |
| A-V3 | 62% | 75% | 23% | 1.31 | 58% | 73% | 27% | 1.54 | 65% | 81% | 17% | 1.42 |
| A-ins edges | 35% | 52% | 44% | 2.02 | 35% | 46% | 54% | 2.71 | 42% | 56% | 38% | 2.42 |
| A-ins lr tau=0 | 35% | 52% | 44% | 2.02 | 35% | 50% | 48% | 2.65 | 42% | 56% | 38% | 2.44 |
| A-ins lr tau=2 | 35% | 52% | 44% | 2.02 | 35% | 52% | 46% | 2.62 | 42% | 56% | 38% | 2.38 |
| A5-unjudged | 56% | 71% | 27% | 1.00 | 48% | 52% | 48% | 1.67 | 56% | 65% | 31% | 1.48 |
| A5-phoneme | 27% | 52% | 44% | 1.69 | 21% | 46% | 54% | 2.38 | 27% | 58% | 38% | 2.15 |
| A5-phoneme+lr tau=0 | 27% | 52% | 44% | 1.69 | 21% | 46% | 54% | 2.35 | 27% | 58% | 38% | 2.12 |
| A5-phoneme+lr tau=2 | 31% | 52% | 44% | 1.56 | 29% | 46% | 54% | 2.12 | 35% | 58% | 38% | 1.92 |
| A5-phoneme+lr tau=4 | 35% | 52% | 44% | 1.50 | 35% | 46% | 54% | 1.98 | 40% | 58% | 38% | 1.83 |
| A-converse | 35% | 52% | 44% | 2.02 | 35% | 46% | 54% | 2.71 | 42% | 56% | 38% | 2.48 |
| A-zero=equal | 35% | 52% | 44% | 1.77 | 35% | 46% | 54% | 2.42 | 42% | 56% | 38% | 2.23 |
| B-stretched | 31% | 35% | 62% | 2.02 | 33% | 35% | 65% | 2.67 | 40% | 42% | 54% | 2.38 |
| B-linear | 44% | 65% | 15% | 2.02 | 42% | 56% | 19% | 2.71 | 52% | 69% | 17% | 2.48 |
| B-stretched+linear | 31% | 52% | 23% | 2.02 | 33% | 50% | 35% | 2.67 | 40% | 58% | 25% | 2.38 |
| B-deletions | 35% | 52% | 33% | 2.10 | 35% | 46% | 44% | 2.81 | 42% | 56% | 27% | 2.54 |
| C-lv60 | 31% | 52% | 46% | 2.27 | 23% | 35% | 58% | 2.83 | 35% | 46% | 54% | 2.29 |
| C-xlsr-fr | 35% | 52% | 44% | 2.02 | 35% | 46% | 54% | 2.71 | 42% | 56% | 38% | 2.48 |
| rec de | 50% | 73% | 25% | 0.83 | 52% | 73% | 27% | 0.88 | 56% | 81% | 19% | 0.79 |
| rec en | 83% | 94% | 6% | 0.27 | 75% | 79% | 21% | 0.42 | 85% | 88% | 12% | 0.35 |
| rec fr | 83% | 94% | 6% | 0.27 | 75% | 79% | 21% | 0.42 | 85% | 88% | 12% | 0.35 |
| E-check score | 0% | 27% | 40% | – | 0% | 23% | 50% | – | 0% | 27% | 31% | – |
| A-V4 tau=0 | 52% | 71% | 25% | 1.58 | 50% | 69% | 29% | 1.90 | 58% | 75% | 23% | 1.75 |
| A-V4 tau=2 | 62% | 81% | 17% | 1.08 | 58% | 77% | 21% | 1.23 | 73% | 88% | 12% | 1.00 |
| combo clean | 56% | 71% | 27% | 0.88 | 48% | 52% | 48% | 1.46 | 56% | 65% | 31% | 1.35 |
| combo clean+V1 | 90% | 96% | 4% | 0.17 | 79% | 81% | 19% | 0.29 | 90% | 92% | 8% | 0.29 |
| combo clean+V2 | 83% | 94% | 6% | 0.27 | 75% | 79% | 21% | 0.42 | 85% | 88% | 12% | 0.35 |
| combo clean+V3 | 88% | 96% | 4% | 0.23 | 75% | 79% | 21% | 0.35 | 88% | 90% | 10% | 0.33 |
| combo clean+V4 tau=1 | 81% | 94% | 4% | 0.40 | 67% | 77% | 21% | 0.62 | 77% | 85% | 12% | 0.60 |
| combo clean+V4 tau=2 | 81% | 96% | 4% | 0.33 | 71% | 81% | 17% | 0.44 | 85% | 92% | 8% | 0.38 |
| combo clean+V2+ins tau=2 | 83% | 94% | 6% | 0.27 | 77% | 88% | 12% | 0.33 | 85% | 88% | 10% | 0.25 |
| combo clean+V2 keep deletions | 62% | 73% | 27% | 0.58 | 50% | 54% | 46% | 0.77 | 69% | 71% | 29% | 0.65 |
| combo phoneme+lr2+zero+V2 | 50% | 73% | 25% | 0.83 | 52% | 73% | 27% | 0.88 | 56% | 81% | 19% | 0.79 |
| combo phoneme+lr2+zero+V2 keep deletions | 33% | 54% | 44% | 1.15 | 31% | 48% | 52% | 1.23 | 46% | 65% | 35% | 1.08 |
| combo clean+V2 lv60 | 77% | 81% | 19% | 0.46 | 56% | 65% | 33% | 0.65 | 71% | 71% | 27% | 0.54 |
| combo phoneme+lr2+zero+V2 lv60 | 48% | 73% | 27% | 0.98 | 33% | 58% | 40% | 1.19 | 42% | 65% | 33% | 1.06 |
| rec de | 50% | 73% | 25% | 0.83 | 52% | 73% | 27% | 0.88 | 56% | 81% | 19% | 0.79 |
| rec en | 83% | 94% | 6% | 0.27 | 75% | 79% | 21% | 0.42 | 85% | 88% | 12% | 0.35 |
| rec fr | 83% | 94% | 6% | 0.27 | 75% | 79% | 21% | 0.42 | 85% | 88% | 12% | 0.35 |


### Near misses (voice says B, target A; one edit) and their positives (voice says A)

| variant | n | detected at the place | below 100 | mean score | false elsewhere | detected, sound judged | detected, sound unjudged (n) | positives below 100 | positives mean | positives diff |
|---|---|---|---|---|---|---|---|---|---|---|
| baseline | 744 | 93% | 88% | 76.3 | 0.91 | 92% | 97% (124) | 56% | 85.1 | 1.21 |
| A-V1 | 744 | 80% | 73% | 82.7 | 0.50 | 77% | 94% (124) | 28% | 92.9 | 0.61 |
| A-V2 | 744 | 86% | 80% | 80.5 | 0.65 | 84% | 95% (124) | 35% | 90.5 | 0.80 |
| A-V3 | 744 | 83% | 78% | 81.1 | 0.59 | 81% | 95% (124) | 34% | 91.1 | 0.73 |
| A-ins edges | 744 | 85% | 83% | 79.9 | 0.88 | 82% | 97% (124) | 55% | 85.7 | 1.19 |
| A-ins lr tau=0 | 744 | 93% | 86% | 78.6 | 0.84 | 92% | 97% (124) | 54% | 87.5 | 1.13 |
| A-ins lr tau=2 | 744 | 90% | 85% | 80.2 | 0.82 | 88% | 97% (124) | 53% | 88.3 | 1.11 |
| A5-unjudged | 744 | 77% | 88% | 78.0 | 0.64 | 92% | 2% (124) | 50% | 87.2 | 0.85 |
| A5-phoneme | 744 | 86% | 95% | 76.0 | 0.80 | 92% | 56% (124) | 63% | 85.0 | 1.07 |
| A5-phoneme+lr tau=0 | 744 | 86% | 95% | 76.0 | 0.79 | 92% | 55% (124) | 62% | 85.1 | 1.05 |
| A5-phoneme+lr tau=2 | 744 | 85% | 94% | 76.1 | 0.77 | 92% | 48% (124) | 61% | 85.2 | 1.02 |
| A5-phoneme+lr tau=4 | 744 | 82% | 93% | 76.3 | 0.75 | 92% | 34% (124) | 59% | 85.2 | 0.98 |
| A-converse | 744 | 93% | 88% | 75.7 | 0.92 | 92% | 97% (124) | 56% | 85.0 | 1.22 |
| A-zero=equal | 744 | 92% | 88% | 76.3 | 0.81 | 91% | 97% (124) | 56% | 85.1 | 1.09 |
| B-stretched | 744 | 93% | 88% | 58.9 | 0.89 | 93% | 97% (124) | 56% | 76.5 | 1.21 |
| B-linear | 744 | 93% | 88% | 82.0 | 0.91 | 92% | 97% (124) | 53% | 88.5 | 1.21 |
| B-stretched+linear | 744 | 93% | 88% | 67.3 | 0.89 | 93% | 97% (124) | 56% | 81.2 | 1.21 |
| B-deletions | 744 | 93% | 88% | 77.5 | 0.92 | 92% | 97% (124) | 56% | 86.2 | 1.21 |
| C-lv60 | 740 | 90% | 88% | 74.3 | 1.09 | 91% | 85% (124) | 64% | 82.3 | 1.45 |
| C-xlsr-fr | 744 | 93% | 88% | 76.3 | 0.91 | 92% | 97% (124) | 56% | 85.1 | 1.21 |
| rec de | 744 | 77% | 86% | 80.3 | 0.48 | 83% | 47% (124) | 41% | 90.5 | 0.57 |
| rec en | 744 | 69% | 78% | 82.2 | 0.35 | 82% | 1% (124) | 28% | 92.5 | 0.41 |
| rec fr | 744 | 69% | 78% | 82.2 | 0.35 | 82% | 1% (124) | 28% | 92.5 | 0.41 |
| E-check score | 741 | 70% | 100% | 52.5 | – | 87% | 1% (124) | 98% | 72.1 | – |
| A-V4 tau=0 | 744 | 89% | 85% | 78.8 | 0.70 | 88% | 95% (124) | 49% | 88.3 | 0.96 |
| A-V4 tau=2 | 744 | 82% | 80% | 81.7 | 0.47 | 83% | 74% (124) | 35% | 92.3 | 0.61 |
| combo clean | 744 | 76% | 88% | 78.0 | 0.57 | 90% | 2% (124) | 50% | 87.2 | 0.76 |
| combo clean+V1 | 744 | 63% | 71% | 84.5 | 0.23 | 76% | 0% (124) | 19% | 95.0 | 0.24 |
| combo clean+V2 | 744 | 69% | 78% | 82.2 | 0.35 | 82% | 1% (124) | 28% | 92.5 | 0.41 |
| combo clean+V3 | 744 | 66% | 76% | 82.8 | 0.30 | 79% | 1% (124) | 26% | 93.1 | 0.34 |
| combo clean+V4 tau=1 | 744 | 70% | 81% | 81.7 | 0.35 | 84% | 2% (124) | 35% | 92.0 | 0.46 |
| combo clean+V4 tau=2 | 744 | 68% | 79% | 82.8 | 0.29 | 82% | 0% (124) | 28% | 93.7 | 0.36 |
| combo clean+V2+ins tau=2 | 744 | 66% | 74% | 86.2 | 0.26 | 79% | 1% (124) | 23% | 95.6 | 0.31 |
| combo clean+V2 keep deletions | 744 | 71% | 83% | 78.8 | 0.43 | 85% | 1% (124) | 38% | 87.9 | 0.55 |
| combo phoneme+lr2+zero+V2 | 744 | 77% | 86% | 80.3 | 0.48 | 83% | 47% (124) | 41% | 90.5 | 0.57 |
| combo phoneme+lr2+zero+V2 keep deletions | 744 | 79% | 89% | 76.9 | 0.56 | 85% | 47% (124) | 50% | 85.9 | 0.71 |
| combo clean+V2 lv60 | 740 | 67% | 79% | 80.0 | 0.46 | 81% | 2% (124) | 39% | 89.2 | 0.57 |
| combo phoneme+lr2+zero+V2 lv60 | 740 | 76% | 87% | 78.4 | 0.56 | 81% | 51% (124) | 50% | 87.0 | 0.74 |
| rec de | 744 | 77% | 86% | 80.3 | 0.48 | 83% | 47% (124) | 41% | 90.5 | 0.57 |
| rec en | 744 | 69% | 78% | 82.2 | 0.35 | 82% | 1% (124) | 28% | 92.5 | 0.41 |
| rec fr | 744 | 69% | 78% | 82.2 | 0.35 | 82% | 1% (124) | 28% | 92.5 | 0.41 |


### Native speech (Common Phone test speakers) and the roles-reversed proxy

| variant | n | =100 | ≥95 | <90 | mean score | diff | roles reversed: n | detected | false elsewhere |
|---|---|---|---|---|---|---|---|---|---|
| baseline | 300 | 3% | 12% | 85% | 70.8 | 9.02 | – | – | – |
| A-V1 | 300 | 25% | 48% | 39% | 90.1 | 4.40 | – | – | – |
| A-V2 | 300 | 15% | 37% | 52% | 86.4 | 5.37 | – | – | – |
| A-V3 | 300 | 17% | 41% | 49% | 87.4 | 5.10 | – | – | – |
| A-ins edges | 300 | 3% | 12% | 85% | 71.0 | 9.01 | – | – | – |
| A-ins lr tau=0 | 300 | 3% | 13% | 84% | 71.9 | 8.93 | – | – | – |
| A-ins lr tau=2 | 300 | 4% | 14% | 83% | 72.4 | 8.88 | – | – | – |
| A5-unjudged | 300 | 7% | 16% | 79% | 75.2 | 5.63 | – | – | – |
| A5-phoneme | 300 | 1% | 12% | 87% | 70.3 | 7.80 | – | – | – |
| A5-phoneme+lr tau=0 | 300 | 1% | 12% | 87% | 70.4 | 7.69 | – | – | – |
| A5-phoneme+lr tau=2 | 300 | 1% | 12% | 87% | 70.6 | 7.35 | – | – | – |
| A5-phoneme+lr tau=4 | 300 | 3% | 12% | 86% | 70.8 | 6.86 | – | – | – |
| A-converse | 300 | 3% | 12% | 86% | 70.4 | 9.07 | – | – | – |
| A-zero=equal | 300 | 3% | 12% | 85% | 70.8 | 7.98 | – | – | – |
| B-stretched | 300 | 3% | 4% | 92% | 57.7 | 8.71 | – | – | – |
| B-linear | 300 | 10% | 43% | 19% | 93.3 | 9.02 | – | – | – |
| B-stretched+linear | 300 | 3% | 24% | 43% | 89.8 | 8.71 | – | – | – |
| B-deletions | 300 | 3% | 13% | 81% | 75.3 | 9.17 | – | – | – |
| C-lv60 | 300 | 5% | 10% | 86% | 71.6 | 9.01 | – | – | – |
| C-xlsr-fr | 300 | 3% | 12% | 85% | 70.8 | 9.02 | – | – | – |
| rec de | 300 | 8% | 38% | 54% | 86.2 | 3.31 | – | – | – |
| rec en | 300 | 35% | 50% | 39% | 90.7 | 1.60 | – | – | – |
| rec fr | 300 | 35% | 50% | 39% | 90.7 | 1.60 | – | – | – |
| E-check score | 300 | 0% | 3% | 75% | 83.7 | – | – | – | – |
| A-V4 tau=0 | 300 | 10% | 28% | 64% | 82.5 | 6.58 | – | – | – |
| A-V4 tau=2 | 300 | 17% | 45% | 46% | 88.8 | 4.33 | – | – | – |
| combo clean | 300 | 7% | 16% | 79% | 75.2 | 4.77 | – | – | – |
| combo clean+V1 | 300 | 56% | 65% | 24% | 94.4 | 0.83 | – | – | – |
| combo clean+V2 | 300 | 35% | 50% | 39% | 90.7 | 1.60 | – | – | – |
| combo clean+V3 | 300 | 39% | 54% | 36% | 91.7 | 1.34 | – | – | – |
| combo clean+V4 tau=1 | 300 | 25% | 47% | 43% | 89.4 | 2.17 | – | – | – |
| combo clean+V4 tau=2 | 300 | 34% | 54% | 35% | 91.7 | 1.50 | – | – | – |
| combo clean+V2+ins tau=2 | 300 | 39% | 58% | 31% | 92.3 | 1.45 | – | – | – |
| combo clean+V2 keep deletions | 300 | 13% | 19% | 72% | 77.7 | 2.89 | – | – | – |
| combo phoneme+lr2+zero+V2 | 300 | 8% | 38% | 54% | 86.2 | 3.31 | – | – | – |
| combo phoneme+lr2+zero+V2 keep deletions | 300 | 4% | 14% | 82% | 73.3 | 4.60 | – | – | – |
| combo clean+V2 lv60 | 300 | 29% | 41% | 45% | 89.4 | 1.71 | – | – | – |
| combo phoneme+lr2+zero+V2 lv60 | 300 | 9% | 37% | 56% | 86.6 | 3.52 | – | – | – |
| rec de | 300 | 8% | 38% | 54% | 86.2 | 3.31 | – | – | – |
| rec en | 300 | 35% | 50% | 39% | 90.7 | 1.60 | – | – | – |
| rec fr | 300 | 35% | 50% | 39% | 90.7 | 1.60 | – | – | – |


### Learner takes (English), by the owner's verdict

| variant | fair: n | mean | diff | changed | harsh: n | mean | diff | fewer diff | more diff | generous: n | mean | diff | unjudged: n | mean | diff |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| baseline | 5 | 89.6 | 1.80 | 0 | 2 | 38.0 | 4.00 | 0 | 0 | 2 | 88.5 | 2.50 | 0 | – | – |
| A-V1 | 5 | 90.8 | 0.80 | 3 | 2 | 46.0 | 3.50 | 1 | 0 | 2 | 100.0 | 1.00 | 0 | – | – |
| A-V2 | 5 | 90.8 | 1.00 | 3 | 2 | 46.0 | 3.50 | 1 | 0 | 2 | 100.0 | 1.00 | 0 | – | – |
| A-V3 | 5 | 90.8 | 1.00 | 3 | 2 | 46.0 | 3.50 | 1 | 0 | 2 | 100.0 | 1.00 | 0 | – | – |
| A-ins edges | 5 | 89.6 | 1.80 | 0 | 2 | 38.0 | 4.00 | 0 | 0 | 2 | 88.5 | 2.50 | 0 | – | – |
| A-ins lr tau=0 | 5 | 89.6 | 1.80 | 0 | 2 | 38.0 | 4.00 | 0 | 0 | 2 | 88.5 | 2.50 | 0 | – | – |
| A-ins lr tau=2 | 5 | 89.6 | 1.80 | 0 | 2 | 38.0 | 4.00 | 0 | 0 | 2 | 88.5 | 2.50 | 0 | – | – |
| A5-unjudged | 5 | 98.6 | 1.00 | 2 | 2 | 50.0 | 2.50 | 2 | 0 | 2 | 88.5 | 2.00 | 0 | – | – |
| A5-phoneme | 5 | 89.6 | 1.80 | 2 | 2 | 39.5 | 3.50 | 1 | 0 | 2 | 88.0 | 2.50 | 0 | – | – |
| A5-phoneme+lr tau=0 | 5 | 89.6 | 1.80 | 2 | 2 | 39.5 | 3.50 | 1 | 0 | 2 | 88.0 | 2.50 | 0 | – | – |
| A5-phoneme+lr tau=2 | 5 | 89.6 | 1.80 | 2 | 2 | 39.5 | 3.50 | 1 | 0 | 2 | 88.5 | 2.00 | 0 | – | – |
| A5-phoneme+lr tau=4 | 5 | 89.6 | 1.80 | 2 | 2 | 39.5 | 3.00 | 2 | 0 | 2 | 88.5 | 2.00 | 0 | – | – |
| A-converse | 5 | 89.6 | 1.80 | 0 | 2 | 38.0 | 4.50 | 0 | 1 | 2 | 88.5 | 2.50 | 0 | – | – |
| A-zero=equal | 5 | 89.6 | 1.40 | 2 | 2 | 38.0 | 4.00 | 0 | 0 | 2 | 88.5 | 1.50 | 0 | – | – |
| B-stretched | 5 | 79.2 | 1.80 | 4 | 2 | 32.5 | 4.00 | 0 | 0 | 2 | 86.0 | 2.50 | 0 | – | – |
| B-linear | 5 | 95.4 | 1.80 | 4 | 2 | 69.5 | 4.00 | 0 | 0 | 2 | 94.5 | 2.50 | 0 | – | – |
| B-stretched+linear | 5 | 89.2 | 1.80 | 4 | 2 | 67.0 | 4.00 | 0 | 0 | 2 | 93.5 | 2.50 | 0 | – | – |
| B-deletions | 5 | 91.8 | 1.80 | 1 | 2 | 46.0 | 4.00 | 0 | 0 | 2 | 88.5 | 2.50 | 0 | – | – |
| C-lv60 | 5 | 97.0 | 1.60 | 4 | 2 | 49.0 | 4.50 | 1 | 1 | 2 | 88.5 | 2.50 | 0 | – | – |
| C-xlsr-fr | 5 | 89.6 | 1.80 | 0 | 2 | 38.0 | 4.00 | 0 | 0 | 2 | 88.5 | 2.50 | 0 | – | – |
| rec de | 5 | 90.8 | 0.80 | 4 | 2 | 47.0 | 3.00 | 2 | 0 | 2 | 100.0 | 0.00 | 0 | – | – |
| rec en | 5 | 100.0 | 0.00 | 4 | 2 | 58.0 | 2.00 | 2 | 0 | 2 | 100.0 | 0.00 | 0 | – | – |
| rec fr | 5 | 100.0 | 0.00 | 4 | 2 | 58.0 | 2.00 | 2 | 0 | 2 | 100.0 | 0.00 | 0 | – | – |
| E-check score | 5 | 78.2 | – | – | 2 | 63.5 | – | – | – | 2 | 87.0 | – | 0 | – | – |
| A-V4 tau=0 | 5 | 89.6 | 1.80 | 0 | 2 | 39.5 | 3.50 | 1 | 0 | 2 | 99.5 | 2.00 | 0 | – | – |
| A-V4 tau=2 | 5 | 99.2 | 0.60 | 4 | 2 | 39.5 | 3.50 | 1 | 0 | 2 | 100.0 | 1.00 | 0 | – | – |
| combo clean | 5 | 98.6 | 0.60 | 4 | 2 | 50.0 | 2.50 | 2 | 0 | 2 | 88.5 | 1.00 | 0 | – | – |
| combo clean+V1 | 5 | 100.0 | 0.00 | 4 | 2 | 58.0 | 2.00 | 2 | 0 | 2 | 100.0 | 0.00 | 0 | – | – |
| combo clean+V2 | 5 | 100.0 | 0.00 | 4 | 2 | 58.0 | 2.00 | 2 | 0 | 2 | 100.0 | 0.00 | 0 | – | – |
| combo clean+V3 | 5 | 100.0 | 0.00 | 4 | 2 | 58.0 | 2.00 | 2 | 0 | 2 | 100.0 | 0.00 | 0 | – | – |
| combo clean+V4 tau=1 | 5 | 99.4 | 0.20 | 4 | 2 | 50.0 | 2.50 | 2 | 0 | 2 | 100.0 | 0.00 | 0 | – | – |
| combo clean+V4 tau=2 | 5 | 100.0 | 0.00 | 4 | 2 | 50.0 | 2.50 | 2 | 0 | 2 | 100.0 | 0.00 | 0 | – | – |
| combo clean+V2+ins tau=2 | 5 | 100.0 | 0.00 | 4 | 2 | 58.0 | 2.00 | 2 | 0 | 2 | 100.0 | 0.00 | 0 | – | – |
| combo clean+V2 keep deletions | 5 | 100.0 | 0.00 | 4 | 2 | 50.0 | 2.50 | 2 | 0 | 2 | 89.0 | 0.50 | 0 | – | – |
| combo phoneme+lr2+zero+V2 | 5 | 90.8 | 0.80 | 4 | 2 | 47.0 | 3.00 | 2 | 0 | 2 | 100.0 | 0.00 | 0 | – | – |
| combo phoneme+lr2+zero+V2 keep deletions | 5 | 90.8 | 0.80 | 4 | 2 | 39.5 | 3.50 | 1 | 0 | 2 | 89.0 | 0.50 | 0 | – | – |
| combo clean+V2 lv60 | 5 | 100.0 | 0.00 | 4 | 2 | 66.0 | 2.50 | 2 | 0 | 2 | 100.0 | 0.00 | 0 | – | – |
| combo phoneme+lr2+zero+V2 lv60 | 5 | 99.0 | 0.60 | 4 | 2 | 64.5 | 3.50 | 1 | 0 | 2 | 99.5 | 0.50 | 0 | – | – |
| rec de | 5 | 90.8 | 0.80 | 4 | 2 | 47.0 | 3.00 | 2 | 0 | 2 | 100.0 | 0.00 | 0 | – | – |
| rec en | 5 | 100.0 | 0.00 | 4 | 2 | 58.0 | 2.00 | 2 | 0 | 2 | 100.0 | 0.00 | 0 | – | – |
| rec fr | 5 | 100.0 | 0.00 | 4 | 2 | 58.0 | 2.00 | 2 | 0 | 2 | 100.0 | 0.00 | 0 | – | – |


### V4: the likelihood-ratio threshold τ (keep an edit iff log P(edited target) − log P(target) ≥ τ)

| τ | near miss detected | near miss below 100 | false elsewhere | positives below 100 | reference diff (G/M/P) | native diff | roles reversed detected | harsh: fewer diff | fair: changed |
|---|---|---|---|---|---|---|---|---|---|
| greedy (baseline) | 93% | 88% | 0.91 | 56% | 2.02/2.71/2.48 | 9.02 | – | 0 | 0 |
| -6 | 93% | 88% | 0.88 | 55% | 1.96/2.50/2.27 | 8.30 | – | 0 | 0 |
| -4 | 92% | 88% | 0.84 | 55% | 1.90/2.33/2.08 | 7.82 | – | 0 | 0 |
| -2 | 91% | 87% | 0.80 | 53% | 1.73/2.06/1.90 | 7.23 | – | 0 | 0 |
| -1 | 90% | 85% | 0.76 | 51% | 1.67/2.00/1.83 | 6.92 | – | 1 | 0 |
| 0 | 89% | 85% | 0.70 | 49% | 1.58/1.90/1.75 | 6.58 | – | 1 | 0 |
| 1 | 86% | 82% | 0.56 | 42% | 1.31/1.60/1.42 | 5.48 | – | 1 | 2 |
| 2 | 82% | 80% | 0.47 | 35% | 1.08/1.23/1.00 | 4.33 | – | 1 | 4 |
| 4 | 72% | 72% | 0.32 | 24% | 0.56/0.79/0.67 | 2.61 | – | 2 | 4 |
| 6 | 53% | 54% | 0.19 | 16% | 0.29/0.42/0.44 | 1.72 | – | 2 | 4 |
| 10 | 15% | 22% | 0.10 | 10% | 0.04/0.12/0.15 | 0.41 | – | 2 | 4 |



## French


### Reference phrases (48 a voice): share of phrases at 100, at 95 or more, under 90; mean sounds shown different

| variant | Google =100 | Google ≥95 | Google <90 | Google diff | compact Mac =100 | compact Mac ≥95 | compact Mac <90 | compact Mac diff | Premium Mac =100 | Premium Mac ≥95 | Premium Mac <90 | Premium Mac diff |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| baseline | 81% | 83% | 17% | 0.29 | 75% | 79% | 21% | 0.52 | 75% | 79% | 21% | 0.46 |
| A-V1 | 85% | 85% | 15% | 0.19 | 81% | 85% | 15% | 0.33 | 83% | 85% | 15% | 0.23 |
| A-V2 | 81% | 83% | 17% | 0.25 | 77% | 81% | 19% | 0.46 | 79% | 83% | 17% | 0.35 |
| A-V3 | 81% | 83% | 17% | 0.23 | 79% | 83% | 17% | 0.42 | 79% | 85% | 15% | 0.31 |
| A-ins edges | 83% | 85% | 15% | 0.25 | 75% | 79% | 19% | 0.50 | 75% | 79% | 21% | 0.44 |
| A-ins lr tau=0 | 81% | 83% | 17% | 0.29 | 75% | 79% | 19% | 0.50 | 75% | 81% | 19% | 0.44 |
| A-ins lr tau=2 | 83% | 85% | 15% | 0.27 | 77% | 81% | 17% | 0.48 | 77% | 83% | 17% | 0.38 |
| A5-unjudged | 81% | 83% | 17% | 0.29 | 77% | 79% | 21% | 0.50 | 75% | 79% | 21% | 0.46 |
| A5-phoneme | 81% | 83% | 17% | 0.29 | 77% | 79% | 21% | 0.50 | 75% | 79% | 21% | 0.46 |
| A5-phoneme+lr tau=0 | 81% | 83% | 17% | 0.29 | 77% | 79% | 21% | 0.50 | 75% | 79% | 21% | 0.46 |
| A5-phoneme+lr tau=2 | 81% | 83% | 17% | 0.29 | 77% | 79% | 21% | 0.50 | 75% | 79% | 21% | 0.46 |
| A5-phoneme+lr tau=4 | 81% | 83% | 17% | 0.29 | 77% | 79% | 21% | 0.50 | 75% | 79% | 21% | 0.46 |
| A-converse | 79% | 81% | 17% | 0.33 | 73% | 77% | 23% | 0.65 | 75% | 79% | 21% | 0.46 |
| A-zero=equal | 81% | 83% | 17% | 0.27 | 75% | 79% | 21% | 0.50 | 75% | 79% | 21% | 0.44 |
| B-stretched | 79% | 81% | 17% | 0.29 | 73% | 75% | 23% | 0.52 | 75% | 75% | 23% | 0.42 |
| B-linear | 83% | 90% | 4% | 0.29 | 77% | 85% | 8% | 0.52 | 77% | 83% | 2% | 0.46 |
| B-stretched+linear | 81% | 90% | 4% | 0.29 | 75% | 83% | 12% | 0.52 | 75% | 81% | 8% | 0.42 |
| B-deletions | 81% | 83% | 17% | 0.40 | 77% | 81% | 19% | 0.62 | 77% | 81% | 19% | 0.50 |
| C-lv60 | 29% | 73% | 23% | 1.98 | 19% | 48% | 48% | 2.29 | 8% | 33% | 50% | 2.56 |
| C-xlsr-fr | 12% | 48% | 42% | 2.38 | 21% | 52% | 46% | 1.96 | 23% | 51% | 38% | 2.40 |
| rec de | 81% | 83% | 17% | 0.23 | 79% | 81% | 19% | 0.42 | 79% | 83% | 17% | 0.33 |
| rec en | 81% | 83% | 17% | 0.23 | 79% | 81% | 19% | 0.42 | 79% | 83% | 17% | 0.33 |
| rec fr | 81% | 83% | 17% | 0.23 | 79% | 81% | 19% | 0.42 | 79% | 83% | 17% | 0.33 |
| E-check score | 8% | 77% | 10% | – | 0% | 62% | 17% | – | 2% | 67% | 15% | – |
| A-V4 tau=0 | 81% | 83% | 17% | 0.23 | 77% | 81% | 19% | 0.44 | 77% | 81% | 19% | 0.33 |
| A-V4 tau=2 | 85% | 85% | 15% | 0.19 | 83% | 85% | 15% | 0.23 | 83% | 83% | 15% | 0.21 |
| combo clean | 81% | 83% | 17% | 0.27 | 77% | 79% | 21% | 0.48 | 75% | 79% | 21% | 0.44 |
| combo clean+V1 | 85% | 85% | 15% | 0.17 | 83% | 85% | 15% | 0.31 | 83% | 85% | 15% | 0.21 |
| combo clean+V2 | 81% | 83% | 17% | 0.23 | 79% | 81% | 19% | 0.42 | 79% | 83% | 17% | 0.33 |
| combo clean+V3 | 81% | 83% | 17% | 0.21 | 81% | 83% | 17% | 0.38 | 79% | 85% | 15% | 0.29 |
| combo clean+V4 tau=1 | 81% | 83% | 17% | 0.23 | 81% | 83% | 17% | 0.29 | 79% | 81% | 19% | 0.29 |
| combo clean+V4 tau=2 | 85% | 85% | 15% | 0.19 | 83% | 85% | 15% | 0.23 | 83% | 83% | 15% | 0.21 |
| combo clean+V2+ins tau=2 | 83% | 85% | 15% | 0.21 | 81% | 83% | 15% | 0.38 | 81% | 88% | 12% | 0.25 |
| combo clean+V2 keep deletions | 81% | 83% | 17% | 0.23 | 77% | 79% | 21% | 0.44 | 77% | 81% | 19% | 0.35 |
| combo phoneme+lr2+zero+V2 | 81% | 83% | 17% | 0.23 | 79% | 81% | 19% | 0.42 | 79% | 83% | 17% | 0.33 |
| combo phoneme+lr2+zero+V2 keep deletions | 81% | 83% | 17% | 0.23 | 77% | 79% | 21% | 0.44 | 77% | 81% | 19% | 0.35 |
| combo clean+V2 lv60 | 35% | 73% | 23% | 1.44 | 19% | 48% | 46% | 1.81 | 10% | 33% | 48% | 2.21 |
| combo phoneme+lr2+zero+V2 lv60 | 35% | 73% | 23% | 1.44 | 19% | 48% | 46% | 1.81 | 10% | 33% | 48% | 2.21 |
| rec de | 81% | 83% | 17% | 0.23 | 79% | 81% | 19% | 0.42 | 79% | 83% | 17% | 0.33 |
| rec en | 81% | 83% | 17% | 0.23 | 79% | 81% | 19% | 0.42 | 79% | 83% | 17% | 0.33 |
| rec fr | 81% | 83% | 17% | 0.23 | 79% | 81% | 19% | 0.42 | 79% | 83% | 17% | 0.33 |


### Near misses (voice says B, target A; one edit) and their positives (voice says A)

| variant | n | detected at the place | below 100 | mean score | false elsewhere | detected, sound judged | detected, sound unjudged (n) | positives below 100 | positives mean | positives diff |
|---|---|---|---|---|---|---|---|---|---|---|
| baseline | 705 | 96% | 98% | 77.1 | 0.40 | 96% | – | 44% | 90.3 | 0.62 |
| A-V1 | 705 | 91% | 94% | 79.7 | 0.23 | 91% | – | 27% | 94.1 | 0.35 |
| A-V2 | 705 | 96% | 98% | 77.2 | 0.38 | 96% | – | 43% | 90.6 | 0.59 |
| A-V3 | 705 | 94% | 96% | 77.9 | 0.34 | 94% | – | 40% | 91.2 | 0.54 |
| A-ins edges | 705 | 83% | 88% | 82.6 | 0.37 | 83% | – | 43% | 91.3 | 0.60 |
| A-ins lr tau=0 | 705 | 96% | 98% | 77.3 | 0.39 | 96% | – | 44% | 90.8 | 0.61 |
| A-ins lr tau=2 | 705 | 95% | 98% | 78.4 | 0.37 | 95% | – | 43% | 91.3 | 0.60 |
| A5-unjudged | 705 | 96% | 98% | 77.1 | 0.40 | 96% | – | 44% | 90.3 | 0.62 |
| A5-phoneme | 705 | 96% | 98% | 77.1 | 0.40 | 96% | – | 44% | 90.3 | 0.62 |
| A5-phoneme+lr tau=0 | 705 | 96% | 98% | 77.1 | 0.40 | 96% | – | 44% | 90.3 | 0.62 |
| A5-phoneme+lr tau=2 | 705 | 96% | 98% | 77.1 | 0.40 | 96% | – | 44% | 90.3 | 0.62 |
| A5-phoneme+lr tau=4 | 705 | 96% | 98% | 77.1 | 0.40 | 96% | – | 44% | 90.3 | 0.62 |
| A-converse | 705 | 96% | 98% | 76.2 | 0.45 | 96% | – | 44% | 90.3 | 0.63 |
| A-zero=equal | 705 | 96% | 98% | 77.1 | 0.39 | 96% | – | 44% | 90.3 | 0.61 |
| B-stretched | 705 | 96% | 98% | 57.7 | 0.40 | 96% | – | 46% | 82.4 | 0.62 |
| B-linear | 705 | 96% | 98% | 80.4 | 0.40 | 96% | – | 43% | 91.3 | 0.62 |
| B-stretched+linear | 705 | 96% | 98% | 61.4 | 0.40 | 96% | – | 46% | 83.7 | 0.62 |
| B-deletions | 705 | 96% | 98% | 77.2 | 0.41 | 96% | – | 44% | 90.5 | 0.63 |
| C-lv60 | 739 | 91% | 99% | 67.4 | 1.27 | 91% | – | 85% | 75.8 | 1.76 |
| C-xlsr-fr | 733 | 95% | 100% | 71.2 | 1.09 | 95% | – | 80% | 80.5 | 1.55 |
| rec de | 705 | 96% | 98% | 77.2 | 0.37 | 96% | – | 43% | 90.6 | 0.58 |
| rec en | 705 | 96% | 98% | 77.2 | 0.37 | 96% | – | 43% | 90.6 | 0.58 |
| rec fr | 705 | 96% | 98% | 77.2 | 0.37 | 96% | – | 43% | 90.6 | 0.58 |
| E-check score | 705 | 98% | 99% | 48.6 | – | 98% | – | 92% | 74.3 | – |
| A-V4 tau=0 | 705 | 96% | 97% | 78.2 | 0.36 | 96% | – | 41% | 91.4 | 0.57 |
| A-V4 tau=2 | 705 | 91% | 94% | 80.7 | 0.22 | 91% | – | 27% | 94.7 | 0.34 |
| combo clean | 705 | 96% | 98% | 77.1 | 0.39 | 96% | – | 44% | 90.3 | 0.61 |
| combo clean+V1 | 705 | 91% | 94% | 79.7 | 0.23 | 91% | – | 26% | 94.1 | 0.34 |
| combo clean+V2 | 705 | 96% | 98% | 77.2 | 0.37 | 96% | – | 43% | 90.6 | 0.58 |
| combo clean+V3 | 705 | 94% | 96% | 77.9 | 0.34 | 94% | – | 40% | 91.2 | 0.53 |
| combo clean+V4 tau=1 | 705 | 94% | 96% | 79.1 | 0.28 | 94% | – | 34% | 93.1 | 0.45 |
| combo clean+V4 tau=2 | 705 | 91% | 94% | 80.7 | 0.22 | 91% | – | 27% | 94.7 | 0.33 |
| combo clean+V2+ins tau=2 | 705 | 95% | 97% | 78.5 | 0.35 | 95% | – | 42% | 91.6 | 0.55 |
| combo clean+V2 keep deletions | 705 | 96% | 98% | 77.1 | 0.38 | 96% | – | 43% | 90.5 | 0.58 |
| combo phoneme+lr2+zero+V2 | 705 | 96% | 98% | 77.2 | 0.37 | 96% | – | 43% | 90.6 | 0.58 |
| combo phoneme+lr2+zero+V2 keep deletions | 705 | 96% | 98% | 77.1 | 0.38 | 96% | – | 43% | 90.5 | 0.58 |
| combo clean+V2 lv60 | 739 | 90% | 98% | 67.9 | 1.16 | 90% | – | 83% | 76.5 | 1.61 |
| combo phoneme+lr2+zero+V2 lv60 | 739 | 90% | 98% | 67.9 | 1.16 | 90% | – | 83% | 76.5 | 1.61 |
| rec de | 705 | 96% | 98% | 77.2 | 0.37 | 96% | – | 43% | 90.6 | 0.58 |
| rec en | 705 | 96% | 98% | 77.2 | 0.37 | 96% | – | 43% | 90.6 | 0.58 |
| rec fr | 705 | 96% | 98% | 77.2 | 0.37 | 96% | – | 43% | 90.6 | 0.58 |


### Native speech (Common Phone test speakers) and the roles-reversed proxy

| variant | n | =100 | ≥95 | <90 | mean score | diff | roles reversed: n | detected | false elsewhere |
|---|---|---|---|---|---|---|---|---|---|
| baseline | 300 | 50% | 63% | 29% | 93.0 | 1.52 | 294 | 99% | 1.50 |
| A-V1 | 300 | 64% | 74% | 18% | 96.0 | 0.70 | 294 | 99% | 0.68 |
| A-V2 | 300 | 52% | 66% | 27% | 93.5 | 1.37 | 294 | 99% | 1.33 |
| A-V3 | 300 | 54% | 69% | 24% | 94.6 | 1.16 | 294 | 99% | 1.12 |
| A-ins edges | 300 | 50% | 63% | 27% | 93.3 | 1.49 | 294 | 99% | 1.48 |
| A-ins lr tau=0 | 300 | 50% | 64% | 26% | 93.3 | 1.49 | 294 | 99% | 1.47 |
| A-ins lr tau=2 | 300 | 52% | 66% | 25% | 93.8 | 1.44 | 294 | 99% | 1.43 |
| A5-unjudged | 300 | 50% | 63% | 29% | 93.0 | 1.50 | 294 | 99% | 1.48 |
| A5-phoneme | 300 | 50% | 63% | 29% | 93.0 | 1.50 | 294 | 99% | 1.48 |
| A5-phoneme+lr tau=0 | 300 | 50% | 63% | 29% | 93.0 | 1.50 | 294 | 99% | 1.48 |
| A5-phoneme+lr tau=2 | 300 | 50% | 63% | 29% | 93.0 | 1.50 | 294 | 99% | 1.48 |
| A5-phoneme+lr tau=4 | 300 | 50% | 63% | 29% | 93.0 | 1.50 | 294 | 99% | 1.48 |
| A-converse | 300 | 49% | 62% | 30% | 92.5 | 1.64 | 294 | 99% | 1.60 |
| A-zero=equal | 300 | 50% | 63% | 29% | 93.0 | 1.47 | 294 | 99% | 1.45 |
| B-stretched | 300 | 47% | 54% | 36% | 88.9 | 1.49 | 294 | 99% | 1.45 |
| B-linear | 300 | 62% | 94% | 2% | 98.5 | 1.52 | 294 | 99% | 1.50 |
| B-stretched+linear | 300 | 50% | 85% | 5% | 97.4 | 1.49 | 294 | 99% | 1.45 |
| B-deletions | 300 | 51% | 64% | 27% | 93.7 | 1.71 | 294 | 99% | 1.81 |
| C-lv60 | 300 | 3% | 12% | 84% | 73.5 | 6.88 | 294 | 99% | 6.67 |
| C-xlsr-fr | 300 | 7% | 20% | 74% | 79.5 | 5.42 | 294 | 99% | 5.28 |
| rec de | 300 | 52% | 66% | 27% | 93.5 | 1.31 | 294 | 99% | 1.27 |
| rec en | 300 | 52% | 66% | 27% | 93.5 | 1.31 | 294 | 99% | 1.27 |
| rec fr | 300 | 52% | 66% | 27% | 93.5 | 1.31 | 294 | 99% | 1.27 |
| E-check score | 300 | 6% | 68% | 14% | 94.8 | – | 294 | 100% | – |
| A-V4 tau=0 | 300 | 54% | 70% | 23% | 94.5 | 1.21 | 294 | 98% | 1.15 |
| A-V4 tau=2 | 300 | 67% | 77% | 16% | 96.4 | 0.63 | 294 | 98% | 0.59 |
| combo clean | 300 | 50% | 63% | 29% | 93.0 | 1.46 | 294 | 99% | 1.43 |
| combo clean+V1 | 300 | 64% | 74% | 18% | 96.0 | 0.67 | 294 | 99% | 0.64 |
| combo clean+V2 | 300 | 52% | 66% | 27% | 93.5 | 1.31 | 294 | 99% | 1.27 |
| combo clean+V3 | 300 | 54% | 69% | 24% | 94.6 | 1.10 | 294 | 99% | 1.05 |
| combo clean+V4 tau=1 | 300 | 63% | 74% | 19% | 95.6 | 0.84 | 294 | 98% | 0.80 |
| combo clean+V4 tau=2 | 300 | 67% | 77% | 16% | 96.4 | 0.60 | 294 | 98% | 0.56 |
| combo clean+V2+ins tau=2 | 300 | 55% | 70% | 23% | 94.4 | 1.24 | 294 | 99% | 1.20 |
| combo clean+V2 keep deletions | 300 | 50% | 63% | 29% | 93.1 | 1.35 | 294 | 99% | 1.31 |
| combo phoneme+lr2+zero+V2 | 300 | 52% | 66% | 27% | 93.5 | 1.31 | 294 | 99% | 1.27 |
| combo phoneme+lr2+zero+V2 keep deletions | 300 | 50% | 63% | 29% | 93.1 | 1.35 | 294 | 99% | 1.31 |
| combo clean+V2 lv60 | 300 | 4% | 14% | 81% | 76.5 | 5.24 | 294 | 92% | 5.00 |
| combo phoneme+lr2+zero+V2 lv60 | 300 | 4% | 14% | 81% | 76.5 | 5.24 | 294 | 92% | 5.00 |
| rec de | 300 | 52% | 66% | 27% | 93.5 | 1.31 | 294 | 99% | 1.27 |
| rec en | 300 | 52% | 66% | 27% | 93.5 | 1.31 | 294 | 99% | 1.27 |
| rec fr | 300 | 52% | 66% | 27% | 93.5 | 1.31 | 294 | 99% | 1.27 |


### Learner takes (French), by the owner's verdict

| variant | fair: n | mean | diff | changed | harsh: n | mean | diff | fewer diff | more diff | generous: n | mean | diff | unjudged: n | mean | diff |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| baseline | 9 | 95.8 | 0.89 | 0 | 3 | 84.3 | 1.33 | 0 | 0 | 0 | – | – | 2 | 100.0 | 0.00 |
| A-V1 | 9 | 99.9 | 0.11 | 1 | 3 | 85.7 | 1.00 | 1 | 0 | 0 | – | – | 2 | 100.0 | 0.00 |
| A-V2 | 9 | 96.4 | 0.78 | 1 | 3 | 84.3 | 1.33 | 0 | 0 | 0 | – | – | 2 | 100.0 | 0.00 |
| A-V3 | 9 | 99.9 | 0.11 | 1 | 3 | 84.3 | 1.33 | 0 | 0 | 0 | – | – | 2 | 100.0 | 0.00 |
| A-ins edges | 9 | 95.8 | 0.89 | 0 | 3 | 84.3 | 1.33 | 0 | 0 | 0 | – | – | 2 | 100.0 | 0.00 |
| A-ins lr tau=0 | 9 | 95.8 | 0.89 | 0 | 3 | 84.3 | 1.33 | 0 | 0 | 0 | – | – | 2 | 100.0 | 0.00 |
| A-ins lr tau=2 | 9 | 95.8 | 0.89 | 0 | 3 | 84.3 | 1.33 | 0 | 0 | 0 | – | – | 2 | 100.0 | 0.00 |
| A5-unjudged | 9 | 95.8 | 0.89 | 0 | 3 | 84.3 | 1.33 | 0 | 0 | 0 | – | – | 2 | 100.0 | 0.00 |
| A5-phoneme | 9 | 95.8 | 0.89 | 0 | 3 | 84.3 | 1.33 | 0 | 0 | 0 | – | – | 2 | 100.0 | 0.00 |
| A5-phoneme+lr tau=0 | 9 | 95.8 | 0.89 | 0 | 3 | 84.3 | 1.33 | 0 | 0 | 0 | – | – | 2 | 100.0 | 0.00 |
| A5-phoneme+lr tau=2 | 9 | 95.8 | 0.89 | 0 | 3 | 84.3 | 1.33 | 0 | 0 | 0 | – | – | 2 | 100.0 | 0.00 |
| A5-phoneme+lr tau=4 | 9 | 95.8 | 0.89 | 0 | 3 | 84.3 | 1.33 | 0 | 0 | 0 | – | – | 2 | 100.0 | 0.00 |
| A-converse | 9 | 95.8 | 0.89 | 0 | 3 | 82.0 | 1.67 | 0 | 1 | 0 | – | – | 2 | 100.0 | 0.00 |
| A-zero=equal | 9 | 95.8 | 0.89 | 0 | 3 | 84.3 | 1.33 | 0 | 0 | 0 | – | – | 2 | 100.0 | 0.00 |
| B-stretched | 9 | 90.3 | 0.56 | 1 | 3 | 71.7 | 1.33 | 0 | 0 | 0 | – | – | 2 | 100.0 | 0.00 |
| B-linear | 9 | 97.8 | 0.89 | 1 | 3 | 87.3 | 1.33 | 0 | 0 | 0 | – | – | 2 | 100.0 | 0.00 |
| B-stretched+linear | 9 | 94.9 | 0.56 | 1 | 3 | 79.3 | 1.33 | 0 | 0 | 0 | – | – | 2 | 100.0 | 0.00 |
| B-deletions | 9 | 95.8 | 0.89 | 0 | 3 | 84.3 | 1.33 | 0 | 0 | 0 | – | – | 2 | 100.0 | 0.00 |
| C-lv60 | 9 | 83.8 | 2.44 | 8 | 3 | 94.0 | 2.00 | 0 | 1 | 0 | – | – | 2 | 92.0 | 2.00 |
| C-xlsr-fr | 9 | 81.6 | 2.22 | 7 | 3 | 85.7 | 2.33 | 0 | 2 | 0 | – | – | 2 | 90.0 | 2.50 |
| rec de | 9 | 96.4 | 0.78 | 1 | 3 | 84.3 | 1.33 | 0 | 0 | 0 | – | – | 2 | 100.0 | 0.00 |
| rec en | 9 | 96.4 | 0.78 | 1 | 3 | 84.3 | 1.33 | 0 | 0 | 0 | – | – | 2 | 100.0 | 0.00 |
| rec fr | 9 | 96.4 | 0.78 | 1 | 3 | 84.3 | 1.33 | 0 | 0 | 0 | – | – | 2 | 100.0 | 0.00 |
| E-check score | 9 | 92.8 | – | – | 3 | 66.0 | – | – | – | 0 | – | – | 2 | 95.0 | – |
| A-V4 tau=0 | 9 | 99.9 | 0.11 | 1 | 3 | 84.3 | 1.33 | 0 | 0 | 0 | – | – | 2 | 100.0 | 0.00 |
| A-V4 tau=2 | 9 | 99.9 | 0.11 | 1 | 3 | 98.7 | 0.33 | 2 | 0 | 0 | – | – | 2 | 100.0 | 0.00 |
| combo clean | 9 | 95.8 | 0.89 | 0 | 3 | 84.3 | 1.33 | 0 | 0 | 0 | – | – | 2 | 100.0 | 0.00 |
| combo clean+V1 | 9 | 99.9 | 0.11 | 1 | 3 | 85.7 | 1.00 | 1 | 0 | 0 | – | – | 2 | 100.0 | 0.00 |
| combo clean+V2 | 9 | 96.4 | 0.78 | 1 | 3 | 84.3 | 1.33 | 0 | 0 | 0 | – | – | 2 | 100.0 | 0.00 |
| combo clean+V3 | 9 | 99.9 | 0.11 | 1 | 3 | 84.3 | 1.33 | 0 | 0 | 0 | – | – | 2 | 100.0 | 0.00 |
| combo clean+V4 tau=1 | 9 | 99.9 | 0.11 | 1 | 3 | 98.3 | 0.67 | 1 | 0 | 0 | – | – | 2 | 100.0 | 0.00 |
| combo clean+V4 tau=2 | 9 | 99.9 | 0.11 | 1 | 3 | 98.7 | 0.33 | 2 | 0 | 0 | – | – | 2 | 100.0 | 0.00 |
| combo clean+V2+ins tau=2 | 9 | 96.4 | 0.78 | 1 | 3 | 84.3 | 1.33 | 0 | 0 | 0 | – | – | 2 | 100.0 | 0.00 |
| combo clean+V2 keep deletions | 9 | 96.4 | 0.78 | 1 | 3 | 84.3 | 1.33 | 0 | 0 | 0 | – | – | 2 | 100.0 | 0.00 |
| combo phoneme+lr2+zero+V2 | 9 | 96.4 | 0.78 | 1 | 3 | 84.3 | 1.33 | 0 | 0 | 0 | – | – | 2 | 100.0 | 0.00 |
| combo phoneme+lr2+zero+V2 keep deletions | 9 | 96.4 | 0.78 | 1 | 3 | 84.3 | 1.33 | 0 | 0 | 0 | – | – | 2 | 100.0 | 0.00 |
| combo clean+V2 lv60 | 9 | 85.3 | 1.89 | 8 | 3 | 94.0 | 2.00 | 0 | 1 | 0 | – | – | 2 | 92.0 | 2.00 |
| combo phoneme+lr2+zero+V2 lv60 | 9 | 85.3 | 1.89 | 8 | 3 | 94.0 | 2.00 | 0 | 1 | 0 | – | – | 2 | 92.0 | 2.00 |
| rec de | 9 | 96.4 | 0.78 | 1 | 3 | 84.3 | 1.33 | 0 | 0 | 0 | – | – | 2 | 100.0 | 0.00 |
| rec en | 9 | 96.4 | 0.78 | 1 | 3 | 84.3 | 1.33 | 0 | 0 | 0 | – | – | 2 | 100.0 | 0.00 |
| rec fr | 9 | 96.4 | 0.78 | 1 | 3 | 84.3 | 1.33 | 0 | 0 | 0 | – | – | 2 | 100.0 | 0.00 |


### V4: the likelihood-ratio threshold τ (keep an edit iff log P(edited target) − log P(target) ≥ τ)

| τ | near miss detected | near miss below 100 | false elsewhere | positives below 100 | reference diff (G/M/P) | native diff | roles reversed detected | harsh: fewer diff | fair: changed |
|---|---|---|---|---|---|---|---|---|---|
| greedy (baseline) | 96% | 98% | 0.40 | 44% | 0.29/0.52/0.46 | 1.52 | 99% | 0 | 0 |
| -6 | 96% | 98% | 0.40 | 44% | 0.29/0.52/0.38 | 1.47 | 99% | 0 | 1 |
| -4 | 96% | 98% | 0.39 | 44% | 0.29/0.50/0.38 | 1.41 | 99% | 0 | 1 |
| -2 | 96% | 98% | 0.39 | 43% | 0.29/0.48/0.35 | 1.32 | 99% | 0 | 1 |
| -1 | 96% | 98% | 0.38 | 43% | 0.25/0.46/0.35 | 1.27 | 99% | 0 | 1 |
| 0 | 96% | 97% | 0.36 | 41% | 0.23/0.44/0.33 | 1.21 | 98% | 0 | 1 |
| 1 | 94% | 96% | 0.29 | 34% | 0.23/0.29/0.29 | 0.88 | 98% | 1 | 1 |
| 2 | 91% | 94% | 0.22 | 27% | 0.19/0.23/0.21 | 0.63 | 98% | 2 | 1 |
| 4 | 81% | 85% | 0.13 | 16% | 0.15/0.15/0.19 | 0.40 | 94% | 2 | 1 |
| 6 | 66% | 69% | 0.08 | 8% | 0.15/0.15/0.19 | 0.29 | 85% | 2 | 1 |
| 10 | 36% | 40% | 0.05 | 5% | 0.12/0.10/0.17 | 0.19 | 55% | 2 | 1 |



## Learner takes, all languages, by verdict

| variant | fair: n | mean | diff | changed | harsh: n | mean | diff | fewer diff | more diff | generous: n | mean | diff | unjudged: n | mean | diff |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| baseline | 33 | 92.1 | 1.54 | 0 | 23 | 83.3 | 2.26 | 0 | 0 | 2 | 88.5 | 2.50 | 20 | 81.5 | 2.55 |
| A-V1 | 33 | 95.1 | 0.58 | 19 | 23 | 86.5 | 1.65 | 12 | 0 | 2 | 100.0 | 1.00 | 20 | 88.7 | 0.95 |
| A-V2 | 33 | 93.7 | 1.03 | 14 | 23 | 85.7 | 1.96 | 7 | 0 | 2 | 100.0 | 1.00 | 20 | 84.9 | 1.75 |
| A-V3 | 33 | 94.7 | 0.79 | 15 | 23 | 86.0 | 1.87 | 8 | 0 | 2 | 100.0 | 1.00 | 20 | 85.8 | 1.45 |
| A-ins edges | 33 | 92.1 | 1.54 | 0 | 23 | 84.1 | 2.22 | 1 | 0 | 2 | 88.5 | 2.50 | 20 | 84.1 | 2.35 |
| A-ins lr tau=0 | 33 | 92.1 | 1.54 | 0 | 23 | 83.3 | 2.26 | 0 | 0 | 2 | 88.5 | 2.50 | 20 | 81.5 | 2.55 |
| A-ins lr tau=2 | 33 | 93.4 | 1.49 | 2 | 23 | 85.8 | 2.09 | 4 | 0 | 2 | 88.5 | 2.50 | 20 | 83.5 | 2.45 |
| A5-unjudged | 33 | 93.4 | 1.33 | 6 | 23 | 84.4 | 1.91 | 7 | 0 | 2 | 88.5 | 2.00 | 20 | 81.5 | 2.50 |
| A5-phoneme | 33 | 92.0 | 1.49 | 6 | 23 | 83.2 | 2.17 | 2 | 0 | 2 | 88.0 | 2.50 | 20 | 81.5 | 2.55 |
| A5-phoneme+lr tau=0 | 33 | 92.0 | 1.49 | 6 | 23 | 83.2 | 2.17 | 2 | 0 | 2 | 88.0 | 2.50 | 20 | 81.5 | 2.55 |
| A5-phoneme+lr tau=2 | 33 | 92.1 | 1.46 | 6 | 23 | 83.3 | 2.09 | 4 | 0 | 2 | 88.5 | 2.00 | 20 | 81.5 | 2.50 |
| A5-phoneme+lr tau=4 | 33 | 92.1 | 1.46 | 6 | 23 | 83.3 | 2.04 | 5 | 0 | 2 | 88.5 | 2.00 | 20 | 81.5 | 2.50 |
| A-converse | 33 | 90.9 | 1.61 | 2 | 23 | 81.4 | 2.44 | 0 | 4 | 2 | 88.5 | 2.50 | 20 | 80.5 | 2.60 |
| A-zero=equal | 33 | 92.1 | 1.33 | 7 | 23 | 83.3 | 2.17 | 2 | 0 | 2 | 88.5 | 1.50 | 20 | 81.5 | 2.30 |
| B-stretched | 33 | 83.8 | 1.46 | 17 | 23 | 72.4 | 2.26 | 0 | 0 | 2 | 86.0 | 2.50 | 20 | 68.8 | 2.40 |
| B-linear | 33 | 96.5 | 1.54 | 17 | 23 | 91.7 | 2.26 | 0 | 0 | 2 | 94.5 | 2.50 | 20 | 90.0 | 2.55 |
| B-stretched+linear | 33 | 91.6 | 1.46 | 20 | 23 | 84.8 | 2.26 | 0 | 0 | 2 | 93.5 | 2.50 | 20 | 82.7 | 2.40 |
| B-deletions | 33 | 93.5 | 1.64 | 3 | 23 | 84.8 | 2.26 | 0 | 0 | 2 | 88.5 | 2.50 | 20 | 82.7 | 2.50 |
| C-lv60 | 33 | 85.3 | 2.36 | 29 | 23 | 79.4 | 3.30 | 1 | 11 | 2 | 88.5 | 2.50 | 20 | 78.5 | 3.05 |
| C-xlsr-fr | 33 | 88.2 | 1.91 | 7 | 23 | 83.5 | 2.39 | 0 | 2 | 2 | 88.5 | 2.50 | 20 | 80.5 | 2.80 |
| rec de | 33 | 93.7 | 0.88 | 15 | 23 | 85.6 | 1.78 | 10 | 0 | 2 | 100.0 | 0.00 | 20 | 84.9 | 1.65 |
| rec en | 33 | 95.1 | 0.76 | 15 | 23 | 86.7 | 1.61 | 11 | 0 | 2 | 100.0 | 0.00 | 20 | 84.9 | 1.65 |
| rec fr | 33 | 95.1 | 0.76 | 15 | 23 | 86.7 | 1.61 | 11 | 0 | 2 | 100.0 | 0.00 | 20 | 84.9 | 1.65 |
| E-check score | 33 | 85.0 | – | – | 23 | 78.4 | – | – | – | 2 | 87.0 | – | 20 | 75.1 | – |
| A-V4 tau=0 | 33 | 93.2 | 1.24 | 4 | 23 | 84.6 | 2.09 | 3 | 0 | 2 | 99.5 | 2.00 | 20 | 84.8 | 2.05 |
| A-V4 tau=2 | 33 | 94.9 | 0.76 | 16 | 23 | 86.7 | 1.56 | 13 | 0 | 2 | 100.0 | 1.00 | 20 | 86.9 | 1.20 |
| combo clean | 33 | 93.4 | 1.12 | 10 | 23 | 84.4 | 1.83 | 8 | 0 | 2 | 88.5 | 1.00 | 20 | 81.5 | 2.25 |
| combo clean+V1 | 33 | 96.5 | 0.36 | 20 | 23 | 87.5 | 1.30 | 16 | 0 | 2 | 100.0 | 0.00 | 20 | 88.7 | 0.90 |
| combo clean+V2 | 33 | 95.1 | 0.76 | 15 | 23 | 86.7 | 1.61 | 11 | 0 | 2 | 100.0 | 0.00 | 20 | 84.9 | 1.65 |
| combo clean+V3 | 33 | 96.1 | 0.55 | 16 | 23 | 87.1 | 1.52 | 12 | 0 | 2 | 100.0 | 0.00 | 20 | 85.8 | 1.40 |
| combo clean+V4 tau=1 | 33 | 94.9 | 0.64 | 17 | 23 | 87.5 | 1.48 | 14 | 0 | 2 | 100.0 | 0.00 | 20 | 86.5 | 1.55 |
| combo clean+V4 tau=2 | 33 | 95.1 | 0.58 | 18 | 23 | 87.6 | 1.39 | 15 | 0 | 2 | 100.0 | 0.00 | 20 | 86.9 | 1.15 |
| combo clean+V2+ins tau=2 | 33 | 96.4 | 0.70 | 16 | 23 | 89.2 | 1.44 | 12 | 0 | 2 | 100.0 | 0.00 | 20 | 86.9 | 1.55 |
| combo clean+V2 keep deletions | 33 | 93.9 | 0.82 | 15 | 23 | 85.3 | 1.70 | 11 | 0 | 2 | 89.0 | 0.50 | 20 | 84.0 | 1.70 |
| combo phoneme+lr2+zero+V2 | 33 | 93.7 | 0.88 | 15 | 23 | 85.6 | 1.78 | 10 | 0 | 2 | 100.0 | 0.00 | 20 | 84.9 | 1.65 |
| combo phoneme+lr2+zero+V2 keep deletions | 33 | 92.5 | 0.94 | 15 | 23 | 84.2 | 1.87 | 9 | 0 | 2 | 89.0 | 0.50 | 20 | 84.0 | 1.70 |
| combo clean+V2 lv60 | 33 | 88.2 | 1.42 | 29 | 23 | 82.8 | 2.39 | 8 | 6 | 2 | 100.0 | 0.00 | 20 | 81.2 | 2.50 |
| combo phoneme+lr2+zero+V2 lv60 | 33 | 88.0 | 1.54 | 29 | 23 | 82.6 | 2.52 | 7 | 7 | 2 | 99.5 | 0.50 | 20 | 81.2 | 2.50 |
| rec de | 33 | 93.7 | 0.88 | 15 | 23 | 85.6 | 1.78 | 10 | 0 | 2 | 100.0 | 0.00 | 20 | 84.9 | 1.65 |
| rec en | 33 | 95.1 | 0.76 | 15 | 23 | 86.7 | 1.61 | 11 | 0 | 2 | 100.0 | 0.00 | 20 | 84.9 | 1.65 |
| rec fr | 33 | 95.1 | 0.76 | 15 | 23 | 86.7 | 1.61 | 11 | 0 | 2 | 100.0 | 0.00 | 20 | 84.9 | 1.65 |


## D: understood (share of items taken as understood)

INFLATION = near misses (the voice said B, the target is A) taken as understood: it should be low.  Positives = the voice said the target word: it should be high.


| variant | English reference | English positives | English archive | English INFLATION | French reference | French positives | French archive | French INFLATION | German reference | German positives | German archive | German INFLATION |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| baseline | 98% | 76% | 89% | 2% | 92% | 54% | 79% | 2% | 95% | 68% | 85% | 1% |
| D-prompt | 99% | 97% | 89% | 19% | 100% | 80% | 100% | 13% | 100% | 93% | 96% | 25% |
| D-tf m=0 | 76% | 72% | 67% | 2% | 84% | 42% | 86% | 2% | 92% | 69% | 82% | 2% |
| D-either m=0 | 98% | 79% | 89% | 2% | 94% | 60% | 93% | 3% | 97% | 71% | 89% | 2% |
| D-tf m=1 | 80% | 79% | 67% | 3% | 89% | 51% | 93% | 3% | 95% | 75% | 87% | 3% |
| D-either m=1 | 98% | 83% | 89% | 3% | 97% | 64% | 93% | 4% | 97% | 77% | 93% | 3% |
| D-tf m=2 | 82% | 85% | 67% | 4% | 94% | 59% | 100% | 5% | 97% | 81% | 93% | 6% |
| D-either m=2 | 98% | 87% | 89% | 4% | 98% | 68% | 100% | 6% | 98% | 82% | 95% | 6% |
| D-tf m=3 | 85% | 89% | 67% | 8% | 96% | 68% | 100% | 10% | 98% | 85% | 93% | 11% |
| D-either m=3 | 98% | 90% | 89% | 8% | 99% | 75% | 100% | 11% | 98% | 86% | 95% | 11% |
| D-tf m=5 | 88% | 96% | 67% | 25% | 97% | 79% | 100% | 21% | 99% | 92% | 96% | 28% |
| D-either m=5 | 99% | 96% | 89% | 25% | 99% | 82% | 100% | 22% | 99% | 92% | 98% | 28% |
| D-tf m=8 | 92% | 98% | 67% | 57% | 99% | 87% | 100% | 50% | 99% | 95% | 98% | 60% |
| D-either m=8 | 99% | 98% | 89% | 57% | 100% | 88% | 100% | 50% | 99% | 95% | 98% | 60% |


## Reference voices: which one the recommended analysis agrees with

Per language, under the recommended configuration: the 48 reference phrases a voice (share at 100, at 95 or more, under 90, mean sounds shown different) and the near-miss positives (single words said correctly); then paired comparisons on the SAME phrases / words (sign test, two-sided, ties left out); then the weighted error of the phone model's free reading against espeak (`lab/native_error.py`, no rule applied).


### German

| voice | phrases =100 | ≥95 | <90 | diff | words below 100 | words diff | free-reading weighted error (phrases) |
|---|---|---|---|---|---|---|---|
| Google | 73% | 88% | 12% | 0.50 | 40% (100) | 0.65 | 0.022 |
| Anna | 67% | 79% | 21% | 0.71 | 50% (252) | 0.77 | 0.027 |
| Petra (Premium) | 62% | 83% | 17% | 0.67 | 52% (250) | 0.89 | 0.028 |

- phrases: Google has fewer differences than Petra (Premium) on 12, more on 6, equal on 30 (sign test p = 0.238)
- phrases: Google has fewer differences than Anna on 11, more on 7, equal on 30 (sign test p = 0.481)
- phrases: Petra (Premium) has fewer differences than Anna on 9, more on 10, equal on 29 (sign test p = 1.000)
- words: Google has fewer differences than Petra (Premium) on 28, more on 17, equal on 55 (sign test p = 0.135)
- words: Google has fewer differences than Anna on 24, more on 14, equal on 62 (sign test p = 0.143)
- words: Petra (Premium) has fewer differences than Anna on 60, more on 68, equal on 124 (sign test p = 0.536)

### English

| voice | phrases =100 | ≥95 | <90 | diff | words below 100 | words diff | free-reading weighted error (phrases) |
|---|---|---|---|---|---|---|---|
| Google | 83% | 94% | 6% | 0.27 | 9% (98) | 0.12 | 0.050 |
| Daniel | 75% | 79% | 21% | 0.42 | 44% (244) | 0.64 | 0.058 |
| Serena (Premium) | 85% | 88% | 12% | 0.35 | 20% (242) | 0.29 | 0.053 |

- phrases: Google has fewer differences than Serena (Premium) on 5, more on 5, equal on 38 (sign test p = 1.000)
- phrases: Google has fewer differences than Daniel on 10, more on 3, equal on 35 (sign test p = 0.092)
- phrases: Serena (Premium) has fewer differences than Daniel on 8, more on 4, equal on 36 (sign test p = 0.388)
- words: Google has fewer differences than Serena (Premium) on 20, more on 6, equal on 72 (sign test p = 0.009)
- words: Google has fewer differences than Daniel on 37, more on 4, equal on 57 (sign test p = 0.000)
- words: Serena (Premium) has fewer differences than Daniel on 81, more on 22, equal on 142 (sign test p = 0.000)

### French

| voice | phrases =100 | ≥95 | <90 | diff | words below 100 | words diff | free-reading weighted error (phrases) |
|---|---|---|---|---|---|---|---|
| Google | 81% | 83% | 17% | 0.23 | 34% (97) | 0.42 | 0.017 |
| Thomas | 79% | 81% | 19% | 0.42 | 50% (204) | 0.68 | 0.036 |
| Audrey (Premium) | 79% | 83% | 17% | 0.33 | 41% (217) | 0.56 | 0.018 |

- phrases: Google has fewer differences than Audrey (Premium) on 5, more on 2, equal on 41 (sign test p = 0.453)
- phrases: Google has fewer differences than Thomas on 5, more on 1, equal on 42 (sign test p = 0.219)
- phrases: Audrey (Premium) has fewer differences than Thomas on 5, more on 4, equal on 39 (sign test p = 1.000)
- words: Google has fewer differences than Audrey (Premium) on 16, more on 13, equal on 68 (sign test p = 0.711)
- words: Google has fewer differences than Thomas on 29, more on 17, equal on 51 (sign test p = 0.104)
- words: Audrey (Premium) has fewer differences than Thomas on 60, more on 46, equal on 115 (sign test p = 0.206)


## C: the phone models' free reading against espeak (no rule applied)

Weighted error = d / (1000 × max(m, n)) with the live costs (1 − Miolingo's weighted similarity, linear normalisation); PER = unweighted edit distance / target length.  Mean over utterances.  The priors (Common Phone natives, Miolingo): German xlsr-53 0.043, lv-60 0.114; French Cnam 0.013, lv-60 0.072.

| language | model | natives n | natives weighted error | natives PER | Google | compact Mac | Premium Mac |
|---|---|---|---|---|---|---|---|
| German | xlsr-53 | 249 | 0.036 | 11.6% | 0.022 | 0.027 | 0.028 |
| German | lv-60 | 249 | 0.098 | 26.2% | 0.053 | 0.071 | 0.068 |
| English | xlsr-53 | 300 | 0.072 | 22.1% | 0.050 | 0.058 | 0.053 |
| English | lv-60 | 300 | 0.069 | 20.5% | 0.049 | 0.064 | 0.060 |
| French | Cnam | 300 | 0.017 | 4.0% | 0.017 | 0.036 | 0.018 |
| French | xlsr-53 | 300 | 0.053 | 15.1% | 0.072 | 0.064 | 0.072 |
| French | lv-60 | 300 | 0.068 | 18.3% | 0.045 | 0.078 | 0.070 |


## Method

**Pipeline per take** (`lab/analyse.py`): target sounds = `env.target_ipa` + the engine's `norm`; the greedy
heard sounds = the phone model's own decode cut as `env.hear` cuts it (cached log-probabilities, float16, with
the greedy path taken from the float32 logits); Miolingo's `sound_check.score` on the same log-probabilities with
the live token-to-sound mapping and the host's `flags_out` and the engine's flag filter; the engine's alignment of
target and greedy sounds (`lab/engine_py.py`, a copy of the engine's `dist`, `align` with its tie-break, `score`,
`byWord`, `columnsFrom`, `understood`); each difference of that alignment is an edit; the variant decides which
edits are kept; the final heard sequence is aligned and scored again.

**Validation before any variant was believed** (`var/lab/validate/`): (1) the replay of the 81 archived takes
through the live environment and the REAL compiled engine equals the lab's baseline in target, heard text, heard
sounds, flags, score, understood and columns for 81 of 81; (2) against the stored lines, every take written by the
present engine is equal, and the 9 that differ because a target changed since are equal when run with the stored
target; (3) the real engine fed the lab's cached answers (and, for a variant, the variant's final heard sounds and
its cost list and curve): see the validation section above (`var/lab/validate/engine-*.md`).

**Data**: ARCHIVE = learner takes (`var/archive/`), test-voice takes excluded, verdict = last judgement line;
REFERENCE = the 48 phrases a language in Google's voice, the compact Mac voice and the Premium Mac voice (anything
shown different is a false alarm by construction); NEAR MISSES = mined minimal pairs (one substitution, deletion or
insertion between espeak's readings of two words; German includes ü/u, ü/i, ö/o), the voice says B for target A,
with both directions and the positives (the voice says A); three voices (Google for a random third of the pairs);
NATIVE = Common Phone test speakers (accent of the variant's country; English partly train split), French
utterances with a typographic apostrophe skipped; ROLES REVERSED = the native audio with ONE target sound changed
to a typical English-speaker error from Miolingo's `english_l1_errors` (German also y→ʊ), detection = a
difference reported at that sound (none for English: Miolingo lists no such errors for English).

**Variants**: A: V1 keep an edit only where the check says `off`; V2 `check` or `off`; V3 `off`, or `check` with the
check's alternative equal to the greedy sound; V4 keep iff log P(target with this edit | audio) − log P(target |
audio) ≥ τ (CTC likelihoods, `sound_check._nll`), τ swept; insertions all / not at the edges / verified by the same
ratio; A5 for the `unreliable` sounds: baseline / unjudged / phoneme (and phoneme confirmed by the ratio);
converse; zero=equal (a pair the table makes free shown as the target sound).  B: stretched costs (Miolingo's
min(1, (4c)^0.6)); linear curve (division by the length); deletions priced by the accept list's "∅" weights (the
data suggested it: schwa deletion is the commonest English false difference); C: lv-60 for every language, xlsr-53
for French; D: the live rule, the prompted transcription, the teacher-forced log-probability of the phrase against
that of the free transcription within a margin m (tf), and free OR tf (either); E: 100 × mean p_ok.

**Priors** quoted beside these figures: on learner English (speechocean762, Miolingo branch
`origin/claude/mdd-benchmark-zipa`) the free transcription falsely rejects 26.6% of correctly said phones with
xlsr-53 (and finds 88% of real errors), while the target-conditioned check ranks errors with AUC 0.92 and catches 61%
of real errors at 5% false rejection.  Miolingo's Swift port removed the target text as a recogniser hint because it
returned the target almost regardless of the audio.  Natives' error against espeak (Common Phone): German xlsr-53
0.043, lv-60 0.114; French Cnam 0.013, lv-60 0.072; English not measured before (here: see the native error table).


## Caveats

- **Learners**: one learner, under two names (uid me and benita: the owner testing sign-in with two users); all
  78 learner takes are counted.  The archive is small and almost all German.
  The judged learner takes: fair 33, harsh 23, generous 2.
- **Near misses are synthetic**: voices saying single words; "what B sounds like" is espeak's reading of B, not a
  transcription of the voice; some pairs differ by a sound the voice may not realise as espeak says.
- **Natives**: Common Phone is built from Common Voice, and both espeak-cv-ft models were fine-tuned on Common
  Voice: these recordings may overlap the models' training data (results there may be optimistic, for xlsr-53 and
  lv-60 alike).  The English sample is England-accent only and partly from the train split.
- **Calibration made elsewhere**: the check's thresholds were calibrated on Common Phone dev speakers with xlsr-53
  (English, German) and Cnam (French).  For lv-60 everywhere and xlsr-53 on French the check runs with another
  model's thresholds: the check-based rules (V1 to V3, E) are not a fair comparison for those models; the greedy
  baseline is.
- **Thresholds chosen on these data**: τ for V4 and the ü/ö ratio threshold (2) were read off these same sets;
  there is no held-out set.  The ratio threshold was chosen from three values (0, 2, 4).
- **Reference voices**: 48 phrases a voice; differences of a few phrases are not significant (sign tests given).
- **Display rules** (zero=equal, unjudged) change what the page shows, not the engine's score; V2 and the ü/ö rule
  change the heard sounds and so the score and the columns.  The engine itself has one deletion cost, so
  B-deletions could not be run on it.


## Commands (from `neolingo/`, Miolingo's venv python, `HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1`)

    PY=~/Software/working/miolingo/venv/bin/python
    $PY -m lab.build_nearmiss mine && $PY -m lab.build_nearmiss synth --gtts   # near-miss pairs and audio (gTTS: network)
    $PY -m lab.premium reference && $PY -m lab.premium nearmiss                  # Apple Premium voices (no network)
    $PY -m lab.build_cp select && $PY -m lab.build_cp extract && $PY -m lab.build_cp items   # Common Phone sample
    $PY -m lab.datasets                                                           # wav lists under var/lab/lists/
    $PY -m lab.phone_run --model <hf id> --list var/lab/lists/all-de.txt --threads 4   # log-probabilities (one model a process)
    $PY -m lab.jobs reference nearmiss positive archive
    $PY -m lab.whisper_run --jobs var/lab/jobs/<set>.jsonl --shard K/N [--reverse]      # Whisper medium: free, prompt, teacher-forced
    $PY -m lab.validate stored | replay | engine <sets> [--variant NAME] [--every K]
    $PY -m lab.run fill --workers 3                                              # sound check + likelihood ratios (cache)
    $PY -m lab.run variants [NAME ...]                                           # every variant -> var/lab/results/
    $PY -m lab.native_error                                                       # free-reading error per model
    $PY -m lab.report                                                             # var/lab/report.md and lab/RESULTS.md
    $PY -m lab.deck                                                               # var/flick/deck-results.json

