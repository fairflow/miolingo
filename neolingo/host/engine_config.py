"""The engine's configuration (protocol section 5), built from env and data/cost_table.json."""
import json
import os

import env
from env.soundcheck import VERIFY_LANGS
from lab.analyse import FULL_VOWELS
from .paths import DATA

LANGUAGE_NAMES = {"en": "English", "fr": "French", "de": "German"}
CURVE = {"kind": "sqrt", "scale": 2250000}
# protocol 5, `significant` (since 14 October): for the PICTURE of a result only, never the score; a substitution costing
# this much or more is drawn `off`, less (and not 0) `near`.  The costs sent are raw panphon feature distances
# (thousandths), not Miolingo's stretched ones, so the number is small: 42 is the raw-cost equivalent of Miolingo's 340.
SIGNIFICANT = 42


def equiv_enabled():
    """The switch NEOLINGO_EQUIV: "1" = treat the pairs of data/symbol_equivalents.json as the same sound (default off)."""
    return os.environ.get("NEOLINGO_EQUIV", "0") == "1"


def equivalents(lang=None):
    """{lang: [(target, heard), ...]} from data/symbol_equivalents.json; {} when the switch is off or the file is missing.
    With `lang`, just that language's list.  Direction matters: (target sound, sound the recogniser wrote)."""
    out = {}
    f = DATA / "symbol_equivalents.json"
    if equiv_enabled() and f.exists():
        d = json.loads(f.read_text("utf-8"))
        for code, rows in (d.get("languages") or {}).items():
            out[code] = [(r["target"], r["heard"]) for r in rows.get("included", [])]
    return out.get(lang, []) if lang is not None else out


def build_costs(table):
    """cost entries in thousandths.

    Generic entries (neither variant nor lang): the full panphon-based matrix, off the diagonal (an equal pair
    is not asked: the engine treats it as 0).  Entries with "lang":L override for every variant of language L
    (protocol section 5; they were sent once per variant before, which doubled English).  They are:
      tolerated pairs -> 0 (both directions); with NEOLINGO_EQUIV=1 also the pairs of data/symbol_equivalents.json
      -> 0 (target -> heard only); accept[t][h] = w -> base * (1 - w); unreliable targets -> 0
      against every phone of the table, EXCEPT, in a language of the German ü/ö rule (env.soundcheck.VERIFY_LANGS),
      against a full vowel of the language (lab.analyse.FULL_VOWELS), where the plain panphon cost stands: the lab's
      "phoneme" cost mode of `rec de`, so that a substitution the rule flags (ü heard as u, confirmed by the likelihood
      ratio) is aligned and costed as the lab did; an unflagged one is not counted by the engine (V2, `unjudged`).
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
        for t, h in equivalents(code):
            put(t, h, 0)
        for t, d in lang["accept"].items():
            for h, w in d.items():
                put(t, h, round(base.get((t, h), other) * (1000 - w) / 1000))
        verified = FULL_VOWELS.get(code, set()) if code in VERIFY_LANGS else set()
        for t in lang["unreliable"]:
            for h in P:
                if h in verified:
                    over.pop((t, h), None)          # the plain cost (the lab's Costs "phoneme": generic entry)
                else:
                    put(t, h, 0)
        out += [{"lang": code, "target": t, "heard": h, "cost": c} for (t, h), c in over.items()
                if base.get((t, h), other) != c]
    return out


def build_unjudged(table, langs):
    """protocol 5, `unjudged` (since 14 October): per language, the target sounds the recogniser cannot judge, as
    [{"lang": L, "sounds": [...]}] (a language with none is left out).  Taken from the cost table's `unreliable` list, which
    env.tables builds from Miolingo's calibrated sound check (scoring/data/sound_check_calibrated.yaml, normalised as the
    engine holds sounds, length attached): German y yː øː œ ɔø, English a eə iə ɒ ɔɪ əʊ ʊə, French none (its calibrated
    entry is a lone length mark, which is no sound).  Such a sound with no flag at its place is drawn `unjudged` and its
    heard sound taken as the target's; with a flag it is judged like any other."""
    return [{"lang": l, "sounds": list(table["langs"][l]["unreliable"])} for l in langs
            if (table["langs"].get(l) or {}).get("unreliable")]


def build_config():
    vs = env.variants()
    table = json.loads((DATA / "cost_table.json").read_text("utf-8"))
    langs = sorted({v["lang"] for v in vs}, key=["en", "fr", "de"].index)
    return {"cmd": "config",
            "variants": [{"code": v["code"], "name": v["name"]} for v in vs],
            "languages": [{"code": l, "name": LANGUAGE_NAMES[l]} for l in langs],
            "costs": build_costs(table), "costOtherwise": table["unknown_cost"], "significant": SIGNIFICANT,
            "unjudged": build_unjudged(table, langs), "curve": CURVE}
