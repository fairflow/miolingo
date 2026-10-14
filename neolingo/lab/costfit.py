"""The third run of the lab (14 October, evening): costs fitted to the owner's verdicts (A); the German vocalised r (B);
length (C); "understood" on three takes (D); the candidate's deck (F).  Results: lab/RESULTS-3.md.  Everything this
module writes goes under var/lab/run3/ (and the deck to var/flick/deck-candidate.json).

    <python> -m lab.costfit grid                 the learner takes under every cost combination of the grid
    <python> -m lab.costfit guards [--workers N] [--top K]
                                                 the guard sets (near misses, positives, reference phrases, natives)
                                                 under the shortlist of combinations (and the live one)
    <python> -m lab.costfit fit                  agreement, leave-one-out, time split, guards, the choice
    <python> -m lab.costfit extras [--workers N] B (vocalised r), C (length), D (understood)
    <python> -m lab.costfit report               lab/RESULTS-3.md
    <python> -m lab.costfit deck                 var/flick/deck-candidate.json

A CANDIDATE is the live analysis of each language (lab/combos.py `rec de`, `rec en`, `rec fr`: what the real host runs
since 14 October 11:28) with other costs.  Its parameters (the order in which they act on a substitution cost c in
thousandths, engine_py.transform):
    p   Miolingo's stretch min(1000, 1000 (4c/1000)^p) (None: the raw panphon distance, as live; Miolingo uses 0.6)
    F   a floor: a substitution that costs anything costs at least F (0: none)
    I   the cost of an insertion and of a deletion (live 1000).  The engine's is fixed at 1000, so it is given as DATA:
        every substitution cost (and costOtherwise) times k = 1000 / I, the curve's scale times k^2.  The scores are
        exactly those of insertion and deletion I (the distance is linear in the costs, the curve divides by
        sqrt(scale n)), up to the rounding of the costs to whole thousandths.
    S   the curve's scale, as a multiple of the live 2250000 (before the factor k^2)
    vr  German: espeak's [ɜ] and [ɐ] heard as [r] or [ɾ] cost 0 and are shown as the target (B, as data)
A COMBINATION is a candidate without S (S acts on the final distance only, so a combination is analysed once).

THE OWNER'S NOTES.  For this run only (the overseer's brief of 14 October 2026) the notes on his takes were read BY
HAND to sort the judged takes into causes; the result is the table CAUSES (take token -> a cause of `CAUSE_TEXT`).  No
note text is in this file, in RESULTS-3.md or in any committed file, and the code reads no note, except `deck`, which
shows each card's note in var/flick/ (never committed).

THE AGREEMENT MEASURE.  Per take, against the score the owner judged: for a verdict given in the app or on the review
page, the score the app showed him then (the stored line's score; for the takes since 11:28 that is today's live
analysis); for a flick on the deck of 14 October ("results"), the card's score (today's live analysis):
    harsh     the new score is higher            generous  the new score is lower
    fair      the new score is within 3 points   flick good (no verdict in the app): within 3 points of the card's
A flick "bad" has no direction and is not counted; a take with an app verdict is counted by that verdict only.
The literal reading (every take against TODAY's live score) is reported beside it."""
from __future__ import annotations

import argparse
import collections
import gzip
import itertools
import json
import math
import sys
import time
from datetime import datetime

from . import analyse as A
from . import engine_py as E
from . import run as RUN
from .common import ARCHIVE, DATA, LAB, LANGS, ROOT, VAR, read_jsonl, write_json

OUT = LAB / "run3"
LIVE = {"de": "rec de", "en": "rec en", "fr": "rec fr"}
SCALE = 2250000
SIGNIFICANT_RAW = 42                    # host/engine_config.SIGNIFICANT: the picture's near / off line on raw costs
VR_PAIRS = frozenset({("ɜ", "r"), ("ɜ", "ɾ"), ("ɐ", "r"), ("ɐ", "ɾ")})
TWO = ("tfb3a25d80bc8603f", "t800f08aee9bac6a0")   # first take (86, judged harsh), second (95, judged generous)

# the grid
P_GRID = (None, 0.6)
F_GRID = (0, 100, 200, 250, 300, 340, 400, 500)
I_GRID = (1000, 900, 800, 700, 600, 500, 400)
VR_GRID = (False, True)
S_GRID = (0.5, 0.6, 0.75, 0.9, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0, 4.0)

# ------------------------------------------------------------------ the causes (read by hand from the notes)
CAUSE_TEXT = {
    "cut": "the recording was cut off: the missing sound is not in the audio",
    "artefact": "recogniser artefact: a sound heard that was not said, or a distinction the recogniser does not hear",
    "target": "the target (espeak's reading) differs from what the reference voice says, which the learner copied",
    "whisper": "Whisper's transcription failed (not understood) while the sounds were right; the score is not in question",
    "wrong-language": "a phrase of another language practised in this one",
    "data": "a data error in the phrase (a bracketed note read as part of it)",
    "warnings": "the verdict is about the warnings or the display; the score is 100 already",
    "display": "the verdict is about the display (punctuation of the heard text), not the score",
}
EXCLUDE = set(CAUSE_TEXT)                # every cause listed here is one no cost can fix
CAUSES = {
    "t42d936847f737257": "cut",
    "tb04d902ac8cd948c": "artefact",
    "tf643f69ceac5c363": "whisper",
    "t698f309611ca82f7": "wrong-language",
    "t40d744904c5b09ee": "wrong-language",
    "t309e11c9266ac008": "artefact",
    "t859484532bb31584": "display",
    "t0389573fa9a3259e": "artefact",
    "tdd8c8fdf73aef07b": "target",
    "tcce1e0e938376149": "target",
    "tcbdd329ccd8bf363": "target",
    "tc99e694dafcbfa2b": "target",
    "t08be428fc63c7522": "warnings",
    "t89361d5898b8ec57": "whisper",
    "tf9e1a1605ba75fc3": "artefact",
    "t3c9b76d436e3e4d3": "warnings",
    "t2160614fae687b2f": "warnings",
    "t58aaefcc520b11f5": "data",
    "t1033c77e57778da5": "target",
    "t34daef706e341932": "target",
    "t9960c7f218cd1343": "target",
}
# the three German takes judged right but flicked "not understood" (D)
D_TAKES = ("t89361d5898b8ec57", "tf643f69ceac5c363", "td203986f3b255854")


# ------------------------------------------------------------------ candidates
class Combo(tuple):
    """(p, F, I, vr, vr12, length): vr12 (the one-to-two rule of B) and length "count" (C) are engine rules, measured
    but not part of the grid."""

    def __new__(cls, p=None, F=0, I=1000, vr=False, vr12=False, length="v2"):
        return tuple.__new__(cls, (p, F, I, vr, vr12, length))

    def __getnewargs__(self):                 # pickling (the worker processes): the fields, not the tuple as one
        return tuple(self)

    p = property(lambda s: s[0])
    F = property(lambda s: s[1])
    I = property(lambda s: s[2])
    vr = property(lambda s: s[3])
    vr12 = property(lambda s: s[4])
    length = property(lambda s: s[5])

    @property
    def k(self):
        return 1000 / self.I

    def name(self):
        parts = []
        if self.p:
            parts.append(f"stretch {self.p:g}")
        if self.F:
            parts.append(f"floor {self.F}")
        if self.I != 1000:
            parts.append(f"indel {self.I}")
        if self.vr:
            parts.append("vocal r")
        if self.vr12:
            parts.append("vocal r 1:2")
        if self.length != "v2":
            parts.append("length counted")
        return ", ".join(parts) or "live"

    def key(self):
        return "c_" + "_".join(str(x) for x in self)


LIVE_COMBO = Combo()


def cand_name(c: Combo, S: float) -> str:
    n = c.name()
    if S != 1:
        n = (n + ", " if n != "live" else "") + f"scale ×{S:g}"
    return n


def complexity(c: Combo, S: float):
    """Simpler first: fewer parameters away from live, then the smaller moves."""
    return (int(c.p is not None) + int(c.F > 0) + int(c.I != 1000) + int(S != 1) + int(c.vr) + int(c.vr12)
            + int(c.length != "v2"), abs(math.log(S)), 1000 - c.I, c.F)


def data_scale(c: Combo, S: float) -> int:
    return round(SCALE * S * c.k * c.k)


def score_of(d, n, nothing, c: Combo, S: float) -> int:
    return 0 if nothing else E.curve(d, n, "sqrt", data_scale(c, S))


def cfg_for(c: Combo, lang: str, S: float = 1.0) -> dict:
    """The analysis configuration of a language under the combination (and the scale S: then rec["score"] is the
    candidate's score; the grid computes scores for every S from the distance instead)."""
    allv = RUN.all_variants()
    cfg = {**A.BASELINE, **allv[LIVE[lang]]}
    cfg["model"] = RUN.model_of(cfg, lang)
    extra = VR_PAIRS if (c.vr or c.vr12) and lang == "de" else frozenset()
    cfg["cost"] = ("tx", c.p, c.F, c.k, extra)
    cfg["scale"] = data_scale(c, S)
    if c.vr12:
        cfg["vocal_r12"] = True
    if c.length != "v2":
        cfg["length"] = c.length
    return cfg


def costs_of(c: Combo, lang: str):
    cfg = cfg_for(c, lang)
    return A.costs_for(lang, cfg["cost"], cfg["unchecked"])


def significant(c: Combo) -> int:
    """The picture's near / off line under the candidate: the raw 42 transformed as any cost (stretched 42 is 343, on
    the same side of every stretched raw cost as Miolingo's 340), as host/engine_config.apply_candidate sends it.
    With a floor at or above it every substitution that costs anything is drawn `off`."""
    return E.transform(SIGNIFICANT_RAW, ("tx", c.p, c.F, c.k, frozenset()))


# ------------------------------------------------------------------ the analysis of one item under a combination
def analyse(it, c: Combo):
    cfg = cfg_for(c, it["lang"])
    rec = A.analyse(it, cfg)
    return rec, cfg


def compact(it, rec, cfg):
    r = {"d": rec["dist"], "n": rec["n"], "x": bool(rec["nothing"]), "nd": rec["n_diff"]}
    if "truth" in it:
        det, detc, false = RUN.truth_eval(rec["columns"], it["truth"], A.costs_for(it["lang"], cfg["cost"], cfg["unchecked"]))
        r.update(det=det, detc=detc, false=false)
    return r


def _work(args):
    c, its = args
    out = {}
    for it in its:
        try:
            rec, cfg = analyse(it, c)
        except KeyError:                    # no cached log-probabilities
            continue
        out[it["id"]] = compact(it, rec, cfg)
    return c, out


def _init_worker():
    import torch
    torch.set_num_threads(1)


def save_gz(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)


def load_gz(path):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return json.load(f)


# ------------------------------------------------------------------ data: learner takes, verdicts, flicks
def learner_items():
    return [i for i in RUN.items() if i["set"] == "archive" and i["voice"] == "learner"]


def flicks(deck="results"):
    d = {}
    p = VAR / "flick" / "judgements.jsonl"
    if p.exists():
        for j in read_jsonl(p):
            if isinstance(j, dict) and j.get("deck") == deck and j.get("verdict") in ("good", "bad", "skip"):
                d[str(j["id"])] = j["verdict"]
    return d


def card_scores(deck="results"):
    p = VAR / "flick" / f"deck-{deck}.json"
    if not p.exists():
        return {}
    return {c["id"]: c["score"] for c in json.loads(p.read_text("utf-8"))["cards"]}


def verdict_set():
    """-> [{id, lang, text, time, kind (fair | harsh | generous | good), ref (the score judged), source (app | flick),
    cause, excluded}] for every learner take with an app verdict or a flick "good"."""
    fl, cards = flicks(), card_scores()
    out = []
    for it in learner_items():
        v = it["verdict"]
        if v in ("fair", "harsh", "generous"):
            kind, ref, src = v, it["stored"]["score"], "app"
        elif fl.get(it["id"]) == "good" and it["id"] in cards:
            kind, ref, src = "good", cards[it["id"]], "flick"
        else:
            continue
        cause = CAUSES.get(it["id"])
        out.append({"id": it["id"], "lang": it["lang"], "text": it["text"], "time": it.get("time") or "",
                    "kind": kind, "ref": ref, "source": src, "flick": fl.get(it["id"]), "cause": cause,
                    "excluded": cause in EXCLUDE})
    return out


def agrees(kind, ref, new) -> bool:
    if kind == "harsh":
        return new > ref
    if kind == "generous":
        return new < ref
    return abs(new - ref) <= 3


# ------------------------------------------------------------------ grid
def all_combos():
    return [Combo(p, F, I, vr) for p in P_GRID for F in F_GRID for I in I_GRID for vr in VR_GRID]


def cmd_grid(a):
    its = learner_items()
    combos = all_combos()
    t0 = time.perf_counter()
    res = {}
    for n, c in enumerate(combos, 1):
        _c, out = _work((c, its))
        res[c.key()] = out
        if n % 20 == 0:
            print(f"  {n}/{len(combos)}  {time.perf_counter() - t0:.0f} s", flush=True)
    save_gz(OUT / "grid.json.gz", {"combos": [list(c) for c in combos], "rows": res})
    print(f"grid: {len(combos)} combinations x {len(its)} learner takes ({time.perf_counter() - t0:.0f} s)")


def load_grid():
    g = load_gz(OUT / "grid.json.gz")
    return [Combo(*c) for c in g["combos"]], g["rows"]


def scores_for(rows, c: Combo, S: float) -> dict:
    return {i: score_of(r["d"], r["n"], r["x"], c, S) for i, r in rows.items()}


def agreement(vs, sc) -> dict:
    """vs: the verdict set (included takes); sc: id -> new score.  -> counts by kind and the total."""
    by = collections.Counter()
    tot = collections.Counter()
    for v in vs:
        if v["id"] not in sc:
            continue
        tot[v["kind"]] += 1
        if agrees(v["kind"], v["ref"], sc[v["id"]]):
            by[v["kind"]] += 1
    return {"agree": sum(by.values()), "n": sum(tot.values()), "by": dict(by), "of": dict(tot)}


def order_ok(sc) -> bool:
    a, b = TWO
    return a in sc and b in sc and sc[b] < sc[a]


# ------------------------------------------------------------------ guards
GUARD_SETS = ("nearmiss", "positive", "reference", "cp")


def guard_items():
    return [i for i in RUN.items() if i["set"] in GUARD_SETS]


def shortlist(top: int):
    combos, rows = load_grid()
    vs = [v for v in verdict_set() if not v["excluded"]]
    best = []
    for c in combos:
        b = max(((agreement(vs, scores_for(rows[c.key()], c, S))["agree"], order_ok(scores_for(rows[c.key()], c, S)), S)
                 for S in S_GRID), key=lambda x: (x[1], x[0]))
        best.append((b[1], b[0], c))
    best.sort(key=lambda x: (-int(x[0]), -x[1], complexity(x[2], 1.0)))
    out = [LIVE_COMBO] + [c for (_o, _a, c) in best[:top]]
    # named representatives, whatever their agreement: one change at a time
    for c in (Combo(p=0.6), Combo(I=500), Combo(I=900), Combo(F=340), Combo(F=250), Combo(vr=True),
              Combo(p=0.6, I=900), Combo(p=0.6, I=800), Combo(F=300, I=900)):
        if c not in out:
            out.append(c)
    return out


def cmd_guards(a):
    import multiprocessing as mp
    its = guard_items()
    done = {}
    gfile = OUT / "guards.json.gz"
    if gfile.exists() and not a.fresh:
        done = load_gz(gfile)
    todo = [c for c in shortlist(a.top) if c.key() not in done]
    print(f"guards: {len(todo)} combinations to run over {len(its)} items ({len(done)} done before)", flush=True)
    t0 = time.perf_counter()
    # one combination a task, split in chunks of items so that the workers stay busy
    chunks = [its[i::a.workers] for i in range(a.workers)]
    with mp.get_context("spawn").Pool(a.workers, initializer=_init_worker) as pool:
        for n, c in enumerate(todo, 1):
            out = {}
            for _c, part in pool.imap_unordered(_work, [(c, ch) for ch in chunks]):
                out.update(part)
            done[c.key()] = out
            save_gz(gfile, done)
            print(f"  {n}/{len(todo)} {c.name()}  {time.perf_counter() - t0:.0f} s", flush=True)


def auc(good, bad):
    return RUN._auc(good, bad)


def guard_measures(grow, c: Combo, S: float, its_by_id) -> dict:
    """Per language: AUC (positives above near misses), near misses detected (costing), reference phrases at 100 and
    mean differences, natives mean score and at 100."""
    out = {}
    for lang in LANGS:
        sel = collections.defaultdict(list)
        for i, r in grow.items():
            it = its_by_id[i]
            if it["lang"] != lang or r["x"]:
                continue
            sel[it["set"]].append((r, score_of(r["d"], r["n"], r["x"], c, S)))
        nm, pos, ref, cp = sel["nearmiss"], sel["positive"], sel["reference"], sel["cp"]
        out[lang] = {
            "auc": auc([s for _r, s in pos], [s for _r, s in nm]),
            "nm_detc": _share([r["detc"] for r, _s in nm]),
            "nm_det": _share([r["det"] for r, _s in nm]),
            "nm_mean": _mean([s for _r, s in nm]), "pos_mean": _mean([s for _r, s in pos]),
            "ref100": _share([s == 100 for _r, s in ref]), "ref_mean": _mean([s for _r, s in ref]),
            "ref_diff": _mean([r["nd"] for r, _s in ref]),
            "cp_mean": _mean([s for _r, s in cp]), "cp100": _share([s == 100 for _r, s in cp]),
            "cp_diff": _mean([r["nd"] for r, _s in cp]),
        }
    return out


def _share(xs):
    xs = [bool(x) for x in xs if x is not None]
    return round(sum(xs) / len(xs), 4) if xs else None


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 3) if xs else None


# ------------------------------------------------------------------ fit
def mcnemar(a, b):
    """Two candidates' agreement vectors over the same takes -> (takes only a agrees with, takes only b agrees with,
    the exact two-sided sign test on those takes).  The takes where they differ are the takes that DECIDE between
    them; the others agree (or disagree) under both."""
    na = sum(1 for p, q in zip(a, b) if p and not q)
    nb = sum(1 for p, q in zip(a, b) if q and not p)
    n = na + nb
    if n == 0:
        return na, nb, 1.0
    k = min(na, nb)
    return na, nb, min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)


ALPHA = 0.05


def choose(pool, vecs, idx):
    """THE RULE (the overseer's amendment of 14 October, 20:1x: the verdicts are noisy): among the eligible candidates
    `pool`, the best agreement on the takes `idx`; then every candidate NOT separated from it (sign test on the
    deciding takes, p >= ALPHA); of those, the fewest parameters, then the best agreement, then the smallest moves
    (`complexity`).  -> (chosen, best)."""
    def ag(x):
        v = vecs[x["k"]]
        return sum(v[i] for i in idx)
    best = max(pool, key=lambda x: (ag(x), [-y for y in x["cx"]]))
    bv = [vecs[best["k"]][i] for i in idx]
    near = [x for x in pool if mcnemar(bv, [vecs[x["k"]][i] for i in idx])[2] >= ALPHA]
    return min(near, key=lambda x: (x["cx"][0], -ag(x), x["cx"][1:])), best


def cmd_fit(a):
    combos, rows = load_grid()
    guards = load_gz(OUT / "guards.json.gz")
    its_by_id = {i["id"]: i for i in guard_items()}
    vs_all = verdict_set()
    vs = [v for v in vs_all if not v["excluded"]]
    live_sc = scores_for(rows[LIVE_COMBO.key()], LIVE_COMBO, 1.0)
    live_g = guard_measures(guards[LIVE_COMBO.key()], LIVE_COMBO, 1.0, its_by_id)
    cands, vecs = [], {}
    for c in combos:
        for S in S_GRID:
            sc = scores_for(rows[c.key()], c, S)
            ag = agreement(vs, sc)
            g = guard_measures(guards[c.key()], c, S, its_by_id) if c.key() in guards else None
            auc_ok = None if g is None else all(
                g[l]["auc"] is not None and live_g[l]["auc"] is not None and g[l]["auc"] >= live_g[l]["auc"] - 0.02
                for l in LANGS)
            k = f"{c.key()}|{S:g}"
            vecs[k] = [agrees(v["kind"], v["ref"], sc[v["id"]]) for v in vs]
            cands.append({"k": k, "combo": list(c), "S": S, "name": cand_name(c, S), "agree": ag["agree"], "n": ag["n"],
                          "by": ag["by"], "of": ag["of"], "order": order_ok(sc), "auc_ok": auc_ok, "guards": g,
                          "two": [sc.get(t) for t in TWO], "cx": list(complexity(c, S))})
    # the order of the two takes is REPORTED, not a guard (the amendment); the guard is the near-miss AUC
    eligible = [x for x in cands if x["auc_ok"]]
    allidx = list(range(len(vs)))
    chosen, best = choose(eligible, vecs, allidx)
    live = next(x for x in cands if x["combo"] == list(LIVE_COMBO) and x["S"] == 1.0)
    deciding = [i for i in allidx if len({vecs[x["k"]][i] for x in eligible}) > 1]
    sep = {}
    for name, x in (("chosen_vs_live", chosen), ("best_vs_live", best), ("best_vs_chosen", None)):
        a1 = vecs[(x or best)["k"]]
        b1 = vecs[(live if x else chosen)["k"]]
        na, nb, p = mcnemar(a1, b1)
        sep[name] = {"a_only": na, "b_only": nb, "p": round(p, 4),
                     "takes": [vs[i]["id"] for i in allidx if a1[i] != b1[i]]}
    near_best = [x for x in eligible if mcnemar(vecs[best["k"]], vecs[x["k"]])[2] >= ALPHA]
    # leave one out: the rule applied without the take, judged on the take
    loo = []
    for j, v in enumerate(vs):
        idx = [i for i in allidx if i != j]
        x, _b = choose(eligible, vecs, idx)
        loo.append({"id": v["id"], "kind": v["kind"], "chosen": x["name"], "agree": vecs[x["k"]][j],
                    "live_agree": vecs[live["k"]][j]})
    # time split: the rule on the takes of 13 October, judged on those of 14 October
    early = [i for i in allidx if vs[i]["time"] < "2026-10-14"]
    late = [i for i in allidx if vs[i]["time"] >= "2026-10-14"]
    xe, _b = choose(eligible, vecs, early)
    split = {"chosen": xe["name"], "late_n": len(late), "late_agree": sum(vecs[xe["k"]][i] for i in late),
             "late_live": sum(vecs[live["k"]][i] for i in late)}
    cc = Combo(*chosen["combo"])
    ch_sc = scores_for(rows[cc.key()], cc, chosen["S"])
    bc = Combo(*best["combo"])
    best_sc = scores_for(rows[bc.key()], bc, best["S"])

    def literal(sc):
        n = ag = 0
        for v in vs:
            if v["id"] in sc:
                n += 1
                ag += agrees(v["kind"], live_sc[v["id"]], sc[v["id"]])
        return {"agree": ag, "n": n}

    strip = lambda x: {k: v for k, v in x.items() if k != "k"}      # noqa: E731
    fit = {"made": datetime.now().astimezone().isoformat(timespec="seconds"), "alpha": ALPHA,
           "n_verdicts": len(vs_all), "n_included": len(vs),
           "excluded": [{k: v[k] for k in ("id", "lang", "text", "time", "kind", "cause")} for v in vs_all if v["excluded"]],
           "included": [{**{k: v[k] for k in ("id", "lang", "text", "time", "kind", "ref", "source")},
                         "live": live_sc.get(v["id"]), "chosen": ch_sc.get(v["id"]), "best": best_sc.get(v["id"])}
                        for v in vs],
           "live": strip(live), "chosen": strip(chosen), "best": strip(best), "eligible": len(eligible),
           "candidates": len(cands), "near_best": len(near_best),
           "near_best_fewest": sorted({x["cx"][0] for x in near_best}),
           "deciding": {"n": len(deciding), "takes": [vs[i]["id"] for i in deciding]},
           "separation": sep,
           "loo": {"agree": sum(x["agree"] for x in loo), "live": sum(x["live_agree"] for x in loo), "n": len(loo),
                   "chosen": dict(collections.Counter(x["chosen"] for x in loo)), "rows": loo},
           "split": split,
           "literal": {"live": literal(live_sc), "chosen": literal(ch_sc), "best": literal(best_sc)},
           "table": [strip(x) for x in sorted(cands, key=lambda x: (-x["agree"], x["cx"]))]}
    write_json(OUT / "fit.json", fit, indent=1)
    print(f"best agreement: {best['name']} {best['agree']}/{best['n']}; chosen (fewest parameters not separated from "
          f"it): {chosen['name']} {chosen['agree']}/{chosen['n']}; live {live['agree']}/{live['n']}")
    print(f"separation: {sep['chosen_vs_live']['a_only']}:{sep['chosen_vs_live']['b_only']} takes chosen:live "
          f"(p {sep['chosen_vs_live']['p']}); best:live {sep['best_vs_live']['a_only']}:{sep['best_vs_live']['b_only']} "
          f"(p {sep['best_vs_live']['p']}); deciding takes over all eligible candidates {len(deciding)} of {len(vs)}")
    print(f"LOO {fit['loo']['agree']}/{fit['loo']['n']} (live {fit['loo']['live']}); chosen in LOO {fit['loo']['chosen']}")
    print(f"split: {split}; literal {fit['literal']}")
    print(f"two takes: live {live['two']}, chosen {chosen['two']}, best {best['two']}")


# ------------------------------------------------------------------ extras: B, C, D
def cmd_extras(a):
    import multiprocessing as mp
    from . import understood as U
    fit = json.loads((OUT / "fit.json").read_text("utf-8"))
    best = Combo(*fit["chosen"]["combo"])           # the rule's choice (see cmd_fit)
    S = fit["chosen"]["S"]
    its = guard_items() + learner_items()
    gfile = OUT / "extras.json.gz"
    done = load_gz(gfile) if gfile.exists() and not a.fresh else {}
    run3, _S3, _c3 = candidate("run3")
    want = [Combo(vr=True), Combo(vr=True, vr12=True), Combo(length="count"), run3,
            Combo(*best[:3], vr=True, vr12=True), Combo(*best[:4], length="count")]
    chunks = [its[i::a.workers] for i in range(a.workers)]
    with mp.get_context("spawn").Pool(a.workers, initializer=_init_worker) as pool:
        for c in [LIVE_COMBO, best] + want:
            if c.key() in done:
                continue
            out = {}
            for _c, part in pool.imap_unordered(_work, [(c, ch) for ch in chunks]):
                out.update(part)
            done[c.key()] = out
            save_gz(gfile, done)
            print("extras:", c.name(), flush=True)
    # C: what the live analysis does with length-only differences of the free reading
    length = collections.Counter()
    for it in its:
        if it["set"] not in ("reference", "cp", "nearmiss", "positive", "archive"):
            continue
        try:
            rec, _cfg = analyse(it, LIVE_COMBO)
        except KeyError:
            continue
        kept = rec["kept"]
        i = 0
        T = E.flat(rec["target"])
        for col, (t, h) in enumerate(rec["align0"]):
            if t is None:
                continue
            if A.length_only(t, h):
                length[(it["set"], it["lang"], "kept" if kept[col] else "undone")] += 1
            i += 1
        length[(it["set"], it["lang"], "items")] += 1
        length[(it["set"], it["lang"], "sounds")] += len(T)
    # D: understood, the live rule against free OR teacher-forced (m = 0)
    D = collections.Counter()
    flips = []
    for it in its:
        if it["set"] not in ("reference", "nearmiss", "positive", "archive"):
            continue
        tgt = it["target"] if it.get("target") else A.target_of(it["text"], it["variant"])
        tx = U.texts(it)
        u0, _ = U.decide("free", it, tgt, A.target_ipa, tx)
        u1, _ = U.decide(("either", 0.0), it, tgt, A.target_ipa, tx)
        if u0 is None or u1 is None:
            D[(it["set"], it["lang"], "unknown")] += 1
            continue
        D[(it["set"], it["lang"], "n")] += 1
        D[(it["set"], it["lang"], "free")] += int(u0)
        D[(it["set"], it["lang"], "either")] += int(u1)
        if it["set"] == "archive" and u0 != u1:
            flips.append({"id": it["id"], "lang": it["lang"], "text": it["text"], "verdict": it.get("verdict"),
                          "free": u0, "either": u1, "heard": tx["free"], "lp_target": tx["lp_target"],
                          "lp_free": tx["lp_free"]})
    d3 = []
    for t in D_TAKES:
        it = next((i for i in its if i["id"] == t), None)
        if it is None:
            continue
        tgt = A.target_of(it["text"], it["variant"])
        tx = U.texts(it)
        d3.append({"id": t, "text": it["text"], "heard": tx["free"], "free": U.decide("free", it, tgt, A.target_ipa, tx)[0],
                   "either": U.decide(("either", 0.0), it, tgt, A.target_ipa, tx)[0],
                   "margin": None if tx["lp_target"] is None or tx["lp_free"] is None
                   else round(tx["lp_target"] - tx["lp_free"], 3)})
    # D at larger margins, German
    dm = {"nearmiss": {}, "positive": {}}
    for m in (0.0, 1.0, 2.0):
        for sname in dm:
            n = u = 0
            for it in its:
                if it["set"] != sname or it["lang"] != "de":
                    continue
                tgt = it["target"] if it.get("target") else A.target_of(it["text"], it["variant"])
                r, _ = U.decide(("either", m), it, tgt, A.target_ipa, U.texts(it))
                if r is not None:
                    n += 1
                    u += int(r)
            dm[sname][f"{m:g}"] = round(u / n, 4) if n else None
    write_json(OUT / "extras.json", {"d_margins": dm, "length": {"|".join(k): v for k, v in length.items()},
                                      "understood": {"|".join(k): v for k, v in D.items()},
                                      "understood_flips": flips, "d3": d3,
                                      "combos": [list(c) for c in [LIVE_COMBO, best] + want], "S": S}, indent=1)
    print("extras ->", OUT / "extras.json")


# ------------------------------------------------------------------ A, the floor on "likely off" only (an engine change)
F_OFF_GRID = (0, 250, 340, 400, 500, 600, 800)


def cmd_offfloor(a):
    """A floor F on the substitutions at target sounds the check flags "likely off" ONLY.  The engine's costs do not
    see the flags (`score` is computed on the verified heard sounds alone), so this needs an engine change; it is
    APPROXIMATED here on the live alignment: d' = the live analysis's substitutions, each at a sound flagged off
    costing at least F, plus I for each insertion and deletion; score with the scale S.  Selected by the same rule as
    `fit` (AUC guard, fewest parameters among those not separated from the best), with leave-one-out."""
    its = guard_items() + learner_items()
    offrows = {}
    for it in its:
        try:
            rec, cfg = analyse(it, LIVE_COMBO)
        except KeyError:
            continue
        cost = A.costs_for(it["lang"], cfg["cost"], cfg["unchecked"])
        subs, nid, i = [], 0, 0
        for (t, h, _k) in rec["columns"]:
            if t is None or h is None:
                nid += 1
            elif t != h:
                lv = rec["check"][i]["level"] if i < len(rec["check"]) else None
                subs.append((cost(t, h), lv == "off"))
            if t is not None:
                i += 1
        offrows[it["id"]] = (subs, nid, rec["n"], rec["nothing"], rec["score"])
    bad = [k for k, r in offrows.items() if not r[3] and E.curve(sum(c for c, _o in r[0]) + 1000 * r[1], r[2]) != r[4]]
    vs = [v for v in verdict_set() if not v["excluded"]]
    gl = {i["id"]: i for i in guard_items()}

    def scores(F, I, S):
        out = {}
        for k, (subs, nid, n, nothing, _s) in offrows.items():
            d = sum(max(c, F) if off and c > 0 else c for (c, off) in subs) + nid * I
            out[k] = 0 if nothing else E.curve(d, n, "sqrt", round(SCALE * S))
        return out

    def aucs(sc):
        return {lang: auc([sc[k] for k, it in gl.items() if k in sc and it["lang"] == lang and it["set"] == "positive"
                           and not offrows[k][3]],
                          [sc[k] for k, it in gl.items() if k in sc and it["lang"] == lang and it["set"] == "nearmiss"
                           and not offrows[k][3]]) for lang in LANGS}

    live_auc = aucs(scores(0, 1000, 1.0))
    rows, vecs = [], {}
    for F in F_OFF_GRID:
        for I in I_GRID:
            for S in S_GRID:
                sc = scores(F, I, S)
                au = aucs(sc)
                k = f"{F}|{I}|{S:g}"
                vecs[k] = [agrees(v["kind"], v["ref"], sc[v["id"]]) for v in vs]
                rows.append({"k": k, "F_off": F, "I": I, "S": S, "agree": sum(vecs[k]), "n": len(vs),
                             "two": [sc.get(t) for t in TWO], "auc": au,
                             "auc_ok": all(au[l] >= live_auc[l] - 0.02 for l in LANGS),
                             "cx": [int(F > 0) + int(I != 1000) + int(S != 1), abs(math.log(S)), 1000 - I, F]})
    eligible = [x for x in rows if x["auc_ok"]]
    live = next(x for x in rows if x["F_off"] == 0 and x["I"] == 1000 and x["S"] == 1.0)
    allidx = list(range(len(vs)))
    chosen, best = choose(eligible, vecs, allidx)
    with_floor = [x for x in eligible if x["F_off"] > 0]
    fchosen, fbest = choose(with_floor, vecs, allidx)
    loo = []
    for j in allidx:
        x, _b = choose(eligible, vecs, [i for i in allidx if i != j])
        loo.append(vecs[x["k"]][j])
    strip = lambda x: {k: v for k, v in x.items() if k != "k"}      # noqa: E731
    out = {"approximation_mismatch": len(bad), "live_auc": live_auc, "live": strip(live), "chosen": strip(chosen),
           "best": strip(best), "floor_chosen": strip(fchosen), "floor_best": strip(fbest),
           "sep": {n: dict(zip(("a_only", "b_only", "p"), mcnemar(vecs[x["k"]], vecs[live["k"]])))
                   for n, x in (("chosen", chosen), ("best", best), ("floor_chosen", fchosen), ("floor_best", fbest))},
           "loo": {"agree": sum(loo), "live": sum(vecs[live["k"]]), "n": len(loo)},
           "by_floor": [strip(x) for x in rows if x["I"] == 1000 and x["S"] == 1.0],
           "table": [strip(x) for x in sorted(eligible, key=lambda x: (-x["agree"], x["cx"]))[:40]]}
    write_json(OUT / "offfloor.json", out, indent=1)
    print(json.dumps({k: out[k] for k in ("approximation_mismatch", "live_auc", "sep", "loo")}, ensure_ascii=False))
    for n in ("live", "chosen", "best", "floor_chosen", "floor_best"):
        x = out[n]
        print(n, x["F_off"], x["I"], x["S"], x["agree"], x["two"], x["auc"])


# ------------------------------------------------------------------ the deck
def picture(rec, c: Combo):
    """The engine's picture of the lab's record: per word, sounds {t, h, k}; k by the engine's kindOf with the
    candidate's `significant` (a pair costing 0 is shown as the target; under V2 an unflagged sound is the target)."""
    cost = A.costs_for(rec["lang"], *cfg_cost(c, rec["lang"]))
    sig = significant(c)
    groups = A.word_columns(rec)
    names = word_names(rec["text"], len(groups))
    out = []
    for name, g in zip(names, groups):
        ss = []
        for (t, h, k) in g:
            if k in ("near", "off"):
                cc = cost(t, h)
                k = "ok" if cc == 0 else ("near" if cc < sig else "off")
                if k == "ok":
                    h = t
            ss.append({"t": t or "", "h": h or "", "k": k})
        out.append({"text": name, "sounds": ss})
    return out


def cfg_cost(c: Combo, lang):
    cfg = cfg_for(c, lang)
    return cfg["cost"], cfg["unchecked"]


def word_names(text, n):
    from .deck import word_names as wn
    return wn(text, n)


def notes_by_take():
    """The latest note per take (for the DECK only: var/flick/, never committed)."""
    d = {}
    for j in read_jsonl(ARCHIVE / "judgements.jsonl"):
        if isinstance(j, dict) and isinstance(j.get("take"), str):
            d[j["take"]] = {"verdict": j.get("verdict"), "note": j.get("note") or ""}
    return d


def cmd_deck(a):
    from .deck import validate as validate_cards
    c, S, cand = candidate(a.name)
    fl = flicks()
    notes = notes_by_take()
    its = {i["id"]: i for i in learner_items()}
    want = [t for t, i in its.items() if i["verdict"] in ("fair", "harsh", "generous") or fl.get(t) == "bad"]
    for t in TWO:
        if t not in want:
            want.append(t)
    cards = []
    for t in want:
        it = its[t]
        old, _ = analyse(it, LIVE_COMBO)
        new, _ = analyse(it, c)
        new_score = score_of(new["dist"], new["n"], new["nothing"], c, S)
        j = notes.get(t, {})
        earlier = []
        if j.get("verdict"):
            earlier.append(f"app: {j['verdict']} at {it['stored']['score']}%")
        if fl.get(t):
            earlier.append(f"flick ({'results'}): {fl[t]}")
        card = {"id": t, "kind": "result", "audio": f"/take/{t}.wav", "variant": it["variant"], "phrase": it["text"],
                "heardText": new["heard_text"] or "", "understood": bool(new["understood"]), "score": int(new_score),
                "words": picture(new, c),
                "before": {"score": int(old["score"]), "different": int(old["n_diff"])},
                "old": {"score": int(old["score"]), "words": picture(old, LIVE_COMBO), "label": "live now"},
                "earlier": {"text": " · ".join(earlier), "note": j.get("note") or ""}}
        cards.append((abs(new_score - old["score"]), it.get("time") or "", card))
    # the two takes first, then the largest changes
    cards.sort(key=lambda x: (x[2]["id"] not in TWO, TWO.index(x[2]["id"]) if x[2]["id"] in TWO else 0, -x[0], x[1]))
    deck = {"title": "Candidate: old against new score on your judged takes",
            "made": datetime.now().astimezone().isoformat(timespec="seconds"),
            "config": f"candidate {a.name}: {cand['describe']}.  Old = the live analysis now (score and picture); new = "
                      f"the candidate (the larger score and the picture above).  Swipe right if the new score is "
                      f"better, left if worse, up if no opinion; the note box saves a line with the verdict.",
            "cards": [x[2] for x in cards]}
    errs = validate_cards(deck)
    for c2 in deck["cards"]:
        for w in c2["old"]["words"]:
            for s in w["sounds"]:
                if set(s) != {"t", "h", "k"}:
                    errs.append(f"card {c2['id']}: bad old sound {s!r}")
    if errs:
        sys.exit("DECK NOT WRITTEN:\n  " + "\n  ".join(errs[:40]))
    out = VAR / "flick" / "deck-candidate.json"
    write_json(out, deck, indent=1)
    print(f"{out}: {len(deck['cards'])} cards; validated")


# ------------------------------------------------------------------ the candidate as the host sends it, on the real engine
def candidate(name: str):
    """(Combo, S, the entry) of a candidate of data/cost_candidates.json ("live": today's costs)."""
    if name == "live":
        return LIVE_COMBO, 1.0, {"free": [], "describe": "the live costs"}
    cand = json.loads((DATA / "cost_candidates.json").read_text("utf-8"))["candidates"][name]
    vr = any(l == "de" and (t, h) in VR_PAIRS for (l, t, h) in cand.get("free", []))
    return Combo(cand.get("p"), cand.get("F", 0), cand.get("I", 1000), vr), cand.get("S", 1.0), cand


def cmd_validate(a):
    """The real compiled engine, given the configuration the HOST builds with NEOLINGO_COSTS=<name>
    (host/engine_config.apply_candidate) and the lab's cached answers (the candidate's final heard sounds, the flags):
    its score and columns must equal the lab's analysis under the same candidate.  As lab/validate.py `engine`."""
    import os
    from . import cache, check
    from .validate import _engine, flag_key, OUT as VOUT
    c, S, _cand = candidate(a.name)
    os.environ["NEOLINGO_COSTS"] = a.name
    ra, paths = _engine()
    from host.engine import Environment, flags_out
    from host.engine_config import build_config
    config = build_config()
    state = {}

    class CachedEnvironment(Environment):
        def answer(self, q):
            k = q["q"]
            rec = state.get("rec")
            if k == "targetIpa":
                if rec is not None and q["text"] == rec["text"] and q["variant"] == rec["variant"]:
                    return {"ipa": rec["target"]}
                return {"ipa": A.target_ipa(q["text"], q["variant"])}
            if k == "fill":
                return {"translation": "", "notes": ""}
            if k == "audible":
                return {"audible": True}
            if k == "hear":
                return {"text": rec["heard_text"] or "", "ipa": [rec["heard"]] if rec["heard"] else []}
            if k == "sounds":
                return {"flags": rec["flags_sent"]}
            raise ValueError(q)

    eng = ra.Engine(config)
    eng.env = CachedEnvironment()
    items = [i for i in RUN.items() if i["set"] in a.sets][::a.every]
    same, diff, t0 = 0, [], time.perf_counter()
    for n, it in enumerate(items, 1):
        cfg = cfg_for(c, it["lang"], S)
        if not cache.has_lp(it["wav"], cfg["model"]):
            continue
        rec = A.analyse(it, cfg)
        if not rec["heard"]:
            continue
        raw = check.raw_tokens(it["wav"], cfg["model"], rec["target"], it["variant"])
        lib = check.lib_findings(raw["tokens"])
        fl = flags_out(lib, rec["target"]) if lib else []
        # the German ü/ö rule's findings (env.sounds adds them; the check's own findings never flag those sounds): a
        # flag "likely off" at each `unreliable` target sound where the analysis kept a substitution
        unrel = A.costs_for(it["lang"], cfg["cost"], cfg["unchecked"]).unreliable
        if cfg["unchecked"] == "phoneme_lr":
            i = 0
            for (t, h, _k) in rec["columns"]:
                if t is None:
                    continue
                if t in unrel and h is not None and h != t and not any(f["at"] == i for f in fl):
                    fl.append({"at": i, "sound": t, "heardAs": h, "off": True})
                i += 1
            fl.sort(key=lambda f: f["at"])
        free = {(t, h) for (l, t, h) in _cand.get("free", []) if l == it["lang"]}
        rec["flags_sent"] = [f for f in fl if (f["sound"], f["heardAs"]) not in free]     # as host/engine.py drops them
        state["rec"] = rec
        new = ra.replay_one(eng, None, {"variant": it["variant"], "text": it["text"], "take": f"x{n:07d}"})
        state.pop("rec", None)
        if not new.get("checked"):
            diff.append((it, ["not checked"]))
            continue
        ch = []
        if new["score"] != rec["score"]:
            ch.append(f"score engine {new['score']} lab {rec['score']}")
        kept = E.keep_flags(rec["flags_sent"], rec["target"])
        cols_lab = E.columns_from(kept, E.by_word(rec["target"], [(t, h) for (t, h, _k) in rec["columns"]]))
        if new["columns"] != cols_lab:
            ch.append("columns")
        if ch:
            diff.append((it, ch))
        else:
            same += 1
        if n % 500 == 0:
            print(f"  {n}/{len(items)}  {time.perf_counter() - t0:.0f} s  equal {same}  different {len(diff)}", flush=True)
    eng.proc.terminate()
    w = [f"# Candidate `{a.name}` on the real engine ({time.strftime('%Y-%m-%d %H:%M')})\n",
         f"The configuration the host builds with NEOLINGO_COSTS={a.name} ({len(config['costs'])} cost entries, "
         f"costOtherwise {config['costOtherwise']}, significant {config['significant']}, curve {config['curve']}); the "
         f"engine `{paths.ENGINE}` given the lab's final heard sounds and the flags.  Sets: {', '.join(a.sets)} (every "
         f"{a.every}th item).  Compared: score, columns with their marks.  Equal: **{same}**.  Different: **{len(diff)}**.\n"]
    for it, ch in diff[:100]:
        w.append(f"- `{it['id']}` {it['variant']} {it['text']!r}: {'; '.join(ch)}")
    VOUT.mkdir(parents=True, exist_ok=True)
    (VOUT / f"engine-candidate-{a.name}.md").write_text("\n".join(w) + "\n", "utf-8")
    print("\n".join(w[:20]))


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("grid")
    g = sub.add_parser("guards")
    g.add_argument("--workers", type=int, default=8)
    g.add_argument("--top", type=int, default=24)
    g.add_argument("--fresh", action="store_true")
    sub.add_parser("fit")
    sub.add_parser("offfloor")
    e = sub.add_parser("extras")
    e.add_argument("--workers", type=int, default=8)
    e.add_argument("--fresh", action="store_true")
    sub.add_parser("report")
    d = sub.add_parser("deck")
    d.add_argument("--name", default="run3")
    v = sub.add_parser("validate")
    v.add_argument("sets", nargs="*", default=["archive", "reference", "nearmiss", "positive", "cp"])
    v.add_argument("--name", default="run3")
    v.add_argument("--every", type=int, default=1)
    a = ap.parse_args()
    if a.cmd == "grid":
        cmd_grid(a)
    elif a.cmd == "guards":
        cmd_guards(a)
    elif a.cmd == "fit":
        cmd_fit(a)
    elif a.cmd == "offfloor":
        cmd_offfloor(a)
    elif a.cmd == "extras":
        cmd_extras(a)
    elif a.cmd == "report":
        from .report3 import main as report_main
        report_main()
    elif a.cmd == "deck":
        cmd_deck(a)
    elif a.cmd == "validate":
        cmd_validate(a)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
