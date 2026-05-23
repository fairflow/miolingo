"""Tests for the practice orchestration pipeline (headless, no models/espeak).

The transcriber is injected via ``transcribe_fn`` and phoneme extraction is
monkeypatched, so the full pipeline (trim -> transcribe -> phonemes -> score ->
assemble -> on_result) runs deterministically with no Whisper model or espeak
binary. A real audio->score run is a manual test (needs a mic + model).
"""

from __future__ import annotations

import io

import numpy as np
import pytest
import soundfile as sf

from miolingo_desktop.core import practice


def _make_wav(seconds: float = 0.5, sr: int = 16000) -> bytes:
    t = np.linspace(0, seconds, int(sr * seconds), endpoint=False)
    tone = 0.3 * np.sin(2 * np.pi * 220 * t)
    buf = io.BytesIO()
    sf.write(buf, tone, sr, format="WAV")
    return buf.getvalue()


def test_trim_silence_returns_bytes() -> None:
    wav = _make_wav()
    trimmed, original = practice.trim_silence(wav)
    assert isinstance(trimmed, bytes)
    assert original == wav


def test_trim_silence_handles_garbage() -> None:
    trimmed, original = practice.trim_silence(b"not audio")
    assert trimmed == b"not audio"
    assert original == b"not audio"


def test_practice_pipeline_scores_and_calls_on_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Deterministic phonemes: target and recognised differ by one symbol.
    monkeypatch.setattr(
        practice, "get_phonemes", lambda text, voice="": "abc" if text == "ola" else "abd"
    )
    monkeypatch.setattr(practice, "get_ipa", lambda text, voice="": "[x]")

    captured: dict = {}
    result = practice.practice_word_from_audio(
        "ola",
        _make_wav(),
        {"voice": "pt-br", "comparison_algorithm": "edit_distance"},
        language="Portuguese",
        on_result=captured.update,
        transcribe_fn=lambda *a, **k: "olha",
    )

    assert result is not None
    assert result["target"] == "ola"
    assert result["recognized"] == "olha"
    assert result["exact_match"] is False
    assert result["edit_distance"] == 1
    assert result["similarity"] == pytest.approx(2 / 3)
    # on_result received the same dict.
    assert captured["target"] == "ola"


def test_practice_pipeline_returns_none_on_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(*a, **k):
        raise RuntimeError("transcription exploded")

    errors: list[str] = []
    result = practice.practice_word_from_audio(
        "ola",
        _make_wav(),
        {"voice": "pt-br"},
        transcribe_fn=_boom,
        error_fn=errors.append,
    )
    assert result is None
    assert errors and "exploded" in errors[0]
