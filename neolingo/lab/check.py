"""The sound check from cached log-probabilities, with EVERY verdict kept, and the likelihood-ratio test of an edit.

`verdicts(...)` runs Miolingo's `scoring.sound_check.score` (unchanged) on the cached log-probabilities and maps the
recogniser tokens to target sounds with `env.soundcheck._map_tokens_to_phones` (the live mapping).  It keeps all
verdicts (p_ok, level ok / check / off / unchecked, the most likely other sound), builds the same findings that
`env.sounds` returns for the flagged ones, and the flags the host sends (`host.engine.flags_out`, then the engine's own
filter).  Per TARGET SOUND it gives:

    level   "off" | "check"   the page would show a warning on this sound (a flag of the host lands on it)
            "unchecked"       a token covering it is `unreliable` for the language (never flagged)
            "ok"              covered by a verdict, no flag
            None              no verdict (the check could not run, or no token covers the sound)
    p_ok    the least p_ok of the tokens covering it
    alt     for check / off: the sound the check says it sounded like; "" = left out

`lr_edits(...)` is the V4 test: log P(target with ONE edit applied | audio) - log P(target | audio), CTC likelihoods
from the same log-probabilities with Miolingo's `sound_check._nll`; both sequences are cut into recogniser tokens with
`sound_check.tokenize`.  None where it cannot be computed (take too short for the target, or the edit disappears when
cut into tokens).

Results are cached on disk under var/lab/cache/check/ (key: wav hash, model, variant, the target's sounds)."""
from __future__ import annotations

import hashlib
import json
import os

import numpy as np

from . import cache
from .common import CACHE, wav_sha
from . import engine_py as E

CK = CACHE / "check"
_MEM: dict = {}


def _mio():
    import env  # noqa: F401
    from env import _miolingo as mio
    return mio


def _key(sha, model_id, variant, payload) -> str:
    return hashlib.sha1(json.dumps([sha, model_id, variant, payload], ensure_ascii=False).encode("utf-8")).hexdigest()


def _disk_get(kind, key):
    p = CK / kind / key[:2] / f"{key}.json"
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _disk_put(kind, key, obj):
    p = CK / kind / key[:2] / f"{key}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False), "utf-8")
    os.replace(tmp, p)


def ipa_str(words) -> str:
    return " ".join("".join(w) for w in words if w)


def raw_tokens(wav, model_id: str, target, variant: str, lp=None) -> dict:
    """{"ran": bool, "note": str, "tokens": [{tok, word, p_ok, level, heard, p_heard, first, last}]} (cached)."""
    sha = wav_sha(wav)
    words = [w for w in target if w]
    key = _key(sha, model_id, variant, words)
    if key in _MEM:
        return _MEM[key]
    got = _disk_get("tokens", key)
    if got is None:
        mio = _mio()
        from env.soundcheck import _map_tokens_to_phones
        from env.variants import variant as variant_of
        v = variant_of(variant)
        s = ipa_str(words)
        vocab, blank = cache.get_vocab(model_id)
        if lp is None:
            lp = cache.get_lp(wav, model_id)["lp"]
        got = {"ran": False, "note": "", "tokens": []}
        if s:
            res = mio.sound_check.score(lp, vocab, blank, s, v["espeak"], model_id)
            got["note"] = res.note
            if res.phones:
                ref = mio.sound_check.tokenize(s, vocab)
                hidden = set()
                cfg = mio.sound_check.lang_config(v["espeak"])
                if cfg.get("glottal_onsets") and "ʔ" in vocab:
                    ref = mio.sound_check._with_glottal_onsets(ref)
                    hidden = {i for i, (t, _) in enumerate(ref) if t == "ʔ"}
                visible = [i for i in range(len(ref)) if i not in hidden]
                place = _map_tokens_to_phones(words, ref, hidden)
                got["ran"] = True
                for pv, i in zip(res.phones, visible):
                    first, last = place.get(i, (0, 0))
                    got["tokens"].append({"tok": pv.phone, "word": pv.word_index, "p_ok": pv.p_ok, "level": pv.level,
                                          "heard": pv.heard, "p_heard": pv.p_heard, "first": first, "last": last})
        _disk_put("tokens", key, got)
    _MEM[key] = got
    return got


def lib_findings(tokens) -> list[dict]:
    """The findings `env.sounds` returns (flagged verdicts only; a finding whose `like` equals its `sound` dropped)."""
    mio = _mio()
    from env.ipa import norm_word
    out = []
    for t in tokens:
        if t["level"] not in ("check", "off"):
            continue
        like = "" if t["heard"] in (None, mio.sound_check.DEL) else norm_word(t["heard"])
        sound = norm_word(t["tok"]) or t["tok"]
        if like and like == sound:
            continue
        out.append({"at": t["first"], "span": t["last"] - t["first"] + 1, "off": t["level"] == "off", "like": like,
                    "left_out": t["heard"] == mio.sound_check.DEL, "sound": sound, "word": t["word"]})
    return out


def verdicts(wav, model_id: str, target, variant: str) -> dict:
    """{"ran", "note", "tokens", "flags" (as the engine keeps them), "dropped" (flags the engine would drop),
    "phones": [{"level", "p_ok", "alt"}] per target sound}."""
    raw = raw_tokens(wav, model_id, target, variant)
    return {"ran": raw["ran"], "note": raw["note"], **phones_from_tokens(raw["tokens"], target)}


def phones_from_tokens(tokens, target) -> dict:
    """The per-target-sound verdicts of `verdicts`, from the check's tokens (no cache, no file: the host's
    env.sounds calls it with the tokens of the take in hand).  -> {"tokens", "flags", "dropped", "phones"}."""
    from host.engine import flags_out
    raw = {"tokens": tokens}
    words = [w for w in target if w]
    n = sum(len(w) for w in words)
    lib = lib_findings(raw["tokens"])
    sent = flags_out(lib, words) if lib else []
    kept = E.keep_flags(sent, words)
    by_at = {f["at"]: f for f in kept}
    cover = [[] for _ in range(n)]
    for t in raw["tokens"]:
        for a in range(t["first"], t["last"] + 1):
            if 0 <= a < n:
                cover[a].append(t)
    phones = []
    for a in range(n):
        if not cover[a]:
            phones.append({"level": None, "p_ok": None, "alt": None})
            continue
        p_ok = min(t["p_ok"] for t in cover[a])
        if a in by_at:
            f = by_at[a]
            phones.append({"level": "off" if f["off"] else "check", "p_ok": p_ok,
                           "alt": f["heardAs"] if f["heardAs"] is not None else ""})
        elif any(t["level"] == "unchecked" for t in cover[a]):
            phones.append({"level": "unchecked", "p_ok": p_ok, "alt": None})
        else:
            phones.append({"level": "ok", "p_ok": p_ok, "alt": None})
    return {"tokens": raw["tokens"], "flags": kept, "dropped": len(sent) - len(kept), "phones": phones}


# ------------------------------------------------------------------ the likelihood-ratio test of ONE edit (V4)
def apply_edit(words, edit):
    """`words`: the target by word.  `edit`: ("sub", i, h) | ("del", i) | ("ins", i, h), i a flat index of the target
    (for "ins": the heard sound h stands BEFORE target sound i; i == number of sounds: at the end).  -> words'."""
    out = [list(w) for w in words]
    kind, i = edit[0], edit[1]
    k = 0
    for wi, w in enumerate(out):
        if i < k + len(w) or (wi == len(out) - 1 and i == k + len(w)):
            j = i - k
            if kind == "sub":
                w[j] = edit[2]
            elif kind == "del":
                del w[j]
            else:
                w.insert(j, edit[2])
            return out
        k += len(w)
    raise IndexError(f"edit {edit!r} outside the target")


def lr_from_lp(lp, vocab, blank, words, edits) -> list:
    """The V4 test on log-probabilities in hand (numpy (T, V) or a torch tensor): for each edit, log P(edited target |
    audio) - log P(target | audio), rounded to 4 places, or None (take too short for the sequence, or the edit
    disappears when cut into recogniser tokens).  No cache: `lr_edits` caches it; the host's env.sounds calls it."""
    mio = _mio()
    import torch
    lpt = lp if isinstance(lp, torch.Tensor) else torch.from_numpy(np.asarray(lp, dtype=np.float32))
    lpt = lpt.float()

    def ids_of(ws):
        return [vocab[t] for t, _ in mio.sound_check.tokenize(ipa_str(ws), vocab)]

    words = [w for w in words if w]
    base = ids_of(words)
    T = lpt.shape[0]
    if not base or T < 2 * len(base):
        return [None] * len(edits)
    seqs, idx = [base], []
    for e in edits:
        q = ids_of(apply_edit(words, e))
        if not q or q == base or T < len(q) + sum(1 for a, b in zip(q, q[1:]) if a == b):
            idx.append(None)
        else:
            idx.append(len(seqs))
            seqs.append(q)
    ll = -mio.sound_check._nll(lpt, seqs, blank)
    return [None if k is None else round(float(ll[k] - ll[0]), 4) for k in idx]


def lr_edits(wav, model_id: str, target, variant: str, edits) -> list:
    """For each edit: log P(edited target | audio) - log P(target | audio), or None."""
    edits = [tuple(e) for e in edits]
    if not edits:
        return []
    sha = wav_sha(wav)
    words = [w for w in target if w]
    key = _key(sha, model_id, variant, [words, edits])
    if key in _MEM:
        return _MEM[key]
    got = _disk_get("lr", key)
    if got is None:
        vocab, blank = cache.get_vocab(model_id)
        got = lr_from_lp(cache.get_lp(wav, model_id)["lp"], vocab, blank, words, edits)
        _disk_put("lr", key, got)
    _MEM[key] = got
    return got
