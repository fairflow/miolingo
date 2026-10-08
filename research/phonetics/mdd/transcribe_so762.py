#!/usr/bin/env python3
"""
Free phone transcription of speechocean762 (non-native English, Mandarin L1) with a
phone recognizer; one JSON line per utterance, resumable. Scored by score_so762.py.

    venv/bin/python research/phonetics/mdd/transcribe_so762.py --model zipa --out /opt/mdd/zipa.jsonl
    venv/bin/python research/phonetics/mdd/transcribe_so762.py --model xlsr --out /opt/mdd/xlsr.jsonl

Data: https://huggingface.co/datasets/mispeech/speechocean762 (Apache-2.0), test split parquet.
"""
import argparse, io, json, os, sys, time
from pathlib import Path

import numpy as np
import pandas as pd
import soundfile as sf

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

MODELS = {
    "zipa": "anyspeech/zipa-large-crctc-500k (model.fp16.onnx, CC BY 4.0)",
    "xlsr": "facebook/wav2vec2-xlsr-53-espeak-cv-ft",
    "lv60": "facebook/wav2vec2-lv-60-espeak-cv-ft",
}


def hf_ctc(model_id):
    import torch
    from transformers import AutoModelForCTC, AutoProcessor
    proc = AutoProcessor.from_pretrained(model_id)
    model = AutoModelForCTC.from_pretrained(model_id).eval()
    inv = {i: t for t, i in proc.tokenizer.get_vocab().items()}
    blank = proc.tokenizer.pad_token_id
    skip = {blank} | {proc.tokenizer.convert_tokens_to_ids(t) for t in ("<s>", "</s>", "<unk>") if t in proc.tokenizer.get_vocab()}

    def run(x):
        inp = proc(x.astype(np.float32), sampling_rate=16000, return_tensors="pt").input_values
        with torch.no_grad():
            lp = torch.log_softmax(model(inp).logits[0], -1)
        run.lp = lp.numpy()
        ids = lp.argmax(-1).tolist()
        out, prev = [], None
        for i in ids:
            if i != prev and i not in skip:
                out.append(inv[i])
            prev = i
        return " ".join(out)
    run.vocab = {t: i for i, t in inv.items()}
    run.blank = blank
    return run


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", choices=MODELS, required=True)
    ap.add_argument("--parquet", default="/opt/so762/test.parquet")
    ap.add_argument("--out", required=True)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--save-lp", help="dir: <idx>.npy float16 log-probs (T, V) + vocab.json")
    a = ap.parse_args()
    if a.model == "zipa":
        from zipa_onnx import Zipa
        z = Zipa()

        def run(x):
            run.lp = z.log_probs(x)
            return z.greedy(run.lp)
        run.vocab, run.blank = {t: i for i, t in z.id2tok.items()}, 0
    else:
        run = hf_ctc(MODELS[a.model])
    df = pd.read_parquet(a.parquet)
    if a.save_lp:
        os.makedirs(a.save_lp, exist_ok=True)
        json.dump({"vocab": run.vocab, "blank": run.blank, "model": MODELS[a.model]},
                  open(os.path.join(a.save_lp, "vocab.json"), "w", encoding="utf-8"), ensure_ascii=False)
    done = set()
    if os.path.exists(a.out):
        done = {json.loads(l)["idx"] for l in open(a.out, encoding="utf-8")}
    t0 = time.time()
    with open(a.out, "a", encoding="utf-8") as f:
        for k, r in df.iterrows():
            if a.limit and k >= a.limit:
                break
            if k in done:
                continue
            x, sr = sf.read(io.BytesIO(r["audio"]["bytes"]))
            assert sr == 16000
            if x.ndim > 1:
                x = x.mean(1)
            hyp = run(x)
            if a.save_lp:
                np.save(os.path.join(a.save_lp, f"{k}.npy"), run.lp.astype(np.float16))
            f.write(json.dumps({"idx": int(k), "model": MODELS[a.model], "text": r["text"],
                                "hyp": hyp}, ensure_ascii=False) + "\n")
            f.flush()
            if k % 250 == 0:
                print(k, round(time.time() - t0), "s", flush=True)
    print("done", round(time.time() - t0), "s")


if __name__ == "__main__":
    main()
