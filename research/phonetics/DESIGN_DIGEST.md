# Miolingo pronunciation core — design digest

A condensed record of the design reasoning developed in a session on 2026-06-26.
The prototype scorer code was lost (see README); this preserves the *design* and
its justification, which matter more than the code.

## The core idea: separate REFERENCE from REALIZATION

The product goal is **phone-level feedback** — telling a learner *which phoneme*
they got wrong — while **tolerating accent** and never giving confident wrong
feedback. Two requirements pull in opposite directions:

- "Native speakers should recognise the phonemes as correct" → needs a **phonemic
  reference**: the idealized, dictionary-level target for a word. A property of
  the *language*, not the audio. (espeak-ng generates this.)
- "Recognise different accents without insisting on RP" → needs to not penalize
  the **realization**: what the learner actually produced. A property of *this
  audio*. (a phone recognizer produces this.)

The common mistake is making one tool do both. The leverage is to keep two
channels separate and compare them:

```
  target text ──► espeak-ng ──► phonemic REFERENCE IPA ─┐
                                                          ├─► WEIGHTED SCORER ─► feedback
  learner audio ─► recognizer ─► realized phones ────────┘         ▲
                                                          tolerance/fold map
```

The "expert mixing" the user reached for (a vague "MoE of approaches") lives in
the **compare step**, not in choosing one recognizer. A learned mixture-of-experts
was rejected as over-engineering: the experts here are not learned but a small,
inspectable set of rules — a confusability/tolerance matrix per language that
encodes which differences are accent (tolerate) vs error (flag). For a
*teaching* tool, auditable judgment beats weights you can't inspect.

## Why plain edit distance fails (the bug that triggered all this)

Miolingo scored a **character-level Levenshtein** on **orthographic** text. Both
its ASR engines output spelling, not phones. Consequences:
- Substituting a phonetically-near phone (/ɪ/ for /iː/) scored identically to a
  wildly different one — no notion of phonetic closeness.
- Whisper auto-corrects toward real words, erasing the exact slip a learner needs
  to see (false positives); one misheard word inflated to many char-errors (false
  negatives). The "inaccuracy" was substantially a *measurement* problem, not just
  a recognition one.

## The panphon weighted phone-distance scorer (design of the lost module)

A drop-in replacement for the character-Levenshtein in `src/scoring/comparison.py`:

1. **Tokenize IPA into phones**, handling multi-codepoint segments (length marks
   `ː`, combining diacritics, tie bars, affricates `t͡ʃ`, diphthongs). Naive
   per-character splitting is wrong. Prefer espeak-ng `--ipa --sep=' '` to
   pre-segment, or panphon's segmenter.
2. **Feature vectors from `panphon`** (articulatory: place, manner, voicing,
   height, backness, rounding, length, nasality…) for BOTH vowels and consonants.
   Key reason panphon is required rather than espeak's own feature tables:
   **espeak source carries full features for consonants but vowels carry only
   `vwl`** — no height/back/round — so vowel features must come from the IPA
   symbol via panphon.
3. **Substitution cost** = normalized panphon feature distance (0 identical → 1
   maximally different), via `weighted_feature_edit_distance`.
4. **Weighted Levenshtein alignment** returning similarity 0..1, per-phone ops
   (match/substitute/insert/delete), and the substitutions flagged significant.
5. **Optional tolerance/fold-map override**: a per-language map that marks certain
   substitutions as accent-level (cost→~0) vs error-level (full cost). This is
   where "tolerate accent, keep the contrast" is encoded.

The scorer ships **regardless of recognizer** — it already helps on Whisper-derived
IPA and should help much more on a true phone channel.

## Deriving the accent-vs-error boundary from espeak-ng (so you needn't be a phonetician)

espeak-ng encodes its own allophony **as data**: `ChangePhoneme` / `ChangeIf*`
directives and same-IPA variants in `phsource/ph_*` tables, assembled along the
inheritance tree `base→base1→base2→lang`. Examples: French's four r-variants all
map to a single /ʁ/ (collapse → tolerate); pt-BR `s#→z` before voiced (positional
allophone → tolerate). Crossing to a *different* phoneme label = real error. So
the tolerance/fold map is **extracted**, not hand-authored.

## The confidence / abstention requirement (don't confidently say "wrong")

A phone recognizer also errs; if it mishears a correct /iː/ as /ɪ/ and we tell the
learner they're wrong, that's worse than no feedback. So a recognizer must **know
when to abstain**. Empirically, whole-utterance min-confidence was useless
(corr with error ≈ −0.15). The viable design aligns CTC posteriors to *individual
target phones* and abstains **per phone**. This is the real, honest form of the
user's "mixture of approaches" instinct: a recognizer that knows when to shut up.

## The decision gate: does phone recognition actually beat Whisper-large?

The weighted scorer is adopted unconditionally; the *phone-recognition channel* is
adopted **only if** it outperforms Whisper-large for the target languages
(pt, pt-br, fr, nl). Candidates benchmarked: `wav2vec2-lv-60-espeak-cv-ft` (more
accurate, 2.4 GB, emits tone-digit/retroflex symbols espeak-ng doesn't — needs a
normalization layer) vs `allosaurus` (52 MB, instant, clean IPA, lower accuracy).
The prior benchmark used **synthetic espeak audio** (out-of-distribution) and is
NOT a valid answer — re-run on **real human audio**. A phonic *gate* on Whisper
(verify its words against expected phones) is an acceptable middle path.

## Coda

The user's original 2025 aim was modest: get phonemic transcriptions of words and
reproduce them via IPA-to-speech codes. That simple idea grew into miolingo. The
implementation above leans, mostly implicitly, on existing phonetics and
language-learning research (articulatory feature distance; allophonic vs phonemic
contrast; pronunciation-feedback abstention) that the user had not previously
encountered — the value here is connecting that body of work to the concrete
two-channel + weighted-scorer + extracted-tolerance architecture.
