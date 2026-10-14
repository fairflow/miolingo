"""Native human speech: a sample of the Common Phone corpus (Mozilla Common Voice recordings), read only.

    <python> -m lab.build_cp select      choose the utterances -> var/lab/cp/selection.json  (+ the list for tar, en)
    <python> -m lab.build_cp extract     English only: pull the chosen wav and TextGrid files out of cp-1-0.tgz into
                                         var/lab/cp_en/ (nothing is written under ~/datasets)
    <python> -m lab.build_cp items       -> var/lab/cp/items.jsonl  (sets "cp" and "cpflip")

Where: ~/datasets/common_phone/CP/{de,fr} (extracted, wav + TextGrid); English is only inside
~/datasets/common_phone/cp-1-0.tgz.  Up to N = 300 utterances a language from the TEST split (the sound check was
calibrated on the dev split: other speakers), at most PER_SPEAKER from one speaker, accent = the variant's country
(germany, france, england).  English has 181 such test utterances; the rest come from the train split (never dev).
French utterances with a typographic apostrophe are skipped (their corpus labels are wrong; Miolingo
docs/research/phonetics/common_phone_apostrophe_report.md), as are texts with digits.

"cp": a native reading the sentence: a CORRECT reading, scored against `env.target_ipa` of its text, as the app does.
The corpus's own phone labels (TextGrid tiers) are in another symbol convention (ʀ, ɐ, ʔ, no espeak diphthong
tokens) and are not used.

"cpflip": the same audio with ONE expected sound changed to a typical English-speaker error (Miolingo
`sound_check.yaml: english_l1_errors`, the design of scripts/sound_check/calibrate.py): the target says [ɹ] where the
native says [ɾ], and so on.  Roles reversed: a real learner would say the English sound for the German target.  A proxy,
but real speech.  One change an utterance, the error kinds used in turn; "truth" gives the place(s) of the changed
sound(s) in the changed target.  German adds [y] -> [ʊ] beside the list's [ʏ] -> [ʊ] (espeak writes short ü as y)."""
from __future__ import annotations

import collections
import csv
import json
import os
import random
import subprocess
import sys
from pathlib import Path

from . import analyse as A
from . import engine_py as E
from .common import LAB, VARIANT, write_json, write_jsonl

CP = Path.home() / "datasets" / "common_phone" / "CP"
TGZ = Path.home() / "datasets" / "common_phone" / "cp-1-0.tgz"
EN = LAB / "cp_en" / "CP" / "en"
OUT = LAB / "cp"
N = 300
PER_SPEAKER = 3
ACCENT = {"de": "germany", "fr": "france", "en": "england"}
SEED = 20261014
EXTRA_FLIPS = {"de": [["y", "ʊ"]]}


def base(lang):
    return EN if lang == "en" else CP / lang


def rows_of(lang, split):
    f = base(lang) / f"{split}.csv"
    with f.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def select():
    OUT.mkdir(parents=True, exist_ok=True)
    sel = {}
    for lang in ("de", "fr", "en"):
        b = base(lang)
        if not (b / "test.csv").exists():
            sel[lang] = {"note": "not on disk", "items": []}
            continue
        meta = {r["id"]: r for r in csv.DictReader((b / "meta.csv").open(encoding="utf-8"))}
        rng = random.Random(f"{SEED}-{lang}")
        chosen, per = [], collections.Counter()
        skipped = collections.Counter()
        for split in (("test", "train") if lang == "en" else ("test",)):
            rows = rows_of(lang, split)
            rng.shuffle(rows)
            for r in rows:
                if len(chosen) >= N:
                    break
                if (meta.get(r["id"]) or {}).get("accent") != ACCENT[lang]:
                    skipped["other accent or none given"] += 1
                    continue
                t = r["text"]
                if "’" in t:
                    skipped["typographic apostrophe"] += 1
                    continue
                if any(c.isdigit() for c in t):
                    skipped["digits"] += 1
                    continue
                if per[r["id"]] >= PER_SPEAKER:
                    skipped["speaker has enough"] += 1
                    continue
                stem = Path(r["audio file"]).stem
                if lang != "en" and not (b / "wav" / f"{stem}.wav").exists():
                    skipped["no wav"] += 1
                    continue
                per[r["id"]] += 1
                chosen.append({"stem": stem, "text": t, "speaker": r["id"][:10], "split": split,
                               "gender": (meta.get(r["id"]) or {}).get("gender"), "age": (meta.get(r["id"]) or {}).get("age")})
        sel[lang] = {"items": chosen, "speakers": len(per), "skipped": dict(skipped),
                     "by_split": dict(collections.Counter(c["split"] for c in chosen))}
        print(lang, len(chosen), "utterances,", len(per), "speakers", sel[lang]["by_split"], dict(skipped))
    write_json(OUT / "selection.json", sel, indent=1)
    if sel.get("en", {}).get("items"):
        lst = OUT / "en_tar_list.txt"
        lst.write_text("".join(f"CP/en/wav/{c['stem']}.wav\nCP/en/grids/{c['stem']}.TextGrid\n" for c in sel["en"]["items"]), "utf-8")
        print("tar list:", lst)


def extract():
    lst = OUT / "en_tar_list.txt"
    dest = LAB / "cp_en"
    dest.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(["tar", "-x", "-z", "-f", str(TGZ), "-C", str(dest), "-T", str(lst)], capture_output=True, text=True)
    print("tar exit", r.returncode, r.stderr[-300:])
    sel = json.loads((OUT / "selection.json").read_text("utf-8"))
    have = sum((EN / "wav" / f"{c['stem']}.wav").exists() for c in sel["en"]["items"])
    print("English wavs extracted:", have, "of", len(sel["en"]["items"]))


def find_sub(seq, pat):
    n, m = len(seq), len(pat)
    return [i for i in range(n - m + 1) if seq[i:i + m] == pat]


def items():
    import env
    from env import _miolingo as mio
    import soundfile as sf
    sel = json.loads((OUT / "selection.json").read_text("utf-8"))
    out, stats = [], {}
    for lang in ("de", "fr", "en"):
        variant = VARIANT[lang]
        cfg = mio.sound_check.lang_config(env.variant(variant)["espeak"])
        flips = [list(e) for e in (cfg.get("english_l1_errors") or [])] + EXTRA_FLIPS.get(lang, [])
        flips = [(e, [list(env.phones_of(env.norm_word(x))) for x in e]) for e in flips]
        used = collections.Counter()
        rng = random.Random(f"{SEED}-flip-{lang}")
        n_cp = n_flip = 0
        bad = collections.Counter()
        for c in sel.get(lang, {}).get("items", []):
            wav = base(lang) / "wav" / f"{c['stem']}.wav"
            if not wav.exists():
                bad["no wav"] += 1
                continue
            info = sf.info(str(wav))
            if info.duration > 20:
                bad["longer than 20 s"] += 1
                continue
            voice = env.variant(variant)["espeak"]
            raw = mio.phonemes.get_ipa(c["text"], voice)
            if "?" in raw:
                bad["espeak wrote ?? for a sound"] += 1
                continue
            target = A.target_of(c["text"], variant)
            T = E.flat(target)
            if not T:
                bad["no target"] += 1
                continue
            it = {"id": f"cp-{lang}-{c['stem']}", "set": "cp", "lang": lang, "variant": variant, "text": c["text"],
                  "wav": str(wav), "speaker": c["speaker"], "seconds": round(info.duration, 2)}
            out.append(it)
            n_cp += 1
            # one flip: the applicable error used least so far
            cands = []
            for (e, (exp, said)) in flips:
                # occurrences of the expected sound(s) inside one word
                k, occ = 0, []
                for w in target:
                    occ += [k + i for i in find_sub(w, exp)]
                    k += len(w)
                if occ:
                    cands.append((used[tuple(e)], rng.random(), e, exp, said, occ))
            if not cands:
                continue
            _n, _r, e, exp, said, occ = min(cands)
            at = rng.choice(occ)
            used[tuple(e)] += 1
            new, k = [], 0
            for w in target:
                if k <= at < k + len(w):
                    j = at - k
                    new.append(w[:j] + said + w[j + len(exp):])
                else:
                    new.append(list(w))
                k += len(w)
            out.append({**it, "id": f"cpflip-{lang}-{c['stem']}", "set": "cpflip", "target": new,
                        "truth": {"kind": "flip", "pos": list(range(at, at + len(said))), "expected": e[0], "changed_to": e[1],
                                  "t": e[1], "s": e[0]}})
            n_flip += 1
        stats[lang] = {"cp": n_cp, "cpflip": n_flip, "flips_used": {f"{a}->{b}": n for (a, b), n in used.items()},
                       "flips_never_applicable": [f"{e[0]}->{e[1]}" for (e, _p) in flips if tuple(e) not in used],
                       "dropped": dict(bad)}
        print(lang, stats[lang])
    write_jsonl(OUT / "items.jsonl", out)
    write_json(OUT / "stats.json", stats, indent=1)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    {"select": select, "extract": extract, "items": items}.get(cmd, lambda: sys.exit(__doc__))()
