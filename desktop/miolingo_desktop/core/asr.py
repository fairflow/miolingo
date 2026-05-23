"""Automatic Speech Recognition (Whisper, local).

Ported from ``src/audio/asr.py`` with all Streamlit coupling removed:
- ``st.session_state`` model caching -> a plain in-process module cache.
- ``st.spinner`` -> an optional ``progress_fn`` callback (the Qt layer wires a
  worker-thread progress signal to it; defaults to a no-op).
- ``st.warning``/``st.error`` -> an optional ``warn_fn`` (defaults to logging).
- wav2vec2 dropped entirely (DECISIONS.md: Whisper covers all languages).

Transcription itself is a pure function: it takes a loaded model and returns
text. Model loading is separated so the UI can run it off-thread with progress.
"""

from __future__ import annotations

import logging
import warnings
from collections.abc import Callable

from .config import LANGUAGE_CONFIG

logger = logging.getLogger(__name__)

ProgressFn = Callable[[str], None]
WarnFn = Callable[[str], None]

# In-process model cache: model_name -> loaded whisper model.
_WHISPER_CACHE: dict[str, object] = {}


def _default_warn(msg: str) -> None:
    logger.warning(msg)


def get_whisper_model(model_name: str, *, progress_fn: ProgressFn | None = None) -> object:
    """Load (or return cached) a Whisper model by name.

    The first load of a model that is not present locally triggers
    openai-whisper's download-on-first-run (cached under ``~/.cache/whisper``);
    ``progress_fn`` is called once before the potentially slow load so the UI
    can show a "loading model" state.
    """
    cached = _WHISPER_CACHE.get(model_name)
    if cached is not None:
        return cached

    if progress_fn is not None:
        progress_fn(f"Loading Whisper model '{model_name}'...")

    import whisper  # imported lazily; heavy dependency

    model = whisper.load_model(model_name)
    _WHISPER_CACHE[model_name] = model
    return model


def clear_model_cache() -> None:
    """Drop cached models (used by tests and on a settings model-size change)."""
    _WHISPER_CACHE.clear()


def transcribe_audio_whisper(
    audio_file: str,
    model: object,
    language_code: str = "pt",
) -> str:
    """Transcribe *audio_file* with a loaded Whisper *model*.

    Includes the source app's hallucination guards: returns a bracketed error
    string if a short pattern repeats 10+ times or the transcript exceeds 100
    words.
    """
    result = model.transcribe(  # type: ignore[attr-defined]
        audio=audio_file,
        language=language_code,
        task="transcribe",
        temperature=0.0,
        no_speech_threshold=0.6,
        logprob_threshold=-1.0,
        condition_on_previous_text=False,
        word_timestamps=False,
        compression_ratio_threshold=2.4,
    )

    detected_lang = result.get("language", "unknown")
    if detected_lang != language_code:
        warnings.warn(
            f"Whisper detected language '{detected_lang}' instead of '{language_code}'",
            stacklevel=2,
        )

    transcribed_text = result["text"].strip().lower()

    words = transcribed_text.split()
    if len(words) > 20:
        for pattern_len in (2, 3, 4):
            if len(words) >= pattern_len * 10:
                pattern = " ".join(words[:pattern_len])
                repetitions = transcribed_text.count(pattern)
                if repetitions >= 10:
                    warnings.warn(
                        f"Whisper hallucination detected: '{pattern}' x{repetitions}",
                        stacklevel=2,
                    )
                    return f"[hallucination detected: '{pattern}' x{repetitions}]"

        if len(words) > 100:
            warnings.warn(
                f"Suspiciously long transcription: {len(words)} words", stacklevel=2
            )
            return f"[error: transcription too long - {len(words)} words, possible hallucination]"

    return transcribed_text


def transcribe_audio(
    audio_file: str,
    settings: dict,
    language: str = "Portuguese",
    *,
    warn_fn: WarnFn | None = None,
    progress_fn: ProgressFn | None = None,
) -> str:
    """Transcribe *audio_file* using Whisper, honouring *settings*.

    ``settings`` supplies ``whisper_model_size`` (default ``medium``). The
    ``language`` name selects the Whisper language code via ``LANGUAGE_CONFIG``.
    """
    if warn_fn is None:
        warn_fn = _default_warn

    lang_config = LANGUAGE_CONFIG[language]
    lang_code = str(lang_config["code"])

    model_size = str(settings.get("whisper_model_size", "medium"))
    model = get_whisper_model(model_size, progress_fn=progress_fn)
    return transcribe_audio_whisper(audio_file, model, lang_code)
