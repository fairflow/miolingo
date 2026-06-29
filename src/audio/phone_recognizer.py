"""
Acoustic phone recognition: derive IPA phones DIRECTLY from the audio waveform.

This is the ACCURACY channel of the two-channel design (see
docs/research/phonetics/FINDING_audio_to_ipa_gap.md, miolingo-7w3): it reports
what the learner actually PRODUCED, as opposed to the comprehensibility channel
(Whisper -> espeak) which reports what a listener would have UNDERSTOOD.

Recognizer choice is per-language (validated in miolingo-0x9 on Common Phone
French against a sentence-level espeak reference, weighted_phone metric):
  - French  -> Cnam-LMSSC/wav2vec2-french-phonemizer  (specialist, ~0.015 err)
  - other   -> facebook/wav2vec2-lv-60-espeak-cv-ft    (multilingual fallback)
Both are wav2vec2 phoneme-CTC models that emit espeak-ng-convention IPA (same
convention as our espeak targets), output phones directly from audio, and load
via transformers AutoModelForCTC. Allosaurus was evaluated and dropped: weaker
(~0.14 weighted on French) and its lang_id is only a phone-inventory mask over a
single universal model.

Import-light: transformers/torch and the model load lazily on first use, so the
comprehensibility-only path never pays for them.
"""

from __future__ import annotations

import functools
from typing import Callable, Optional

# espeak voice code (or its language prefix) -> HuggingFace phoneme-CTC model id.
_FRENCH_MODEL = "Cnam-LMSSC/wav2vec2-french-phonemizer"
_MULTILINGUAL_MODEL = "facebook/wav2vec2-lv-60-espeak-cv-ft"

_VOICE_TO_MODEL = {
    "fr": _FRENCH_MODEL,
    "fr-fr": _FRENCH_MODEL,
    "fr-be": _FRENCH_MODEL,
    "fr-ch": _FRENCH_MODEL,
}


def model_for_voice(voice: str) -> str:
    """Pick the phoneme-CTC model id for an espeak voice code."""
    if not voice:
        return _MULTILINGUAL_MODEL
    v = voice.lower()
    if v in _VOICE_TO_MODEL:
        return _VOICE_TO_MODEL[v]
    return _VOICE_TO_MODEL.get(v.split("-")[0], _MULTILINGUAL_MODEL)


@functools.lru_cache(maxsize=2)
def _load(model_id: str):
    """Lazily load (processor, model) for a phoneme-CTC model, cached per id."""
    from transformers import AutoProcessor, AutoModelForCTC

    processor = AutoProcessor.from_pretrained(model_id)
    model = AutoModelForCTC.from_pretrained(model_id)
    model.eval()
    return processor, model


def _load_audio_16k(audio_file: str):
    """Read a WAV to mono float32 at 16 kHz (what wav2vec2 expects)."""
    import soundfile as sf

    data, sr = sf.read(audio_file)
    if getattr(data, "ndim", 1) > 1:
        data = data.mean(axis=1)
    data = data.astype("float32")
    if sr != 16000:
        import resampy

        data = resampy.resample(data, sr, 16000)
    return data


def phones_from_audio(
    audio_file: str,
    voice: str = "fr",
    warn_fn: Optional[Callable] = None,
) -> str:
    """
    Recognize IPA phones directly from an audio file (the waveform).

    Args:
        audio_file: Path to a WAV file (the trimmed user recording).
        voice: espeak voice code; selects the per-language recognizer.
        warn_fn: Optional warning callback for graceful degradation.

    Returns:
        Space-separated IPA phones (espeak-ng convention), or "" if recognition
        is unavailable / fails, letting the caller fall back gracefully.
    """
    model_id = model_for_voice(voice)
    try:
        processor, model = _load(model_id)
    except ImportError:
        if warn_fn is not None:
            warn_fn(
                "Acoustic phone recognizer needs `transformers`/`torch`; "
                "falling back to the comprehensibility (ASR-text) channel."
            )
        return ""
    except Exception as e:  # download / load failure
        if warn_fn is not None:
            warn_fn(f"Phone recognizer unavailable: {e}")
        return ""

    try:
        import torch

        audio = _load_audio_16k(audio_file)
        inputs = processor(
            audio, sampling_rate=16000, return_tensors="pt"
        ).input_values
        with torch.no_grad():
            logits = model(inputs).logits
        ids = torch.argmax(logits, dim=-1)
        text = processor.batch_decode(ids)[0]
    except Exception as e:
        if warn_fn is not None:
            warn_fn(f"Phone recognition failed: {e}")
        return ""

    # Models emit space-separated (fb) or word-grouped (Cnam) IPA; collapse to a
    # single normalized whitespace run. Phone-level segmentation/normalization
    # for scoring is handled downstream by the scorer (panphon) and ipa_norm.
    return " ".join(text.split())
