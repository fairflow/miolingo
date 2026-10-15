"""The costs of the configuration: NEOLINGO_COSTS (host/engine_config.cost_option, data/cost_candidates.json; the
lab's third run) and the shape of the cost list.

  * unset and "live" give the same configuration: the plain one (today's costs and curve) plus exactly the German
    vocalised-r pairs at 0 (ɜ, ɐ heard as r, ɾ), and the live entry's `offFloor` and `splits` (the engine mechanisms of
    locus 977af82) when it has them, nothing else changed; the pairs' warnings are dropped (free_pairs);
  * a candidate (run3, ...) transforms every entry as lab/engine_py.transform does, its free pairs at 0;
  * an unknown name stops the host;
  * an override is sent once per language.
No models, no engine.   <miolingo venv python> tests/check_costs.py   (from neolingo/)

Each case is named by the fault it guards (locus docs/neolingo-test-design.md 4D): "F1 13 Oct" for the fault below,
"designed 14 Oct" for a case written with NEOLINGO_COSTS (b6e87de, d3bf084, b0013f8), no fault of it recorded.
  F1  13 Oct (found by reading; fixed in 308100b, 14:20): the per-language overrides of the cost list (tolerated and
      accepted pairs, unreliable targets) were sent once per VARIANT, so English's twice (en-gb, en-us).  Watched
      15 Oct: with the loop over variants put back, the F1 case fails."""
import json
import os
import sys
import tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("NEOLINGO_VAR", tempfile.mkdtemp(prefix="neolingo_costs_"))

from host import engine_config as EC          # noqa: E402
from lab import engine_py as E                # noqa: E402

VR = {("de", "ɜ", "r"), ("de", "ɜ", "ɾ"), ("de", "ɐ", "r"), ("de", "ɐ", "ɾ")}
F1, D = "F1 13 Oct: ", "designed 14 Oct: "
bad = []


def check(cond, what):
    print(("ok   " if cond else "FAIL ") + what)
    if not cond:
        bad.append(what)


def build(name):
    if name is None:
        os.environ.pop("NEOLINGO_COSTS", None)
    else:
        os.environ["NEOLINGO_COSTS"] = name
    return EC.build_config()


def plain():
    """The configuration without any entry of cost_candidates.json (what the host sent before 14 October, 21:1x)."""
    real = EC.cost_option
    EC.cost_option = lambda: ("live", None)
    try:
        return EC.build_config()
    finally:
        EC.cost_option = real


def entries(c):
    return {(e.get("lang"), e["target"], e["heard"]): e["cost"] for e in c["costs"]}


def main():
    base = plain()
    default = build(None)

    # F1: an override once per language, never per variant
    keys = Counter((e.get("lang"), e["target"], e["heard"]) for e in default["costs"])
    twice = [k for k, n in keys.items() if n > 1]
    per_variant = [e for e in default["costs"] if "variant" in e]
    check(not twice and not per_variant, F1 + f"each cost entry is sent once, overrides per language "
          f"({len(default['costs'])} entries; {len(twice)} sent twice, e.g. {twice[:2]}; {len(per_variant)} per variant)")

    check(json.dumps(build("live"), sort_keys=True) == json.dumps(default, sort_keys=True),
          D + "unset and live give the same configuration")
    same = [k for k in ("costOtherwise", "significant", "curve", "unjudged", "variants", "languages") if default[k] == base[k]]
    check(len(same) == 6, D + f"the default keeps the plain configuration's {', '.join(same)}")
    live = json.loads((ROOT / "data" / "cost_candidates.json").read_text("utf-8"))["candidates"]["live"]
    want_floor = live.get("offFloor") or None
    want_splits = live.get("splits") or None
    if isinstance(want_splits, str):
        want_splits = json.loads((ROOT / "data" / want_splits).read_text("utf-8"))["splits"]
    check(default.get("offFloor") == want_floor and "offFloor" not in base,
          D + f"offFloor {default.get('offFloor')}: the live entry's, absent from the plain configuration")
    check(default.get("splits") == want_splits and "splits" not in base,
          D + f"splits: the live entry's {len(default.get('splits') or [])}, absent from the plain configuration")
    check(all(isinstance(x["heard"], list) and len(x["heard"]) == 2 and x["cost"] >= 0 for x in default.get("splits") or []),
          D + "each split is one target heard as exactly two sounds, at a cost of at least 0")
    extra = set(default) - set(base) - {"offFloor", "splits"}
    check(not extra, D + f"no other field added ({sorted(extra)})")
    b, d = entries(base), entries(default)
    check(set(d) - set(b) <= VR and all(d[k] == 0 for k in VR), D + f"the {len(VR)} German vocalised-r pairs are at 0")
    check({k: v for k, v in d.items() if k not in VR} == {k: v for k, v in b.items() if k not in VR},
          D + f"every other entry is the plain one (costOtherwise {default['costOtherwise']}, significant "
          f"{default['significant']}, scale {default['curve']['scale']})")
    os.environ.pop("NEOLINGO_COSTS", None)
    check(EC.free_pairs("de") == {(t, h) for (_l, t, h) in VR} and EC.free_pairs("en") == set() == EC.free_pairs("fr"),
          D + "the vocalised-r pairs' warnings are dropped, German only")

    cands = json.loads((ROOT / "data" / "cost_candidates.json").read_text("utf-8"))["candidates"]
    for name, cand in cands.items():
        if name == "live":
            continue
        c = build(name)
        k = 1000 / cand.get("I", 1000)
        tx = ("tx", cand.get("p"), cand.get("F", 0), k, frozenset())
        free = {(l, t, h) for (l, t, h) in cand.get("free", [])}
        got = entries(c)
        wrong = [(e.get("lang"), e["target"], e["heard"]) for e in base["costs"]
                 if (e.get("lang"), e["target"], e["heard"]) not in free
                 and got[(e.get("lang"), e["target"], e["heard"])] != E.transform(e["cost"], tx)]
        check(c["costOtherwise"] == E.transform(base["costOtherwise"], tx)
              and c["significant"] == E.transform(base["significant"], tx)
              and c["curve"]["scale"] == round(base["curve"]["scale"] * cand.get("S", 1.0) * k * k)
              and not wrong and all(got[key] == 0 for key in free),
              D + f"{name}: costOtherwise {c['costOtherwise']}, significant {c['significant']}, scale "
              f"{c['curve']['scale']}, {len(free)} free pair(s), every entry transformed ({len(wrong)} not)")
    try:
        build("no-such-candidate")
        check(False, D + "an unknown name stops the host (it was accepted)")
    except SystemExit:
        check(True, D + "an unknown name stops the host")
    os.environ.pop("NEOLINGO_COSTS", None)
    print(f"\n{len(bad)} FAILED" if bad else "\nall passed")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
