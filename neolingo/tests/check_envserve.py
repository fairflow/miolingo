"""THE REFERENCE for the speech service (host/envserve.py): the real host's OWN DRIVER (host.serve.Host.press, its
engine, its environment, its configuration) on a COPY of var/, given the test recordings beside the host, phrase by
phrase.  Its results are what a page with the engine in the browser and the speech service must reproduce (locus
web/neolingo/test/speech-compare.ts compares them, case by case: understood, score, the picture, the banner, the heard
text, the flag lines; for a recording that is not audible, Record's and Check's step and message).

    cp a backup:  sqlite3 var/neolingo.sqlite ".backup <COPY>/neolingo.sqlite"
    NEOLINGO_VAR=<COPY> NEOLINGO_SLOTS=1 NEOLINGO_TTS=en-gb=say,de=say \\
      ~/Software/working/miolingo/venv/bin/python -m tests.check_envserve --out <file.json>

It refuses to run on this folder's var/.  The recordings are read from var/ (the synthetic ones tests/check_env.py made:
espeak-ng, not a learner) and copied into the COPY's takes/; nothing is written to var/."""
import argparse
import json
import os
import secrets
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REAL_VAR = (ROOT / "var").resolve()
if not os.environ.get("NEOLINGO_VAR") or Path(os.environ["NEOLINGO_VAR"]).resolve() == REAL_VAR:
    sys.exit("check_envserve: set NEOLINGO_VAR to a COPY of var/ (never var/ itself)")
sys.path.insert(0, str(ROOT))
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

from host import paths                      # noqa: E402
from host import serve                      # noqa: E402

# (recording in var/, the phrase practised, its variant): the phrases tests/check_env.py synthesised them from
FR, EN, DE = "Pouvez-vous m'indiquer le chemin?", "Thank you very much", "Ich möchte einen Termin vereinbaren"
CASES = [
    ("fr-fr_good.wav", FR, "fr-fr"), ("fr-fr_wrongphrase.wav", FR, "fr-fr"),
    ("en-gb_good.wav", EN, "en-gb"), ("en-gb_wrongphrase.wav", EN, "en-gb"),
    ("de_good.wav", DE, "de"), ("de_wrongphrase.wav", DE, "de"),
    ("silence.wav", FR, "fr-fr"), ("hiss.wav", FR, "fr-fr"), ("click.wav", FR, "fr-fr"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    serve.HOST = host = serve.Host()                 # the real host's start: slot 1, "me" signed in
    p = lambda m: host.press(m)                      # noqa: E731
    d = p({"cmd": "state"})
    me = next((x for x in host.store.all_data() if x["uid"] == "me"), None)
    out = {"host": serve.HOST_COMMIT, "costs": serve.cost_option()[0], "engine": paths.ENGINE,
           "settings": me["settings"] if me else None, "cases": []}
    for wav, phrase, variant in CASES:
        t0 = time.perf_counter()
        sc = d["screens"][0]
        if sc["settings"]["practised"] != variant:
            p({"press": "openSettings", "session": 1, "input": None})
            p({"press": "practised", "session": 1, "input": variant})
            d = p({"press": "closeSettings", "session": 1, "input": None})
        d = p({"press": "load", "session": 1, "input": phrase})
        tok = "t" + secrets.token_hex(8)
        shutil.copyfile(REAL_VAR / wav, paths.TAKES / f"{tok}.wav")
        rec = p({"press": "record", "session": 1, "input": tok})
        chk = p({"press": "check", "session": 1, "input": None})
        res = chk["screens"][0]["body"].get("result") if chk.get("screens") else None
        out["cases"].append({"wav": wav, "phrase": phrase, "variant": variant,
                             "record": {"step": rec.get("step"), "message": rec.get("message")},
                             "check": {"step": chk.get("step"), "message": chk.get("message")},
                             "result": res if chk.get("step") else None,
                             "answers": host.engine.last_answers, "seconds": round(time.perf_counter() - t0, 2)})
        print(f"{wav:24} record {rec.get('step')} {rec.get('message')!r}; check {chk.get('step')} "
              f"{(res or {}).get('score') if chk.get('step') else chk.get('message')!r}", flush=True)
        d = chk if chk.get("screens") else d
    Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=1), "utf-8")
    host.close()
    print(f"written {a.out}")


if __name__ == "__main__":
    main()
