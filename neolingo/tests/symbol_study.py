"""The symbol study: where the sources (espeak-ng target, recogniser) write different symbols for the same sound.

    <miolingo venv python> tests/symbol_study.py evidence [--no-data]   # tables + data/symbol_equivalents.json (no models)
    <miolingo venv python> tests/symbol_study.py measure                 # switch off / on over sweep, archive, wrong references
    <miolingo venv python> tests/symbol_study.py floor                   # audibility floor (no models)
    <miolingo venv python> tests/symbol_study.py targets                 # phrases whose TARGET looks wrong (no models)

Reads var/sweep/results.jsonl (tests/reference_sweep.py) and var/archive/ (the owner's own takes; read only).  Writes
only under var/study/ (git-ignored) and, for `evidence`, data/symbol_equivalents.json (symbol pairs and counts only: no
recordings).  `measure` loads the speech models (about 6 GB): run ONE such process at a time; use NEOLINGO_VAR=<scratch>
(holding copies of sweep/ and archive/) so the live host's var/ is not even read.  Offline (HF_HUB_OFFLINE=1); the sweep
audio is cached, so nothing is downloaded.

The rule for data/symbol_equivalents.json, applied mechanically (restated at the top of the file):
  a pair (target sound -> sound heard) is included for a language when
    1. both reference voices (gtts and say) produced it, in at least one aligned column each;
    2. it occurs in at least MIN_PHRASES distinct phrases (over both voices);
    3. the two sounds differ, in the cost table's panphon feature distance, by at most BOUND thousandths
       (cost = round(1000 * sum_i |f_i(a) - f_i(b)| / 48) over panphon's 24 features; 83 = two features of a pair
       differing completely, 42 = one);  a sound not in the table fails.
  The owner's own takes are counted in a separate column and are NOT evidence for inclusion: a pair only the owner
  produces may be his accent.
The reference voices are SYNTHETIC."""
import argparse
import collections
import copy
import json
import os
import sys
import time
import unicodedata
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from host import paths                                              # noqa: E402

BOUND = 100                 # thousandths (cost-table units); a->ae is 42, a->I is 167
MIN_PHRASES = 3
VOICES = ("gtts", "say")
LANGS = ("en", "fr", "de")
VARIANT = {"en": "en-gb", "fr": "fr-fr", "de": "de"}
LANG_OF = {"en-gb": "en", "en-us": "en", "fr-fr": "fr", "de": "de"}
STUDY = paths.VAR / "study"
EQUIV_FILE = paths.DATA / "symbol_equivalents.json"


def nfc(s):
    return unicodedata.normalize("NFC", s) if isinstance(s, str) else s


def jl(path):
    return [json.loads(l) for l in Path(path).read_text("utf-8").splitlines() if l.strip()]


def sweep_rows():
    return jl(paths.VAR / "sweep" / "results.jsonl")


def live_checks():
    return [l for l in jl(paths.ARCHIVE / "checks.jsonl") if not l.get("reconstructed")]


def all_checks():
    return jl(paths.ARCHIVE / "checks.jsonl")


def subs(columns):
    for word in columns or []:
        for c in word:
            t, h = nfc(c["target"]), nfc(c["heard"])
            if t and h and t != h:
                yield t, h


# ---------------------------------------------------------------- costs

class Costs:
    """Present (switch off) and base costs of a pair, and what Miolingo's tables say about it."""

    def __init__(self):
        saved = os.environ.get("NEOLINGO_EQUIV")
        os.environ["NEOLINGO_EQUIV"] = "0"
        try:
            from host.engine_config import build_costs
            self.table = json.loads((paths.DATA / "cost_table.json").read_text("utf-8"))
            self.entries = build_costs(self.table)
        finally:
            if saved is None:
                os.environ.pop("NEOLINGO_EQUIV", None)
            else:
                os.environ["NEOLINGO_EQUIV"] = saved
        P, C = self.table["phones"], self.table["cost"]
        self.ix = {p: i for i, p in enumerate(P)}
        self.C = C
        self.over = {(e["lang"], e["target"], e["heard"]): e["cost"] for e in self.entries if "lang" in e}

    def base(self, t, h):
        if t in self.ix and h in self.ix:
            return self.C[self.ix[t]][self.ix[h]]
        return None

    def present(self, lang, t, h):
        if (lang, t, h) in self.over:
            return self.over[(lang, t, h)]
        b = self.base(t, h)
        return self.table["unknown_cost"] if b is None else b

    def status(self, lang, t, h):
        L = self.table["langs"][lang]
        if [t, h] in L["tolerated"] or [h, t] in L["tolerated"]:
            return "tolerated (cost 0)"
        w = L["accept"].get(t, {}).get(h)
        if w is not None:
            return f"accept {w / 1000:.1f}"
        if t in L["unreliable"]:
            return "unreliable target"
        return "no"


# ---------------------------------------------------------------- evidence

def collect(rows, lines):
    """-> ref[lang][(t,h)][voice] = (count, set of phrases);  own[lang][(t,h)] = (count, set of phrases)"""
    ref = {l: collections.defaultdict(lambda: {v: [0, set()] for v in VOICES}) for l in LANGS}
    own = {l: collections.defaultdict(lambda: [0, set()]) for l in LANGS}
    for r in rows:
        if not r.get("checked"):
            continue
        for p in subs(r["columns"]):
            d = ref[r["lang"]][p][r["engine"]]
            d[0] += 1
            d[1].add(r["text"])
    for l in lines:
        if not l.get("columns"):
            continue
        lang = LANG_OF.get(l["variant"])
        for p in subs(l["columns"]):
            d = own[lang][p]
            d[0] += 1
            d[1].add(l["text"])
    return ref, own


def judge_pair(lang, p, v, costs):
    """-> (included, list of failed criteria)"""
    fails = []
    for voice in VOICES:
        if v[voice][0] == 0:
            fails.append(f"not produced by {voice}")
    phr = set().union(*[v[x][1] for x in VOICES])
    if len(phr) < MIN_PHRASES:
        fails.append(f"{len(phr)} phrase{'s' if len(phr) != 1 else ''} (< {MIN_PHRASES})")
    b = costs.base(*p)
    if b is None:
        fails.append("a sound is not in the cost table")
    elif b > BOUND:
        fails.append(f"feature distance {b} > {BOUND}")
    return not fails, fails


def evidence(write_data=True):
    rows, lines = sweep_rows(), live_checks()
    costs = Costs()
    ref, own = collect(rows, lines)
    n_rows = collections.Counter((r["lang"], r["engine"]) for r in rows if r.get("checked"))
    md = [f"# Symbol pairs, target -> heard   ({time.strftime('%Y-%m-%d %H:%M')})", "",
          "SYNTHETIC reference voices (gtts = Google, say = macOS) from var/sweep/results.jsonl; `owner` = the owner's own live takes "
          f"in var/archive/checks.jsonl that carry aligned columns ({sum(1 for l in lines if l.get('columns'))} takes, "
          f"{collections.Counter(LANG_OF.get(l['variant']) for l in lines if l.get('columns'))}).",
          "Only substitutions (target sound and heard sound both present and different) are counted.  `base` = panphon feature "
          "distance in thousandths; `present` = the cost the app uses today (after Miolingo's tolerated / accept / unreliable entries).",
          f"Rule: both voices, >= {MIN_PHRASES} distinct phrases, base <= {BOUND}.  The owner column is NOT evidence for inclusion.", ""]
    doc = {"rule": None, "languages": {}}
    for lang in LANGS:
        md += [f"## {lang}   ({', '.join(f'{v}: {n_rows[(lang, v)]} phrases' for v in VOICES)})", "",
               "| target -> heard | gtts | say | phrases | base | present | Miolingo tables | owner n (phrases) | rule |",
               "|---|---|---|---|---|---|---|---|---|"]
        keys = set(ref[lang]) | set(own[lang])
        def total(p):
            return sum(ref[lang][p][v][0] for v in VOICES) if p in ref[lang] else 0
        included, notinc = [], []
        for p in sorted(keys, key=lambda p: (-total(p), -(own[lang][p][0] if p in own[lang] else 0), p)):
            v = ref[lang][p] if p in ref[lang] else {x: [0, set()] for x in VOICES}
            o = own[lang][p] if p in own[lang] else [0, set()]
            phr = set().union(*[v[x][1] for x in VOICES])
            ok, fails = judge_pair(lang, p, v, costs)
            b, pc, st = costs.base(*p), costs.present(lang, *p), costs.status(lang, *p)
            md.append(f"| {p[0]} -> {p[1]} | {v['gtts'][0]} | {v['say'][0]} | {len(phr)} | {b} | {pc} | {st} | "
                      f"{o[0]} ({len(o[1])}) | {'INCLUDED' if ok else 'no: ' + '; '.join(fails)} |")
            ent = {"target": p[0], "heard": p[1], "reference_counts": {x: v[x][0] for x in VOICES},
                   "phrases": len(phr), "owner": {"count": o[0], "phrases": len(o[1])},
                   "cost_base": b, "cost_present": pc, "miolingo_tables": st}
            if ok:
                ent["reason"] = (f"produced by both reference voices (gtts {v['gtts'][0]}, say {v['say'][0]}) in {len(phr)} phrases; "
                                 f"feature distance {b} <= {BOUND}" + ("; already tolerated, no change in cost" if pc == 0 else "")
                                 + ("; the owner also produces it" if o[0] else "; the owner has not produced it in his takes"))
                included.append(ent)
            elif total(p) >= 2:
                ent["fails"] = fails
                ent["reason"] = "fails the rule: " + "; ".join(fails) + (
                    f"; the owner also produces it ({o[0]})" if o[0] else "")
                notinc.append(ent)
        md.append("")
        doc["languages"][lang] = {"included": included, "not_included_for_owner_to_decide": notinc}
    # the sound check's warnings, (sound, sounded like): are any of them equivalent pairs (what the switch would drop)?
    md += ["## Warnings of the sound check, (sound -> sounded like; None = left out)", "",
           "Counted over the same sweep rows and the owner's live takes; `in file` = the pair is in `included` above (the switch would drop it).", ""]
    for lang in LANGS:
        eq = {(e["target"], e["heard"]) for e in doc["languages"][lang]["included"]}
        wc = collections.defaultdict(lambda: {"gtts": 0, "say": 0, "own": 0, "ph": set()})
        for r in rows:
            if r["lang"] == lang and r.get("checked"):
                for f in r["flags"] or []:
                    k = (nfc(f["sound"]), nfc(f["heardAs"]))
                    wc[k][r["engine"]] += 1
                    wc[k]["ph"].add(r["text"])
        for l in lines:
            if LANG_OF.get(l["variant"]) == lang:
                for f in l.get("flags") or []:
                    wc[(nfc(f["sound"]), nfc(f["heardAs"]))]["own"] += 1
        md += [f"### {lang}: {sum(v['gtts'] + v['say'] for v in wc.values())} warnings on the reference voices, "
               f"{sum(1 for k in wc if k in eq)} distinct pairs in the file", "",
               "| sound -> like | gtts | say | phrases | owner | in file |", "|---|---|---|---|---|---|"]
        for k, v in sorted(wc.items(), key=lambda kv: -(kv[1]["gtts"] + kv[1]["say"] + kv[1]["own"]))[:15]:
            md.append(f"| {k[0]} -> {k[1]} | {v['gtts']} | {v['say']} | {len(v['ph'])} | {v['own']} | {'yes' if k in eq else 'no'} |")
        md.append("")
    doc["rule"] = (f"A pair (target sound -> sound heard) is included for a language when (1) BOTH reference voices (gtts, say) "
                   f"produced it in the sweep, (2) it occurs in at least {MIN_PHRASES} distinct phrases over both voices, and (3) the two "
                   f"sounds differ in panphon features by at most {BOUND} thousandths (cost = round(1000 * sum|f_i(a) - f_i(b)| / 48) over "
                   f"the 24 features of data/cost_table.json; 42 = one feature differing fully, 83 = two; a->ae is 42, a->I is 167; a sound "
                   f"missing from the table fails).  Nothing else decides inclusion.  The owner's own takes are counted in a separate column "
                   f"and are never evidence for inclusion (they may be his accent).  Direction is target -> heard; a reverse pair is included "
                   f"only if its own counts pass.  'not_included_for_owner_to_decide' lists pairs with >= 2 occurrences that fail the rule, "
                   f"with the criterion failed.  The voices are synthetic.  Regenerate: tests/symbol_study.py evidence.")
    doc = {"generated": time.strftime("%Y-%m-%d"), "script": "tests/symbol_study.py evidence", "rule": doc["rule"],
           "bound": {"measure": "panphon feature distance, thousandths", "max": BOUND, "min_phrases": MIN_PHRASES, "voices": list(VOICES)},
           "sweep": {f"{l}/{v}": n_rows[(l, v)] for l in LANGS for v in VOICES},
           "owner_takes_with_columns": sum(1 for l in lines if l.get("columns")),
           "languages": doc["languages"]}
    STUDY.mkdir(parents=True, exist_ok=True)
    (STUDY / "symbol_pairs.md").write_text("\n".join(md) + "\n", "utf-8")
    print("\n".join(md))
    if write_data:
        EQUIV_FILE.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", "utf-8")
        print(f"\nwrote {EQUIV_FILE}")
    for lang in LANGS:
        L = doc["languages"][lang]
        print(f"{lang}: {len(L['included'])} included, {len(L['not_included_for_owner_to_decide'])} for the owner")


# ---------------------------------------------------------------- measure

def bucket(s):
    return "100" if s == 100 else "95-99" if s >= 95 else "90-94" if s >= 90 else "<90"


def pick_wrong(rows, lang, n=10):
    """(i, j) pairs: 10 phrases spread over the list, each with another phrase of the nearest text length."""
    g = {r["text"]: r for r in rows if r["lang"] == lang and r["engine"] == "gtts" and r["audible"]}
    texts = [json.loads((paths.DATA / f"{lang}.json").read_text("utf-8"))["phrases"][i]["text"]
             for i in range(0, 48, max(1, 48 // n))][:n]
    allt = [t for t in g]
    out = []
    for t in texts:
        c = sorted((u for u in allt if u != t), key=lambda u: (abs(len(u) - len(t)), allt.index(u)))
        out.append((t, c[0], g[c[0]]["wav"]))
    return out


def measure():
    import replay_archive as ra
    from host import archive
    import env
    from host.engine_config import build_config

    memo_h, memo_s = {}, {}
    oh, os_ = env.hear, env.sounds
    def hear(w, v):
        k = (w, v)
        if k not in memo_h:
            memo_h[k] = oh(w, v)
        return copy.deepcopy(memo_h[k])
    def sounds(w, t, v):
        k = (w, json.dumps(t), v)
        if k not in memo_s:
            memo_s[k] = os_(w, t, v)
        return copy.deepcopy(memo_s[k])
    env.hear, env.sounds = hear, sounds

    rows = sweep_rows()
    js = archive.judgements()
    lines = all_checks()
    engines = {}
    for label, val in (("off", "0"), ("on", "1")):
        os.environ["NEOLINGO_EQUIV"] = val
        e = ra.Engine(build_config())
        e.env = ra.ArchiveEnvironment()
        engines[label] = e
    assert len(engines["on"].config["costs"]) > len(engines["off"].config["costs"]), "the switch changes nothing"
    print("config entries off/on:", len(engines["off"].config["costs"]), len(engines["on"].config["costs"]), flush=True)

    def both(item):
        out = {}
        for label in ("off", "on"):
            os.environ["NEOLINGO_EQUIV"] = "1" if label == "on" else "0"
            e = engines[label]
            before = e.env.flags_equiv_dropped
            try:
                r = ra.replay_one(e, None, item)
            except Exception as ex:
                r = {"error": f"{type(ex).__name__}: {ex}"}
                try:
                    e.restart()
                except Exception:
                    pass
            r["equiv_dropped"] = e.env.flags_equiv_dropped - before
            out[label] = {k: r.get(k) for k in ("audible", "checked", "score", "understood", "flags", "flagLines", "error", "equiv_dropped")}
        return out

    res = {"sweep": [], "archive": [], "wrong": [], "made": time.strftime("%Y-%m-%d %H:%M")}
    t0 = time.time()
    for i, r in enumerate(rows):
        if not (r["audible"] and r["checked"]):
            continue
        token = f"m{r['engine']}{r['lang']}{i}"
        ra.ArchiveEnvironment.extra[token] = paths.VAR / r["wav"]
        res["sweep"].append({"lang": r["lang"], "engine": r["engine"], "text": r["text"], "recorded_score": r["score"],
                             **both({"variant": r["variant"], "text": r["text"], "take": token})})
        if len(res["sweep"]) % 20 == 0:
            print(f"sweep {len(res['sweep'])} ({time.time() - t0:.0f} s)", flush=True)
    for l in lines:
        v = (js.get(l["take"]) or {}).get("verdict") or "unjudged"
        res["archive"].append({"take": l["take"], "variant": l["variant"], "text": l["text"], "verdict": v,
                               "reconstructed": bool(l.get("reconstructed")), "recorded_score": l.get("score"),
                               "recorded_flags": len(l.get("flags") or []), **both(l)})
    print(f"archive {len(res['archive'])} ({time.time() - t0:.0f} s)", flush=True)
    for lang in LANGS:
        for k, (t, other, wav) in enumerate(pick_wrong(rows, lang)):
            token = f"mwrong{lang}{k}"
            ra.ArchiveEnvironment.extra[token] = paths.VAR / wav
            res["wrong"].append({"lang": lang, "text": t, "voice_said": other, **both({"variant": VARIANT[lang], "text": t, "take": token})})
    print(f"wrong references {len(res['wrong'])} ({time.time() - t0:.0f} s)", flush=True)
    STUDY.mkdir(parents=True, exist_ok=True)
    (STUDY / "measure.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), "utf-8")
    for e in engines.values():
        e.proc.terminate()
    render(res)


def nflags(x):
    return len(x.get("flags") or [])


def render(res):
    w = []
    P = lambda *a: w.append(" ".join(str(x) for x in a))
    P(f"# Measurement, switch off / on   ({res['made']})  -- SYNTHETIC voices for 4a and 4c\n")
    P("## 4a  Sweep (scores as replayed now; `rec` = score recorded in results.jsonl)\n")
    P("| lang voice | n | 100 off>on | 95-99 | 90-94 | <90 | warnings | takes with warnings | not understood | dropped by equiv |")
    P("|---|---|---|---|---|---|---|---|---|---|")
    for lang in LANGS:
        for v in VOICES:
            g = [r for r in res["sweep"] if r["lang"] == lang and r["engine"] == v]
            if not g:
                continue
            def cnt(side, b):
                return sum(bucket(r[side]["score"]) == b for r in g if r[side]["score"] is not None)
            cells = [f"{cnt('off', b)} > {cnt('on', b)}" for b in ("100", "95-99", "90-94", "<90")]
            wa = lambda s: sum(nflags(r[s]) for r in g)
            wt = lambda s: sum(nflags(r[s]) > 0 for r in g)
            nu = lambda s: sum(r[s]["understood"] is False for r in g)
            P(f"| {lang} {v} | {len(g)} | " + " | ".join(cells) + f" | {wa('off')} > {wa('on')} | {wt('off')} > {wt('on')} | "
              f"{nu('off')} > {nu('on')} | {sum(r['on']['equiv_dropped'] for r in g)} |")
    ch = [r for r in res["sweep"] if r["off"]["score"] != r["on"]["score"]]
    P(f"\nsweep phrases whose score changed: {len(ch)} of {len(res['sweep'])}; "
      f"mean score change {sum(r['on']['score'] - r['off']['score'] for r in res['sweep']) / max(1, len(res['sweep'])):+.2f}; "
      f"any lower: {sum(r['on']['score'] < r['off']['score'] for r in res['sweep'])}")
    P("\n## 4b  Owner's archive (every line of checks.jsonl, replayed now)\n")
    P("| phrase | variant | judgement | recorded | score off > on | warnings off > on |")
    P("|---|---|---|---|---|---|")
    order = {"harsh": 0, "generous": 1, "fair": 2, "unjudged": 3}
    A = sorted(res["archive"], key=lambda r: (order[r["verdict"]], r["text"]))
    for r in A:
        if r["verdict"] == "unjudged":
            continue
        P(f"| {r['text']} | {r['variant']} | {r['verdict']} | {r['recorded_score']} | {r['off']['score']} > {r['on']['score']} | "
          f"{nflags(r['off'])} > {nflags(r['on'])} |")
    P("\nBy judgement (judged takes):\n")
    P("| judgement | n | score higher | same | lower | warnings fewer | same | more | mean score change |")
    P("|---|---|---|---|---|---|---|---|---|")
    for vd in ("harsh", "fair", "generous"):
        g = [r for r in res["archive"] if r["verdict"] == vd and r["off"]["score"] is not None and r["on"]["score"] is not None]
        if g:
            d = [r["on"]["score"] - r["off"]["score"] for r in g]
            wd = [nflags(r["on"]) - nflags(r["off"]) for r in g]
            P(f"| {vd} | {len(g)} | {sum(x > 0 for x in d)} | {sum(x == 0 for x in d)} | {sum(x < 0 for x in d)} | "
              f"{sum(x < 0 for x in wd)} | {sum(x == 0 for x in wd)} | {sum(x > 0 for x in wd)} | {sum(d) / len(d):+.2f} |")
    g = [r for r in res["archive"] if r["off"]["score"] is not None and r["on"]["score"] is not None]
    P(f"\nall {len(res['archive'])} archived lines ({sum(r['reconstructed'] for r in res['archive'])} reconstructed): "
      f"score changed {sum(r['on']['score'] != r['off']['score'] for r in g)}, warnings changed "
      f"{sum(nflags(r['on']) != nflags(r['off']) for r in g)}, warnings dropped by equiv {sum(r['on']['equiv_dropped'] for r in g)}; "
      f"replayed-off score differs from the recorded one in {sum(r['off']['score'] != r['recorded_score'] for r in g)}")
    P("\n## 4c  Wrong references (the voice says another phrase of similar length; gtts)\n")
    P("| lang | target phrase | voice said | score off > on | warnings off > on |")
    P("|---|---|---|---|---|")
    for r in res["wrong"]:
        P(f"| {r['lang']} | {r['text']} | {r['voice_said']} | {r['off']['score']} > {r['on']['score']} | {nflags(r['off'])} > {nflags(r['on'])} |")
    for lang in LANGS:
        g = [r for r in res["wrong"] if r["lang"] == lang and r["off"]["score"] is not None and r["on"]["score"] is not None]
        if g:
            P(f"\n{lang}: mean score off {sum(r['off']['score'] for r in g) / len(g):.1f}, on {sum(r['on']['score'] for r in g) / len(g):.1f}; "
              f"max off {max(r['off']['score'] for r in g)}, on {max(r['on']['score'] for r in g)}; "
              f"changed {sum(r['on']['score'] != r['off']['score'] for r in g)} of {len(g)}")
    STUDY.mkdir(parents=True, exist_ok=True)
    (STUDY / "measure.md").write_text("\n".join(w) + "\n", "utf-8")
    print("\n".join(w))


# ---------------------------------------------------------------- floor and targets

def voiced(path):
    """(voiced seconds as env.audible counts them, duration, peak) of a WAV."""
    import numpy as np
    import soundfile as sf
    from env import audio_level as al
    data, sr = sf.read(str(path), dtype="float32", always_2d=True)
    x = data.mean(axis=1)
    n = int(al.FRAME * sr)
    if len(x) < n:
        return 0.0, len(x) / sr, float(abs(x).max()) if x.size else 0.0
    fr = x[: (len(x) // n) * n].reshape(-1, n)
    rms = np.sqrt((fr ** 2).mean(axis=1))
    thr = max(al.ABS_FLOOR_RMS, al.REL_RMS * float(np.percentile(rms, 95)))
    return int((rms > thr).sum()) * al.FRAME, len(x) / sr, float(abs(x).max())


def floor():
    import numpy as np
    import soundfile as sf
    import env
    from env import audio_level as al
    print(f"env.audible now: MIN_VOICED_SECONDS {al.MIN_VOICED_SECONDS}, ABS_FLOOR_RMS {al.ABS_FLOOR_RMS}, REL_RMS {al.REL_RMS:.3f}, FRAME {al.FRAME}")
    sr = 16000
    synth = {"silence": np.zeros(sr * 2, dtype="float32"),
             "hiss": (np.random.RandomState(0).randn(sr * 2) * 0.0005).astype("float32"),
             "click": np.r_[np.zeros(sr), [0.5], np.zeros(sr)].astype("float32")}
    import tempfile
    d = Path(tempfile.mkdtemp())
    print("\nthe cases of tests/check_env.py (must stay refused):")
    for k, x in synth.items():
        sf.write(d / f"{k}.wav", x, sr)
        v = voiced(d / f"{k}.wav")
        print(f"  {k:8} voiced {v[0]:.2f} s  audible={env.audible(str(d / f'{k}.wav'))}")
    print("\nsweep, refused as not audible, and the shortest accepted (one-word phrases first):")
    rows = sweep_rows()
    items = []
    for r in rows:
        p = paths.VAR / r["wav"]
        if p.exists():
            v = voiced(p)
            items.append((v[0], v[1], v[2], r["audible"], r["lang"], r["engine"], r["text"]))
    for it in sorted(items)[:25]:
        print(f"  voiced {it[0]:.2f} s  of {it[1]:.2f} s  peak {it[2]:.2f}  audible={it[3]}  {it[4]} {it[5]} {it[6]!r}")
    print(f"  ({sum(not i[3] for i in items)} refused of {len(items)})")
    print("\nthe owner's takes (records.jsonl: step = pressed Check on it):")
    recs = {r["take"]: r for r in jl(paths.ARCHIVE / "records.jsonl")}
    chk = {l["take"]: l for l in all_checks()}
    mine = []
    for p in sorted((paths.ARCHIVE_TAKES).glob("*.wav")):
        v = voiced(p)
        tk = p.stem
        mine.append((v[0], v[1], v[2], tk))
    for v in sorted(mine)[:12]:
        tk = v[3]
        print(f"  voiced {v[0]:.2f} s  of {v[1]:.2f} s  peak {v[2]:.2f}  audible={env.audible(str(paths.ARCHIVE_TAKES / (tk + '.wav')))}  "
              f"record={recs.get(tk, {}).get('audible')}  phrase={chk.get(tk, {}).get('text')!r}")
    print(f"  ({len(mine)} takes)")


def targets():
    rows = [r for r in sweep_rows() if r.get("checked")]
    by = collections.defaultdict(dict)
    for r in rows:
        by[(r["lang"], r["text"])][r["engine"]] = r
    def sim(a, b):
        import difflib
        return difflib.SequenceMatcher(None, a, b).ratio()
    print("Phrases scoring under 90 with BOTH voices (target may be wrong): lang, phrase, target, gtts heard, say heard, similarity of the two heard\n")
    for lang in LANGS:
        for (l, t), d in by.items():
            if l != lang or not all(v in d for v in VOICES):
                continue
            if all(d[v]["score"] < 90 for v in VOICES):
                a, b = "".join(d["gtts"]["heard_flat"]), "".join(d["say"]["heard_flat"])
                print(f"{lang} {t!r}  scores {d['gtts']['score']}/{d['say']['score']}\n    target [{''.join(d['gtts']['target_flat'])}]\n"
                      f"    gtts   [{a}]  {d['gtts']['heard_text']!r}\n    say    [{b}]  {d['say']['heard_text']!r}\n    heard-vs-heard {sim(a, b):.2f}"
                      f"   target-vs-gtts {sim(''.join(d['gtts']['target_flat']), a):.2f}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("what", choices=["evidence", "measure", "floor", "targets"])
    ap.add_argument("--no-data", action="store_true", help="evidence: do not rewrite data/symbol_equivalents.json")
    a = ap.parse_args()
    if a.what == "evidence":
        evidence(not a.no_data)
    elif a.what == "measure":
        measure()
    elif a.what == "floor":
        floor()
    else:
        targets()


if __name__ == "__main__":
    main()
