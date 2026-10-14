"""The cache: after the first run a variant costs almost nothing.

  per (wav, phone model):  var/lab/cache/lp/<model>/<sha[:2]>/<sha>.npz
        lp      CTC log-probabilities, float16, (T, V)
        ids     the greedy path: argmax per frame, taken from the float32 logits BEFORE rounding to float16
        decode  the model's own greedy decode (processor.batch_decode of ids), the string env.hear starts from
     var/lab/cache/lp/<model>/vocab.json: {"vocab": {token: id}, "blank": id}
  per (wav, Whisper settings, prompt):  var/lab/cache/whisper/<sha[:2]>/<sha>.json: {key: value}
        key "free"                      -> {"text", "note"}: env.hearing.transcribe's own parameters
        key "prompt:<sha1 of prompt>"   -> the same call with initial_prompt
        key "tf:<sha1 of text>"         -> teacher-forced log-probability of a text (lab/whisper_run.py)

Keys are the content hash of the wav (sha1 of its bytes), so a renamed or copied file is not computed twice.
A model that cannot be loaded offline is recorded in var/lab/cache/lp/<model>/NOT_AVAILABLE.txt and never fetched."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import numpy as np

from .common import CACHE, slug, wav_sha

LP = CACHE / "lp"
WH = CACHE / "whisper"


# ---------------------------------------------------------------- phone models
def lp_path(sha: str, model_id: str) -> Path:
    return LP / slug(model_id) / sha[:2] / f"{sha}.npz"


def has_lp(wav, model_id: str) -> bool:
    return lp_path(wav_sha(wav), model_id).exists()


def put_lp(sha: str, model_id: str, lp32: np.ndarray, ids: np.ndarray, decode: str):
    p = lp_path(sha, model_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(f".{os.getpid()}.tmp.npz")
    np.savez_compressed(tmp, lp=lp32.astype(np.float16), ids=ids.astype(np.int16), decode=np.array(decode))
    os.replace(tmp, p)


_LP_MEMO: dict = {}


def get_lp(wav, model_id: str, memo: bool = False):
    """-> {"lp": float32 (T, V) from the float16 cache, "ids": int array, "decode": str}; KeyError when not cached."""
    sha = wav_sha(wav)
    k = (sha, model_id)
    if k in _LP_MEMO:
        return _LP_MEMO[k]
    p = lp_path(sha, model_id)
    if not p.exists():
        raise KeyError(f"no log-probabilities cached for {wav} with {model_id}")
    z = np.load(p, allow_pickle=False)
    out = {"lp": z["lp"].astype(np.float32), "ids": z["ids"].astype(np.int64), "decode": str(z["decode"])}
    if memo:
        _LP_MEMO[k] = out
    return out


def vocab_path(model_id: str) -> Path:
    return LP / slug(model_id) / "vocab.json"


_VOCAB: dict = {}


def get_vocab(model_id: str):
    """(vocab {token: id}, blank id) of a phone model, from the cache."""
    if model_id not in _VOCAB:
        d = json.loads(vocab_path(model_id).read_text("utf-8"))
        _VOCAB[model_id] = (d["vocab"], d["blank"])
    return _VOCAB[model_id]


def put_vocab(model_id: str, vocab: dict, blank: int, extra: dict | None = None):
    p = vocab_path(model_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"vocab": vocab, "blank": blank, **(extra or {})}, ensure_ascii=False), "utf-8")


def not_available(model_id: str) -> str | None:
    p = LP / slug(model_id) / "NOT_AVAILABLE.txt"
    return p.read_text("utf-8") if p.exists() else None


def mark_not_available(model_id: str, why: str):
    p = LP / slug(model_id) / "NOT_AVAILABLE.txt"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(why, "utf-8")


# ---------------------------------------------------------------- Whisper
def _wh_path(sha: str) -> Path:
    return WH / sha[:2] / f"{sha}.json"


def text_key(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:16]


def wh_all(wav) -> dict:
    p = _wh_path(wav_sha(wav))
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return {}


def wh_get(wav, key: str):
    return wh_all(wav).get(key)


def wh_put(wav, entries: dict):
    """Merge `entries` into the wav's file (one writer per wav at a time: the runners shard by sha)."""
    sha = wav_sha(wav)
    p = _wh_path(sha)
    p.parent.mkdir(parents=True, exist_ok=True)
    try:
        cur = json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        cur = {}
    cur.update(entries)
    tmp = p.with_suffix(f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(cur, ensure_ascii=False), "utf-8")
    os.replace(tmp, p)


def wh_key(lang: str, prompt: str | None = None, size: str = "medium") -> str:
    base = f"{size}|{lang}"
    return f"{base}|free" if prompt is None else f"{base}|prompt:{text_key(prompt)}"


def tf_key(lang: str, text: str, size: str = "medium") -> str:
    return f"{size}|{lang}|tf:{text_key(text)}"
