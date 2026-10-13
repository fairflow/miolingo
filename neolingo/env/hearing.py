"""`hear`: what the recognisers make of a take, WITHOUT being given the target.

Two independent recognisers on the same file:
  * Whisper (text), language forced to the variant's language;
  * Miolingo's phone recogniser (wav2vec2 phoneme-CTC; the model is chosen
    per language by `variants.phone_model`), read greedily.

Models are loaded on first use and kept in module-level caches.

Why Whisper is not taken from Miolingo's `audio/asr.py`: that module imports
Streamlit at the top and keeps its model in `st.session_state`.  Its pure
function `transcribe_audio_whisper(audio_file, model, language_code)` is
reproduced here with the same decoding parameters (temperature 0, etc.) and
the same hallucination guards.  Differences: audio is decoded with soundfile
(no ffmpeg needed), the text is not lower-cased (comparison lower-cases), and
a guard hit gives "" plus a `note`, not a bracketed error string.
"""
from __future__ import annotations

import os
import threading
import time
from pathlib import Path

from . import _miolingo as mio
from .ipa import norm_word, phones_of
from .variants import variant

WHISPER_SIZE = os.environ.get("NEOLINGO_WHISPER_MODEL", "medium")  # Matthew's setting
_LOCK = threading.RLock()
_WHISPER: dict[str, object] = {}


class ModelMissing(RuntimeError):
    """A model needed is not in the local cache (we never download)."""


def whisper_model(size: str = WHISPER_SIZE):
    with _LOCK:
        if size not in _WHISPER:
            import whisper
            url = whisper._MODELS.get(size)
            if url is None:
                raise ModelMissing(f"unknown Whisper model {size!r}")
            cache = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "whisper"
            if not (cache / os.path.basename(url)).exists():
                raise ModelMissing(f"Whisper model {size!r} not in {cache}")
            _WHISPER[size] = whisper.load_model(size, download_root=str(cache))
        return _WHISPER[size]


def transcribe(wav_path: str, whisper_lang: str, size: str = WHISPER_SIZE) -> tuple[str, str]:
    """(text, note).  Same parameters and guards as Miolingo's
    transcribe_audio_whisper."""
    model = whisper_model(size)
    audio = mio.phone_recognizer._load_audio_16k(wav_path)
    with _LOCK:
        result = model.transcribe(
            audio=audio, language=whisper_lang, task="transcribe",
            temperature=0.0, no_speech_threshold=0.6, logprob_threshold=-1.0,
            condition_on_previous_text=False, word_timestamps=False,
            compression_ratio_threshold=2.4, fp16=False, verbose=None)
    text = result["text"].strip()
    words = text.lower().split()
    if len(words) > 20:
        for k in (2, 3, 4):
            if len(words) >= k * 10:
                pat = " ".join(words[:k])
                if text.lower().count(pat) >= 10:
                    return "", f"hallucination guard: {pat!r} repeated"
        if len(words) > 100:
            return "", f"too long: {len(words)} words"
    return text, ""


def phone_stream(wav_path: str, espeak_voice: str) -> tuple[str, str]:
    """(raw IPA string from the phone model, note)."""
    notes: list[str] = []
    with _LOCK:
        s = mio.phone_recognizer.phones_from_audio(
            wav_path, espeak_voice, warn_fn=notes.append)
    return s, "; ".join(notes)


def hear(wav_path: str, variant_code: str) -> dict:
    """{"text": str, "ipa": [[phone, ...]]} (+ "note" only if something odd).

    `ipa` is the phone recogniser's output, normalised as `norm` says, as ONE
    word: the recogniser has no word boundaries that can be trusted, and it is
    not given the target, so nothing here regroups into words."""
    v = variant(variant_code)
    text, n1 = transcribe(wav_path, v["whisper"])
    raw, n2 = phone_stream(wav_path, v["espeak"])
    joined = "".join(norm_word(c) for c in raw.split())
    ipa = [phones_of(joined)] if joined else []
    out = {"text": text, "ipa": ipa}
    note = "; ".join(n for n in (n1, n2) if n)
    if note:
        out["note"] = note
    return out


def preload(variant_code: str) -> dict:
    """Load the models for a variant now; returns seconds taken per model."""
    t = {}
    v = variant(variant_code)
    t0 = time.time(); whisper_model(); t["whisper"] = time.time() - t0
    t0 = time.time(); mio.phone_recognizer._load(v["phone_model"]); t["phone_model"] = time.time() - t0
    return t
