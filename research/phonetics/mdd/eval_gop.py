#!/usr/bin/env python3
"""
Evaluate gop_so762.py output against speechocean762's expert phone labels.

    venv/bin/python research/phonetics/mdd/eval_gop.py /opt/mdd/gop_zipa.jsonl /opt/mdd/gop_xlsr.jsonl \
        --out research/phonetics/mdd/results/so762_gop.json

  pcc            Pearson r of p_canon with expert phone accuracy (0..2), all phones -- the
                 standard speechocean762 phone-level metric
  auc            P(score of a correct phone > score of an error phone); correct: acc >= 1.6,
                 error: acc <= 1.0
  at threshold   reject when p_canon < t: false rejection of correct phones, recall of
                 errors, precision, F1
  diagnosis      labelled substitutions (expert wrote the phone actually said): model's best
                 hypothesis == that phone; deletions: model's best == <DEL>
"""
import argparse, collections, json
from pathlib import Path

import numpy as np
import pandas as pd


def arpa(p):
    return "".join(c for c in p if not c.isdigit()).rstrip("*").strip()


def auc(pos, neg):
    """P(pos > neg) via ranks (ties = 0.5)."""
    x = np.concatenate([pos, neg]); r = pd.Series(x).rank().to_numpy()
    rp = r[: len(pos)].sum()
    return (rp - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg))


def evaluate(path, df):
    S, A, AGE, diag, model = [], [], [], collections.Counter(), None
    confus = collections.Counter()
    for l in open(path, encoding="utf-8"):
        r = json.loads(l); model = r["model"]; ex = df.iloc[r["idx"]]
        acc, misp, base = [], {}, 0
        for w in ex["words"]:
            for mm in w["mispronunciations"]:
                misp[base + int(mm["index"])] = mm["pronounced-phone"].strip()
            acc += list(w["phones-accuracy"]); base += len(w["phones"])
        for k, (p, q, a) in enumerate(zip(r["ref"], r["phones"], acc)):
            S.append(q["p_canon"]); A.append(a); AGE.append(ex["age"])
            said = misp.get(k)
            if said is None:
                continue
            if said == "<DEL>":
                diag["del_n"] += 1; diag["del_flag"] += q["p_canon"] < 0.5
                diag["del_hit"] += q["best"] == "<DEL>"
            elif said == "<unk>" or "*" in said or " " in said:
                diag["unk_n"] += 1; diag["unk_flag"] += q["p_canon"] < 0.5
            else:
                s = arpa(said)
                diag["sub_n"] += 1; diag["sub_flag"] += q["p_canon"] < 0.5
                diag["sub_best"] += q["best"] == s
                diag["sub_alt"] += q["best_alt"] == s
                diag["sub_canon_won"] += q["best"] == p
                confus[(p, s, q["best"])] += 1
    S, A, AGE = np.array(S), np.array(A), np.array(AGE)

    def block(m):
        s, a = S[m], A[m]
        cor, err = s[a >= 1.6], s[a <= 1.0]
        out = {"n_phones": int(m.sum()), "n_correct": len(cor), "n_error": len(err),
               "pcc": round(float(np.corrcoef(s, a)[0, 1]), 4), "auc": round(float(auc(cor, err)), 4)}
        for fr in (0.05, 0.10, 0.20):     # ROC operating points: errors caught at a set false-rejection rate
            t = float(np.quantile(cor, fr)); tp = int((err < t).sum()); fp = int((cor < t).sum())
            out[f"at_false_rejection_{fr:.2f}"] = {"recall": round(tp / max(1, len(err)), 4),
                                                  "precision": round(tp / max(1, tp + fp), 4)}
        for t in (0.5, 0.2):
            fp, tp = int((cor < t).sum()), int((err < t).sum())
            rec, prec = tp / max(1, len(err)), tp / max(1, tp + fp)
            out[f"t{t}"] = {"false_rejection": round(fp / max(1, len(cor)), 4), "recall": round(rec, 4),
                            "precision": round(prec, 4), "f1": round(2 * rec * prec / max(1e-9, rec + prec), 4)}
        return out
    n = lambda k: diag[k + "_n"]
    return {"model": model, "n_utts": int(sum(1 for _ in open(path))),
            **block(np.ones(len(S), bool)),
            "children (<16)": block(AGE < 16), "adults": block(AGE >= 16),
            "substitutions": {"n": n("sub"), "flagged": round(diag["sub_flag"] / max(1, n("sub")), 4),
                              "best_is_what_learner_said": round(diag["sub_best"] / max(1, n("sub")), 4),
                              "top_alternative_is_what_learner_said": round(diag["sub_alt"] / max(1, n("sub")), 4),
                              "model_still_prefers_canonical": round(diag["sub_canon_won"] / max(1, n("sub")), 4)},
            "deletions": {"n": n("del"), "flagged": round(diag["del_flag"] / max(1, n("del")), 4),
                          "best_is_deletion": round(diag["del_hit"] / max(1, n("del")), 4)},
            "unidentifiable_or_distorted": {"n": n("unk"), "flagged": round(diag["unk_flag"] / max(1, n("unk")), 4)},
            "top_substitutions": [{"expected": a, "learner_said": s, "model_best": b, "n": c}
                                  for (a, s, b), c in confus.most_common(20)]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("jsonl", nargs="+")
    ap.add_argument("--parquet", default="/opt/so762/test.parquet")
    ap.add_argument("--out")
    a = ap.parse_args()
    df = pd.read_parquet(a.parquet, columns=["words", "age"])
    res = {"corpus": "speechocean762 test (Apache-2.0): 2500 utts, Mandarin-L1 learners of English "
                     "(half children), phone accuracy = mean of 5 experts (0..2)",
           "method": "substitution-aware alignment-free GOP (gop_so762.py), zero-shot",
           "published_reference_pcc": {"GOP baselines": "~0.45", "GOPT (trained on so762)": 0.612,
                                       "later trained models": "~0.65-0.70"},
           "results": [evaluate(p, df) for p in a.jsonl]}
    js = json.dumps(res, ensure_ascii=False, indent=1)
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True); Path(a.out).write_text(js, encoding="utf-8")
    print(js)


if __name__ == "__main__":
    main()
