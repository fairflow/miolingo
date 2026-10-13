"""The engine's configuration (protocol section 5), built from env and data/cost_table.json."""
import json

import env
from .paths import DATA

LANGUAGE_NAMES = {"en": "English", "fr": "French", "de": "German"}
CURVE = {"kind": "sqrt", "scale": 2250000}


def build_costs(table):
    """cost entries in thousandths.

    Generic entries (neither variant nor lang): the full panphon-based matrix, off the diagonal (an equal pair
    is not asked: the engine treats it as 0).  Entries with "lang":L override for every variant of language L
    (protocol section 5; they were sent once per variant before, which doubled English).  They are:
      tolerated pairs -> 0 (both directions); accept[t][h] = w -> base * (1 - w); unreliable targets -> 0
      against every phone of the table.
    A pair not listed costs `costOtherwise` (the table's unknown_cost)."""
    P, C = table["phones"], table["cost"]
    base = {(P[i], P[j]): C[i][j] for i in range(len(P)) for j in range(len(P)) if i != j}
    out = [{"target": t, "heard": h, "cost": c} for (t, h), c in base.items()]
    other = table["unknown_cost"]
    for code in dict.fromkeys(v["lang"] for v in env.variants()):
        lang = table["langs"].get(code)
        if not lang:
            continue
        over = {}
        def put(t, h, c):
            if t != h:
                over[(t, h)] = min(c, over.get((t, h), c))
        for a, b in lang["tolerated"]:
            put(a, b, 0)
            put(b, a, 0)
        for t, d in lang["accept"].items():
            for h, w in d.items():
                put(t, h, round(base.get((t, h), other) * (1000 - w) / 1000))
        for t in lang["unreliable"]:
            for h in P:
                put(t, h, 0)
        out += [{"lang": code, "target": t, "heard": h, "cost": c} for (t, h), c in over.items()
                if base.get((t, h), other) != c]
    return out


def build_config():
    vs = env.variants()
    table = json.loads((DATA / "cost_table.json").read_text("utf-8"))
    langs = sorted({v["lang"] for v in vs}, key=["en", "fr", "de"].index)
    return {"cmd": "config",
            "variants": [{"code": v["code"], "name": v["name"]} for v in vs],
            "languages": [{"code": l, "name": LANGUAGE_NAMES[l]} for l in langs],
            "costs": build_costs(table), "costOtherwise": table["unknown_cost"], "curve": CURVE}
