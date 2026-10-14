"""NEOLINGO_COSTS (host/engine_config.cost_option, data/cost_candidates.json; the lab's third run): unset and "live"
give the same configuration; a candidate transforms it as lab/engine_py.transform does; an unknown name stops.
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


def build(name):
    if name is None:
        os.environ.pop("NEOLINGO_COSTS", None)
    else:
        os.environ["NEOLINGO_COSTS"] = name
    return EC.build_config()


def main():
    base = build(None)
    assert json.dumps(build("live"), sort_keys=True) == json.dumps(base, sort_keys=True), "live differs from unset"
    print("ok   unset and live give the same configuration")
    cands = json.loads((ROOT / "data" / "cost_candidates.json").read_text("utf-8"))["candidates"]
    for name, cand in cands.items():
        c = build(name)
        k = 1000 / cand.get("I", 1000)
        tx = ("tx", cand.get("p"), cand.get("F", 0), k, frozenset())
        assert c["costOtherwise"] == E.transform(base["costOtherwise"], tx)
        assert c["significant"] == E.transform(base["significant"], tx)
        assert c["curve"]["scale"] == round(base["curve"]["scale"] * cand.get("S", 1.0) * k * k)
        free = {(l, t, h) for (l, t, h) in cand.get("free", [])}
        got = {(e.get("lang"), e["target"], e["heard"]): e["cost"] for e in c["costs"]}
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
