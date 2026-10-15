"""Unit cases of env.audible, the level check before a take is heard.  espeak-ng, no models, under a second:
    <miolingo venv python> tests/check_audible.py
Works in a temporary folder.  Exits 1 on failure.

Each case is named by the fault it guards (locus docs/neolingo-test-design.md 4D): "F1 13 Oct" for the fault below,
"designed 13 Oct" for a case written with the floor (c21d6d9), no fault of it recorded.
  F1  13 Oct (measurement: the audit's sweep of the reference voices; fixed in c21d6d9, 15:54): the floor of 0.25 s of
      sound refused the one-word phrases "Ja", "Oui", "Prost" (0.20 to 0.24 s) as "Nothing audible".  Watched 15 Oct:
      with MIN_VOICED_SECONDS back at 0.25 the three F1 cases fail.
The synthetic words are espeak's, at speeds that give 0.20 to 0.24 s of sound, as the reference voices measured."""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

os.environ.setdefault("HF_HUB_OFFLINE", "1")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import env                                                   # noqa: E402
from env import audio_level as AL                            # noqa: E402

TMP = Path(tempfile.mkdtemp(prefix="neolingo_audible_"))
ESPEAK = shutil.which("espeak-ng") or "espeak-ng"
F1, D = "F1 13 Oct: ", "designed 13 Oct: "
bad = []


def check(cond, what):
    print(("ok   " if cond else "FAIL ") + what)
    if not cond:
        bad.append(what)


def voiced(p):
    """The seconds of sound env.audible counts (its own frames and thresholds)."""
    data, sr = sf.read(str(p), dtype="float32", always_2d=True)
    x = data.mean(axis=1)
    n = int(AL.FRAME * sr)
    fr = x[: (len(x) // n) * n].reshape(-1, n)
    rms = np.sqrt((fr ** 2).mean(axis=1))
    thr = max(AL.ABS_FLOOR_RMS, AL.REL_RMS * float(np.percentile(rms, 95)))
    return int((rms > thr).sum()) * AL.FRAME


for voice, word, speed in (("de", "Ja", 260), ("fr-fr", "Oui", 175), ("de", "Prost", 260)):
    p = TMP / f"{word}.wav"
    subprocess.run([ESPEAK, "-v", voice, "-s", str(speed), "-w", str(p), word], check=True)
    check(env.audible(str(p)), F1 + f"a one-word take is audible: {word!r} ({voiced(p):.2f} s of sound)")

sr = 16000
sf.write(TMP / "silence.wav", np.zeros(sr * 2, dtype="float32"), sr)
sf.write(TMP / "hiss.wav", (np.random.RandomState(0).randn(sr * 2) * 0.0005).astype("float32"), sr)
sf.write(TMP / "click.wav", np.r_[np.zeros(sr), [0.5], np.zeros(sr)].astype("float32"), sr)
for name in ("silence", "hiss", "click"):
    p = TMP / f"{name}.wav"
    check(not env.audible(str(p)), D + f"{name} is not audible ({voiced(p):.2f} s of sound)")
check(not env.audible(str(TMP / "missing.wav")), D + "a file that cannot be read is not audible")

shutil.rmtree(TMP, ignore_errors=True)
print("\nFAILED: " + "; ".join(bad) if bad else "\nall ok")
sys.exit(1 if bad else 0)
