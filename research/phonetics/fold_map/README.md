# espeak-ng allophony fold-map (miolingo-ark)

End-to-end miner + generated fold-map + loader + tests for the
*tolerate-accent-vs-flag-error* boundary used by the weighted phone-distance
scorer (`miolingo-8f0`). Self-contained research artifact — not yet wired into
the app; `miolingo-8f0` will adopt the loader/data when it lands.

Builds on the raw extractors rescued in `../inventory/` (`extract_features.py`,
`inventory.sh`): this directory takes the next step and actually *produces* the
fold-map, resolving the vowel-feature gap noted there by reading IPA from the
espeak-ng **binary** rather than the source mnemonics.

## Files

- `espeak_mine.py` — the miner. Parses the phsource phoneme-table inheritance
  chain (`base → base1 → base2 → lang`), probes the espeak-ng binary
  (`espeak-ng -v LANG -q --ipa '[[name]]'`) to resolve each phoneme name to its
  realized IPA, and builds the empirical inventory from the app's phrasebooks
  (`language_materials/<lang>/phrasebook_complete.json`).
- `espeak_fold_map.json` — generated output: per-language inventory +
  `tolerated_pairs` (with rule provenance) + `elision_candidates`.
- `fold_map.py` — dependency-free loader. `is_tolerated(lang, a, b)` is the
  contract `miolingo-8f0` consumes.
- `test_fold_map.py` — 12 tests; guards non-transitivity and real-error flagging.

## Regenerate

```bash
python research/phonetics/fold_map/espeak_mine.py
```

Needs the espeak-ng **source** tree (for `phsource/`, default
`~/Software/working/adaptive-text/espeak-ng/phsource`, override `--phsource`)
and the `espeak-ng` binary. Generated from espeak-ng 1.51.1.

## Policy (decided in beads miolingo-ark)

**Tier 1+2**: fold mechanical variants AND context-predictable native allophony
(reduction, devoicing, positional realization); never fold cross-dialect
(pt-BR ↔ pt-PT) — each language mined independently. Tolerance is **pairwise,
not transitive** (`ɪ~ə` + `ɛ~ə` does not tolerate `ɪ~ɛ`), so real minimal pairs
(*pé/pês*, *bit/bet*) survive. Folding is **context-free** — a tolerated pair is
tolerated everywhere — so a few broad pairs may want pruning for pedagogy
(flagged candidates: en `n~ŋ`, `d~t`, `ɛ~ɪ`). Delete a pair from the JSON to
flag it again.
