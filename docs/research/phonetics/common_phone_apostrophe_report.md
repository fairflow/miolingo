# Common Phone (French): systematic G2P error on words with a typographic apostrophe (U+2019)

**Dataset:** Common Phone, Zenodo record [5846137](https://zenodo.org/records/5846137)
(`cp-1-0.tgz`), French subset (`CP/fr`). CC0.
**Reporter:** Matthew Fairtlough (with analysis assistance).
**Date:** 2026-06-29

## Summary

In the French subset, the phonetic reference (the `KAN-MAU` tier of the
per-utterance TextGrids) is **systematically wrong for every word written with a
typographic / curly apostrophe `’` (U+2019)**. For these words the
grapheme-to-phoneme step appears to fall back to spelling the letters out rather
than phonemizing the word, producing transcriptions that do not correspond to
any French pronunciation.

The same words written with a straight apostrophe `'` (U+0027) are transcribed
correctly elsewhere in the corpus, which localises the cause to apostrophe /
text-normalisation handling **upstream of the G2P step**.

## Evidence

Scanned all 13,437 French TextGrids. Word tokens containing U+2019: **2,092**
(1.6% of 130,855 word tokens), across **253 distinct word types**. Every
affected type we inspected is mis-transcribed. Representative cases (dataset
`KAN-MAU` label vs. the correct French pronunciation):

| Word (with `’`) | Dataset label | Correct IPA | What went wrong |
|---|---|---|---|
| `c’est`       | `k s t`             | `sɛ`     | "c" spelled as /k/, silent "t" emitted |
| `j’ai`        | `ʒ a i`             | `ʒe`     | "ai" spelled out as /a i/ |
| `qu’il`       | `k y i j`           | `kil`    | "qu" spelled as /k y/, "il" as /i j/ |
| `n’est`       | `ɛ s t`             | `nɛ`     | "n" dropped, silent "t" emitted |
| `aujourd’hui` | `o ʒ u ʀ d ʃ ɥ i`   | `oʒuʁdɥi`| spurious /ʃ/, /d/ surfaced |
| `l’`          | `l`                 | `l`+vowel| elided article reduced to bare /l/ |
| `d’`          | `d`                 | `d`+vowel| elided preposition reduced to bare /d/ |

The straight-apostrophe form `c'est` (U+0027) appears **322×** correctly labelled
`s e`, while the curly form `c’est` (U+2019) appears **202×** mislabelled
`k s t` — the same word, the apostrophe character being the only difference.

## Cause (localised, not yet root-caused in your pipeline)

The failure is in **text normalisation before G2P**: U+2019 is not folded to a
plain apostrophe (or not recognised as an elision marker), so the tokeniser /
G2P treats the orthographic string literally and spells it out.

Note: current **espeak-ng** phonemizes both `c'est` and `c’est` correctly
(`sˈɛ`), so this error is **not** reproducible with an up-to-date espeak-ng. It
points to the specific (or older) G2P/normalisation tooling used to build the
released labels.

## Suggested fix

Normalise the typographic apostrophe **U+2019 → U+0027** (and ideally other
Unicode apostrophe variants, U+02BC etc.) in text normalisation **before** G2P,
then re-generate the `KAN-MAU` tier for affected utterances. A single
normalisation step repairs all 253 word types.

## Scope / caveats

- Figures are for the **French** subset only; other languages (EN/DE/IT/ES/RU)
  were not checked but may share the issue if the same normalisation path is used.
- This is **distinct** from a separate observation that the reference uses
  word-isolated citation forms (silent final consonants kept, no liaison across
  word boundaries) — that is a labelling-policy matter, not a bug, and is not
  part of this report.
- For most published uses (training multilingual phone recognisers, where the
  corpus is robust to a few percent of label noise) this error is unlikely to
  have affected results. It surfaces when the labels are used as a **per-example
  gold reference**, which is how it was found here.
