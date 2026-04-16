"""
Practice orchestration: process recorded audio against a target phrase.

This module contains the core logic for:
1. Silence trimming on user recordings
2. ASR transcription
3. Phoneme comparison and scoring
4. Result assembly

The function practice_word_from_audio() is the main entry point.
Session persistence (st.session_state writes, DB saves) is handled by
the caller in app.py via the on_result callback.
"""

import io
import tempfile
from pathlib import Path
from typing import Dict, Optional, Callable, Any

import numpy as np
import soundfile as sf

from scoring.phonemes import (
    get_phonemes,
    get_ipa,
    normalize_for_phoneme_scoring,
)
from scoring.comparison import compare_phonemes
from audio.asr import transcribe_audio


def trim_silence(
    audio_bytes: bytes,
    silence_threshold: float = 0.01,
) -> tuple[bytes, bytes]:
    """
    Trim silence/noise from the start and end of a WAV recording.

    Uses energy-based detection with configurable threshold.

    Args:
        audio_bytes: Raw WAV audio bytes
        silence_threshold: Fraction of max energy below which frames are
            considered silence (default 0.01 = 1%)

    Returns:
        (trimmed_wav_bytes, original_bytes) — trimmed version and the
        original passed through unchanged. If trimming fails, both are
        the original bytes.
    """
    try:
        # Write bytes to a temporary in-memory buffer for sf.read
        buf = io.BytesIO(audio_bytes)
        audio_data, sample_rate = sf.read(buf)

        # Short-term energy (20 ms frames)
        frame_length = int(0.02 * sample_rate)
        energy = np.array([
            np.sum(audio_data[i : i + frame_length] ** 2)
            for i in range(0, len(audio_data) - frame_length, frame_length)
        ])

        threshold = silence_threshold * np.max(energy)
        speech_frames = np.where(energy > threshold)[0]

        if len(speech_frames) > 0:
            padding_samples = int(0.2 * sample_rate)  # 200 ms padding
            start = max(0, speech_frames[0] * frame_length - padding_samples)
            end = min(
                len(audio_data),
                (speech_frames[-1] + 1) * frame_length + padding_samples,
            )
            trimmed_audio = audio_data[start:end]

            trimmed_buffer = io.BytesIO()
            sf.write(trimmed_buffer, trimmed_audio, sample_rate, format="WAV")
            return trimmed_buffer.getvalue(), audio_bytes
        else:
            return audio_bytes, audio_bytes
    except Exception:
        return audio_bytes, audio_bytes


def practice_word_from_audio(
    text: str,
    audio_bytes: bytes,
    settings: Dict,
    *,
    language: str = "Portuguese",
    on_result: Optional[Callable[[Dict[str, Any]], None]] = None,
    error_fn: Optional[Callable] = None,
    warn_fn: Optional[Callable] = None,
) -> Optional[Dict[str, Any]]:
    """
    Score a user's pronunciation against a target phrase.

    This is the core practice pipeline:
    1. Save audio to temp file and trim silence
    2. Generate phonemes and IPA for the target text
    3. Transcribe the user's audio (ASR)
    4. Generate phonemes and IPA for the recognised text
    5. Compare phonemes using the configured algorithm
    6. Assemble and return the result dict

    Session-state persistence and DB writes are delegated to on_result().

    Args:
        text: Target phrase the user is trying to pronounce
        audio_bytes: Raw WAV bytes from the user's recording
        settings: User settings dict (voice, silence_threshold,
            comparison_algorithm, asr_engine, whisper_model_size)
        language: Language name for ASR (e.g. "Portuguese")
        on_result: Callback invoked with the result dict for session
            persistence. Called before returning.
        error_fn: Error display callback (defaults to st.error)
        warn_fn: Warning display callback (defaults to st.warning)

    Returns:
        Result dict with keys: target, recognized, correct_phonemes,
        user_phonemes, correct_ipa, user_ipa, exact_match, similarity,
        edit_distance, correct_phonemes_normalized,
        user_phonemes_normalized, user_audio_bytes,
        user_audio_trimmed_bytes.  Returns None on error.
    """
    # Lazy import to avoid circular dependency at module load time
    import streamlit as _st

    if error_fn is None:
        error_fn = _st.error
    if warn_fn is None:
        warn_fn = _st.warning

    # Create temp file properly (cleaned up in finally block)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    temp_audio = tmp.name
    tmp.close()

    try:
        with open(temp_audio, "wb") as f:
            f.write(audio_bytes)

        # Trim silence
        trimmed_wav_bytes, _ = trim_silence(
            audio_bytes,
            silence_threshold=settings.get("silence_threshold", 0.01),
        )

        # Write trimmed audio back to temp file for ASR
        with open(temp_audio, "wb") as f:
            f.write(trimmed_wav_bytes)

        # Target phonemes and IPA
        voice = settings.get("voice", "en")
        correct_phonemes = get_phonemes(text, voice)
        correct_ipa = get_ipa(text, voice)

        # ASR
        recognized_text = transcribe_audio(
            temp_audio, settings, language, warn_fn=warn_fn
        )

        # User phonemes and IPA
        user_phonemes = get_phonemes(recognized_text, voice)
        user_ipa = get_ipa(recognized_text, voice)

        # Normalise for comparison
        correct_phonemes_normalized = normalize_for_phoneme_scoring(
            correct_phonemes
        )
        user_phonemes_normalized = normalize_for_phoneme_scoring(user_phonemes)

        # Score
        algorithm = settings.get("comparison_algorithm", "edit_distance")
        exact_match, similarity, edit_distance = compare_phonemes(
            user_phonemes_normalized,
            correct_phonemes_normalized,
            algorithm=algorithm,
        )

        result = {
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

        # Delegate session persistence to caller
        if on_result is not None:
            on_result(result)

        return result

    except Exception as e:
        error_fn(f"Error during practice: {e}")
        import traceback
        error_fn(traceback.format_exc())
        return None

    finally:
        Path(temp_audio).unlink(missing_ok=True)
