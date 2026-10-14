"""Run the variants over every data set and measure them.

    <python> -m lab.run fill [--workers N] [--langs de,en] [--models xlsr,lv60,cnam]
                            precompute the sound check and the likelihood ratios (V4) of every item for the models
                            that apply (disk cache under var/lab/cache/check/); cheap to repeat
    <python> -m lab.run variants [names...]
                            analyse every item under every variant (or the named ones)
                            -> var/lab/results/rows/<variant>.jsonl.gz   one compact row an item
                            -> var/lab/results/metrics.json              the measures (lab/report.py renders them)

A variant is ONE change against the baseline (the live pipeline) unless its name says "combo".  The phone model of a
variant is given per language (`model`); an item whose wav has no cached log-probabilities for that model is left out
of that variant and counted under "missing".

Measures (definitions; lab/RESULTS.md repeats them):
  different        a column whose kind is near, off, missing or added (what the page shows as not equal)
  reference/cp     share of items scoring 100, >= 95, < 90; mean number of differences; mean score
  near miss        the voice said B, the target is A (one edit apart, ground truth known):
                     detected  a difference AT the place of the edit: for a substitution or a deletion a column
                               near / off / missing at that target sound (any of the places when a doubled sound
                               makes the place ambiguous); for an insertion an `added` column between the two
                               target sounds where the extra sound stands
                     below100  score < 100
                     false     differences elsewhere (not at the place of the edit), per item
  positive         the voice said A, the target is A: share below 100, mean differences (all false)
  cpflip           native audio, ONE target sound changed to a typical English-speaker error: detected as above
  archive          learner takes only (test voices excluded), by the owner's verdict: mean score, mean differences;
                   harsh_fewer = harsh takes with FEWER differences than the baseline; fair_changed = fair takes whose
                   score or columns differ from the baseline at all
  understood       share understood: reference, archive, positives (correct words) and near misses (INFLATION:
                   the voice said B and the target A was taken as understood)
"""
from __future__ import annotations

import argparse
import collections
import gzip
import json
import statistics
import sys
import time

from . import analyse as A
from . import cache, datasets
from .common import CNAM, LAB, LANGS, LV60, XLSR, write_json

RES = LAB / "results"
ROWS = RES / "rows"
MODELS = {"xlsr": XLSR, "lv60": LV60, "cnam": CNAM}
BASE = {"en": XLSR, "de": XLSR, "fr": CNAM}

# models that apply per language: the live one first
APPLY = {"en": [XLSR, LV60], "de": [XLSR, LV60], "fr": [CNAM, XLSR, LV60]}

TAUS = [-6.0, -4.0, -2.0, -1.0, 0.0, 1.0, 2.0, 4.0, 6.0, 10.0]
TF_MARGINS = [0.0, 1.0, 2.0, 3.0, 5.0, 8.0]


def variants() -> dict:
    """name -> config (analyse's keys; "model" a dict per language)."""
    v = {"baseline": {}}
    # A: what counts as heard
    v["A-V1"] = {"heard": "V1"}
    v["A-V2"] = {"heard": "V2"}
    v["A-V3"] = {"heard": "V3"}
    for t in TAUS:
        v[f"A-V4 tau={t:g}"] = {"heard": "V4", "tau": t}
    v["A-ins edges"] = {"ins": "edges"}
    for t in (0.0, 2.0):
        v[f"A-ins lr tau={t:g}"] = {"ins": "lr", "tau_ins": t}
    v["A5-unjudged"] = {"unchecked": "unjudged"}
    v["A5-phoneme"] = {"unchecked": "phoneme"}
    for t in (0.0, 2.0, 4.0):
        v[f"A5-phoneme+lr tau={t:g}"] = {"unchecked": "phoneme_lr", "tau_unrel": t}
    v["A-converse"] = {"converse": True}
    v["A-zero=equal"] = {"zero_equal": True}
    # B: costs and curve
    v["B-stretched"] = {"cost": "stretched"}
    v["B-linear"] = {"curve": "linear"}
    v["B-stretched+linear"] = {"cost": "stretched", "curve": "linear"}
    v["B-deletions"] = {"del_accept": True}
    # C: phone model
    v["C-lv60"] = {"model": {"en": LV60, "de": LV60, "fr": LV60}}
    v["C-xlsr-fr"] = {"model": {"fr": XLSR}}
    # D: understood
    v["D-prompt"] = {"understood": "prompt"}
    for m in TF_MARGINS:
        v[f"D-tf m={m:g}"] = {"understood": ("tf", m)}
        v[f"D-either m={m:g}"] = {"understood": ("either", m)}
    return v


def combos() -> dict:
    """The promising combinations (chosen after the single changes; see lab/RESULTS.md)."""
    from .combos import COMBOS
    return COMBOS


def all_variants() -> dict:
    out = variants()
    try:
        out.update(combos())
    except ImportError:
        pass
    return out


def model_of(cfg: dict, lang: str) -> str:
    m = cfg.get("model")
    if isinstance(m, dict):
        return m.get(lang, BASE[lang])
    return m or BASE[lang]


# ------------------------------------------------------------------ items
def items() -> list[dict]:
    its = datasets.all_items()
    for i in its:
        if i["set"] in ("cp", "cpflip"):
            i.setdefault("voice", "native")
        if i["set"] == "archive":
            i["voice"] = i["source"]
    return its


# ------------------------------------------------------------------ fill
def _fill_one(args):
    it, model = args
    try:
        if not cache.has_lp(it["wav"], model):
            return 0
        A.analyse(it, {"model": model, "heard": "V4", "ins": "lr"})
        return 1
    except Exception as e:                       # noqa: BLE001
        return f"{it['id']} {model}: {type(e).__name__}: {e}"


def cmd_fill(a):
    import multiprocessing as mp
    langs = a.langs.split(",") if a.langs else list(LANGS)
    models = [MODELS[m] for m in a.models.split(",")] if a.models else None
    jobs = []
    for it in items():
        if it["lang"] not in langs:
            continue
        for m in APPLY[it["lang"]]:
            if models is None or m in models:
                jobs.append((it, m))
    print(f"{len(jobs)} (item, model) pairs", flush=True)
    t0 = time.perf_counter()
    done = errs = 0
    with mp.get_context("spawn").Pool(a.workers, initializer=_init_worker) as pool:
        for k, r in enumerate(pool.imap_unordered(_fill_one, jobs, chunksize=8), 1):
            if isinstance(r, str):
                errs += 1
                if errs <= 20:
                    print("FAILED", r, flush=True)
            else:
                done += r
            if k % 500 == 0:
                print(f"  {k}/{len(jobs)}  {time.perf_counter() - t0:.0f} s  analysed {done}  failed {errs}", flush=True)
    print(f"done: {done} analysed, {errs} failed, {len(jobs) - done - errs} without log-probabilities "
          f"({time.perf_counter() - t0:.0f} s)")


def _init_worker():
    import torch
    torch.set_num_threads(1)


# ------------------------------------------------------------------ the place of the edit
DIFF = ("near", "off", "missing", "added")


def truth_eval(cols, truth, cost=None):
    """-> (detected, detected AND costing something, false differences elsewhere).  cols: [(t, h, kind)];
    cost(t, h) the variant's substitution cost (None: every difference counts as costing)."""
    pos = set(truth["pos"])
    kind = truth["kind"]
    i = 0
    det, detc, false = False, False, 0
    for (t, h, k) in cols:
        if t is None:                            # an extra heard sound, standing before target sound i
            if kind == "ins" and i in pos:
                det = detc = True
            else:
                false += 1
            continue
        if k in ("near", "off", "missing"):
            if kind != "ins" and i in pos:
                det = True
                if h is None or cost is None or cost(t, h) > 0:
                    detc = True
            else:
                false += 1
        i += 1
    return det, detc, false


def check_detect(rec, truth):
    """E (the check alone): the check's level at the place is check or off.  None for an insertion."""
    if truth["kind"] == "ins":
        return None
    ph = rec["check"]
    return any(p < len(ph) and ph[p]["level"] in ("check", "off") for p in truth["pos"])


def row_of(it, rec, cost=None):
    r = {"id": it["id"], "set": it["set"], "lang": it["lang"], "voice": it.get("voice"), "score": rec["score"],
         "sc": rec["score_check"], "nd": rec["n_diff"], "nc": rec["n_cost"], "u": rec["understood"],
         "cols": [[t, h, k] for (t, h, k) in rec["columns"]], "nw": rec["n_warn"], "nothing": rec["nothing"]}
    if it["set"] == "archive":
        r["verdict"] = it["verdict"]
        r["uid"] = it["uid"]
        r["ht"] = rec["heard_text"]
    if "truth" in it:
        det, detc, false = truth_eval(rec["columns"], it["truth"], cost)
        r["det"], r["detc"], r["false"] = det, detc, false
        r["cdet"] = check_detect(rec, it["truth"])
        r["unrel"] = bool(it["truth"].get("unreliable_target"))
        r["tk"] = it["truth"]["kind"]
        if it["set"] == "cpflip":
            r["flip"] = f"{it['truth']['expected']}->{it['truth']['changed_to']}"
    return r


def run_variant(name, cfg, its):
    rows, missing = [], collections.Counter()
    for it in its:
        m = model_of(cfg, it["lang"])
        if not cache.has_lp(it["wav"], m):
            missing[(it["set"], it["lang"])] += 1
            continue
        c = {**A.BASELINE, **cfg, "model": m}
        rec = A.analyse(it, c)
        rows.append(row_of(it, rec, A.costs_for(it["lang"], c["cost"], c["unchecked"])))
    return rows, missing


def save_rows(name, rows):
    ROWS.mkdir(parents=True, exist_ok=True)
    p = ROWS / (name.replace("/", "_").replace(" ", "_") + ".jsonl.gz")
    with gzip.open(p, "wt", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def load_rows(name):
    p = ROWS / (name.replace("/", "_").replace(" ", "_") + ".jsonl.gz")
    with gzip.open(p, "rt", encoding="utf-8") as f:
        return [json.loads(l) for l in f]


# ------------------------------------------------------------------ measures
def _mean(xs):
    xs = [x for x in xs if x is not None]
    return round(statistics.mean(xs), 3) if xs else None


def _share(xs, pred):
    xs = [x for x in xs if x is not None]
    return round(sum(1 for x in xs if pred(x)) / len(xs), 4) if xs else None


def _auc(good, bad):
    """P(a correct item scores higher than a wrong one), ties counted half."""
    good = [x for x in good if x is not None]
    bad = [x for x in bad if x is not None]
    if not good or not bad:
        return None
    import bisect
    b = sorted(bad)
    tot = 0.0
    for g in good:
        lo, hi = bisect.bisect_left(b, g), bisect.bisect_right(b, g)
        tot += lo + 0.5 * (hi - lo)
    return round(tot / (len(good) * len(b)), 4)


def score_block(rows, key="score"):
    s = [r[key] for r in rows]
    return {"n": len(rows), "at100": _share(s, lambda x: x == 100), "ge95": _share(s, lambda x: x >= 95),
            "lt90": _share(s, lambda x: x < 90), "mean": _mean(s), "diff": _mean([r["nd"] for r in rows]),
            "costly": _mean([r["nc"] for r in rows])}


def understood_block(rows):
    u = [r["u"] for r in rows if r["u"] is not None]
    return {"n": len(u), "rate": round(sum(u) / len(u), 4) if u else None}


def measures(rows, base_rows=None, key="score"):
    """Items the recogniser heard nothing of ("nothing recognised": the engine gives no result to judge) are left
    out of every measure except the learner takes (where the app showed 0) and counted under "nothing"."""
    by = collections.defaultdict(list)
    nothing = collections.Counter()
    for r in rows:
        if r.get("nothing") and r["set"] != "archive":
            nothing[f"{r['set']}/{r['lang']}/{r['voice']}"] += 1
            continue
        by[r["set"]].append(r)
    out = {"reference": {}, "nearmiss": {}, "positive": {}, "cp": {}, "cpflip": {}, "archive": {}, "understood": {},
           "nothing": dict(sorted(nothing.items()))}
    for lang in LANGS:
        L = lambda s: [r for r in by[s] if r["lang"] == lang]       # noqa: E731
        ref = L("reference")
        out["reference"][lang] = {v: score_block([r for r in ref if r["voice"] == v], key)
                                  for v in ("gtts", "say", "premium")}
        out["reference"][lang]["all"] = score_block(ref, key)
        nm = L("nearmiss")
        blk = {}
        for sub, sel in (("all", nm), ("gtts", [r for r in nm if r["voice"] == "gtts"]),
                         ("say", [r for r in nm if r["voice"] == "say"]),
                         ("premium", [r for r in nm if r["voice"] == "premium"]),
                         ("unreliable", [r for r in nm if r["unrel"]]),
                         ("judged", [r for r in nm if not r["unrel"]]),
                         ("sub", [r for r in nm if r["tk"] == "sub"]), ("del", [r for r in nm if r["tk"] == "del"]),
                         ("ins", [r for r in nm if r["tk"] == "ins"])):
            sb = score_block(sel, key)
            sb["detected"] = _share([r["det"] for r in sel], bool)
            sb["detected_costed"] = _share([r["detc"] for r in sel], bool)
            sb["below100"] = _share([r[key] for r in sel], lambda x: x < 100)
            sb["false"] = _mean([r["false"] for r in sel])
            sb["check_detected"] = _share([r["cdet"] for r in sel if r["cdet"] is not None], bool)
            blk[sub] = sb
        out["nearmiss"][lang] = blk
        pos = L("positive")
        out["positive"][lang] = {"all": score_block(pos, key)}
        out["positive"][lang]["auc_vs_nearmiss"] = _auc([r[key] for r in pos], [r[key] for r in nm])
        for v in ("gtts", "say", "premium"):
            out["positive"][lang][v] = score_block([r for r in pos if r["voice"] == v], key)
        out["cp"][lang] = score_block(L("cp"), key)
        fl = L("cpflip")
        fb = {"n": len(fl), "detected": _share([r["det"] for r in fl], bool), "false": _mean([r["false"] for r in fl]),
              "detected_costed": _share([r["detc"] for r in fl], bool),
              "check_detected": _share([r["cdet"] for r in fl if r["cdet"] is not None], bool), "by_flip": {}}
        cps = {r["id"].split("-", 2)[2]: r[key] for r in L("cp")}
        pairs = [(cps.get(r["id"].split("-", 2)[2]), r[key]) for r in fl]
        pairs = [(a, b) for a, b in pairs if a is not None and b is not None]
        fb["score_lower"] = round(sum(1 for a, b in pairs if b < a) / len(pairs), 4) if pairs else None
        for f in sorted({r["flip"] for r in fl}):
            sel = [r for r in fl if r["flip"] == f]
            fb["by_flip"][f] = {"n": len(sel), "detected": _share([r["det"] for r in sel], bool)}
        out["cpflip"][lang] = fb
        # understood
        out["understood"][lang] = {
            "reference": understood_block(ref), "positive": understood_block(pos),
            "nearmiss_inflation": understood_block(nm),
            "archive": understood_block([r for r in L("archive") if r["voice"] == "learner"]),
            "reference_by_voice": {v: understood_block([r for r in ref if r["voice"] == v]) for v in ("gtts", "say", "premium")},
        }
    # archive: learner takes, by verdict, all languages together and per language
    arch = [r for r in by["archive"] if r["voice"] == "learner"]
    base = {r["id"]: r for r in (base_rows or []) if r["set"] == "archive"}
    for scope in ("all",) + tuple(LANGS):
        sel = arch if scope == "all" else [r for r in arch if r["lang"] == scope]
        blk = {}
        for vd in ("fair", "harsh", "generous", "unjudged", "any"):
            s = sel if vd == "any" else [r for r in sel if r["verdict"] == vd]
            b = {"n": len(s), "mean": _mean([r[key] for r in s]), "diff": _mean([r["nd"] for r in s])}
            if base:
                b["fewer_diff"] = sum(1 for r in s if r["id"] in base and r["nd"] < base[r["id"]]["nd"])
                b["more_diff"] = sum(1 for r in s if r["id"] in base and r["nd"] > base[r["id"]]["nd"])
                b["changed"] = sum(1 for r in s if r["id"] in base and
                                   (r[key] != base[r["id"]]["score"] or r["cols"] != base[r["id"]]["cols"]))
                b["score_up"] = sum(1 for r in s if r["id"] in base and r[key] > base[r["id"]]["score"])
                b["score_down"] = sum(1 for r in s if r["id"] in base and r[key] < base[r["id"]]["score"])
            blk[vd] = b
        out["archive"][scope] = blk
    return out


def cmd_variants(a):
    its = items()
    allv = all_variants()
    names = a.names or list(allv)
    RES.mkdir(parents=True, exist_ok=True)
    mfile = RES / "metrics.json"
    try:
        metrics = json.loads(mfile.read_text("utf-8"))
    except (OSError, ValueError):
        metrics = {}
    t0 = time.perf_counter()
    if "baseline" not in names and not (ROWS / "baseline.jsonl.gz").exists():
        names = ["baseline"] + names
    base_rows = None
    if (ROWS / "baseline.jsonl.gz").exists() and "baseline" not in names:
        base_rows = load_rows("baseline")
    for name in (["baseline"] if "baseline" in names else []) + [n for n in names if n != "baseline"]:
        cfg = allv[name]
        rows, missing = run_variant(name, cfg, its)
        save_rows(name, rows)
        if name == "baseline":
            base_rows = rows
        m = measures(rows, base_rows)
        m["config"] = {k: (v if k != "model" else {l: model_of(cfg, l) for l in LANGS}) for k, v in cfg.items()}
        m["models"] = {l: model_of(cfg, l) for l in LANGS}
        m["missing"] = {f"{s}/{l}": n for (s, l), n in sorted(missing.items())}
        m["rows"] = len(rows)
        metrics[name] = m
        print(f"{name}: {len(rows)} rows, missing {sum(missing.values())}  ({time.perf_counter() - t0:.0f} s)", flush=True)
        write_json(mfile, metrics, indent=1)
    # E: the check alone (100 x mean p_ok over the judged target sounds), from the baseline rows
    if base_rows is not None:
        e = measures([{**r, "score": r["sc"]} for r in base_rows if r["sc"] is not None], None)
        e["config"] = {"score": "100 x mean p_ok over judged target sounds (the check alone)"}
        e["models"] = {l: BASE[l] for l in LANGS}
        e["rows"] = sum(1 for r in base_rows if r["sc"] is not None)
        metrics["E-check score"] = e
        write_json(mfile, metrics, indent=1)
    print("metrics ->", mfile)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd")
    f = sub.add_parser("fill")
    f.add_argument("--workers", type=int, default=3)
    f.add_argument("--langs")
    f.add_argument("--models")
    v = sub.add_parser("variants")
    v.add_argument("names", nargs="*")
    a = ap.parse_args()
    if a.cmd == "fill":
        cmd_fill(a)
    elif a.cmd == "variants":
        cmd_variants(a)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
