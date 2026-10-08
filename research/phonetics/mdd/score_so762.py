#!/usr/bin/env python3
"""
Score free phone transcriptions against speechocean762's expert phone labels: does the
recognizer hear what the LEARNER said, or what the text says?

Each hypothesis (IPA) is mapped to ARPAbet-39 and aligned to the canonical phone sequence
(weighted edit distance). Per canonical phone the model then "accepts" it (same phone),
"rejects" it (other phone or deleted). Expert labels (mean of 5 experts, 0..2):
  correct  acc >= 1.6     error  acc <= 1.0     (1.2-1.4 = disputed, reported separately)
Metrics:
  false rejection  : correct phones the model rejects            (lower = better)
  detection recall : error phones the model rejects               (higher = better)
  precision / F1   : of rejections, how many are expert errors
  diagnosis        : labelled substitutions (pronounced-phone is a real phone) where the
                     model's phone == what the learner said
  deletions        : labelled <DEL> where the model also has nothing

    venv/bin/python research/phonetics/mdd/score_so762.py /opt/mdd/zipa.jsonl /opt/mdd/xlsr.jsonl \
        --out research/phonetics/mdd/results/so762_test.json
"""
import argparse, collections, json, sys, unicodedata
from pathlib import Path

import pandas as pd

# --- IPA -> ARPAbet-39 -------------------------------------------------------------------
MULTI = {"tʃ": "CH", "dʒ": "JH", "eɪ": "EY", "aɪ": "AY", "aʊ": "AW", "oʊ": "OW", "əʊ": "OW",
         "ɔɪ": "OY", "ɜɹ": "ER", "əɹ": "ER", "ɚ": "ER", "ɝ": "ER", "ʧ": "CH", "ʤ": "JH"}
SINGLE = {"ɑ": "AA", "a": "AA", "ɒ": "AA", "æ": "AE", "ʌ": "AH", "ə": "AH", "ɐ": "AH", "ɔ": "AO",
          "ɛ": "EH", "e": "EY", "ɜ": "ER", "ɪ": "IH", "ɨ": "IH", "ᵻ": "IH", "i": "IY", "ʊ": "UH",
          "u": "UW", "ʉ": "UW", "o": "OW", "ɵ": "OW", "y": "IY", "ø": "EH", "œ": "EH", "ɯ": "UW",
          "b": "B", "d": "D", "ð": "DH", "f": "F", "ɡ": "G", "g": "G", "h": "HH", "ɦ": "HH",
          "k": "K", "l": "L", "ɫ": "L", "m": "M", "n": "N", "ŋ": "NG", "p": "P", "ɹ": "R",
          "r": "R", "ɻ": "R", "ʁ": "R", "s": "S", "ʃ": "SH", "t": "T", "θ": "TH", "v": "V",
          "ʋ": "V", "w": "W", "j": "Y", "z": "Z", "ʒ": "ZH", "ɾ": "DX", "ʔ": "Q", "x": "HH",
          "ç": "SH", "ɕ": "SH", "ʂ": "SH", "ʐ": "ZH", "ʑ": "ZH", "β": "V", "ɸ": "F", "ɣ": "G",
          "ɲ": "N", "ɳ": "N", "ʎ": "L", "ɭ": "L", "ʈ": "T", "ɖ": "D", "c": "K", "ɟ": "G", "q": "K"}
DROP = set("ːˑʰʲʷˠˤ˞ʼ‿ ̃") | {"̥", "̩", "̪", "̚", "̺", "̴", "ˈ", "ˌ", "-", "|"}
VOWELS = {"AA", "AE", "AH", "AO", "AW", "AY", "EH", "ER", "EY", "IH", "IY", "OW", "OY", "UH", "UW"}


def ipa_to_arpa(s: str) -> list[str]:
    s = unicodedata.normalize("NFD", s.replace("ɝ", "ɜɹ").replace("ɚ", "əɹ"))
    s = "".join(c for c in s if c not in DROP and not unicodedata.combining(c))
    s = unicodedata.normalize("NFC", s)
    out, i = [], 0
    while i < len(s):
        if s[i].isspace():
            i += 1; continue
        two = s[i:i + 2]
        if two in MULTI:
            out.append(MULTI[two]); i += 2; continue
        out.append(SINGLE.get(s[i], "?" + s[i])); i += 1
    return out


def arpa(p: str) -> str:
    return "".join(c for c in p if not c.isdigit()).rstrip("*").strip()


# --- alignment ------------------------------------------------------------------------------
def sub_cost(a: str, h: str) -> float:
    if a == h:
        return 0.0
    if h == "DX" and a in ("T", "D"):
        return 0.0                       # American flap: accepted for t/d
    if h == "Q" and a == "T":
        return 0.0                       # glottal stop for t: accepted
    if (a in VOWELS) == (h in VOWELS):
        return 0.6
    return 1.2


def align(ref: list[str], hyp: list[str]) -> list:
    """For each ref phone: the hyp phone aligned to it, or None (deleted)."""
    n, m = len(ref), len(hyp)
    D = [[0.0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1): D[i][0] = i
    for j in range(1, m + 1): D[0][j] = j * 0.8
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            D[i][j] = min(D[i - 1][j - 1] + sub_cost(ref[i - 1], hyp[j - 1]),
                          D[i - 1][j] + 1.0, D[i][j - 1] + 0.8)
    out, i, j = [None] * n, n, m
    while i > 0:
        if j > 0 and abs(D[i][j] - (D[i - 1][j - 1] + sub_cost(ref[i - 1], hyp[j - 1]))) < 1e-9:
            out[i - 1] = hyp[j - 1]; i -= 1; j -= 1
        elif abs(D[i][j] - (D[i - 1][j] + 1.0)) < 1e-9:
            i -= 1
        else:
            j -= 1
    return out


def accepts(ref: str, h) -> bool:
    return h is not None and sub_cost(ref, h) == 0.0


# --- scoring --------------------------------------------------------------------------------
def score(path: str, df: pd.DataFrame) -> dict:
    rows = {json.loads(l)["idx"]: json.loads(l) for l in open(path, encoding="utf-8")}
    c = collections.Counter()
    diag_pairs = collections.Counter()
    by_age = collections.defaultdict(collections.Counter)
    unknown = collections.Counter()
    model = None
    for idx, r in rows.items():
        model = r["model"]
        ex = df.iloc[idx]
        ref, acc, misp = [], [], {}
        for w in ex["words"]:
            base = len(ref)
            ref += [arpa(p) for p in w["phones"]]
            acc += list(w["phones-accuracy"])
            for mm in w["mispronunciations"]:
                misp[base + int(mm["index"])] = mm["pronounced-phone"]
        hyp = ipa_to_arpa(r["hyp"])
        unknown.update(h for h in hyp if h.startswith("?"))
        al = align(ref, hyp)
        grp = "child" if ex["age"] < 16 else "adult"
        for k, (p, a, h) in enumerate(zip(ref, acc, al)):
            ok = accepts(p, h)
            lab = "correct" if a >= 1.6 else "error" if a <= 1.0 else "disputed"
            c[(lab, ok)] += 1
            by_age[grp][(lab, ok)] += 1
            pr = misp.get(k)
            if pr is None:
                continue
            pr0 = pr.strip()
            if pr0 == "<DEL>":
                c["del_n"] += 1; c["del_hit"] += h is None
            elif pr0 == "<unk>" or "*" in pr0 or " " in pr0:
                c["unk_n"] += 1; c["unk_flag"] += not ok
            else:
                said = arpa(pr0)
                c["sub_n"] += 1
                c["sub_flag"] += not ok
                hit = h is not None and sub_cost(said, h) == 0.0
                c["sub_exact"] += hit
                c["sub_said_canonical"] += ok
                diag_pairs[(p, said, h or "∅", hit)] += 1

    def block(cc):
        tp, fn = cc[("error", False)], cc[("error", True)]
        fp, tn = cc[("correct", False)], cc[("correct", True)]
        rec = tp / max(1, tp + fn); prec = tp / max(1, tp + fp)
        return {"n_correct": tp + 0 if False else fp + tn, "n_error": tp + fn,
                "false_rejection": round(fp / max(1, fp + tn), 4),
                "detection_recall": round(rec, 4), "precision": round(prec, 4),
                "f1": round(2 * prec * rec / max(1e-9, prec + rec), 4),
                "disputed_rejected": round(cc[("disputed", False)] / max(1, cc[("disputed", False)] + cc[("disputed", True)]), 4)}
    out = {"model": model, "n_utts": len(rows), **block(c),
           "by_age": {g: block(v) for g, v in by_age.items()},
           "substitutions": {"n": c["sub_n"],
                             "flagged": round(c["sub_flag"] / max(1, c["sub_n"]), 4),
                             "model_heard_what_learner_said": round(c["sub_exact"] / max(1, c["sub_n"]), 4),
                             "model_heard_the_canonical_phone": round(c["sub_said_canonical"] / max(1, c["sub_n"]), 4)},
           "deletions": {"n": c["del_n"], "model_also_deleted": round(c["del_hit"] / max(1, c["del_n"]), 4)},
           "unidentifiable_or_distorted": {"n": c["unk_n"], "flagged": round(c["unk_flag"] / max(1, c["unk_n"]), 4)},
           "unmapped_symbols": dict(unknown.most_common(15)),
           "examples_substitution": [
               {"canonical": a, "learner_said": s, "model_heard": h, "match": hit, "n": n}
               for (a, s, h, hit), n in diag_pairs.most_common(25)]}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("jsonl", nargs="+")
    ap.add_argument("--parquet", default="/opt/so762/test.parquet")
    ap.add_argument("--out")
    a = ap.parse_args()
    df = pd.read_parquet(a.parquet, columns=["words", "age", "text"])
    res = {"corpus": "speechocean762 test (Apache-2.0; Mandarin-L1 learners of English, 5 expert raters)",
           "labels": "correct: phone accuracy >= 1.6 of 2; error: <= 1.0; disputed: 1.2-1.4",
           "results": [score(p, df) for p in a.jsonl]}
    js = json.dumps(res, ensure_ascii=False, indent=1)
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(js, encoding="utf-8")
    for r in res["results"]:
        print(json.dumps({k: v for k, v in r.items() if k not in ("examples_substitution", "by_age")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
