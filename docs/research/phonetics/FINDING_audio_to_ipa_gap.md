# Finding: Miolingo does not derive IPA from the voice recording

**Status:** confirmed by code trace, 2026-06-28
**Severity:** Critical — invalidates the premise of the pronunciation score
**Scope:** Streamlit app (`src/`). The `weighted_phone` refactor (miolingo-8f0)
does not change this; it improves the *comparison*, not the *input*.

---

## The claim under test

> "Miolingo creates IPA characters directly from voice recordings."

**This is false.** IPA is derived from *text*, not from audio. The recording is
converted to text by an ASR engine (Whisper, or Wav2Vec2 for pt), and the IPA is
then generated from that recognized **text** by espeak-ng's grapheme-to-phoneme
conversion. The audio waveform is discarded the moment ASR returns a string.

## The proof (one function)

All of it is visible in `src/scoring/practice.py`, `practice_word_from_audio()`:

```python
# src/scoring/practice.py:154-164
correct_phonemes = get_phonemes(text, voice)        # TARGET text → phonemes
correct_ipa      = get_ipa(text, voice)             # TARGET text → IPA

recognized_text  = transcribe_audio(temp_audio, settings, language, ...)  # AUDIO → TEXT (Whisper)

user_phonemes    = get_phonemes(recognized_text, voice)   # RECOGNIZED TEXT → phonemes
user_ipa         = get_ipa(recognized_text, voice)        # RECOGNIZED TEXT → IPA
```

`get_ipa()` is a thin wrapper over the espeak-ng CLI (`src/scoring/phonemes.py:68`):

```python
subprocess.run([espeak_cmd, "-v", voice, "--ipa", "-q", text], ...)
```

`espeak --ipa <text>` is **text-to-speech grapheme-to-phoneme**: given a spelling,
it returns the language's idealized dictionary pronunciation. It never receives
the microphone signal. So `user_ipa` is "the dictionary pronunciation of whatever
word Whisper decided it heard" — not "what the learner's mouth actually produced."

### The literal chain

```
microphone audio ─► Whisper/Wav2Vec2 (transcribe_audio) ─► recognized TEXT
                                                                  │
                          target TEXT ─► espeak --ipa ─► target_ipa │
                                                                  ▼
                                          espeak --ipa ─► user_ipa
                                                                  │
                          target_ipa ──── weighted_phone / edit_distance ──── user_ipa
                                                       │
                                                       ▼
                                                  similarity score
```

Both inputs to the scorer are espeak G2P outputs of text. There is **no**
acoustic-phonetic component anywhere in the codebase: no phone recognizer
(Allosaurus / wav2vec2-phoneme-CTC), no forced alignment (MFA / Kaldi), no
goodness-of-pronunciation (GOP) scoring.

## Why this makes the score unreliable

The only acoustic judgment in the system is Whisper's *word-identity* decision,
and Whisper is a language model with a strong prior toward real, expected words:

1. **False positives (the dangerous case).** A learner badly mispronounces a word,
   but Whisper "auto-corrects" to the intended word. `get_ipa(recognized)` then
   equals `get_ipa(target)` by construction → **perfect score** for a wrong
   pronunciation. The exact slip the learner needs to see is erased before scoring.
2. **False negatives.** A correctly-pronounced word is misheard as a different
   word → large IPA mismatch → poor score for a correct attempt.

The "inaccuracy" is substantially a **measurement** problem, not just a
recognition one — the pipeline measures the wrong quantity.

## The weighted_phone refactor does not fix it

`src/scoring/phone_distance.py` (`score(user_ipa, target_ipa, lang)`) is genuinely
good work — panphon articulatory-feature substitution costs, a per-language
espeak-ng allophony fold-map (`src/ipa/fold_map.py`) that tolerates accent
variation. But it compares `user_ipa` vs `target_ipa`, **both espeak G2P outputs
of text.** A more refined comparison of two idealized pronunciations cannot recover
acoustic information that was already thrown away at the ASR step. It is the right
*comparator* wired to the wrong *input channel*.

The refactor's own design digest (`DESIGN_DIGEST.md`, 2026-06-26) reached this same
conclusion and named it: *"Both its ASR engines output spelling, not phones …
Whisper auto-corrects toward real words, erasing the exact slip a learner needs to
see."*

## File / line index

| Step | File | Line | Note |
|------|------|------|------|
| Audio capture | `src/ui/practice_tab.py` | 171 | `st.audio_input()` → WAV bytes |
| Silence trim | `src/scoring/practice.py` | 32–82 | energy-based, still audio |
| **ASR (audio→text)** | `src/audio/asr.py` | 69–214 | Whisper / Wav2Vec2 — lossy step |
| **IPA from text** | `src/scoring/phonemes.py` | 68–87 | `espeak --ipa <text>` (G2P) |
| Scorer (legacy) | `src/scoring/comparison.py` | 83–121 | char Levenshtein |
| Scorer (weighted) | `src/scoring/phone_distance.py` | 102–159 | panphon + fold-map |
| Orchestration | `src/scoring/practice.py` | 152–188 | the chain above |

## What a real audio→phones path requires

To score pronunciation *from the recording*, the `user_ipa` line must be replaced
by a channel that reads the waveform:

- **Acoustic phone recognizer** — Allosaurus (52 MB, clean IPA, lower accuracy) or
  a wav2vec2 phoneme-CTC model (e.g. `wav2vec2-lv-60-espeak-cv-ft`, 2.4 GB, more
  accurate, needs a symbol-normalization layer). Closest drop-in: swap
  `get_ipa(recognized_text)` for `phones_from_audio(wav)`, keep the weighted scorer.
- **Forced alignment + GOP** — align audio against the *target* phone sequence and
  score each phone acoustically. This is what commercial pronunciation trainers do.

Either way the recognizer must be able to **abstain per phone** (the digest's
"recognizer that knows when to shut up"): a phone recognizer that confidently
mishears a correct sound and reports it wrong is worse than no feedback. The
decision gate (digest §"does phone recognition actually beat Whisper-large?")
remains open and must be benchmarked on **real human audio**, not synthetic espeak
audio.
