#!/usr/bin/env python3
"""
Substitution-aware, alignment-free goodness of pronunciation (GOP) on speechocean762.

For every canonical phone i of an utterance, the CTC likelihood of the whole canonical
sequence is compared with the same sequence where phone i is replaced by each of the 39
English phones (any of its token spellings) or deleted. Softmax over those hypotheses gives
  p_canon   : how sure the model is that the expected phone was said (0..1)
  best_alt  : the most likely phone if it wasn't (the "realised phone")
No forced aligner, no detectors: one recognizer, any phone.

Standard speechocean762 metric: Pearson correlation (PCC) of the phone score with the
experts' phone accuracy (0..2). Published: GOP baselines ~0.45; GOPT (trained on the
train split) 0.61; later trained models ~0.65-0.70. Ours are zero-shot (no training on
speechocean762).

    venv/bin/python research/phonetics/mdd/gop_so762.py --lp /opt/mdd/lp_zipa --spell zipa --out /opt/mdd/gop_zipa.jsonl
"""
import argparse, json, os, sys

import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F

V = ["ː"]          # optional length mark (ZIPA spelling)
SPELL = {
    # ARPAbet -> token spellings (each a list of tokens); first = default in context
    "zipa": {
        "AA": [["ɑ"], ["a"], ["ɑ", "ː"], ["ɒ"]], "AE": [["æ"]], "AH": [["ʌ"], ["ə"], ["ɐ"]],
        "AO": [["ɔ"], ["ɔ", "ː"]], "AW": [["a", "ʊ"]], "AY": [["a", "ɪ"]], "EH": [["ɛ"], ["e"]],
        "ER": [["ə", "˞"], ["ɜ", "˞"], ["ɜ", "ː"], ["ə", "ɹ"]], "EY": [["e", "ɪ"], ["e"]],
        "IH": [["ɪ"], ["ɨ"]], "IY": [["i"], ["i", "ː"]], "OW": [["o", "ʊ"], ["o"], ["ə", "ʊ"]],
        "OY": [["ɔ", "ɪ"]], "UH": [["ʊ"]], "UW": [["u"], ["u", "ː"], ["ʉ"]],
        "B": [["b"]], "CH": [["t", "ʃ"]], "D": [["d"], ["ɾ"]], "DH": [["ð"]], "F": [["f"]],
        "G": [["g"]], "HH": [["h"], ["ɦ"]], "JH": [["d", "ʒ"]], "K": [["k"], ["k", "ʰ"]],
        "L": [["l"]], "M": [["m"]], "N": [["n"]], "NG": [["ŋ"]], "P": [["p"], ["p", "ʰ"]],
        "R": [["ɹ"], ["ɻ"]], "S": [["s"]], "SH": [["ʃ"]], "T": [["t"], ["t", "ʰ"], ["ɾ"], ["ʔ"]],
        "TH": [["θ"]], "V": [["v"]], "W": [["w"]], "Y": [["j"]], "Z": [["z"]], "ZH": [["ʒ"]]},
    "espeak": {
        "AA": [["ɑː"], ["ɑ"], ["a"], ["ɒ"]], "AE": [["æ"]], "AH": [["ʌ"], ["ə"], ["ɐ"]],
        "AO": [["ɔː"], ["ɔ"]], "AW": [["aʊ"]], "AY": [["aɪ"]], "EH": [["ɛ"], ["e"]],
        "ER": [["ɚ"], ["ɜː"], ["ə", "ɹ"]], "EY": [["eɪ"], ["e"]], "IH": [["ɪ"], ["ᵻ"]],
        "IY": [["iː"], ["i"]], "OW": [["oʊ"], ["o"], ["əʊ"]], "OY": [["ɔɪ"]], "UH": [["ʊ"]],
        "UW": [["uː"], ["u"]], "B": [["b"]], "CH": [["tʃ"]], "D": [["d"], ["ɾ"]], "DH": [["ð"]],
        "F": [["f"]], "G": [["ɡ"]], "HH": [["h"]], "JH": [["dʒ"]], "K": [["k"]], "L": [["l"]],
        "M": [["m"]], "N": [["n"]], "NG": [["ŋ"]], "P": [["p"]], "R": [["ɹ"]], "S": [["s"]],
        "SH": [["ʃ"]], "T": [["t"], ["ɾ"], ["ʔ"]], "TH": [["θ"]], "V": [["v"]], "W": [["w"]],
        "Y": [["j"]], "Z": [["z"]], "ZH": [["ʒ"]]},
}
PHONES = list(SPELL["zipa"])


def arpa(p):
    return "".join(c for c in p if not c.isdigit()).rstrip("*").strip()


def nll(lp: torch.Tensor, seqs: list[list[int]], blank: int, chunk=256) -> np.ndarray:
    """-log P(seq | audio) for each token-id sequence (CTC, batched)."""
    T = lp.shape[0]
    out = []
    for s in range(0, len(seqs), chunk):
        part = seqs[s:s + chunk]
        tgt = torch.tensor([t for q in part for t in q], dtype=torch.long)
        lens = torch.tensor([len(q) for q in part], dtype=torch.long)
        x = lp[:, None, :].expand(T, len(part), lp.shape[1])
        out.append(F.ctc_loss(x, tgt, torch.full((len(part),), T, dtype=torch.long), lens,
                              blank=blank, reduction="none", zero_infinity=True).numpy())
    return np.concatenate(out)


def utterance(lp, ref, spell, vocab, blank):
    ids = {p: [[vocab[t] for t in v] for v in vs if all(t in vocab for t in v)] for p, vs in spell.items()}
    # 1) context spelling per position: the canonical phone's most likely spelling
    ctx = [ids[p][0] for p in ref]
    seqs, where = [], []
    for i, p in enumerate(ref):
        for k, v in enumerate(ids[p]):
            seqs.append(sum(ctx[:i], []) + v + sum(ctx[i + 1:], [])); where.append((i, k))
    ll = -nll(lp, seqs, blank)
    best = {}
    for (i, k), l in zip(where, ll):
        if i not in best or l > best[i][1]:
            best[i] = (k, l)
    ctx = [ids[p][best[i][0]] for i, p in enumerate(ref)]
    # 2) per position: canonical vs every other phone vs deletion
    seqs, where = [], []
    for i in range(len(ref)):
        pre, post = sum(ctx[:i], []), sum(ctx[i + 1:], [])
        for q in PHONES:
            for v in ids[q]:
                seqs.append(pre + v + post); where.append((i, q))
        if pre or post:
            seqs.append(pre + post); where.append((i, "<DEL>"))
    ll = -nll(lp, seqs, blank)
    per = [dict() for _ in ref]
    for (i, q), l in zip(where, ll):
        per[i][q] = max(per[i].get(q, -np.inf), float(l))
    res = []
    for i, p in enumerate(ref):
        d = per[i]
        ks = list(d); arr = np.array([d[k] for k in ks]); arr = np.exp(arr - arr.max()); arr /= arr.sum()
        post = dict(zip(ks, arr))
        alt = max((k for k in ks if k != p), key=lambda k: post[k])
        res.append({"p_canon": round(float(post.get(p, 0.0)), 4), "best": max(ks, key=lambda k: post[k]),
                    "best_alt": alt, "p_alt": round(float(post[alt]), 4),
                    "top": [[k, round(float(post[k]), 4)] for k in sorted(ks, key=lambda k: -post[k])[:5]]})
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lp", required=True)
    ap.add_argument("--spell", choices=SPELL, required=True)
    ap.add_argument("--parquet", default="/opt/so762/test.parquet")
    ap.add_argument("--out", required=True)
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--end", type=int, default=10**9)
    a = ap.parse_args()
    torch.set_num_threads(max(1, os.cpu_count() // 2))
    meta = json.load(open(os.path.join(a.lp, "vocab.json"), encoding="utf-8"))
    vocab, blank = meta["vocab"], meta["blank"]
    df = pd.read_parquet(a.parquet, columns=["words"])
    done = set()
    if os.path.exists(a.out):
        done = {json.loads(l)["idx"] for l in open(a.out, encoding="utf-8")}
    with open(a.out, "a", encoding="utf-8") as f:
        for idx in range(a.start, min(a.end, len(df))):
            fn = os.path.join(a.lp, f"{idx}.npy")
            if idx in done or not os.path.exists(fn):
                continue
            ref = [arpa(p) for w in df.iloc[idx]["words"] for p in w["phones"]]
            lp = torch.from_numpy(np.load(fn).astype(np.float32))
            if "▁" in vocab:          # ZIPA word-boundary symbol: fold into blank
                w = vocab["▁"]
                lp[:, blank] = torch.logaddexp(lp[:, blank], lp[:, w])
                lp[:, w] = -1e4
            f.write(json.dumps({"idx": idx, "model": meta["model"], "ref": ref,
                                "phones": utterance(lp, ref, SPELL[a.spell], vocab, blank)},
                               ensure_ascii=False) + "\n")
            f.flush()


if __name__ == "__main__":
    main()
