"""
See and hear the discrepancy (HANDOFF §2) -- data layer, UI-agnostic.

For a flagged segment (cut at alignment boundaries):
  hear: learner segment (word and isolated sound), slowed copy, native exemplar
  see:  waveform, spectrogram, the measurement that drove the verdict
        (voiced-band envelope with occlusion markers; F3 track vs the speaker's
        reference -- the rhotic cues), target vs realised IPA.

Native exemplars come from a bank directory (MIO_NATIVE_BANK/<l2>/<word>.wav,
optional <word>.json = MFA alignment) built by
scripts/realised_phone/build_native_bank.py from aligned native corpora
(Common Phone es on the M4). If no exemplar exists, the view says so.
"""

from __future__ import annotations

import io
import json
import os
from pathlib import Path
from typing import Optional

import numpy as np

from realised_phone.align import parse_mfa_json
from realised_phone.detectors.rhotic import envelope_db, f3_track, load_calibration
from realised_phone.model import Verdict


def wav_bytes(x: np.ndarray, sr: int) -> bytes:
    import soundfile as sf
    buf = io.BytesIO()
    sf.write(buf, np.clip(x, -1, 1), sr, format="WAV", subtype="PCM_16")
    return buf.getvalue()


def cut(x: np.ndarray, sr: int, start: float, end: float, pad: float = 0.0) -> np.ndarray:
    s = max(0, int((start - pad) * sr))
    e = min(len(x), int((end + pad) * sr))
    return x[s:e]


def slowed(x: np.ndarray, sr: int, factor: float = 2.0) -> np.ndarray:
    """Time-stretch without pitch change (Praat overlap-add)."""
    import parselmouth
    from parselmouth.praat import call
    if len(x) < int(0.05 * sr):
        x = np.pad(x, (0, int(0.05 * sr) - len(x)))
    snd = parselmouth.Sound(x.astype(np.float64), sampling_frequency=sr)
    out = call(snd, "Lengthen (overlap-add)", 75, 600, factor)
    return np.asarray(out.values[0])


def spectrogram(x: np.ndarray, sr: int, max_hz: float = 5500.0,
                n_t: int = 160, n_f: int = 64) -> dict:
    """Downsampled dB spectrogram for plotting: {'t', 'f', 'db'} (db: n_f x n_t)."""
    import parselmouth
    snd = parselmouth.Sound(x.astype(np.float64), sampling_frequency=sr)
    sp = snd.to_spectrogram(window_length=0.005, maximum_frequency=max_hz)
    v = 10 * np.log10(np.asarray(sp.values) + 1e-12)
    ti = np.linspace(0, v.shape[1] - 1, min(n_t, v.shape[1])).astype(int)
    fi = np.linspace(0, v.shape[0] - 1, min(n_f, v.shape[0])).astype(int)
    xs = np.asarray(sp.xs())
    ys = np.asarray(sp.ys())
    return {"t": xs[ti].tolist(), "f": ys[fi].tolist(), "db": v[np.ix_(fi, ti)].round(1).tolist()}


def segment_view(x: np.ndarray, sr: int, v: Verdict, word_span: tuple[float, float],
                 pad: float = 0.12) -> dict:
    """Everything the UI needs for one flagged verdict."""
    cal = load_calibration()
    s0 = max(0.0, v.start - pad)
    region = cut(x, sr, v.start, v.end, pad)
    t_env, env = envelope_db(region, sr, cal)
    ts, f3 = f3_track(x, sr, cal)
    sel = (ts >= s0) & (ts <= v.end + pad)
    det = next((e for e in v.evidence if e.source == "detector"), None)
    m = det.measurements if det else {}
    wav_word = cut(x, sr, word_span[0], word_span[1], 0.03)
    wav_sound = cut(x, sr, v.start, v.end, 0.03)
    return {
        "target_ipa": v.target, "realised": v.realised_phone or v.realised_class,
        "status": v.status, "between": v.between, "word": v.word, "context": v.context,
        "segment": (v.start, v.end), "offset": s0,
        "waveform": {"t": (np.arange(0, len(region), max(1, len(region) // 800)) / sr + s0).tolist(),
                     "y": region[:: max(1, len(region) // 800)].round(4).tolist()},
        "envelope": {"t": (t_env + s0).tolist(), "db": env.round(2).tolist(),
                     "occlusions": [o["t"] for o in m.get("occlusions", [])]},
        "f3": {"t": ts[sel].tolist(), "hz": [None if not np.isfinite(h) else round(float(h), 1)
                                             for h in f3[sel]],
               "reference_hz": m.get("f3_reference_hz"),
               "lowered_below_hz": (m.get("f3_reference_hz") or 0) * cal["formant"]["f3_ratio_max"] or None},
        "spectrogram": spectrogram(region, sr),
        "audio": {"word": wav_bytes(wav_word, sr), "sound": wav_bytes(wav_sound, sr),
                  "word_slow": wav_bytes(slowed(wav_word, sr), sr),
                  "sound_slow": wav_bytes(slowed(wav_sound, sr, 3.0), sr)},
        "measurements": m,
    }


def native_exemplar(word: str, l2: str, target: str,
                    bank: Optional[str] = None) -> Optional[dict]:
    """Native word audio (+ isolated target sound if the bank has its alignment)."""
    root = Path(bank or os.environ.get("MIO_NATIVE_BANK", "")) / l2
    wav = root / f"{word}.wav"
    if not bank and not os.environ.get("MIO_NATIVE_BANK") or not wav.exists():
        return None
    import soundfile as sf
    x, sr = sf.read(str(wav), dtype="float64")
    out = {"word": wav_bytes(x, sr), "word_slow": wav_bytes(slowed(x, sr), sr), "source": str(wav)}
    js = wav.with_suffix(".json")
    if js.exists():
        al = parse_mfa_json(json.loads(js.read_text(encoding="utf-8")))
        ph = next((p for p in al.phones if p.label == target), None)
        if ph is not None:
            snd = cut(x, sr, ph.start, ph.end, 0.03)
            out["sound"] = wav_bytes(snd, sr)
            out["sound_slow"] = wav_bytes(slowed(snd, sr, 3.0), sr)
    return out
