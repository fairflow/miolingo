"""Validation of the lab's baseline, before anything is measured.

    <python> -m lab.validate stored          the lab's baseline against the stored archive lines
    <python> -m lab.validate replay          tests/replay_archive.py's own replay (real env, real compiled engine) of
                                             every archived take -> var/lab/validate/replay.jsonl, then compared
    <python> -m lab.validate engine [sets]   the real compiled engine fed with the lab's CACHED answers (hear, sounds)
                                             for every item of the sets: score, understood, columns must be equal

`stored`: per take the lab's target, heard text, heard sounds, flags, score, understood and columns are compared with
the line the live host stored.  Lines are grouped by the engine version that wrote them; reconstructed lines (rebuilt
from the history table: no columns, no flags) are listed apart.
`replay` and `engine` start a SCRATCH engine process (`neolingo neohost`, as tests/replay_archive.py does); the live
host is not involved, and every file the host's code writes goes under var/lab/hostvar/."""
from __future__ import annotations

import collections
import json
import sys
import time

from . import analyse as A
from . import datasets
from . import engine_py as E
from .common import ARCHIVE, LAB, ROOT, read_jsonl, write_jsonl

OUT = LAB / "validate"


def cols_of(rec, flags):
    return E.columns_from(flags, E.by_word(rec["target"], [(t, h) for (t, h, _k) in rec["columns"]]))


def flag_key(fl):
    return [(f["at"], f["sound"], f.get("heardAs"), bool(f["off"])) for f in (fl or [])]


def compare(rec, old, lower_text=False):
    """-> list of differences between the lab's baseline record and a stored (or replayed) result."""
    ch = []
    if old.get("target") is not None and old["target"] != rec["target"]:
        ch.append("target")
    oh = old.get("hear") or {}
    lo = (lambda t: (t or "").lower()) if lower_text else (lambda t: t)
    if lo(oh.get("text")) != lo(rec["heard_text"]):
        ch.append("text")
    if E.flat(oh.get("ipa")) != rec["greedy"]:
        ch.append("heard")
    if old.get("flags") is not None and flag_key(old["flags"]) != flag_key(rec["flags"]):
        ch.append("flags")
    if old.get("score") != rec["score"]:
        ch.append("score")
    if old.get("understood") != rec["understood"]:
        ch.append("understood")
    if old.get("columns") is not None and old["columns"] != cols_of(rec, rec["flags"]):
        ch.append("columns")
    return ch


def describe(rec, old, ch):
    out = []
    oh = old.get("hear") or {}
    if "target" in ch:
        out.append(f"target  stored {''.join(E.flat(old['target']))}  lab {''.join(E.flat(rec['target']))}")
    if "text" in ch:
        out.append(f"text    stored {oh.get('text')!r}  lab {rec['heard_text']!r}")
    if "heard" in ch:
        out.append(f"heard   stored {' '.join(E.flat(oh.get('ipa')))}  lab {' '.join(rec['greedy'])}")
    if "flags" in ch:
        out.append(f"flags   stored {flag_key(old['flags'])}  lab {flag_key(rec['flags'])}")
    if "score" in ch:
        out.append(f"score   stored {old.get('score')}  lab {rec['score']}")
    if "understood" in ch:
        out.append(f"understood stored {old.get('understood')}  lab {rec['understood']}")
    for c in ch:
        if c.startswith("WITH THE STORED TARGET"):
            out.append(c)
    if "columns" in ch and not ({"heard", "flags", "target"} & set(ch)):
        out.append("columns differ though target, heard sounds and flags agree")
    return out


def cmd_stored():
    items = datasets.archive_items()
    groups = collections.defaultdict(lambda: [0, 0, []])
    lines = []
    for it in items:
        rec = A.analyse(it)
        old = it["stored"]
        ver = (old.get("version") or {})
        g = "reconstructed" if it["reconstructed"] else f"engine {ver.get('engine')} (host {ver.get('host')}, page {ver.get('page')})"
        ch = compare(rec, old, lower_text=it["reconstructed"])
        retarget = None
        if "target" in ch:                 # the target of the phrase has changed since (data/ipa_exceptions.json):
            rec2 = A.analyse({**it, "target": old["target"]})          # the same take against the STORED target
            retarget = compare(rec2, old, lower_text=it["reconstructed"])
            ch = ch + [f"WITH THE STORED TARGET: {'equal' if not retarget else 'still different: ' + ', '.join(retarget)}"]
        groups[g][0] += 1
        if ch:
            groups[g][1] += 1
            groups[g][2].append((it, rec, ch))
        lines.append({"take": it["id"], "group": g, "variant": it["variant"], "text": it["text"], "differences": ch,
                      "stored_score": old.get("score"), "lab_score": rec["score"],
                      "stored_understood": old.get("understood"), "lab_understood": rec["understood"]})
    OUT.mkdir(parents=True, exist_ok=True)
    write_jsonl(OUT / "stored.jsonl", lines)
    w = []
    w.append(f"# The lab's baseline against the stored archive lines ({time.strftime('%Y-%m-%d %H:%M')})\n")
    w.append("Compared per take: target sounds, heard text, heard sounds, flags (as the engine kept them), score, "
             "understood, columns with their marks.  Reconstructed lines have only text, sounds, score, understood, flags.\n")
    w.append("| written by | takes | equal | different |\n|---|---|---|---|")
    for g, (n, bad, _l) in sorted(groups.items()):
        w.append(f"| {g} | {n} | {n - bad} | {bad} |")
    w.append("")
    for g, (n, bad, l) in sorted(groups.items()):
        if not l:
            continue
        w.append(f"\n## {g}: {bad} different\n")
        for it, rec, ch in l:
            w.append(f"- `{it['id']}` {it['variant']} {it['text']!r}: {', '.join(ch)}")
            for d in describe(rec, it["stored"], ch):
                w.append(f"    - {d}")
    (OUT / "stored.md").write_text("\n".join(w) + "\n", "utf-8")
    print("\n".join(w))


def _engine():
    sys.path.insert(0, str(ROOT / "tests"))
    import replay_archive as ra                      # sets the scratch log under var/lab/hostvar/replay
    from host import paths
    paths.ARCHIVE = ARCHIVE                          # the real archive, READ only
    paths.ARCHIVE_TAKES = ARCHIVE / "takes"
    return ra, paths


def cmd_replay():
    ra, paths = _engine()
    items = datasets.archive_items()
    OUT.mkdir(parents=True, exist_ok=True)
    eng = ra.Engine(ra.build_config())
    eng.env = ra.ArchiveEnvironment()
    rows = []
    t0 = time.perf_counter()
    for k, it in enumerate(items, 1):
        line = {"variant": it["variant"], "text": it["text"], "take": it["id"]}
        try:
            new = ra.replay_one(eng, None, line)
        except Exception as e:
            new = {"error": f"{type(e).__name__}: {e}"}
            eng.restart()
        rows.append({"take": it["id"], "variant": it["variant"], "text": it["text"], "new": new})
        if k % 10 == 0:
            print(f"  replayed {k}/{len(items)}  {time.perf_counter() - t0:.0f} s", flush=True)
    eng.proc.terminate()
    write_jsonl(OUT / "replay.jsonl", rows)
    print(f"replayed {len(rows)} takes through the real engine in {time.perf_counter() - t0:.0f} s -> {OUT / 'replay.jsonl'}")
    cmd_replay_compare()


def cmd_replay_compare():
    items = {it["id"]: it for it in datasets.archive_items()}
    rows = read_jsonl(OUT / "replay.jsonl")
    same, diff, w = 0, [], []
    not_checked = 0
    for r in rows:
        it, new = items[r["take"]], r["new"]
        if not new.get("checked"):
            not_checked += 1
            diff.append((it, None, [f"the engine did not check it: {json.dumps(new, ensure_ascii=False)[:200]}"]))
            continue
        rec = A.analyse(it)
        ch = compare(rec, new)
        if ch:
            diff.append((it, rec, describe(rec, new, ch) or ch))
        else:
            same += 1
    w.append(f"# The lab's baseline against tests/replay_archive.py through the real engine ({time.strftime('%Y-%m-%d %H:%M')})\n")
    w.append(f"{len(rows)} takes replayed (env.audible, env.hear, env.sounds answered live; the compiled engine "
             f"`neolingo neohost` computed the result).  Equal in target, heard text, heard sounds, flags, score, "
             f"understood and columns: **{same}**.  Different: **{len(diff)}** (of which not checked by the engine: {not_checked}).\n")
    for it, rec, d in diff:
        w.append(f"- `{it['id']}` {it['variant']} {it['text']!r}")
        for x in d:
            w.append(f"    - {x}")
    (OUT / "replay.md").write_text("\n".join(w) + "\n", "utf-8")
    print("\n".join(w))


def cmd_engine(sets, variant="baseline", every=1):
    """The real engine, fed with the lab's cached answers.

    variant  a name of lab/run.py's variants: the engine is given the variant's FINAL heard sounds (what the variant
             counts as heard) as the answer to `hear`, so that its score and columns can be compared with the lab's.
             For a cost or curve variant (B) the engine gets a configuration with those costs and that curve
             (the engine has the curves "sqrt" and "linear"; the stretched costs are entries of the cost list).
             Display-only rules (zero_equal) and the understood rules other than "free" are not the engine's.
    every    take every k-th item of the sets (a sample)."""
    ra, paths = _engine()
    from host.engine import Environment
    from host.engine_config import build_config
    from . import check, run as RUN
    from host.engine import flags_out
    cfg = {**A.BASELINE, **RUN.all_variants()[variant]}
    if cfg.get("understood") != "free":
        cfg["understood"] = "free"
    items = [i for i in RUN.items() if i["set"] in sets][::every]
    state = {}

    class CachedEnvironment(Environment):
        def answer(self, q):
            k = q["q"]
            rec = state.get("rec")
            if k == "targetIpa":
                if rec is not None and q["text"] == rec["text"] and q["variant"] == rec["variant"]:
                    return {"ipa": rec["target"]}          # the item's target (cpflip: the changed one)
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

    config = build_config()
    if cfg["cost"] == "stretched":
        for e in config["costs"]:
            e["cost"] = E.stretch(e["cost"])
        config["costOtherwise"] = E.stretch(config["costOtherwise"])
    if cfg["curve"] == "linear":
        config["curve"] = {"kind": "linear"}
    if cfg.get("del_accept"):
        sys.exit("the engine has one deletion cost (1000): del_accept cannot be given to it")
    if cfg["unchecked"] in ("phoneme", "phoneme_lr"):
        # an `unreliable` target costs its plain panphon distance against a full vowel of the language: drop those
        # per-language zero entries from the cost list (the generic entry then applies), as engine_py.Costs does
        tab = E.cost_table()
        drop = {(l, t, h) for l, L in tab["langs"].items() for t in L.get("unreliable", [])
                for h in A.FULL_VOWELS.get(l, ())}
        config["costs"] = [e for e in config["costs"] if (e.get("lang"), e["target"], e["heard"]) not in drop]
    eng = ra.Engine(config)
    eng.env = CachedEnvironment()
    same, diff, no_text = 0, [], 0
    t0 = time.perf_counter()
    for n, it in enumerate(items, 1):
        m = RUN.model_of(cfg, it["lang"])
        from . import cache
        if not cache.has_lp(it["wav"], m):
            continue
        rec = A.analyse(it, {**cfg, "model": m})
        if not rec["heard"]:
            continue                                # the engine treats an empty hearing apart (nothing heard)
        text_known = rec["understood"] is not None
        if not text_known:
            no_text += 1
        raw = check.raw_tokens(it["wav"], m, rec["target"], it["variant"])
        lib = check.lib_findings(raw["tokens"])
        rec["flags_sent"] = flags_out(lib, rec["target"]) if lib else []
        token = f"x{n:07d}"
        state["rec"] = rec
        new = ra.replay_one(eng, None, {"variant": it["variant"], "text": it["text"], "take": token})
        state.pop("rec", None)
        if not new.get("checked"):
            diff.append((it, [f"not checked: {json.dumps(new, ensure_ascii=False)[:160]}"]))
            continue
        ch = []
        if new["score"] != rec["score"]:
            ch.append(f"score engine {new['score']} lab {rec['score']}")
        if text_known and new["understood"] != rec["understood"]:
            ch.append(f"understood engine {new['understood']} lab {rec['understood']}")
        cols_lab = E.columns_from(rec["flags"], E.by_word(rec["target"], [(t, h) for (t, h, _k) in rec["columns"]]))
        if new["columns"] != cols_lab:
            ch.append("columns")
        if flag_key(new["flags"]) != flag_key(rec["flags"]):
            ch.append("flags kept")
        if new["target"] != rec["target"]:
            ch.append("target")
        if ch:
            diff.append((it, ch))
        else:
            same += 1
        if n % 200 == 0:
            print(f"  {n}/{len(items)}  {time.perf_counter() - t0:.0f} s  equal {same}  different {len(diff)}", flush=True)
    eng.proc.terminate()
    w = [f"# The lab's Python copy of the engine against the real engine, on cached answers ({time.strftime('%Y-%m-%d %H:%M')})\n",
         f"Variant: **{variant}** (config {json.dumps(RUN.all_variants()[variant], ensure_ascii=False)}).  Engine binary: "
         f"`{paths.ENGINE}`.  Sets: {', '.join(sets)} (every {every}th item).  Compared: score, columns with their marks, "
         f"flags kept, target; understood where the Whisper text is cached (not cached: {no_text} items, given the text \"\").  "
         f"Equal: **{same}**.  Different: **{len(diff)}**.\n"]
    for it, ch in diff[:200]:
        w.append(f"- `{it['id']}` {it['variant']} {it['text']!r}: {'; '.join(ch)}")
    OUT.mkdir(parents=True, exist_ok=True)
    name = f"engine-{variant.replace(' ', '_').replace('=', '')}-" + "-".join(sets) + ".md"
    (OUT / name).write_text("\n".join(w) + "\n", "utf-8")
    print("\n".join(w[:30]))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "stored"
    if cmd == "stored":
        cmd_stored()
    elif cmd == "replay":
        cmd_replay()
    elif cmd == "replay-compare":
        cmd_replay_compare()
    elif cmd == "engine":
        import argparse
        ap = argparse.ArgumentParser()
        ap.add_argument("sets", nargs="*", default=["archive", "reference"])
        ap.add_argument("--variant", default="baseline")
        ap.add_argument("--every", type=int, default=1)
        a = ap.parse_args(sys.argv[2:])
        cmd_engine(a.sets, a.variant, a.every)
    else:
        sys.exit(__doc__)
