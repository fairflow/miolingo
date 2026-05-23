"""Practice orchestration: score recorded audio against a target phrase.

Ported from ``src/scoring/practice.py`` with Streamlit removed. The pipeline:
1. trim silence on the user recording,
2. ASR transcription (Whisper),
3. phoneme/IPA generation for target and recognised text,
4. phoneme comparison + scoring,
5. assemble a result dict.

Persistence (DB writes) is delegated to the ``on_result`` callback so this
function stays UI- and storage-agnostic. ``error_fn``/``warn_fn`` default to
logging instead of ``st.error``/``st.warning``. The whole function is safe to
run on a Qt worker thread.
"""

from __future__ import annotations

import io
import logging
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf

from .asr import ProgressFn, transcribe_audio
from .comparison import compare_phonemes
from .phonemes import get_ipa, get_phonemes, normalize_for_phoneme_scoring

logger = logging.getLogger(__name__)


def trim_silence(audio_bytes: bytes, silence_threshold: float = 0.01) -> tuple[bytes, bytes]:
    """Trim leading/trailing silence from a WAV recording.

    Returns ``(trimmed_bytes, original_bytes)``; on any failure both are the
    original bytes (lossless fallback).
    """
    try:
        buf = io.BytesIO(audio_bytes)
        audio_data, sample_rate = sf.read(buf)

        frame_length = int(0.02 * sample_rate)
        energy = np.array(
            [
                np.sum(audio_data[i : i + frame_length] ** 2)
                for i in range(0, len(audio_data) - frame_length, frame_length)
            ]
        )

        threshold = silence_threshold * np.max(energy)
        speech_frames = np.where(energy > threshold)[0]

        if len(speech_frames) > 0:
            padding_samples = int(0.2 * sample_rate)
            start = max(0, speech_frames[0] * frame_length - padding_samples)
            end = min(
                len(audio_data),
                (speech_frames[-1] + 1) * frame_length + padding_samples,
            )
            trimmed_audio = audio_data[start:end]

            trimmed_buffer = io.BytesIO()
            sf.write(trimmed_buffer, trimmed_audio, sample_rate, format="WAV")
            return trimmed_buffer.getvalue(), audio_bytes
        return audio_bytes, audio_bytes
    except Exception:
        return audio_bytes, audio_bytes


def practice_word_from_audio(
    text: str,
    audio_bytes: bytes,
    settings: dict,
    *,
    language: str = "Portuguese",
    on_result: Callable[[dict[str, Any]], None] | None = None,
    error_fn: Callable[[str], None] | None = None,
    warn_fn: Callable[[str], None] | None = None,
    progress_fn: ProgressFn | None = None,
    transcribe_fn: Callable[..., str] | None = None,
) -> dict[str, Any] | None:
    """Score a user's pronunciation against *text*. Returns a result dict or None.

    ``transcribe_fn`` lets callers/tests inject a stub transcriber (defaults to
    the real Whisper ``transcribe_audio``); this keeps the pipeline testable
    without loading a model.
    """
    if error_fn is None:
        error_fn = logger.error
    if warn_fn is None:
        warn_fn = logger.warning
    if transcribe_fn is None:
        transcribe_fn = transcribe_audio

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    temp_audio = tmp.name
    tmp.close()

    try:
        trimmed_wav_bytes, _ = trim_silence(
            audio_bytes, silence_threshold=settings.get("silence_threshold", 0.01)
        )
        with open(temp_audio, "wb") as f:
            f.write(trimmed_wav_bytes)

        voice = settings.get("voice", "en")
        correct_phonemes = get_phonemes(text, voice)
        correct_ipa = get_ipa(text, voice)

        recognized_text = transcribe_fn(
            temp_audio, settings, language, warn_fn=warn_fn, progress_fn=progress_fn
        )

        user_phonemes = get_phonemes(recognized_text, voice)
        user_ipa = get_ipa(recognized_text, voice)

        correct_phonemes_normalized = normalize_for_phoneme_scoring(correct_phonemes)
        user_phonemes_normalized = normalize_for_phoneme_scoring(user_phonemes)

        algorithm = settings.get("comparison_algorithm", "edit_distance")
        exact_match, similarity, edit_distance = compare_phonemes(
            user_phonemes_normalized, correct_phonemes_normalized, algorithm=algorithm
        )

        result: dict[str, Any] = {
            "target": text,
            "recognized": recognized_text,
            "correct_phonemes": correct_phonemes,
            "user_phonemes": user_phonemes,
            "correct_ipa": correct_ipa,
            "user_ipa": user_ipa,
            "exact_match": exact_match,
            "similarity": similarity,
            "edit_distance": edit_distance,
            "correct_phonemes_normalized": correct_phonemes_normalized,
            "user_phonemes_normalized": user_phonemes_normalized,
            "user_audio_bytes": audio_bytes,
            "user_audio_trimmed_bytes": trimmed_wav_bytes,
        }

        if on_result is not None:
            on_result(result)
        return result

    except Exception as e:  # noqa: BLE001 - mirror source's broad guard
        error_fn(f"Error during practice: {e}")
        return None
    finally:
        Path(temp_audio).unlink(missing_ok=True)
