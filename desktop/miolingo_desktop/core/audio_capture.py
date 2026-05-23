"""Microphone capture -> WAV bytes (UI-free).

Uses ``sounddevice`` (cross-platform, simple) to record at 16 kHz mono, matching
the source app's recording format and Whisper's expected sample rate. Returns
in-memory WAV bytes so the practice pipeline never touches the filesystem for
capture.

Recording obviously needs a microphone, so the live-capture path is exercised
only by a ``@pytest.mark.manual`` test. ``encode_wav`` (pure) is unit-tested.
"""

from __future__ import annotations

import io

import numpy as np
import soundfile as sf

SAMPLE_RATE = 16000


def encode_wav(samples: np.ndarray, sample_rate: int = SAMPLE_RATE) -> bytes:
    """Encode float/int samples to WAV bytes (in memory)."""
    buf = io.BytesIO()
    sf.write(buf, samples, sample_rate, format="WAV")
    return buf.getvalue()


def record_wav(duration: float = 3.0, sample_rate: int = SAMPLE_RATE) -> bytes:
    """Record *duration* seconds from the default input device as WAV bytes.

    Blocking — call this from a Qt worker thread, never the UI thread. Raises
    ``RuntimeError`` if ``sounddevice`` (PortAudio) is unavailable.
    """
    try:
        import sounddevice as sd
    except Exception as e:  # noqa: BLE001 - import or PortAudio init failure
        raise RuntimeError(f"Audio input unavailable: {e}") from e

    frames = int(duration * sample_rate)
    recording = sd.rec(frames, samplerate=sample_rate, channels=1, dtype="float32")
    sd.wait()
    return encode_wav(recording.reshape(-1), sample_rate)
