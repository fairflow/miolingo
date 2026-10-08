#!/usr/bin/env python3
"""
Learned acceptance: which realised phones do expert listeners accept for each expected
English phone? Fitted on speechocean762 TRAIN, applied to TEST (no test labels used).

  A[p][q] = mean expert accuracy/2 of train phones with canonical p, weighted by the model's
            posterior that q was said (q = any phone or <DEL>); smoothed toward p's mean.
  score   = sum_q posterior(q) * A[p][q]        (expected expert score; 0..1)

This is the data-driven version of the hand-written `accept` lists in the realised-phone
pair files (e.g. unaspirated [p] for English /b/ is accepted by listeners).

    venv/bin/python research/phonetics/mdd/accept_so762.py --train /opt/mdd/gop_zipa_train.jsonl \
        --train-parquet /opt/so762/train.parquet --test /opt/mdd/gop_zipa.jsonl \
        --out-test /opt/mdd/gop_zipa_accept.jsonl --table research/phonetics/mdd/results/accept_zipa.json
"""
import argparse, collections, json

import pandas as pd

PRIOR = 5.0


def labelled(path, parquet):
    df = pd.read_parquet(parquet, columns=["words"])
    for l in open(path, encoding="utf-8"):
        r = json.loads(l)
        acc = [a for w in df.iloc[r["idx"]]["words"] for a in w["phones-accuracy"]]
        yield r, acc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", required=True)
    ap.add_argument("--train-parquet", default="/opt/so762/train.parquet")
    ap.add_argument("--test", required=True)
    ap.add_argument("--out-test", required=True)
    ap.add_argument("--table")
    a = ap.parse_args()
    num, den = collections.defaultdict(float), collections.defaultdict(float)
    pnum, pden = collections.defaultdict(float), collections.defaultdict(float)
    for r, acc in labelled(a.train, a.train_parquet):
        for p, q, y in zip(r["ref"], r["phones"], acc):
            y = y / 2.0
            rest = 1.0 - sum(v for _, v in q["top"])
            for h, v in q["top"] + [["<other>", rest]]:
                num[(p, h)] += v * y; den[(p, h)] += v
            pnum[p] += y; pden[p] += 1
    pm = {p: pnum[p] / pden[p] for p in pden}
    A = {k: (num[k] + PRIOR * pm[k[0]]) / (den[k] + PRIOR) for k in den}
    with open(a.out_test, "w", encoding="utf-8") as f:
        for l in open(a.test, encoding="utf-8"):
            r = json.loads(l)
            for p, q in zip(r["ref"], r["phones"]):
                rest = 1.0 - sum(v for _, v in q["top"])
                s = sum(v * A.get((p, h), pm.get(p, 0.9)) for h, v in q["top"]) + rest * A.get((p, "<other>"), pm.get(p, 0.9))
                q["p_canon_raw"] = q["p_canon"]; q["p_canon"] = round(s, 4)
            r["model"] = r["model"] + " + learned acceptance (so762 train)"
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    if a.table:
        tab = collections.defaultdict(dict)
        for (p, h), v in A.items():
            if h != p and den[(p, h)] >= 5:
                tab[p][h] = {"accepted": round(v, 3), "soft_n": round(den[(p, h)], 1)}
        out = {p: dict(sorted(d.items(), key=lambda kv: -kv[1]["soft_n"])[:6]) for p, d in sorted(tab.items())}
        json.dump({"what": "A[expected][heard]: expert acceptance (0..1) when the model hears `heard` for "
                           "`expected`; fitted on speechocean762 train", "table": out},
                  open(a.table, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
