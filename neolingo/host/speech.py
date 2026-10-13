"""Local speech for `speak`: macOS `say` with a voice of the right language, else espeak-ng.  Cached by hash."""
import hashlib
import os
import re
import shutil
import subprocess
import tempfile

import env
from .paths import SPEECH

LOCALE = {"en-gb": "en_GB", "en-us": "en_US", "fr-fr": "fr_FR", "de": "de_DE"}
PREFERRED = ["Daniel", "Samantha", "Thomas", "Anna"]
_voices = None


def say_voices():
    """{locale: [voice names]} of the installed `say` voices."""
    global _voices
    if _voices is None:
        _voices = {}
        if shutil.which("say"):
            r = subprocess.run(["say", "-v", "?"], capture_output=True, text=True)
            for ln in r.stdout.splitlines():
                m = re.match(r"^(.+?)\s{2,}([a-z]{2}_[A-Z]{2})\s", ln)
                if m:
                    _voices.setdefault(m.group(2), []).append(m.group(1).strip())
    return _voices


def pick_voice(variant):
    vs = say_voices().get(LOCALE.get(variant, ""), [])
    for p in PREFERRED:
        if p in vs:
            return p
    return vs[0] if vs else None


def speak_wav(text, variant, slow):
    """Path of a cached 16-bit mono WAV of `text` said in `variant`."""
    v = env.variant(variant)
    voice = pick_voice(variant)
    key = hashlib.sha1(f"{text}\0{variant}\0{int(slow)}\0{voice}".encode("utf-8")).hexdigest()[:24]
    out = SPEECH / f"{key}.wav"
    if out.exists():
        return out
    with tempfile.TemporaryDirectory(dir=SPEECH) as td:
        tmp = os.path.join(td, "o.wav")
        if voice and shutil.which("say") and shutil.which("afconvert"):
            tf, aiff = os.path.join(td, "t.txt"), os.path.join(td, "o.aiff")
            with open(tf, "w", encoding="utf-8") as f:
                f.write(text)
            subprocess.run(["say", "-v", voice, "-r", "110" if slow else "175", "-o", aiff, "-f", tf], check=True)
            subprocess.run(["afconvert", "-f", "WAVE", "-d", "LEI16@22050", "-c", "1", aiff, tmp], check=True)
        else:
            subprocess.run([shutil.which("espeak-ng") or "espeak-ng", "-v", v["espeak"], "-s", "110" if slow else "160",
                            "-w", tmp, "--", text], check=True)
        os.replace(tmp, out)
    return out
