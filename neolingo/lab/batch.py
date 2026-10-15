"""The engine's own judgement for the lab: `neolingo batch FILE` (locus a4c5878 and later; the format is written in
locus Neolingo.lean beside the command).  It runs the engine's `judgeWith` per item, so the lab needs no second copy
of the scoring (it replaced lab/engine_py.py, now in lab/archive/, for everything the engine itself decides: alignment, V2, splits, the off
floor, the score, the picture, the flags kept, understood).

    run(config, items)            -> {id: result}; config = protocol section 5 (host.engine_config.build_config())
    host_config(name)             the host's configuration under NEOLINGO_COSTS=name ("live": the default)
    answers(it)                   (target, free reading, findings) as the host's environment would give them, from the
                                  lab's caches (the check's findings and the German ü/ö rule's)
    flags_for(it, target, findings, free)   host.engine.flags_out, the free pairs' warnings dropped (as host/engine.py)
    item_for(it, target, G, flags, text)    one batch item, with the readings `sameSounds` needs (the German
                                  respellings of the text, each with its espeak sounds)

    <python> -m lab.batch compare [--engine PATH]   the lab's analysis (lab/analyse.py: its own V2 rules on the engine's
                                  alignment, lab/align.py) against batch on
                                  every item, under the default configuration (without and with the splits) and run3
                                  -> var/lab/batch/compare.md"""
from __future__ import annotations

import argparse
import collections
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from . import align as AL
from . import analyse as A
from . import cache, check
from . import costfit as C
from . import run as RUN
from .common import LAB, write_json

OUT = LAB / "batch"
DEFAULT_ENGINE = "/Users/matthew/Lean/locus/.lake/build/bin/neolingo"


def engine_path(engine=None):
    return engine or os.environ.get("NEOLINGO_ENGINE") or DEFAULT_ENGINE


def run(config, items, engine=None, chunk=1500):
    """Every item through `neolingo batch`, in chunks; -> {id: result}.  A refusal of the engine is raised."""
    out = {}
    cfg = {k: v for k, v in config.items() if k != "cmd"}
    tmpdir = LAB / "tmp"
    tmpdir.mkdir(parents=True, exist_ok=True)
    for i in range(0, len(items), chunk):
        with tempfile.NamedTemporaryFile("w", suffix=".json", dir=tmpdir, delete=False, encoding="utf-8") as f:
            json.dump({"config": cfg, "items": items[i:i + chunk]}, f, ensure_ascii=False)
            path = f.name
        try:
            p = subprocess.run([engine_path(engine), "batch", path], capture_output=True, text=True)
        finally:
            os.unlink(path)
        if p.returncode != 0:
            raise RuntimeError(f"neolingo batch failed ({p.returncode}): {p.stderr.strip()[:500]}")
        j = json.loads(p.stdout)
        if j.get("format") != "neolingo-batch 1":
            raise RuntimeError(f"unknown batch format {j.get('format')!r}")
        for r in j["results"]:
            out[r["id"]] = r
    return out


def host_config(name="live", plain=False):
    """The configuration the host sends under NEOLINGO_COSTS=name; plain=True: without any entry of
    data/cost_candidates.json (the configuration before 14 October 21:1x)."""
    from host import engine_config as EC
    old = os.environ.get("NEOLINGO_COSTS")
    os.environ["NEOLINGO_COSTS"] = name
    real = EC.cost_option
    try:
        if plain:
            EC.cost_option = lambda: ("live", None)
        return EC.build_config()
    finally:
        EC.cost_option = real
        if old is None:
            os.environ.pop("NEOLINGO_COSTS", None)
        else:
            os.environ["NEOLINGO_COSTS"] = old


def free_pairs(name, lang):
    if name == "plain":
        return set()
    cand = json.loads((C.DATA / "cost_candidates.json").read_text("utf-8"))["candidates"].get(name) or {}
    return {(t, h) for (l, t, h) in cand.get("free", []) if l == lang}


# ------------------------------------------------------------------ the host's answers, from the caches
def answers(it):
    """(target as the engine holds it, the free reading, the findings env.sounds would return)."""
    from env.ipa import norm_word
    from env.soundcheck import VERIFY_LANGS, VERIFY_TAU
    lang, variant, wav = it["lang"], it["variant"], it["wav"]
    model = C.cfg_for(C.LIVE_COMBO, lang)["model"]
    target = it["target"] if it.get("target") else A.target_of(it["text"], variant)
    G = A.greedy_of(wav, model)
    words = [w for w in target if w]
    if not words:
        return target, G, []
    raw = check.raw_tokens(wav, model, target, variant)       # the check could not run: no tokens, no findings
    tokens = raw["tokens"]
    findings = check.lib_findings(tokens) if tokens else []
    if lang in VERIFY_LANGS and any(t["level"] == "unchecked" for t in tokens):
        tn = [[norm_word(x) or x for x in w] for w in words]
        flat = [s for w in tn for s in w]
        word_of = [k for k, w in enumerate(tn) for _ in w]
        phones = check.phones_from_tokens(tokens, tn)["phones"]
        lp = cache.get_lp(wav, model)["lp"]
        vocab, blank = cache.get_vocab(model)
        kept = A.unreliable_subs(lang, tn, G, phones, lambda e: check.lr_from_lp(lp, vocab, blank, tn, e), VERIFY_TAU)
        findings += [{"at": i, "span": 1, "off": True, "like": h, "left_out": False, "sound": flat[i],
                      "word": word_of[i], "verified": round(r, 2)} for (i, h, r) in kept]
        findings.sort(key=lambda f: f["at"])
    return target, G, findings


def flags_for(it, target, findings, free):
    from host.engine import flags_out
    fl = flags_out(findings, target) if findings else []
    return [f for f in fl if (f["sound"], f["heardAs"]) not in free]


def readings_for(variant, text):
    if not text:
        return []
    from .understood import readings
    return [{"text": r, "ipa": A.target_ipa(r, variant)} for r in readings(variant, text)]


def item_for(it, target, G, flags, text):
    return {"id": it["id"], "variant": it["variant"], "phrase": it["text"], "target": target, "text": text or "",
            "heard": [G] if G else [], "flags": flags, "readings": readings_for(it["variant"], text)}


# ------------------------------------------------------------------ compare with the lab's analysis
def lab_columns(rec, cost, sig, flags_kept, understood):
    """The lab's record as the engine draws it: by word, {target, heard, kind, mark}.  Understood: the verified columns
    (rec["columns"]); not understood: the free reading's own alignment (rec["align0"]), each column by kindOf."""
    def kind_of(t, h, lab_kind=None):
        if t is None:
            return "added"
        if h is None:
            return "missing"
        if lab_kind == "unjudged":
            return "unjudged"
        if t == h:
            return "ok"
        c = cost(t, h)
        return "ok" if c == 0 else ("near" if c < sig else "off")
    if understood:
        cols = [(t, (t if (t is not None and h is not None and t != h and "‿" not in h and cost(t, h) == 0) else h),
                 kind_of(t, h, k)) for (t, h, k) in rec["columns"]]
    else:
        cols = [(t, "‿".join(h) if isinstance(h, tuple) else h, kind_of(t, h if not isinstance(h, tuple) else "‿".join(h)))
                for (t, h) in rec["align0"]]
    marks = {f["at"]: (2 if f["off"] else 1) for f in flags_kept}
    out, k_at = [], 0
    for g in A.word_columns({"target": rec["target"], "columns": cols}):
        row = []
        for (t, h, k) in g:
            m = 0
            if t is not None:
                m = marks.get(k_at, 0)
                k_at += 1
            row.append({"target": t, "heard": h, "kind": k, "mark": m})
        out.append(row)
    return out


def norm_cols(cols):
    return [[(c.get("target"), c.get("heard"), c.get("kind"), c.get("mark")) for c in w] for w in cols]


def compare_one(name, combo, S, config, its, engine, free_name):
    def keep_flags(fl, target):              # the flags the engine keeps (protocol section 3, `sounds`)
        tf = [x for w in target for x in w]
        return [f for f in fl if 0 <= f["at"] < len(tf) and tf[f["at"]] == f["sound"]]
    sig = config["significant"]
    items, labrecs, sent = [], {}, {}
    t0 = time.perf_counter()
    for it in its:
        try:
            target, G, findings = answers(it)
        except KeyError:
            continue
        flags = flags_for(it, target, findings, free_pairs(free_name, it["lang"]))
        cfg = C.cfg_for(combo, it["lang"], S)
        rec = A.analyse(it, cfg)
        if not G:
            continue
        text = rec["heard_text"] if rec["understood"] is not None else it["text"]
        items.append(item_for(it, target, G, flags, text))
        labrecs[it["id"]] = (rec, A.costs_for(it["lang"], cfg["cost"], cfg["unchecked"]))
        sent[it["id"]] = keep_flags(flags, target)
    t1 = time.perf_counter()
    res = run(config, items, engine)
    t2 = time.perf_counter()
    # batch's "alignment" field against the `align` command on the same sounds and flags (the lab's analysis aligns
    # with `align`, lab/align.py; both are Neo.alignFor)
    al = AL.Aligner(engine)
    al.configure({k: v for k, v in config.items() if k != "cmd"})
    diff = collections.Counter()
    rows = []
    for x in items:
        i = x["id"]
        rec, cost = labrecs[i]
        b = res[i]
        und = rec["understood"] if rec["understood"] is not None else True
        ch = []
        if b.get("alignment") != al.align(x["variant"], x["target"], x["heard"], x["flags"]):
            ch.append("alignment")
        if b["score"] != rec["score"]:
            ch.append("score")
        if rec["understood"] is not None and b["understood"] != rec["understood"]:
            ch.append("understood")
        fk = lambda fl: [(f["at"], f["sound"], f.get("heardAs"), bool(f["off"])) for f in fl]     # noqa: E731
        if fk(b["flags"]) != fk(sent[i]):
            ch.append("flags")
        if norm_cols(b["columns"]) != norm_cols(lab_columns(rec, cost, sig, sent[i], und)):
            ch.append("columns")
        for c in ch:
            diff[c] += 1
        if ch:
            rows.append({"id": i, "set": its_by[i]["set"], "lang": its_by[i]["lang"], "text": its_by[i]["text"],
                         "ch": ch, "lab": rec["score"], "engine": b["score"]})
    al.close()
    return {"name": name, "n": len(items), "equal": len(items) - len(rows), "diff": dict(diff), "rows": rows,
            "time_lab": round(t1 - t0, 1), "time_batch": round(t2 - t1, 1)}, res


its_by = {}


def cmd_compare(a):
    global its_by
    its = [i for i in RUN.items() if i["set"] in a.sets]
    its_by = {i["id"]: i for i in its}
    live_no_splits = host_config("live")
    live_no_splits.pop("splits", None)
    live_no_splits.pop("offFloor", None)
    run3c, run3S, _ = C.candidate("run3")
    out = []
    r1, res_ns = compare_one("default without the splits", C.Combo(vr=True), 1.0, live_no_splits, its, a.engine, "live")
    out.append(r1)
    r2, _ = compare_one("run3", run3c, run3S, host_config("run3"), its, a.engine, "run3")
    out.append(r2)
    # the splits: where the default (with them) differs from the default without them
    items = []
    for it in its:
        try:
            target, G, findings = answers(it)
        except KeyError:
            continue
        if not G:
            continue
        rec = A.analyse(it, C.cfg_for(C.Combo(vr=True), it["lang"]))
        text = rec["heard_text"] if rec["understood"] is not None else it["text"]
        items.append(item_for(it, target, G, flags_for(it, target, findings, free_pairs("live", it["lang"])), text))
    res_sp = run(host_config("live"), items, a.engine)
    sp = [{"id": i, "set": its_by[i]["set"], "lang": its_by[i]["lang"], "text": its_by[i]["text"],
           "without": res_ns[i]["score"], "with": r["score"],
           "cols": [c for w in r["columns"] for c in w if c.get("heard") and "‿" in (c.get("heard") or "")]}
          for i, r in res_sp.items() if i in res_ns and (r["score"] != res_ns[i]["score"] or r["columns"] != res_ns[i]["columns"])]
    # the lab's emulation of the splits (vocal_r12) against them, where they act
    agree12 = 0
    for x in sp:
        it = its_by[x["id"]]
        rec = A.analyse(it, C.cfg_for(C.Combo(vr=True, vr12=True), it["lang"]))
        agree12 += int(rec["score"] == x["with"])
    write_json(OUT / "compare.json", {"runs": out, "splits": sp, "splits_lab_vr12_same_score": agree12}, indent=1)
    w = [f"# The lab's analysis (its V2 rules on the engine's alignment) against `neolingo batch` ({time.strftime('%Y-%m-%d %H:%M')})\n",
         f"Engine `{engine_path(a.engine)}`.  Items: {', '.join(a.sets)}.  Compared per item: score, understood (where "
         f"Whisper's text is cached), the flags kept, the columns with their kinds and marks, and batch's "
         f"`alignment` field against the `align` command on the same sounds and flags.\n"]
    for r in out:
        w.append(f"## {r['name']}\n\nItems {r['n']}, equal **{r['equal']}**, different **{r['n'] - r['equal']}** "
                 f"({', '.join(f'{k} {v}' for k, v in sorted(r['diff'].items())) or 'none'}).  Time: lab {r['time_lab']} s, "
                 f"batch {r['time_batch']} s.\n")
        for x in r["rows"][:60]:
            w.append(f"- `{x['id']}` {x['lang']} {x['set']} {x['text']!r}: {', '.join(x['ch'])} (score lab {x['lab']}, "
                     f"engine {x['engine']})")
        w.append("")
    w.append(f"## Where the splits act (default with them against without)\n\n{len(sp)} items; the lab's emulation "
             f"(vocal_r12) gives the same score on {agree12}.\n")
    for x in sp[:60]:
        w.append(f"- `{x['id']}` {x['lang']} {x['set']} {x['text']!r}: {x['without']} -> {x['with']}"
                 + (f" ({', '.join(c['target'] + '=' + c['heard'] + ' ' + c['kind'] for c in x['cols'])})" if x["cols"] else ""))
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "compare.md").write_text("\n".join(w) + "\n", "utf-8")
    print("\n".join(w[:12]))
    for r in out:
        print(r["name"], r["n"], r["equal"], r["diff"])
    print("splits act on", len(sp), "items; lab vr12 same score", agree12)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd")
    c = sub.add_parser("compare")
    c.add_argument("--engine")
    c.add_argument("--sets", nargs="*", default=["archive", "reference", "nearmiss", "positive", "cp", "cpflip"])
    a = ap.parse_args()
    if a.cmd == "compare":
        cmd_compare(a)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
