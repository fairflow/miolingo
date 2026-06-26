# Phonetics research artifacts (rescued from an ephemeral scratchpad)

These files were produced by research agents during a VSCode Chat session and
**rescued into the repo** because the original scratchpad
(`/private/tmp/claude-501/.../scratchpad/`) is session-specific and ephemeral —
it is NOT visible to other Claude sessions and vanishes when the session ends.

See beads issues: `miolingo-ark`, `miolingo-8f0`, `miolingo-dy6`, `miolingo-h8q`.

## What's here (real, verified to exist)

### inventory/ — espeak-ng phoneme inventory mining (feeds miolingo-ark)
- `extract_features.py` — parses any `phsource/ph_*` table into
  `{mnemonic, ipa, espeak-features, imports, calls}`. Note: espeak source has
  full features for CONSONANTS but vowels carry only `vwl` (no height/back/round)
  — so vowel features must come from panphon on the IPA symbol, not from espeak.
- `inventory.sh` — empirical IPA-inventory extractor (any voice + wordlist),
  uses `espeak-ng -v <voice> --ipa --sep=' ' -q`.
- `pt_words.txt`, `fr_words.txt`, `nl_words.txt` — sample wordlists.

### phone_poc/ — phone-recognizer benchmark (feeds miolingo-h8q)
- `gen_corpus.py` — synthesizes test audio via espeak/`say` + ffmpeg, captures
  reference IPA. (Regenerates the .wav files, which were NOT copied here.)
- `bench.py` — runs wav2vec2-lv-60-espeak-cv-ft AND allosaurus, computes phone
  error rate vs reference, extracts wav2vec2 CTC confidence.
- `analyze.py` — normalization + error-detection/abstention analysis.
- `corpus.json`, `results/` — the corpus manifest and benchmark outputs.
- NOTE: benchmark used SYNTHETIC espeak audio (out-of-distribution) — the high
  PERs are NOT a valid answer to "does phone recognition beat Whisper." Re-run on
  REAL human audio. See `miolingo-h8q`.

## What's LOST and must be rebuilt

### The panphon weighted phone-distance scorer (the core deliverable for miolingo-8f0)
A research agent reported building + testing a standalone `phone_distance/` module
(IPA tokenization handling multi-codepoint segments + panphon
`weighted_feature_edit_distance` + a hook for an external tolerance/fold map).
**That agent ran in an isolated worktree and never wrote the files to the shared
scratchpad, so the code did not survive.** Only its description remains (here and
in the `miolingo-8f0` beads comments).

**Rebuild spec** (from the agent's report):
1. Tokenize IPA into phones, handling multi-codepoint segments (length marks `ː`,
   combining diacritics, tie bars, affricates). Prefer espeak-ng `--ipa --sep=' '`
   to pre-segment, or panphon's segmenter.
2. Use `panphon` (`pip install panphon`, see `miolingo-dy6`) for articulatory
   feature vectors of BOTH vowels and consonants.
3. Substitution cost = normalized panphon feature distance (0=identical, 1=max).
4. Weighted Levenshtein alignment returning similarity 0..1 + per-phone ops +
   flagged significant substitutions.
5. Accept an optional tolerance/fold-map override (from `miolingo-ark`) so
   allophonic/accent substitutions cost ~0 while phonemic-boundary crossings cost full.
6. Tests: phonetically-near substitutions (/iː/↔/ɪ/) must score much higher
   similarity than distant ones; must handle multi-codepoint IPA.

This replaces the character-level Levenshtein in `src/scoring/comparison.py`.
