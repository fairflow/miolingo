# Weighted phone-distance scorer (miolingo-8f0)

Research prototype of the phone-level pronunciation scorer that replaces the
character-level Levenshtein in `src/scoring/comparison.py`. Proven here; app
integration is the follow-up.

## What it does

`score(user_ipa, target_ipa, lang) -> Result` (exact_match, similarity 0..1,
distance, per-phone `ops`):

1. **Tokenize** both IPA strings into phones with panphon (`dy6`), handling
   multi-codepoint segments — length marks (`iː`), nasal/other diacritics (`ɐ̃`).
   Stress/syllable marks are stripped first. Accepts space-separated phone
   strings too, so it scores Whisper-derived IPA *or* phone-recognizer output.
2. **Substitution cost** = normalized panphon articulatory feature distance
   (0 identical … 1 maximally different), **except** pairs the espeak-ng
   fold-map (`../fold_map/`, `miolingo-ark`) marks as tolerated accent variation,
   which cost 0. Tolerance is language-specific (`pt-pt` folds `a~ɐ`; `pt` does
   not).
3. **Align** with a weighted Levenshtein, returning similarity, per-phone ops,
   and which substitutions are "significant" (≥ `_SIGNIFICANT`) to surface to the
   learner.

## Run

```bash
python -m pytest research/phonetics/phone_distance/test_phone_distance.py
python research/phonetics/phone_distance/phone_distance.py   # importable module
```

## Known calibration notes (for the integration step)

- Substitution cost uses **unweighted** feature distance. panphon ships
  per-feature weights; weighting would make place/manner errors cost more than a
  lone voicing difference (e.g. `z~s` currently scores ~0.04). Worth evaluating
  against `_SIGNIFICANT` once on real learner audio.
- `_INDEL_COST` and `_SIGNIFICANT` are first-cut constants; tune with real data.
- Bare affricates (`dʒ`, `tʃ` without a tie bar, as espeak emits) segment as two
  phones. Consistent on both sides, so alignment is unaffected.

## Integration plan (next, per beads miolingo-8f0)

Promote the fold-map loader+data into `src/ipa/`, add this scorer to
`src/scoring/` as a **selectable** `weighted_phone` algorithm alongside
`edit_distance` (default unchanged), and call it from `scoring/practice.py`
using the `user_ipa`/`correct_ipa`/`voice` already in scope there.
