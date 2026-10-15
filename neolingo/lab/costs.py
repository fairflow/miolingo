"""The lab's configurations and the cost table as DATA (15 October: the alignment, the distance and the judgement are
the engine's own: lab/align.py and lab/batch.py; this module holds no scoring).

    config_for(kind, unrel)    the engine configuration (protocol section 5) of a lab cost variant: the host's plain
                               configuration (host/engine_config.build_config without data/cost_candidates.json), the
                               third run's candidate transform (kind = ("tx", p, F, k, free pairs), as
                               host/engine_config.apply_candidate), the `unreliable` mode ("zero": the host's own
                               entries: an unreliable target costs 0 against every sound, except in German against a
                               full vowel (the ü/ö rule's costs); "phoneme": against a full vowel of the language its
                               plain panphon cost in every language), and the splits when asked for
    Table(lang)                the table's lists for the lab's own rules: `unreliable`, `accepted_any(t, h)` (a
                               tolerated pair or on the accept list), `accepted(t, h)` (the language's entry lowers it),
                               `entry(t, h)` (the cost sent for the pair: language entry, else generic, else costOtherwise)
    curve(d, n, kind, scale)   the score of protocol section 5 from a distance: the curve is part of the configuration
                               the engine is given, written out in the protocol; the lab's scores are checked against
                               the engine's own (`python -m lab.batch compare`)"""
from __future__ import annotations

import json
import math
from functools import lru_cache

from .common import DATA

SCALE = 2250000
FULL_VOWELS = {
    "de": {"i", "iː", "ɪ", "e", "eː", "ɛ", "ɛː", "a", "aː", "ɑ", "ɑː", "u", "uː", "ʊ", "o", "oː", "ɔ"},
    "en": {"i", "iː", "ɪ", "ɛ", "a", "æ", "ɑː", "ɒ", "ɔː", "ʊ", "uː", "ʌ", "ɜː", "e", "o", "u", "ɑ", "ɔ"},
    "fr": set(),
}


@lru_cache(maxsize=None)
def cost_table():
    return json.loads((DATA / "cost_table.json").read_text("utf-8"))


@lru_cache(maxsize=None)
def _plain():
    import env  # noqa: F401
    from host import engine_config as EC
    real = EC.cost_option
    EC.cost_option = lambda: ("live", None)
    try:
        return EC.build_config()
    finally:
        EC.cost_option = real


@lru_cache(maxsize=None)
def _entries():
    generic, by_lang = {}, {}
    c = _plain()
    for e in c["costs"]:
        if "lang" in e:
            by_lang.setdefault(e["lang"], {})[(e["target"], e["heard"])] = e["cost"]
        else:
            generic[(e["target"], e["heard"])] = e["cost"]
    return generic, by_lang, c["costOtherwise"]


@lru_cache(maxsize=64)
def _config_json(kind, unrel, splits):
    from host import engine_config as EC
    c = json.loads(json.dumps(_plain()))
    tab = cost_table()
    if unrel == "phoneme":
        # an unreliable target against a full vowel of the language: the plain (generic) cost; the host already sends
        # this for German, here for every language (the first run's A5 variants)
        drop = {(l, t, h) for l, L in tab["langs"].items() for t in L.get("unreliable", []) for h in FULL_VOWELS.get(l, ())}
        c["costs"] = [e for e in c["costs"] if (e.get("lang"), e["target"], e["heard"]) not in drop]
    if isinstance(kind, tuple):
        _tag, p, F, k, free = kind
        cand = {"p": p, "F": F, "I": 1000 / k, "S": 1.0, "free": [["de", t, h] for (t, h) in sorted(free)]}
        c = EC.apply_candidate(c, cand)
    elif kind == "stretched":
        c = EC.apply_candidate(c, {"p": 0.6, "F": 0, "I": 1000, "S": 1.0, "free": []})
        c["significant"] = 340
    if splits:
        c["splits"] = json.loads((DATA / "splits.json").read_text("utf-8"))["splits"]
    return json.dumps(c, ensure_ascii=False)


@lru_cache(maxsize=None)
def _host_json():
    import env  # noqa: F401
    from host import engine_config as EC
    return json.dumps(EC.build_config(), ensure_ascii=False)


def host_config():
    """The configuration the host sends (host/engine_config.build_config, NEOLINGO_COSTS as set; unset: the default)."""
    return json.loads(_host_json())


def config_for(kind="raw", unrel="zero", splits=False):
    return json.loads(_config_json(kind, unrel, splits))


class Table:
    """The cost table's lists for one language (data for the lab's rules; no alignment, no distance)."""

    def __init__(self, lang):
        L = cost_table()["langs"].get(lang, {})
        self.lang = lang
        self.unreliable = set(L.get("unreliable", []))
        self.accept = {(t, h) for t, d in (L.get("accept") or {}).items() for h in d}
        self.accept |= {(a, b) for a, b in L.get("tolerated", [])} | {(b, a) for a, b in L.get("tolerated", [])}
        self.generic, by_lang, self.other = _entries()
        self.over = by_lang.get(lang, {})

    def entry(self, t, h):
        if t == h:
            return 0
        c = self.over.get((t, h))
        return self.generic.get((t, h), self.other) if c is None else c

    def accepted_any(self, t, h):
        return (t, h) in self.accept

    def accepted(self, t, h):
        return t != h and (t, h) in self.over and self.over[(t, h)] < self.generic.get((t, h), self.other)


@lru_cache(maxsize=None)
def table(lang):
    return Table(lang)


def curve(d, n, kind="sqrt", scale=SCALE):
    if kind == "linear":
        return 100 if n == 0 else 100 - min(100, d // (10 * n))
    D = math.isqrt(n * scale)
    return 100 if D == 0 else 100 - min(100, (d * 100 + D // 2) // D)


def flat(ipa):
    return [p for w in ipa or [] for p in w]
