# Does a phone recognizer hear what the learner said? (speechocean762, 2026-10-08)

The July model sweep scored recognizers on **native** speech against the **dictionary**
pronunciation. That rewards a model that hears the textbook form. This benchmark asks the
question that matters for Miolingo: on **learner** speech, does the model's view of each
phone agree with expert listeners?

**Data:** speechocean762 test set (Apache-2.0).

- 2,500 sentences, 47,369 phones.
- Mandarin-L1 learners of English; half are children.
- Each phone is scored 0–2 by 5 experts.
- For 1,412 mispronounced phones the experts also wrote what was actually said.

**Labels:**

- correct: score ≥ 1.6 (44,097 phones);
- error: score ≤ 1.0 (2,149 phones, 4.5%).

**Method:**

- `gop_so762.py` is a substitution-aware, alignment-free GOP. For each expected phone it
  compares the CTC likelihood of the sentence with that phone against every other English
  phone, and against deleting it. The softmax gives `p_canon` and the most likely realised phone.
- There are no detectors and no forced aligner: one recognizer covers every phone.
- `accept_so762.py` learns from the **train** split which realised phones experts accept for
  each expected phone. Example: unaspirated [p] for /b/ is accepted 96% of the time.
- Everything is zero-shot except that table: no model was trained on speechocean762.

## Results (test set)

| model | PCC with experts | AUC | errors caught at 5% false rejection | precision there | substitution: best guess = what was said | deletion found |
|---|---|---|---|---|---|---|
| ZIPA large CTC (zero-shot) | 0.34 | 0.86 | 22% | 18% | 35% | 57% |
| ZIPA + learned acceptance | 0.49 | 0.90 | 52% | 34% | 35% | 57% |
| **xlsr-53 espeak (zero-shot; the app's model)** | 0.38 | **0.92** | **61%** | **37%** | **40%** | **72%** |
| **xlsr-53 + learned acceptance** | **0.54** | **0.92** | 59% | 37% | 40% | 72% |

For comparison, published PCC values on this test set:

- GOP baselines: about 0.45;
- GOPT, trained on speechocean762 train: 0.61;
- later trained models: about 0.65–0.70.

Children are harder for every model. With xlsr-53 and learned acceptance, PCC is 0.50 for
children and 0.57 for adults.

## Findings

1. **ZIPA does not beat xlsr-53 here.** On paper ZIPA is ~4× better on native read speech.
   On learner speech, xlsr-53, already wired into the app, is better on every measure.
2. **Zero-shot "is this phone wrong?" is usable as a ranking, not as a verdict.**
   - AUC is 0.92.
   - At a 5% false-rejection rate xlsr-53 catches 61% of real errors.
   - Because only 4.5% of phones are errors, 63% of its flags are still false alarms.
3. **Narrow phonetics ≠ what listeners judge.** Zero-shot, both models flag ~1/3 of
   accepted phones. Mostly these are real phonetic differences that experts accept:
   - devoiced /b d g z/;
   - [i] for /ɪ/;
   - [a] for /æ ʌ/;
   - [ŋ] for final /n/.

   A learned acceptance table fixes the correlation (0.38 → 0.54). That table is the
   data-driven form of the realised-phone `accept` lists.
4. **Diagnosis is the weak part.** When a phone is wrong, the model's best guess matches
   what the expert heard 35–40% of the time. Misses are often the neighbouring vowel,
   e.g. [i] where the expert wrote /ɪ/. So "this sound was off" is reliable well before
   "you said X instead of Y" is.

## Caveats

- English only, Mandarin L1 only. No German or other targets have been tested.
- Expert scores are lenient and the lexicon is quirky (e.g. ZERO = Z IH AH OW).
- The 5%/10%/20% points are ROC readouts on test; a deployed threshold must be chosen on train.

## Reproduce

Run these with `venv/bin/python`. Data is in `/opt/so762`; log-probs are in `/opt/mdd/lp_*`.

1. Transcribe, for each `--model zipa|xlsr`:
   ```
   transcribe_so762.py --model zipa --out zipa.jsonl --save-lp lp_zipa
   ```
2. Score:
   ```
   gop_so762.py --lp lp_zipa --spell zipa --out gop_zipa.jsonl
   ```
   For xlsr-53, use `--spell espeak`. Run steps 1 and 2 on `--parquet train.parquet` too.
3. Learn acceptance on train and apply it to test:
   ```
   accept_so762.py --train gop_zipa_train.jsonl --test gop_zipa.jsonl --out-test gop_zipa_accept.jsonl
   ```
4. Evaluate:
   ```
   eval_gop.py gop_*.jsonl --out results/so762_gop.json
   score_so762.py zipa.jsonl xlsr.jsonl
   ```
   `score_so762.py` scores free transcription.
