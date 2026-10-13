"""`audible`: a cheap level check of a recording."""
from __future__ import annotations

import numpy as np
import soundfile as sf

from . import _miolingo as mio

# Decided here (the pipeline document says Miolingo has no such test):
ABS_FLOOR_RMS = 0.003      # about -50 dBFS: below this a frame is silence
MIN_VOICED_SECONDS = 0.25  # at least this much sound above the floor
FRAME = 0.02               # seconds, as Miolingo's trim_silence
# Relative threshold: Miolingo's `silence_threshold` setting is a fraction of
# the 95th-percentile frame ENERGY; as an RMS ratio it is its square root.
REL_RMS = float(mio.mio_config.DEFAULT_SETTINGS.get("silence_threshold", 0.01)) ** 0.5


def audible(wav_path: str) -> bool:
    """True iff the file holds at least MIN_VOICED_SECONDS of sound that is
    both above an absolute floor and above Miolingo's relative silence
    threshold.  False for unreadable, empty, silent or near-silent files."""
    try:
        data, sr = sf.read(wav_path, dtype="float32", always_2d=True)
    except Exception:
        return False
    if data.size == 0:
        return False
    x = data.mean(axis=1)
    n = int(FRAME * sr)
    if n <= 0 or len(x) < n:
        return False
    frames = x[: (len(x) // n) * n].reshape(-1, n)
    rms = np.sqrt((frames ** 2).mean(axis=1))
    thr = max(ABS_FLOOR_RMS, REL_RMS * float(np.percentile(rms, 95)))
    voiced = int((rms > thr).sum())
    return voiced * FRAME >= MIN_VOICED_SECONDS
