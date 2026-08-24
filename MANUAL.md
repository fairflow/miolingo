# Manual

What Miolingo actually does, feature by feature, and how the pronunciation
scoring works underneath.

## Languages

Portuguese (Brazilian and European variants, `pt-br`/`pt-pt`), French, Dutch,
Flemish, German, Italian, Spanish. Language content lives under
`language_materials/<lang>/`, organized by CEFR level (A1–C2) where available.

## Practice modes

- **Words** — single-word pronunciation drills.
- **Phrases / conversations** — short multi-word or dialogue material.
- **Stories** — longer narrative text, read a line at a time. The web port's
  story reader supports switching between modes (e.g. read-along vs.
  practice-each-line) while keeping your position in the story.
- **Minimal pairs** — practice items built by finding words in your own
  vocabulary that differ by one phoneme (e.g. `/i/` vs `/ɪ/`), generated from
  espeak's phoneme output plus a pair-finder (`src/ipa/minimal_pairs.py`).
- **Vocabulary** — a personal word/phrase list per user, with CRUD, CSV
  import/export, and a translation lookup (provider-chain: whichever of
  DeepL/OpenAI/etc. has a configured key).

## The pronunciation attempt pipeline

One "attempt" (recording → feedback) does, in order:

1. **Reference generation**: the target text is run through **espeak-ng**
   (`src/scoring/phonemes.py`) to get the target's phonemic IPA transcription
   — the idealized, dictionary-level pronunciation for that language/voice.
2. **Silence trim**: the raw recording is energy-trimmed (drop near-silent
   frames at start/end) before ASR, threshold configurable
   (`src/scoring/practice.py`).
3. **Speech recognition**: the trimmed audio goes through **OpenAI Whisper**
   (`src/audio/asr.py`) to get what the learner actually said, as text, which
   is then converted to IPA the same way as the target (also via espeak).
4. **Scoring**: the target IPA and the learner's IPA are compared
   phone-by-phone (see below) to produce a similarity score and a list of
   per-phone operations (match / substitute / insert / delete).
5. **Feedback**: score, transcription, both IPA strings, and the flagged
   substitutions are returned to the UI in one response
   (`AttemptResponse`/`/api/attempt` in the web port; the equivalent
   in-process call in the Streamlit app).

## Scoring: two algorithms

`src/scoring/comparison.py` and `src/scoring/phone_distance.py` implement two
selectable scoring algorithms (`algorithm=` parameter on `/api/attempt`):

- **`edit_distance`** — character-level Levenshtein distance over the IPA
  strings. Simple, but treats every substitution as equally wrong: swapping
  a near-identical vowel (`/ɪ/` for `/iː/`) costs the same as a completely
  different phone.
- **`weighted_phone`** (`src/scoring/phone_distance.py`, the newer of the
  two) — phone-level, not character-level, scoring:
  1. Tokenize both IPA strings into individual phones using **panphon**,
     which correctly handles multi-codepoint segments (length marks,
     diacritics, affricates like `t͡ʃ`) that a naive character split would
     break apart.
  2. Look up each phone's articulatory feature vector (place, manner,
     voicing, height, backness, rounding, nasality, …) via panphon. This
     matters for vowels specifically: espeak's own internal feature tables
     only mark vowels as `vwl` with no height/backness/rounding, so vowel
     comparison has to go through panphon rather than espeak's data.
  3. Substitution cost between two phones = normalized panphon feature
     distance (0 = identical, 1 = maximally different) — **except** pairs
     that a per-language fold-map (`src/ipa/fold_map.py`) marks as tolerated
     accent variation, which cost 0. The fold-map is derived from espeak-ng's
     own allophone data (its `ChangePhoneme`/`ChangeIf*` rules), not
     hand-authored — e.g. French's several `r`-variants all collapsing to
     `/ʁ/`, or Brazilian Portuguese's positional `s→z` voicing.
  4. Align target vs. realized phones with a weighted Levenshtein (insertions
     and deletions cost a full phone; substitutions cost the feature
     distance above) to get an overall similarity in `[0, 1]`, plus which
     substitutions exceed a "significant" threshold and should be flagged to
     the learner as a real error rather than accent noise.

The design rationale (why character-level scoring produced misleading
feedback, why panphon rather than espeak's own feature tables, why the
fold-map is extracted rather than hand-written, and what was tried and
rejected — a learned confidence/abstention model on the recognizer, treated
as future work) is written up in
[`research/phonetics/DESIGN_DIGEST.md`](research/phonetics/DESIGN_DIGEST.md).

Both algorithms are available side by side (`algorithm` parameter); the
Streamlit app and the web port's oracle both default to `weighted_phone`.

## Text-to-speech

Reference audio for a target phrase uses a fallback chain
(`src/audio/tts.py`): **Google Cloud TTS** first if a key is configured, then
**gTTS**, then **eSpeak NG** as the always-available fallback. Which engine
actually served a given request is reported back (`X-Tts-Engine` header in
the web port).

## Accounts, progress, and the admin dashboard

The Streamlit app supports guest use (nothing persisted) or a registered
account (Argon2-hashed password) with progress history and vocabulary stored
in MySQL. A separate admin dashboard (`src/miolingo-admin.py`) gives usage
stats, user management, and API cost tracking — it's an operational tool, not
a learner-facing feature.

The web port has no accounts: everything (vocab, history, stats, settings)
lives in the browser's IndexedDB via Dexie, one user per browser profile.

## Language content

`language_materials/<lang>/` holds curated phrases, phrasebook entries, and
stories per language and CEFR level; `language_materials/unified/` is the
consolidated JSON form both the Streamlit app and the web port's
`/api/materials` endpoint read from.
