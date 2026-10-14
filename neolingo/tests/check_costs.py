"""NEOLINGO_COSTS (host/engine_config.cost_option, data/cost_candidates.json; the lab's third run).

  * unset and "live" give the same configuration: the plain one (today's costs and curve) plus exactly the German
    vocalised-r pairs at 0 (ɜ, ɐ heard as r, ɾ), nothing else changed; their warnings are dropped (free_pairs);
  * a candidate (run3, ...) transforms every entry as lab/engine_py.transform does, its free pairs at 0;
  * an unknown name stops the host.
No models, no engine.   <miolingo venv python> tests/check_costs.py   (from neolingo/)"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("NEOLINGO_VAR", str(ROOT / "var" / "lab" / "hostvar"))

from host import engine_config as EC          # noqa: E402
from lab import engine_py as E                # noqa: E402

VR = {("de", "ɜ", "r"), ("de", "ɜ", "ɾ"), ("de", "ɐ", "r"), ("de", "ɐ", "ɾ")}


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
    assert json.dumps(build("live"), sort_keys=True) == json.dumps(default, sort_keys=True), "live differs from unset"
    print("ok   unset and live give the same configuration")
    for k in ("costOtherwise", "significant", "curve", "unjudged", "variants", "languages"):
        assert default[k] == base[k], k
    b, d = entries(base), entries(default)
    assert set(d) - set(b) <= VR and all(d[k] == 0 for k in VR), "the vocalised-r pairs are not 0"
    assert {k: v for k, v in d.items() if k not in VR} == {k: v for k, v in b.items() if k not in VR}, "other entries changed"
    os.environ.pop("NEOLINGO_COSTS", None)
    assert EC.free_pairs("de") == {(t, h) for (_l, t, h) in VR} and EC.free_pairs("en") == set() == EC.free_pairs("fr")
    print(f"ok   the default is the plain configuration plus exactly the {len(VR)} German vocalised-r pairs at 0 "
          f"(costOtherwise {default['costOtherwise']}, significant {default['significant']}, scale "
          f"{default['curve']['scale']}); their warnings are dropped")
    cands = json.loads((ROOT / "data" / "cost_candidates.json").read_text("utf-8"))["candidates"]
    for name, cand in cands.items():
        if name == "live":
            continue
        c = build(name)
        k = 1000 / cand.get("I", 1000)
        tx = ("tx", cand.get("p"), cand.get("F", 0), k, frozenset())
        assert c["costOtherwise"] == E.transform(base["costOtherwise"], tx)
        assert c["significant"] == E.transform(base["significant"], tx)
        assert c["curve"]["scale"] == round(base["curve"]["scale"] * cand.get("S", 1.0) * k * k)
        free = {(l, t, h) for (l, t, h) in cand.get("free", [])}
        got = entries(c)
        for e in base["costs"]:
            key = (e.get("lang"), e["target"], e["heard"])
            if key not in free:
                assert got[key] == E.transform(e["cost"], tx), (name, key)
        for key in free:
            assert got[key] == 0, (name, key)
        print(f"ok   {name}: costOtherwise {c['costOtherwise']}, significant {c['significant']}, scale "
              f"{c['curve']['scale']}, {len(free)} free pair(s), every entry transformed")
    try:
        build("no-such-candidate")
    except SystemExit:
        print("ok   an unknown name stops the host")
    else:
        raise AssertionError("an unknown name was accepted")
    os.environ.pop("NEOLINGO_COSTS", None)
    print("all passed")


if __name__ == "__main__":
    main()
