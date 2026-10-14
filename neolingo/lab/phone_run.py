"""Fill the phone-model cache: CTC log-probabilities and the greedy decode of every wav of a list, for one model.

    <miolingo venv python> -m lab.phone_run --model facebook/wav2vec2-xlsr-53-espeak-cv-ft --list var/lab/lists/all.txt
    [--shard K/N]

The list file has one wav path a line (absolute, or relative to neolingo/).  The computation is the one of Miolingo's
`audio/phone_recognizer.py` (`phones_from_audio`, `log_probs_from_audio`): `_load_audio_16k`, the processor, the model's
logits, argmax, `processor.batch_decode`, `log_softmax` of the float32 logits.  One model is loaded by a process (the
brief: at most two phone models at once on the machine).  pklumpp/Wav2Vec2_CommonPhone has no processor: it is loaded
and decoded with Miolingo's `audio/pklumpp_ctc.py`, and its vocabulary is that module's symbol table (blank 0)."""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np

from . import cache
from .common import ROOT, PKL, mkdirs, save_sha_index, wav_sha


def load(model_id: str):
    """(processor or None, model, vocab, blank).  Raises if the model is not in the local cache."""
    import env  # noqa: F401  (puts Miolingo's src on sys.path, offline)
    from env import _miolingo as mio
    import torch  # noqa: F401
    if model_id == PKL:
        from audio import pklumpp_ctc
        model = pklumpp_ctc.load_model()
        vocab = dict(pklumpp_ctc._SYMBOLS)
        vocab["<blank>"] = 0
        return None, model, vocab, 0
    from transformers import AutoModelForCTC, AutoProcessor
    proc = AutoProcessor.from_pretrained(model_id)
    model = AutoModelForCTC.from_pretrained(model_id)
    model.eval()
    tok = proc.tokenizer
    return proc, model, tok.get_vocab(), tok.pad_token_id


def compute(proc, model, model_id: str, wav: str):
    """-> (log-probs float32 (T, V), greedy ids (T,), decode string)."""
    import torch
    from env import _miolingo as mio
    audio = mio.phone_recognizer._load_audio_16k(wav)
    if proc is None:                                    # pklumpp: standardised audio, blank 0 (as pklumpp_ctc.decode)
        from audio import pklumpp_ctc
        a = np.asarray(audio, dtype="float32")
        a = (a - a.mean()) / (a.std() + 1e-9)
        x = torch.tensor(a, dtype=torch.float).unsqueeze(0)
        with torch.no_grad():
            logits = model(x)[0]
        ids = torch.argmax(logits, dim=-1)
        out, prev = [], None
        for i in ids.tolist():
            if i != prev and i not in pklumpp_ctc._SKIP:
                out.append(pklumpp_ctc._ID_TO_SYMBOL.get(i, ""))
            prev = i
        text = " ".join(s for s in out if s)
    else:
        inputs = proc(audio, sampling_rate=16000, return_tensors="pt").input_values
        with torch.no_grad():
            logits = model(inputs).logits[0]
        ids = torch.argmax(logits, dim=-1)
        text = " ".join(proc.batch_decode(ids[None, :])[0].split())
    lp = torch.log_softmax(logits.float(), -1).numpy()
    return lp, ids.numpy(), text


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--model", required=True)
    ap.add_argument("--list", required=True, action="append")
    ap.add_argument("--shard", default="0/1")
    ap.add_argument("--threads", type=int, default=0)
    a = ap.parse_args()
    mkdirs()
    k, n = (int(x) for x in a.shard.split("/"))
    wavs = []
    for lf in a.list:
        for l in Path(lf).read_text("utf-8").splitlines():
            l = l.strip()
            if l and not l.startswith("#"):
                wavs.append(str(Path(l) if Path(l).is_absolute() else ROOT / l))
    wavs = list(dict.fromkeys(wavs))
    todo = []
    for w in wavs:
        sha = wav_sha(w)
        if int(sha[:8], 16) % n == k and not cache.lp_path(sha, a.model).exists():
            todo.append((w, sha))
    save_sha_index()
    print(f"{a.model}: {len(wavs)} wavs listed, {len(todo)} to compute (shard {a.shard})", flush=True)
    if not todo:
        return
    if cache.not_available(a.model):
        print("recorded as NOT AVAILABLE: " + cache.not_available(a.model))
        return
    import torch
    if a.threads:
        torch.set_num_threads(a.threads)
    t0 = time.perf_counter()
    try:
        proc, model, vocab, blank = load(a.model)
    except Exception as e:
        why = f"{type(e).__name__}: {str(e)[:400]}"
        cache.mark_not_available(a.model, why)
        print("NOT AVAILABLE (recorded, not fetched): " + why)
        return
    if not cache.vocab_path(a.model).exists():
        cache.put_vocab(a.model, vocab, blank)
    print(f"loaded in {time.perf_counter() - t0:.1f} s; vocabulary {len(vocab)}, blank {blank}", flush=True)
    t0 = time.perf_counter()
    done = set()
    for i, (w, sha) in enumerate(todo, 1):
        if sha in done:
            continue
        try:
            lp, ids, text = compute(proc, model, a.model, w)
        except Exception as e:
            print(f"FAILED {w}: {type(e).__name__}: {e}", flush=True)
            continue
        cache.put_lp(sha, a.model, lp, ids, text)
        done.add(sha)
        if i % 50 == 0 or i == len(todo):
            el = time.perf_counter() - t0
            print(f"  {i}/{len(todo)}  {el:.0f} s  ({el / i:.2f} s each)", flush=True)


if __name__ == "__main__":
    main()
