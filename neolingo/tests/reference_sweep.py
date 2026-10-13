"""The reference sweep: the app checked against a reference voice, without the owner.

    <miolingo venv python> tests/reference_sweep.py [--engines gtts,say] [--langs en,fr,de] [--limit N]

Every phrase of data/{en,fr,de}.json is synthesised at normal speed by the host's own speech code
(host/speech.py: `gtts` = Google, the only network use; `say` = macOS; `espeak` also accepted), decoded with ffmpeg
to 16 kHz mono WAV under var/sweep/<engine>/<variant>/ (cached: a second run makes no network call), and run through
the same path as a learner's take: env.audible, env.hear, env.sounds and the engine (score, understood, aligned
columns, flag lines), in a scratch engine session (the same code as tests/replay_archive.py).
Writes var/sweep/results.jsonl (one line a phrase and engine) and var/sweep/report.txt, and prints the report.

These are SYNTHETIC voices.  The report measures how far the sources agree (target from espeak-ng, voice from
Google or `say`, recognisers), not how accurate the app is on learners: a phrase where the reference voice is not
understood or scores under 90 is a fault of the sources."""
import argparse
import collections
import hashlib
import io
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import replay_archive as ra                                  # noqa: E402  (sets the scratch log, offline models)
from replay_archive import paths, replay_one, ArchiveEnvironment, Engine, build_config, flat   # noqa: E402
from host import speech                                      # noqa: E402

FFMPEG = shutil.which("ffmpeg") or "/opt/local/bin/ffmpeg"
SWEEP = paths.VAR / "sweep"
LANGS = {"en": "en-gb", "fr": "fr-fr", "de": "de"}


def synth(engine, text, variant, tries=(0, 5, 20, 60)):
    """(wav path, seconds, error): speech decoded to 16 kHz mono WAV, cached by engine / variant / text."""
    key = hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]
    out = SWEEP / engine / variant / f"{key}.wav"
    if out.exists():
        return out, 0.0, None
    out.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    err = None
    for wait in (tries if engine == "gtts" else (0,)):
        time.sleep(wait)
        try:
            src, _ctype, used = speech.speak(text, variant, False, only=engine)
            break
        except Exception as e:
            err = f"{type(e).__name__}: {str(e)[:150]}"
    else:
        return None, time.perf_counter() - t0, err
    r = subprocess.run([FFMPEG, "-v", "error", "-y", "-i", str(src), "-ar", "16000", "-ac", "1", "-sample_fmt", "s16",
                        str(out)], capture_output=True, text=True)
    if r.returncode or not out.exists():
        return None, time.perf_counter() - t0, "ffmpeg: " + r.stderr[-150:]
    if engine == "gtts":
        time.sleep(0.4)              # be polite to the service
    return out, time.perf_counter() - t0, None


def pairs_of(columns):
    """(substitutions, left out, extra) Counters from aligned columns."""
    sub, out, extra = collections.Counter(), collections.Counter(), collections.Counter()
    for word in columns or []:
        for c in word:
            t, h = c["target"], c["heard"]
            if t == h:
                continue
            if t is not None and h is not None:
                sub[(t, h)] += 1
            elif t is not None:
                out[t] += 1
            else:
                extra[h] += 1
    return sub, out, extra


def report(rows, synth_fail, timing):
    w = io.StringIO()
    P = lambda *a: print(*a, file=w)
    P(f"Reference sweep, {time.strftime('%Y-%m-%d %H:%M')}.  SYNTHETIC voices only: the numbers measure how far the sources "
      f"(espeak-ng target, the reference voice, the recognisers) agree, not accuracy on learners.")
    groups = collections.defaultdict(list)
    for r in rows:
        groups[(r["lang"], r["engine"])].append(r)
    for (lang, eng), rs in sorted(groups.items()):
        P(f"\n{'=' * 78}\n{lang}  {eng}   ({len(rs)} phrases checked; synthesis failed for {synth_fail.get((lang, eng), 0)})")
        na = [r for r in rs if not r["audible"]]
        P(f"not audible: {len(na)}" + "".join(f"\n    {r['text']!r}" for r in na[:15]))
        ok = [r for r in rs if r["audible"] and r["checked"]]
        nu = [r for r in ok if not r["understood"]]
        P(f"not understood: {len(nu)} of {len(ok)}")
        for r in nu[:15]:
            P(f"    {r['text']!r}  heard {r['heard_text']!r}  (score {r['score']})")
        b = [sum(r["score"] == 100 for r in ok), sum(95 <= r["score"] <= 99 for r in ok),
             sum(90 <= r["score"] <= 94 for r in ok), sum(r["score"] < 90 for r in ok)]
        P(f"scores: 100: {b[0]}   95-99: {b[1]}   90-94: {b[2]}   below 90: {b[3]}")
        P("ten lowest:")
        for r in sorted(ok, key=lambda r: r["score"])[:10]:
            P(f"    {r['score']:3}  {r['text']!r}  understood={r['understood']}\n"
              f"         target [{''.join(r['target_flat'])}]\n         heard  [{''.join(r['heard_flat'])}]   text {r['heard_text']!r}")
        sub, left, extra = collections.Counter(), collections.Counter(), collections.Counter()
        warn = collections.defaultdict(lambda: [0, 0, collections.Counter()])
        for r in ok:
            s, o, e = pairs_of(r["columns"])
            sub.update(s); left.update(o); extra.update(e)
            for f in r["flags"] or []:
                x = warn[f["sound"]]
                x[0] += 1
                x[1] += bool(f["off"])
                x[2][f.get("heardAs")] += 1
        P("differing pairs, target -> heard (top 25):")
        for (t, h), n in sub.most_common(25):
            P(f"    {n:3}  [{t}] -> [{h}]")
        P("most often LEFT OUT: " + ", ".join(f"[{t}] {n}" for t, n in left.most_common(15)))
        P("most often EXTRA:    " + ", ".join(f"[{t}] {n}" for t, n in extra.most_common(15)))
        P(f"warnings (flags) on the reference voice, by target sound: {sum(x[0] for x in warn.values())} in all")
        for t, (n, off, ha) in sorted(warn.items(), key=lambda kv: -kv[1][0])[:25]:
            P(f"    [{t}] {n}  (probably off {off}; heard as " + ", ".join(f"{k if k else 'nothing'} {v}" for k, v in ha.most_common(4)) + ")")
    P(f"\n{'=' * 78}\ntimings (seconds)")
    for k, v in sorted(timing.items()):
        if v["n"]:
            P(f"    {k}: {v['n']} phrases; synthesis total {v['synth']:.1f} (cached ones 0); check mean {v['check'] / v['n']:.2f}, "
              f"max {v['max']:.2f}, total {v['check']:.0f}")
    return w.getvalue()


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--engines", default="gtts,say")
    ap.add_argument("--langs", default="en,fr,de")
    ap.add_argument("--limit", type=int, help="only the first N phrases of each language (for trying it out)")
    a = ap.parse_args()
    engines = a.engines.split(",")
    paths.make_dirs()
    SWEEP.mkdir(parents=True, exist_ok=True)
    eng = Engine(build_config())
    eng.env = ArchiveEnvironment()
    rows, synth_fail, timing = [], collections.Counter(), {}
    results = open(SWEEP / "results.jsonl", "w", encoding="utf-8")
    for engine in engines:
        dead = 0
        for lang in a.langs.split(","):
            variant = LANGS[lang]
            phrases = json.loads((paths.DATA / f"{lang}.json").read_text("utf-8"))["phrases"][:a.limit]
            tm = timing.setdefault(f"{lang} {engine}", {"n": 0, "synth": 0.0, "check": 0.0, "max": 0.0})
            for i, p in enumerate(phrases):
                text = p["text"]
                if dead >= 3:
                    synth_fail[(lang, engine)] += 1
                    continue
                wav, ts, err = synth(engine, text, variant)
                tm["synth"] += ts
                if wav is None:
                    synth_fail[(lang, engine)] += 1
                    dead += 1
                    print(f"[{engine} {lang} {i + 1}/{len(phrases)}] SYNTHESIS FAILED {text!r}: {err}", flush=True)
                    continue
                dead = 0
                token = f"s{engine}{lang}{i}"
                ArchiveEnvironment.extra[token] = wav
                t0 = time.perf_counter()
                new = replay_one(eng, None, {"variant": variant, "text": text, "take": token})
                dt = time.perf_counter() - t0
                tm["n"] += 1; tm["check"] += dt; tm["max"] = max(tm["max"], dt)
                hear = new.get("hear") or {}
                row = {"lang": lang, "variant": variant, "engine": engine, "text": text, "wav": str(wav.relative_to(paths.VAR)),
                       "audible": bool(new.get("audible")), "checked": bool(new.get("checked")), "seconds": round(dt, 2),
                       "heard_text": hear.get("text"), "heard_flat": flat(hear.get("ipa")),
                       "target_flat": [s for w in (new.get("target") or []) for s in w], "target": new.get("target"),
                       "score": new.get("score"), "understood": new.get("understood"), "banner": new.get("banner"),
                       "flagLines": new.get("flagLines"), "flags": new.get("flags"), "columns": new.get("columns"),
                       "droppedFlags": new.get("droppedFlags")}
                results.write(json.dumps(row, ensure_ascii=False) + "\n")
                results.flush()
                rows.append(row)
                print(f"[{engine} {lang} {i + 1}/{len(phrases)}] {row['score']} {'ok' if row['understood'] else 'NOT UNDERSTOOD'} "
                      f"{text!r} -> {row['heard_text']!r}", flush=True)
    results.close()
    text = report(rows, synth_fail, timing)
    (SWEEP / "report.txt").write_text(text, "utf-8")
    print("\n" + text)
    eng.proc.terminate()


if __name__ == "__main__":
    main()
