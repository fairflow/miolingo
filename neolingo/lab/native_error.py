"""Native-speech error of each phone model (Common Phone sample, set "cp"), comparable with the prior figures.

    <python> -m lab.native_error      -> var/lab/results/native_error.json

Per utterance: the model's greedy reading (cut as env.hear cuts it) against espeak's reading of the text
(env.target_ipa), aligned with the live costs (raw panphon distances with the language's table):
    weighted error = d / (1000 x max(m, n))     i.e. 1 - Miolingo's weighted similarity with linear normalisation
    PER            = unweighted edit distance / m   (every substitution, deletion, insertion counts 1)
Mean over utterances; also over the reference phrases per voice (synthetic, for comparison)."""
from __future__ import annotations

import json
import statistics

from . import analyse as A
from . import cache
from .common import flat
from .common import CNAM, LANGS, LV60, XLSR, write_json
from .run import RES, items

MODELS = {"en": [XLSR, LV60], "de": [XLSR, LV60], "fr": [CNAM, XLSR, LV60]}


def lev(a, b):
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i]
        for j, y in enumerate(b, 1):
            cur.append(min(prev[j - 1] + (x != y), prev[j] + 1, cur[j - 1] + 1))
        prev = cur
    return prev[-1]


def main():
    its = items()
    out = {}
    for lang in LANGS:
        cost = A.costs_for(lang, "raw", "baseline")
        for m in MODELS[lang]:
            for grp, sel in (("native (Common Phone)", [i for i in its if i["lang"] == lang and i["set"] == "cp"]),
                             ("reference Google", [i for i in its if i["lang"] == lang and i["set"] == "reference" and i["voice"] == "gtts"]),
                             ("reference compact Mac", [i for i in its if i["lang"] == lang and i["set"] == "reference" and i["voice"] == "say"]),
                             ("reference Premium Mac", [i for i in its if i["lang"] == lang and i["set"] == "reference" and i["voice"] == "premium"])):
                we, per, empty, n = [], [], 0, 0
                for it in sel:
                    if not cache.has_lp(it["wav"], m):
                        continue
                    T = flat(A.target_of(it["text"], it["variant"]))
                    G = A.greedy_of(it["wav"], m)
                    n += 1
                    if not G:
                        empty += 1
                    d = sum(c for (_t, _h, c) in A.engine_align(cost, it["variant"], A.target_of(it["text"], it["variant"]), G)) if G else 1000 * len(T)
                    we.append(d / (1000 * max(len(T), len(G), 1)))
                    per.append(lev(T, G) / max(1, len(T)))
                out.setdefault(lang, {}).setdefault(A.short_model(m) if hasattr(A, "short_model") else m, {})[grp] = {
                    "n": n, "weighted_error": round(statistics.mean(we), 4) if we else None,
                    "per": round(statistics.mean(per), 4) if per else None, "empty_readings": empty}
    write_json(RES / "native_error.json", out, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
