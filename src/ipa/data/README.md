# espeak-ng fold-map data

`espeak_fold_map.json` is **generated** — do not hand-edit blindly; prefer
editing the source rules' interpretation in `scripts/espeak_mine.py` and
regenerating. It is checked in so the app and scorer need no espeak source
tree at runtime.

## Regenerate

```bash
python scripts/espeak_mine.py            # needs espeak-ng + phsource tree
```

Requires the espeak-ng **source** tree (for `phsource/`) and the `espeak-ng`
binary. Default phsource path is `~/Software/working/adaptive-text/espeak-ng/
phsource`; override with `--phsource`.

## What it contains (per language: `pt`, `pt-pt`, `fr`, `nl`, `en`)

- `inventory` / `inventory_counts` — IPA segments espeak actually emits over the
  app's own phrasebook (`language_materials/<lang>/phrasebook_complete.json`).
  Authoritative for *which* phones occur (source mnemonics omit vowel features).
- `tolerated_pairs` — Tier-1+2 accent-not-error substitutions. Each carries its
  `sources` (the espeak `ChangePhoneme`/`ChangeIf*` rule it came from).
  **Pairwise, not transitive** by design: `ɪ~ə` + `ɛ~ə` does *not* tolerate
  `ɪ~ɛ`, so real minimal pairs survive.
- `elision_candidates` — phones espeak may delete in context. Hints for the
  scorer to discount an insertion/deletion; **not** auto-folded.
- `tier1_same_ipa_audit` — espeak phoneme names that already realize to the same
  IPA (collapse in the binary output); audit only.

## Policy

Tier 1+2 (decided in beads `miolingo-ark`): fold mechanical variants AND
context-predictable native allophony (reduction, devoicing, positional
realization); never fold cross-dialect (pt-BR ↔ pt-PT) — each language is mined
independently. Because folding is **context-free** (a tolerated pair is
tolerated everywhere), a handful of pairs are defensible-but-broad and may want
pruning for pedagogy. Review `sources` and delete the pair to flag it again.
Candidates flagged at generation time:

- `en` `n ~ ŋ` — from pre-velar `n→N`; context-free it tolerates *thin/thing*.
- `en` `d ~ t` — from flap/assimilation `d#`; tolerates *bed/bet*.
- `en` `ɛ ~ ɪ` — from reduction `E→I2`; tolerates *bet/bit*.

Consumed via `src/ipa/fold_map.py` (`is_tolerated(lang, a, b)`), which the
weighted scorer (`miolingo-8f0`) uses to zero out tolerated substitutions before
applying panphon feature distance to the rest.
