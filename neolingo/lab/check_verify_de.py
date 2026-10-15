"""The German ü/ö rule of env.sounds against the lab's analysis `rec de` (lab/RESULTS.md, "Recommendation").

    <miolingo venv python> -m lab.check_verify_de [--limit N]          (from neolingo/)

A MEASUREMENT, not a host test (moved from tests/ on 15 October 2026, locus docs/neolingo-test-design.md 4F): run it
when the rule, the German phone model or the lab's analysis changes, and read the agreement.

For German items of the lab that have a target sound on the calibrated `unreliable` list (y yː øː œ ɔø): the owner's
archived takes, and the lab's near misses (a voice says "Bruder" for "Brüder") and their positives, it runs
lab.analyse.analyse(item, rec de) (from the lab's cache under var/lab/cache, read only) and env.sounds on the same take,
and compares the substitutions the lab KEEPS at `unchecked` sounds with the findings env.sounds marks "verified".
Items not in the lab's cache are skipped; fewer than 3 compared is a failure.  Loads the German phone model."""
import argparse
import os
import sys
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import env                                    # noqa: E402
from lab import analyse as A, cache, datasets  # noqa: E402

REC_DE = {"zero_equal": True, "unchecked": "phoneme_lr", "tau_unrel": 2.0, "heard": "V2", "understood": "free"}
UNREL = {"y", "yː", "øː", "œ", "ɔø"}


def lab_kept(rec):
    out, i = set(), 0
    for c, (t, h) in enumerate(rec["align0"]):
        if t is None:
            continue
        if h is not None and h != t and rec["kept"][c] and rec["check"][i]["level"] == "unchecked":
            out.add((i, h))
        i += 1
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=6, help="items of each kind (archive, near miss, positive)")
    a = ap.parse_args()

    def has_unrel(i):
        return any(s in UNREL for w in A.target_of(i["text"], i["variant"]) for s in w)
    arch = [i for i in datasets.archive_items() if i["lang"] == "de" and has_unrel(i)]
    nm = [i for i in datasets.nearmiss_items(("nearmiss", "positive")) if i["lang"] == "de"]
    near = [i for i in nm if i["set"] == "nearmiss" and (i.get("truth") or {}).get("t") in UNREL]
    pos = [i for i in nm if i["set"] == "positive" and has_unrel(i)]
    agree = differ = fired = 0
    for it in arch[:a.limit] + near[:a.limit] + pos[:a.limit]:
        try:
            cache.get_lp(it["wav"], A.BASE_MODEL["de"])
        except KeyError:
            print(f"   skipped (not in the lab's cache): {it['id']}")
            continue
        rec = A.analyse(it, REC_DE)
        lab = lab_kept(rec)
        got = env.sounds(it["wav"], rec["target"], it["variant"])
        host = {(f["at"], f["like"]) for f in got if "verified" in f}
        ok = host == lab
        agree += ok
        differ += not ok
        fired += bool(host)
        print(("  ok   " if ok else "  FAIL ") + f"{it['set']:9} {it['text']!r:36} lab {sorted(lab)} env.sounds {sorted(host)} "
              + " ".join(f"ratio {f['verified']}" for f in got if "verified" in f))
    print(f"\n{agree} agree, {differ} differ; the rule fired on {fired}")
    if differ or agree < 3:
        sys.exit("FAILED")
    print("all agree")


if __name__ == "__main__":
    main()
