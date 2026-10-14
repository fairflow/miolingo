"""Render var/lab/results/metrics.json as tables.

    <python> -m lab.report        -> var/lab/report.md (full tables + the per-take listing of the learner takes)
                                     lab/RESULTS.md     (aggregate tables, method, caveats, commands; no per-take data)

The per-take listing quotes phrases and sounds, never the owner's notes (they are not loaded anywhere in the lab)."""
from __future__ import annotations

import json
import time

from . import recommend as R
from .common import LAB, LANGS, ROOT
from .run import RES, load_rows

VOICE_NAME = {"gtts": "Google", "say": "compact Mac", "premium": "Premium Mac"}
LANG_NAME = {"en": "English", "fr": "French", "de": "German"}


def pct(x):
    return "–" if x is None else f"{100 * x:.0f}%"


def pct1(x):
    return "–" if x is None else f"{100 * x:.1f}%"


def num(x, d=1):
    return "–" if x is None else f"{x:.{d}f}"


def order(metrics):
    names = list(metrics)
    first = ["baseline"]
    return first + [n for n in names if n not in first]


def table(head, rows):
    out = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def short_model(m):
    return {"facebook/wav2vec2-xlsr-53-espeak-cv-ft": "xlsr-53", "facebook/wav2vec2-lv-60-espeak-cv-ft": "lv-60",
            "Cnam-LMSSC/wav2vec2-french-phonemizer": "Cnam"}.get(m, m)


def reference_table(M, lang, names):
    head = ["variant"] + [f"{VOICE_NAME[v]} {c}" for v in ("gtts", "say", "premium") for c in ("=100", "≥95", "<90", "diff")]
    rows = []
    for n in names:
        r = M[n]["reference"][lang]
        cells = [n]
        for v in ("gtts", "say", "premium"):
            b = r[v]
            if not b["n"]:
                cells += ["–"] * 4
                continue
            cells += [pct(b["at100"]), pct(b["ge95"]), pct(b["lt90"]), num(b["diff"], 2) if n != "E-check score" else "–"]
        rows.append(cells)
    return table(head, rows)


def nearmiss_table(M, lang, names):
    head = ["variant", "n", "detected at the place", "below 100", "mean score", "false elsewhere",
            "detected, sound judged", "detected, sound unjudged (n)", "positives below 100", "positives mean", "positives diff"]
    rows = []
    for n in names:
        b = M[n]["nearmiss"][lang]
        p = M[n]["positive"][lang]["all"]
        det = "check_detected" if n == "E-check score" else "detected"
        u = b["unreliable"]
        rows.append([n, b["all"]["n"], pct(b["all"][det]), pct(b["all"]["below100"]), num(b["all"]["mean"]),
                     num(b["all"]["false"], 2) if n != "E-check score" else "–", pct(b["judged"][det]),
                     f"{pct(u[det])} ({u['n']})" if u["n"] else "–",
                     pct(1 - p["at100"]) if p["at100"] is not None else "–", num(p["mean"]),
                     num(p["diff"], 2) if n != "E-check score" else "–"])
    return table(head, rows)


def nearmiss_voice_table(M, lang, names):
    head = ["variant"] + [f"{VOICE_NAME[v]} {c}" for v in ("gtts", "say", "premium") for c in ("detected", "below 100", "pos. below 100")]
    rows = []
    for n in names:
        b = M[n]["nearmiss"][lang]
        det = "check_detected" if n == "E-check score" else "detected"
        cells = [n]
        for v in ("gtts", "say", "premium"):
            p = M[n]["positive"][lang][v]
            cells += [pct(b[v][det]), pct(b[v]["below100"]),
                      pct(1 - p["at100"]) if p["at100"] is not None else "–"]
        rows.append(cells)
    return table(head, rows)


def native_table(M, lang, names):
    head = ["variant", "n", "=100", "≥95", "<90", "mean score", "diff", "roles reversed: n", "detected", "false elsewhere"]
    rows = []
    for n in names:
        b = M[n]["cp"][lang]
        f = M[n]["cpflip"][lang]
        det = "check_detected" if n == "E-check score" else "detected"
        rows.append([n, b["n"], pct(b["at100"]), pct(b["ge95"]), pct(b["lt90"]), num(b["mean"]),
                     num(b["diff"], 2) if n != "E-check score" else "–", f["n"] or "–", pct(f[det]) if f["n"] else "–",
                     num(f["false"], 2) if f["n"] and n != "E-check score" else "–"])
    return table(head, rows)


def archive_table(M, scope, names):
    head = ["variant", "fair: n", "mean", "diff", "changed", "harsh: n", "mean", "diff", "fewer diff", "more diff",
            "generous: n", "mean", "diff", "unjudged: n", "mean", "diff"]
    rows = []
    for n in names:
        a = M[n]["archive"][scope]
        f, h, g, u = a["fair"], a["harsh"], a["generous"], a["unjudged"]
        e = n == "E-check score"
        rows.append([n, f["n"], num(f["mean"]), "–" if e else num(f["diff"], 2), "–" if e else f.get("changed", "–"),
                     h["n"], num(h["mean"]), "–" if e else num(h["diff"], 2), "–" if e else h.get("fewer_diff", "–"),
                     "–" if e else h.get("more_diff", "–"),
                     g["n"], num(g["mean"]), "–" if e else num(g["diff"], 2), u["n"], num(u["mean"]), "–" if e else num(u["diff"], 2)])
    return table(head, rows)


def understood_table(M, names):
    head = ["variant"] + [f"{LANG_NAME[l]} {c}" for l in LANGS for c in ("reference", "positives", "archive", "INFLATION")]
    rows = []
    for n in names:
        cells = [n]
        for l in LANGS:
            u = M[n]["understood"][l]
            cells += [pct(u["reference"]["rate"]), pct(u["positive"]["rate"]), pct(u["archive"]["rate"]),
                      pct(u["nearmiss_inflation"]["rate"])]
        rows.append(cells)
    return table(head, rows)


def tau_table(M, lang):
    names = ["baseline"] + [n for n in M if n.startswith("A-V4 tau=")]
    head = ["τ", "near miss detected", "near miss below 100", "false elsewhere", "positives below 100",
            "reference diff (G/M/P)", "native diff", "roles reversed detected", "harsh: fewer diff", "fair: changed"]
    rows = []
    for n in names:
        b = M[n]
        r = b["reference"][lang]
        rows.append([("greedy (baseline)" if n == "baseline" else n.split("=")[1]),
                     pct(b["nearmiss"][lang]["all"]["detected"]), pct(b["nearmiss"][lang]["all"]["below100"]),
                     num(b["nearmiss"][lang]["all"]["false"], 2),
                     pct(1 - b["positive"][lang]["all"]["at100"]) if b["positive"][lang]["all"]["at100"] is not None else "–",
                     "/".join(num(r[v]["diff"], 2) for v in ("gtts", "say", "premium")),
                     num(b["cp"][lang]["diff"], 2), pct(b["cpflip"][lang]["detected"]) if b["cpflip"][lang]["n"] else "–",
                     b["archive"][lang]["harsh"].get("fewer_diff", "–"), b["archive"][lang]["fair"].get("changed", "–")])
    return table(head, rows)


def single_names(M):
    return [n for n in order(M) if not n.startswith("combo") and not n.startswith("A-V4 tau=")
            and not n.startswith("D-")] + ["A-V4 tau=0", "A-V4 tau=2"]


def scoring_names(M):
    return [n for n in single_names(M) if n in M]


def combo_names(M):
    return ["baseline"] + [n for n in M if n.startswith("combo")]


def d_names(M):
    return ["baseline"] + [n for n in M if n.startswith("D-")]


def per_take_listing(names_show):
    """Learner takes: phrase, verdict, the baseline and the recommended analysis (per language)."""
    base = {r["id"]: r for r in load_rows("baseline") if r["set"] == "archive" and r["voice"] == "learner"}
    recs = {}
    for lang in LANGS:
        nm = R.RECOMMENDED[lang]
        for r in load_rows(nm):
            if r["set"] == "archive" and r["voice"] == "learner" and r["lang"] == lang:
                recs[r["id"]] = (nm, r)
    from .datasets import archive_items
    meta = {i["id"]: i for i in archive_items()}
    out = ["| take | learner | variant | phrase | verdict | baseline score | diff | heard (baseline) | recommended score | diff | heard (recommended) |",
           "|---|---|---|---|---|---|---|---|---|---|---|"]

    def heard(r):
        return " ".join(("+" + h) if t is None else ("−" + t) if h is None else (h if h == t else f"{h}≠{t}" if k in ("near", "off") else f"({h})")
                        for (t, h, k) in r["cols"])
    ids = sorted(base, key=lambda i: (meta[i]["variant"], meta[i]["time"] or ""))
    for i in ids:
        b = base[i]
        nm, r = recs.get(i, (None, None))
        out.append(f"| `{i}` | {meta[i]['uid']} | {meta[i]['variant']} | {meta[i]['text']} | {b['verdict']} | {b['score']} | {b['nd']} | "
                   f"{heard(b)} | {r['score'] if r else '–'} | {r['nd'] if r else '–'} | {heard(r) if r else '–'} |")
    return "\n".join(out)


def native_error_table() -> str:
    try:
        ne = json.loads((RES / "native_error.json").read_text("utf-8"))
    except (OSError, ValueError):
        return ""
    out = ["## C: the phone models' free reading against espeak (no rule applied)\n",
           "Weighted error = d / (1000 × max(m, n)) with the live costs (1 − Miolingo's weighted similarity, linear "
           "normalisation); PER = unweighted edit distance / target length.  Mean over utterances.  The priors "
           "(Common Phone natives, Miolingo): German xlsr-53 0.043, lv-60 0.114; French Cnam 0.013, lv-60 0.072.\n",
           "| language | model | natives n | natives weighted error | natives PER | Google | compact Mac | Premium Mac |",
           "|---|---|---|---|---|---|---|---|"]
    for lang in ("de", "en", "fr"):
        for m, g in ne.get(lang, {}).items():
            nat = g.get("native (Common Phone)", {})
            refs = [g.get(f"reference {v}", {}).get("weighted_error") for v in ("Google", "compact Mac", "Premium Mac")]
            out.append(f"| {LANG_NAME[lang]} | {short_model(m)} | {nat.get('n')} | {num(nat.get('weighted_error'), 3)} | "
                       f"{pct1(nat.get('per'))} | " + " | ".join(num(x, 3) for x in refs) + " |")
    return "\n".join(out) + "\n"


def build(full: bool) -> str:
    M = json.loads((RES / "metrics.json").read_text("utf-8"))
    w = []
    stamp = time.strftime("%Y-%m-%d %H:%M %Z")
    if full:
        w.append(f"# Neolingo lab: full report ({stamp})\n")
        w.append("Generated by `lab/report.py` from `var/lab/results/metrics.json` and the rows under `var/lab/results/rows/`. "
                 "Definitions, method, caveats and commands: `lab/RESULTS.md`.  This file is under `var/` (git-ignored): "
                 "it lists the learner takes by phrase; it never contains the owner's notes.\n")
    else:
        w.append(f"# Neolingo lab: results ({stamp})\n")
        w.append(R.INTRO)
    w.append(R.recommendation(M))
    w.append(R.validation_summary())
    w.append("\n## Headline\n")
    w.append(R.headline(M))
    sn = scoring_names(M)
    cn = combo_names(M)
    if not full:                     # RESULTS.md: the single changes and the combinations that matter
        sn = [n for n in sn if n in M]
        cn = ["baseline"] + [n for n in ("combo clean", "combo clean+V1", "combo clean+V2", "combo clean+V3",
                                         "combo clean+V4 tau=1", "combo clean+V4 tau=2", "combo clean+V2+ins tau=2",
                                         "combo clean+V2 keep deletions", "combo phoneme+lr2+zero+V2",
                                         "combo phoneme+lr2+zero+V2 keep deletions", "combo clean+V2 lv60",
                                         "combo phoneme+lr2+zero+V2 lv60", "rec de", "rec en", "rec fr") if n in M]
    else:
        cn = cn + [n for n in ("rec de", "rec en", "rec fr") if n in M and n not in cn]
    for lang in ("de", "en", "fr"):
        w.append(f"\n## {LANG_NAME[lang]}\n")
        w.append(f"\n### Reference phrases (48 a voice): share of phrases at 100, at 95 or more, under 90; mean sounds shown different\n")
        w.append(reference_table(M, lang, sn + [n for n in cn if n != "baseline"]))
        w.append(f"\n\n### Near misses (voice says B, target A; one edit) and their positives (voice says A)\n")
        w.append(nearmiss_table(M, lang, sn + [n for n in cn if n != "baseline"]))
        if full:
            w.append("\n\nBy voice:\n")
            w.append(nearmiss_voice_table(M, lang, sn + [n for n in cn if n != "baseline"]))
        w.append(f"\n\n### Native speech (Common Phone test speakers) and the roles-reversed proxy\n")
        w.append(native_table(M, lang, sn + [n for n in cn if n != "baseline"]))
        w.append(f"\n\n### Learner takes ({LANG_NAME[lang]}), by the owner's verdict\n")
        w.append(archive_table(M, lang, sn + [n for n in cn if n != "baseline"]))
        w.append(f"\n\n### V4: the likelihood-ratio threshold τ (keep an edit iff log P(edited target) − log P(target) ≥ τ)\n")
        w.append(tau_table(M, lang))
        w.append("\n")
    w.append("\n## Learner takes, all languages, by verdict\n")
    w.append(archive_table(M, "all", sn + [n for n in cn if n != "baseline"]))
    w.append("\n\n## D: understood (share of items taken as understood)\n")
    w.append("INFLATION = near misses (the voice said B, the target is A) taken as understood: it should be low.  "
             "Positives = the voice said the target word: it should be high.\n\n")
    w.append(understood_table(M, d_names(M)))
    w.append("\n\n" + R.voices_section(M))
    w.append("\n" + native_error_table())
    if not full:
        w.append("\n" + R.METHOD)
        w.append("\n" + R.CAVEATS)
        w.append("\n" + R.COMMANDS)
    else:
        w.append("\n\n## Missing items per variant (no cached log-probabilities for that model)\n")
        for n in order(M):
            if M[n].get("missing"):
                w.append(f"- {n}: {M[n]['missing']}")
        w.append("\n\n## Per take: learner takes, baseline against the recommended analysis\n")
        w.append("Heard: a sound alone = as the target; `h≠t` = heard h for target t (near/off); `(h)` = shown, costs "
                 "nothing or not judged; `−t` = target sound missing; `+h` = extra heard sound.\n\n")
        w.append(per_take_listing(None))
        w.append("\n\n" + R.CAVEATS)
    return "\n".join(w) + "\n"


def main():
    (LAB / "report.md").write_text(build(True), "utf-8")
    (ROOT / "lab" / "RESULTS.md").write_text(build(False), "utf-8")
    print("wrote", LAB / "report.md", "and", ROOT / "lab" / "RESULTS.md")


if __name__ == "__main__":
    main()
