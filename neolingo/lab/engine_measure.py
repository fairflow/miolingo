"""Measurement on the REAL engine (the third run's follow-up, 14 October 21:1x): the off floor and the splits table,
two engine mechanisms the language lane is building, measured the moment that engine lands.

    <python> -m lab.engine_measure run  --spec lab/engine_variants.json [--engine PATH] [--sets ...] [--shard K/N]
    <python> -m lab.engine_measure measure --spec lab/engine_variants.json

`run` starts a scratch engine (`neolingo neohost`, as tests/replay_archive.py does; never the live host) per variant of
the spec, with the configuration the HOST builds (host/engine_config.build_config: the default, i.e. today's costs with
the German vocalised-r pairs free; or "base": "plain" for the configuration before that) plus the variant's own fields,
and answers the engine's questions from the lab's caches EXACTLY as the host's environment would:
    targetIpa  env.target_ipa (cached; a roles-reversed item's changed target)
    audible    true
    hear       the phone model's free reading (env.hear's sounds, cached), and as text the PHRASE ITSELF: the take is
               then understood and the result's picture is the VERIFIED one, the one the score is computed on (whether a
               take is understood is part D, not measured here)
    sounds     the sound check's findings (env.sounds: the check's own, then the German ü/ö rule's, computed from the
               cached log-probabilities with the same functions), through host.engine.flags_out, the warnings of the
               configuration's free pairs dropped (as host/engine.py does)
The engine computes everything else: alignment, V2, splits, off floor, score, picture.  Rows (score, the picture as
(target, heard, kind) columns) -> var/lab/run3/engine/<variant>.<shard>.json.gz.

`measure` reads the rows of every variant and gives, per language: the near-miss AUC, near misses detected at the
place, reference phrases at 100 and their differences, the natives' mean, share at 100 and DIFFERENCES (the splits
must not raise the natives' false differences), the roles-reversed detection; and on the owner's verdicts (the same
set and agreement as lab/costfit.py) the same rule: AUC guard (no language down by more than 0.02), then the fewest
parameters among the variants not separated from the best.  -> var/lab/run3/engine/measure.json and .md.

THE SPEC (lab/engine_variants.json): {"fields": {"off_floor": <the configuration's field name>, "splits": <...>},
"splits": <the table, data/splits.json by default>, "variants": [{"name", "base": "live" | "plain", "off_floor": F or
null, "splits": true | false}]}.  The field names and the JSON shape are the language lane's (protocol section 5);
until the lane reports them they are placeholders, and `run` refuses a spec still holding one."""
from __future__ import annotations

import argparse
import collections
import gzip
import json
import os
import sys
import time

from . import analyse as A
from . import cache, check
from . import costfit as C
from . import engine_py as E
from . import run as RUN
from .common import DATA, LANGS, ROOT, write_json

OUT = C.OUT / "engine"
SPEC = ROOT / "lab" / "engine_variants.json"
PLACEHOLDER = "<from the language lane>"


# ------------------------------------------------------------------ the configuration of a variant
def config_for(spec, v):
    """The host's configuration (default, or "plain" = before the vocalised-r pairs) plus the variant's fields."""
    from host import engine_config as EC
    os.environ.pop("NEOLINGO_COSTS", None)
    if v.get("base", "live") == "plain":
        real = EC.cost_option
        EC.cost_option = lambda: ("live", None)
        try:
            config = EC.build_config()
        finally:
            EC.cost_option = real
    else:
        config = EC.build_config()
    # the variant decides the floor and the splits (the default configuration may carry them since 14 October)
    config.pop("offFloor", None)
    config.pop("splits", None)
    f = spec["fields"]
    if v.get("off_floor") is not None:
        config[f["off_floor"]] = v["off_floor"]
    if v.get("splits"):
        config[f["splits"]] = spec_splits(spec)
    return config


def spec_splits(spec):
    """The splits table in the shape the engine reads: spec["splits"] if given there, else data/splits.json converted by
    spec["splits_shape"] (default: the file's own list)."""
    if spec.get("splits") is not None:
        return spec["splits"]
    return json.loads((DATA / "splits.json").read_text("utf-8"))["splits"]


def free_pairs_of(v, lang):
    from host import engine_config as EC
    if v.get("base", "live") == "plain":
        return set()
    os.environ.pop("NEOLINGO_COSTS", None)
    return EC.free_pairs(lang)


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
    findings = check.lib_findings(raw["tokens"]) if raw["tokens"] else []
    tokens = raw["tokens"]
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


def flags_for(v, it, target, findings):
    from host.engine import flags_out
    fl = flags_out(findings, target) if findings else []
    free = free_pairs_of(v, it["lang"])
    return [f for f in fl if (f["sound"], f["heardAs"]) not in free]


# ------------------------------------------------------------------ run
def columns_of(picture):
    """The engine's picture -> [(target, heard, kind)] in order (a split shows its heard sounds joined)."""
    out = []
    for w in picture or []:
        for s in w.get("sounds", []):
            h = s.get("heard")
            if isinstance(h, list):
                h = "".join(h)
            out.append((s.get("target"), h, s.get("kind")))
    return out


def cmd_run(a):
    spec = json.loads(a.spec.read_text("utf-8"))
    names = a.only or [v["name"] for v in spec["variants"]]
    bad = [k for k, x in spec["fields"].items() if x == PLACEHOLDER]
    if bad and any(v.get("off_floor") is not None or v.get("splits") for v in spec["variants"] if v["name"] in names):
        sys.exit(f"the spec still holds placeholders for {bad}: fill in the language lane's field names first")
    if a.engine:
        os.environ["NEOLINGO_ENGINE"] = a.engine
    from .validate import _engine
    ra, paths = _engine()
    k, n = (int(x) for x in a.shard.split("/"))
    items = [i for i in RUN.items() if i["set"] in a.sets]
    items = [i for j, i in enumerate(items) if j % n == k]
    pre = {}
    t0 = time.perf_counter()
    for it in items:
        try:
            pre[it["id"]] = answers(it)
        except KeyError:                      # no cached log-probabilities
            continue
    print(f"answers for {len(pre)} items ({time.perf_counter() - t0:.0f} s)", flush=True)
    state = {}
    from host.engine import Environment

    class CachedEnvironment(Environment):
        def answer(self, q):
            kq = q["q"]
            it, target, G, flags = state["cur"]
            if kq == "targetIpa":
                if q["text"] == it["text"] and q["variant"] == it["variant"]:
                    return {"ipa": target}
                return {"ipa": A.target_ipa(q["text"], q["variant"])}
            if kq == "fill":
                return {"translation": "", "notes": ""}
            if kq == "audible":
                return {"audible": True}
            if kq == "hear":
                return {"text": it["text"], "ipa": [G] if G else []}
            if kq == "sounds":
                return {"flags": flags}
            raise ValueError(q)

    for v in spec["variants"]:
        if v["name"] not in names:
            continue
        eng = ra.Engine(config_for(spec, v))
        eng.env = CachedEnvironment()
        rows, t0 = {}, time.perf_counter()
        for j, it in enumerate(items, 1):
            if it["id"] not in pre:
                continue
            target, G, findings = pre[it["id"]]
            state["cur"] = (it, target, G, flags_for(v, it, target, findings))
            new = ra.replay_one(eng, None, {"variant": it["variant"], "text": it["text"], "take": f"x{j:07d}"})
            if not new.get("checked"):
                rows[it["id"]] = {"x": True, "score": 0, "cols": []}
                continue
            rows[it["id"]] = {"x": not G, "score": new["score"], "cols": columns_of(new.get("picture")),
                              "flags": len(new.get("flags") or [])}
            if j % 1000 == 0:
                print(f"  {v['name']}: {j}/{len(items)}  {time.perf_counter() - t0:.0f} s", flush=True)
        eng.proc.terminate()
        p = OUT / f"{v['name']}.{k}-{n}.json.gz"
        p.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(p, "wt", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False)
        print(f"{v['name']}: {len(rows)} rows -> {p} ({time.perf_counter() - t0:.0f} s)", flush=True)


# ------------------------------------------------------------------ measure
DIFF = ("near", "off", "missing", "added")


def load_rows(name):
    rows = {}
    for p in sorted(OUT.glob(f"{name}.*-*.json.gz")):
        with gzip.open(p, "rt", encoding="utf-8") as f:
            rows.update(json.load(f))
    return rows


def kinds_cols(r):
    return [(t, h, k) for (t, h, k) in r["cols"]]


def measures(rows, its):
    out = {}
    for lang in LANGS:
        sel = collections.defaultdict(list)
        for i, r in rows.items():
            it = its.get(i)
            if it is None or it["lang"] != lang or r["x"]:
                continue
            sel[it["set"]].append((it, r))
        nd = lambda r: sum(1 for (_t, _h, k) in r["cols"] if k in DIFF)       # noqa: E731
        det = []
        for it, r in sel["nearmiss"] + sel["cpflip"]:
            d, _dc, _f = RUN.truth_eval(kinds_cols(r), it["truth"])
            det.append((it["set"], d))
        o = {"auc": C.auc([r["score"] for _i, r in sel["positive"]], [r["score"] for _i, r in sel["nearmiss"]]),
             "nm_det": C._share([d for s, d in det if s == "nearmiss"]),
             "rr_det": C._share([d for s, d in det if s == "cpflip"]),
             "ref100": C._share([r["score"] == 100 for _i, r in sel["reference"]]),
             "ref_diff": C._mean([nd(r) for _i, r in sel["reference"]]),
             "cp_mean": C._mean([r["score"] for _i, r in sel["cp"]]),
             "cp100": C._share([r["score"] == 100 for _i, r in sel["cp"]]),
             "cp_diff": C._mean([nd(r) for _i, r in sel["cp"]]),
             "n": {s: len(x) for s, x in sel.items()}}
        out[lang] = o
    return out


def fmt(x, d):
    return "–" if x is None else f"{x:.{d}f}"


def pct(x):
    return "–" if x is None else f"{100 * x:.1f}%"


def cmd_measure(a):
    spec = json.loads(a.spec.read_text("utf-8"))
    its = {i["id"]: i for i in RUN.items()}
    vs = [v for v in C.verdict_set() if not v["excluded"]]
    res, vecs = [], {}
    for v in spec["variants"]:
        rows = load_rows(v["name"])
        if not rows:
            print(f"{v['name']}: no rows (run it first)")
            continue
        g = measures(rows, its)
        sc = {i: r["score"] for i, r in rows.items() if i in its and its[i]["set"] == "archive"}
        vecs[v["name"]] = [C.agrees(x["kind"], x["ref"], sc[x["id"]]) for x in vs if x["id"] in sc]
        npar = int(v.get("off_floor") not in (None, 0)) + int(bool(v.get("splits")))
        res.append({"name": v["name"], "k": v["name"], "guards": g, "agree": sum(vecs[v["name"]]),
                    "n": len(vecs[v["name"]]), "two": [sc.get(t) for t in C.TWO],
                    "cx": [npar, 0, 0, v.get("off_floor") or 0]})
    if not res:
        sys.exit("nothing to measure")
    ref = next((x for x in res if x["cx"][0] == 0), res[0])
    for x in res:
        x["auc_ok"] = all(x["guards"][l]["auc"] is not None and ref["guards"][l]["auc"] is not None
                          and x["guards"][l]["auc"] >= ref["guards"][l]["auc"] - 0.02 for l in LANGS)
        # the splits against the same variant without them (same floor): the natives' differences must not rise
        twin = next((y for y in res if y["name"] == x["name"].replace("splits+", "").replace("splits", ref["name"])), ref)
        x["splits_ok"] = all((x["guards"][l]["cp_diff"] or 0) <= (twin["guards"][l]["cp_diff"] or 0) for l in LANGS)
    eligible = [x for x in res if x["auc_ok"]]
    idx = list(range(min(len(v) for v in vecs.values())))
    chosen, best = C.choose(eligible, vecs, idx)
    sep = {x["name"]: dict(zip(("a_only", "b_only", "p"), C.mcnemar(vecs[x["name"]], vecs[ref["name"]]))) for x in res}
    out = {"made": time.strftime("%Y-%m-%d %H:%M %Z"), "reference": ref["name"], "chosen": chosen["name"],
           "best": best["name"], "variants": [{k: v for k, v in x.items() if k != "k"} for x in res], "sep": sep}
    write_json(OUT / "measure.json", out, indent=1)
    w = [f"# The off floor and the splits on the real engine ({out['made']})\n",
         f"Reference: {ref['name']}.  Chosen by the rule (AUC guard; fewest parameters among the variants not separated "
         f"from the best): **{chosen['name']}** (best agreement: {best['name']}).\n",
         "| variant | agree | against the reference | two takes | " +
         " | ".join(f"{l} AUC | {l} near misses | {l} roles reversed | {l} ref =100 | {l} natives diff" for l in LANGS) + " |",
         "|---|---|---|---|" + "---|" * (5 * len(LANGS))]
    for x in res:
        s = sep[x["name"]]
        cells = []
        for l in LANGS:
            g = x["guards"][l]
            cells += [fmt(g["auc"], 4), pct(g["nm_det"]), pct(g["rr_det"]), pct(g["ref100"]), fmt(g["cp_diff"], 3)]
        w.append(f"| {x['name']} | {x['agree']}/{x['n']} | {s['a_only']}:{s['b_only']} (p {s['p']:.3g}) | "
                 f"{x['two'][0]} / {x['two'][1]} | " + " | ".join(cells) + " |")
    w.append("\nSplits must not raise the natives' false differences: " +
             ", ".join(f"{x['name']} {'ok' if x['splits_ok'] else 'RAISES'}" for x in res if "split" in x["name"]))
    (OUT / "measure.md").write_text("\n".join(w) + "\n", "utf-8")
    print("\n".join(w))


# ------------------------------------------------------------------ the floor on a pair that costs nothing
def cmd_tolerated(a):
    """How often the off floor would price a pair that costs nothing: per set and language, the "likely off" flags the
    host sends (after dropping the free pairs' warnings), and of those, how many fall on a sound the free reading
    heard as ANOTHER sound costing 0 under the default costs (a tolerated or accepted pair, an unreliable target, the
    vocalised-r pairs): the engine's floor makes such a pair cost F and draws it.  The alignment is the lab's (the
    engine's `align` copied, the default costs); a deletion is not a substitution and is counted apart."""
    spec = json.loads(a.spec.read_text("utf-8"))
    v = next(x for x in spec["variants"] if x["name"] == "live")
    combo = C.Combo(vr=True)
    cnt = collections.Counter()
    pairs = collections.Counter()
    for it in RUN.items():
        if it["set"] not in ("cp", "reference", "archive", "nearmiss", "positive"):
            continue
        if it["set"] == "archive" and it.get("voice") != "learner":
            continue
        try:
            target, G, findings = answers(it)
        except KeyError:
            continue
        if not G:
            continue
        flags = [f for f in flags_for(v, it, target, findings) if f["off"]]
        cfg = C.cfg_for(combo, it["lang"])
        cost = A.costs_for(it["lang"], cfg["cost"], cfg["unchecked"])
        T = E.flat(target)
        heard_at, i = {}, 0
        for (t, h) in E.align(cost, T, list(G)):
            if t is None:
                continue
            heard_at[i] = h
            i += 1
        key = (it["set"], it["lang"])
        cnt[key + ("items",)] += 1
        hit = False
        for f in flags:
            h = heard_at.get(f["at"])
            t = T[f["at"]] if f["at"] < len(T) else None
            cnt[key + ("off",)] += 1
            if h is None:
                cnt[key + ("deleted",)] += 1
            elif h == t:
                cnt[key + ("same",)] += 1
            elif cost(t, h) == 0:
                cnt[key + ("free",)] += 1
                pairs[(it["lang"], t, h)] += 1
                hit = True
            else:
                cnt[key + ("costing",)] += 1
        cnt[key + ("items_free",)] += int(hit)
    out = {"counts": {"|".join(k): n for k, n in cnt.items()},
           "pairs": [{"lang": l, "target": t, "heard": h, "n": n} for (l, t, h), n in pairs.most_common()]}
    write_json(OUT / "tolerated.json", out, indent=1)
    for s in ("cp", "reference", "archive", "nearmiss", "positive"):
        for l in LANGS:
            g = lambda k: cnt[(s, l, k)]          # noqa: E731
            if g("items"):
                print(f"{s:9} {l}: items {g('items')}, off flags {g('off')}: heard the same {g('same')}, left out "
                      f"{g('deleted')}, a pair costing 0 {g('free')} (in {g('items_free')} items), costing {g('costing')}")
    print("pairs costing 0 under an off flag:", [(x["lang"], x["target"], x["heard"], x["n"]) for x in out["pairs"][:15]])


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd")
    r = sub.add_parser("run")
    r.add_argument("--spec", type=lambda s: ROOT / s if not s.startswith("/") else __import__("pathlib").Path(s),
                   default=SPEC)
    r.add_argument("--engine")
    r.add_argument("--sets", nargs="*", default=["archive", "reference", "nearmiss", "positive", "cp", "cpflip"])
    r.add_argument("--shard", default="0/1")
    r.add_argument("--only", nargs="*")
    tl = sub.add_parser("tolerated")
    tl.add_argument("--spec", type=lambda s: ROOT / s if not s.startswith("/") else __import__("pathlib").Path(s),
                    default=SPEC)
    m = sub.add_parser("measure")
    m.add_argument("--spec", type=lambda s: ROOT / s if not s.startswith("/") else __import__("pathlib").Path(s),
                   default=SPEC)
    a = ap.parse_args()
    if a.cmd == "run":
        cmd_run(a)
    elif a.cmd == "tolerated":
        cmd_tolerated(a)
    elif a.cmd == "measure":
        cmd_measure(a)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
