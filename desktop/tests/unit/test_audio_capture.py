"""Tests for audio capture helpers."""

from __future__ import annotations

import io

import numpy as np
import pytest
import soundfile as sf

from miolingo_desktop.core import audio_capture


def test_encode_wav_roundtrip() -> None:
    samples = (0.2 * np.sin(np.linspace(0, 6.28, 1600))).astype("float32")
    wav = audio_capture.encode_wav(samples, sample_rate=16000)
    assert wav[:4] == b"RIFF"
    back, sr = sf.read(io.BytesIO(wav))
    assert sr == 16000
    assert len(back) == len(samples)


@pytest.mark.manual
def test_record_wav_live() -> None:
    """Live mic capture — requires a microphone; excluded from the pre-PR run."""
    wav = audio_capture.record_wav(duration=0.5)
    assert wav[:4] == b"RIFF"
