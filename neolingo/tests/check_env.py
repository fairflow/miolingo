"""Smoke test of the environment: run with Miolingo's venv:

    ~/Software/working/miolingo/venv/bin/python neolingo/tests/check_env.py

For each of en, fr, de: target_ipa of three phrases; audible / hear / sounds
on recordings.  No real recordings of the learner are used or copied: Miolingo
keeps none in the repository, and no archive of takes (MIO_AUDIO_DUMP_DIR) exists
on this machine, so every take here is SYNTHETIC (espeak-ng, written to
neolingo/var/, git-ignored).  A synthetic voice is not a learner; scores and
flags below test that the plumbing runs, not that the recognisers are accurate.
"""
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import env                                   # noqa: E402

VAR = ROOT / "var"
VAR.mkdir(exist_ok=True)
ESPEAK = shutil.which("espeak-ng") or "espeak-ng"

CASES = {
    "en-gb": ["Thank you very much", "Where is the station?", "I would like a coffee"],
    "fr-fr": ["Pouvez-vous m'indiquer le chemin?", "Je cherche la gare", "Bonjour, comment allez-vous?"],
    "de": ["Ich möchte einen Termin vereinbaren", "Wie geht's?", "Guten Tag"],
}


def synth(text, voice, name):
    p = VAR / name
    subprocess.run([ESPEAK, "-v", voice, "-w", str(p), text], check=True)
    return str(p)


def timed(f, *a):
    t = time.perf_counter()
    r = f(*a)
    return r, time.perf_counter() - t


def show(ipa):
    return "[" + " ".join("".join(w) for w in ipa) + "]"


def main():
    print("variants:", [(v["code"], v["phone_model"].split("/")[-1]) for v in env.variants()])
    # level checks on constructed files
    sr = 16000
    sf.write(VAR / "silence.wav", np.zeros(sr * 2, dtype="float32"), sr)
    sf.write(VAR / "hiss.wav", (np.random.RandomState(0).randn(sr * 2) * 0.0005).astype("float32"), sr)
    sf.write(VAR / "click.wav", np.r_[np.zeros(sr), [0.5], np.zeros(sr)].astype("float32"), sr)
    print("audible(silence, very quiet hiss, single click):",
          [env.audible(str(VAR / n)) for n in ("silence.wav", "hiss.wav", "click.wav")], "(want False x3)")
    first = {}
    for code, phrases in CASES.items():
        print(f"\n=== {code} ===")
        for t in phrases:
            ti, dt = timed(env.target_ipa, t, code)
            print(f"target_ipa({t!r}) = {show(ti)}  words={len(ti)}  {dt*1000:.0f} ms")
        tgt_text = phrases[0]
        tgt = env.target_ipa(tgt_text, code)
        espeak_voice = next(v["espeak"] for v in env.variants() if v["code"] == code)
        good = synth(tgt_text, espeak_voice, f"{code}_good.wav")
        other = synth(phrases[1], espeak_voice, f"{code}_wrongphrase.wav")
        for label, wav in (("synthetic, target phrase said", good),
                           ("synthetic, a DIFFERENT phrase said", other)):
            print(f"-- take: {label} (target is {tgt_text!r})")
            a, dt = timed(env.audible, wav)
            print(f"   audible = {a}  ({dt*1000:.0f} ms)")
            runs = ["warm call"] if code in first and label.startswith("synthetic, a DIFF") else ["first call", "warm call"]
            for run in runs:
                h, dh = timed(env.hear, wav, code)
                s, ds = timed(env.sounds, wav, tgt, code)
                print(f"   [{run}] hear {dh:.2f} s, sounds {ds:.2f} s")
            first[code] = True
            print(f"   hear.text = {h['text']!r}")
            print(f"   hear.ipa  = {show(h['ipa'])}" + (f"   note={h['note']}" if 'note' in h else ""))
            print(f"   sounds    = {s}")
            print(f"   reference score of heard vs target = {env.reference_score(h['ipa'], tgt, code)}")
    print("\ngloss samples:", env.gloss("Merci", "en", "fr-fr"), "|", env.gloss("Guten Tag", "en", "de"),
          "|", repr(env.gloss("Je cherche la gare", "en", "fr-fr")))


if __name__ == "__main__":
    main()
