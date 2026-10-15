"""Apple's premium `say` voices (installed 14 October 2026): Petra (de_DE), Audrey (fr_FR), Serena (en_GB).

    <python> -m lab.premium reference        the 48 phrases a language of data/{en,fr,de}.json
    <python> -m lab.premium nearmiss         every word of var/lab/nearmiss/pairs.json; adds the items of voice "premium"
                                             to var/lab/nearmiss/items.jsonl

`host/speech.py` knows only the compact voices and is not edited: the voice is called directly,
`say -v "<name>" -r 175 -o x.aiff -f text.txt`, then `afconvert -f WAVE -d LEI16@16000 -c 1`.  No network.
Audio: var/lab/premium/<variant>/<sha1(text)[:16]>.wav (the key of tests/reference_sweep.py)."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from .common import DATA, LAB, LANGS, VARIANT, read_jsonl, write_jsonl

VOICE = {"de": "Petra (Premium)", "fr-fr": "Audrey (Premium)", "en-gb": "Serena (Premium)"}
OUT = LAB / "premium"


def path_of(text: str, variant: str) -> Path:
    return OUT / variant / (hashlib.sha1(text.encode("utf-8")).hexdigest()[:16] + ".wav")


def synth(text: str, variant: str) -> Path:
    out = path_of(text, variant)
    if out.exists():
        return out
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=OUT) as td:
        tf, aiff, tmp = os.path.join(td, "t.txt"), os.path.join(td, "o.aiff"), os.path.join(td, "o.wav")
        with open(tf, "w", encoding="utf-8") as f:
            f.write(text)
        subprocess.run(["say", "-v", VOICE[variant], "-r", "175", "-o", aiff, "-f", tf], check=True)
        subprocess.run(["afconvert", "-f", "WAVE", "-d", "LEI16@16000", "-c", "1", aiff, tmp], check=True)
        os.replace(tmp, out)
    return out


def cmd_reference():
    n = 0
    for lang in LANGS:
        for p in json.loads((DATA / f"{lang}.json").read_text("utf-8"))["phrases"]:
            synth(p["text"], VARIANT[lang])
            n += 1
    print(n, "reference phrases in the premium voices under", OUT)


def cmd_nearmiss():
    from . import build_nearmiss as B
    from .costs import cost_table
    res = json.loads((B.OUT / "pairs.json").read_text("utf-8"))
    cfg = cost_table()
    items = [i for i in read_jsonl(B.OUT / "items.jsonl") if i["voice"] != "premium"]
    for lang in LANGS:
        variant = VARIANT[lang]
        unrel = set(cfg["langs"][lang]["unreliable"])
        chosen = res[lang]["chosen"]
        wav = {}
        for w in dict.fromkeys(w for p in chosen for w in (p["a"], p["b"])):
            wav[w] = str(synth(w, variant))
        pos_done = set()
        for p in chosen:
            for (a, ai, b, bi, tr) in B.directed(lang, [p]):
                tr["unreliable_target"] = bool(tr["t"] in unrel) if tr["kind"] == "sub" else False
                items.append({"id": f"nm-premium-{lang}-{a}-{b}", "set": "nearmiss", "lang": lang, "variant": variant,
                              "text": a, "wav": wav[b], "voice": "premium", "said": b, "said_ipa": bi, "truth": tr})
                if a not in pos_done:
                    pos_done.add(a)
                    items.append({"id": f"pos-premium-{lang}-{a}", "set": "positive", "lang": lang, "variant": variant,
                                  "text": a, "wav": wav[a], "voice": "premium"})
        print(lang, len(wav), "words in the premium voice", flush=True)
    write_jsonl(B.OUT / "items.jsonl", items)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "reference":
        cmd_reference()
    elif cmd == "nearmiss":
        cmd_nearmiss()
    else:
        sys.exit(__doc__)
