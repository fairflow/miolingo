"""The owner's judged takes split once into a CHOOSE half and a JUDGE half (locus docs/neolingo-test-design.md, P6:
"choose on half the data, judge on the other").  Every later cost or rule choice is made on CHOOSE and reported on
JUDGE; JUDGE is never looked at while choosing.

    <miolingo venv python> -m lab.split_judged [--archive DIR]          (from neolingo/)

The takes: each take of var/archive/judgements.jsonl (its LAST line is its verdict, as lab/datasets.verdicts reads
it) that has a line in checks.jsonl (its variant gives the language) and a WAV in archive/takes/, and is not a test
voice (archive/overseer_takes.txt).  Stratified by (language, verdict): each stratum's ids, sorted, are shuffled with
random.Random(SEED) and cut in half; a stratum of odd size gives its extra take to CHOOSE and JUDGE in turn, in the
order of the sorted strata.  The archive is only read.

The split is FIXED: lab/judged_split.json (take ids only: no verdict, note or text) is written when absent and never
rewritten.  When it exists this script checks it: every id is still a judged take, no id is in both halves, and it
lists the judged takes since the split, which are in neither half (extending the split is a later decision)."""
import argparse
import json
import random
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPLIT = ROOT / "lab" / "judged_split.json"
SEED = 20261015
LANG_OF = {"en-gb": "en", "en-us": "en", "fr-fr": "fr", "de": "de"}
TOKEN = re.compile(r"t[0-9a-f]{16}")


def jsonl(path):
    return [json.loads(l) for l in path.read_text("utf-8").splitlines() if l.strip()] if path.exists() else []


def population(archive: Path) -> dict:
    """take -> (language, verdict) of every take eligible for the split."""
    verdict = {j["take"]: j.get("verdict") for j in jsonl(archive / "judgements.jsonl") if isinstance(j.get("take"), str)}
    variant = {c["take"]: c["variant"] for c in jsonl(archive / "checks.jsonl")}
    test = set()
    if (archive / "overseer_takes.txt").exists():
        for l in (archive / "overseer_takes.txt").read_text("utf-8").splitlines():
            if l.strip() and not l.strip().startswith("#") and TOKEN.fullmatch(l.split()[0]):
                test.add(l.split()[0])
    return {t: (LANG_OF[variant[t]], v) for t, v in verdict.items()
            if v in ("fair", "harsh", "generous") and t in variant and t not in test
            and (archive / "takes" / f"{t}.wav").exists()}


def split(pop: dict) -> tuple[list, list, dict]:
    strata = defaultdict(list)
    for t, key in pop.items():
        strata[key].append(t)
    rng, extra_to_choose, choose, judge, sizes = random.Random(SEED), True, [], [], {}
    for key in sorted(strata):
        ids = sorted(strata[key])
        rng.shuffle(ids)
        h = len(ids) // 2
        if len(ids) % 2:
            h += extra_to_choose
            extra_to_choose = not extra_to_choose
        choose += ids[:h]
        judge += ids[h:]
        sizes[key] = (h, len(ids) - h)
    return sorted(choose), sorted(judge), sizes


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--archive", type=Path, default=ROOT / "var" / "archive")
    a = ap.parse_args()
    pop = population(a.archive)
    if not SPLIT.exists():
        choose, judge, sizes = split(pop)
        for (lang, v), (c, j) in sorted(sizes.items()):
            print(f"  {lang} {v:9} choose {c:3}  judge {j:3}")
        print(f"choose {len(choose)}, judge {len(judge)} (of {len(pop)} judged takes; seed {SEED})")
        SPLIT.write_text(json.dumps({"made": "2026-10-15", "seed": SEED, "script": "lab/split_judged.py",
                                     "choose": choose, "judge": judge}, indent=1) + "\n", "utf-8")
        print(f"written: {SPLIT.relative_to(ROOT)}")
        return
    d = json.loads(SPLIT.read_text("utf-8"))
    c, j = set(d["choose"]), set(d["judge"])
    gone = sorted((c | j) - set(pop))
    new = sorted(set(pop) - c - j)
    print(f"{SPLIT.relative_to(ROOT)} (made {d['made']}, seed {d['seed']}): choose {len(c)}, judge {len(j)}; "
          f"in both {len(c & j)}; no longer eligible {len(gone)} {gone}; judged since, in neither half {len(new)}")
    sys.exit(1 if c & j or gone else 0)


if __name__ == "__main__":
    main()
