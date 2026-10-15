"""The "understood" rules (part D) and the Whisper jobs they need.

  free     the live rule: the words of the free transcription equal the target's, or the transcription has the same
           sounds (German respellings tried): the ENGINE's own rule, asked through `neolingo batch` (below)
  prompt   the same test on the transcription made with the target phrase as `initial_prompt`
  tf(m)    Whisper's own log-probability of the target text (teacher-forced) against that of its free transcription
           (teacher-forced the same way): understood iff  lp(target) >= lp(free) - m.
           The target is tried in a few surface forms (first letter capital or not, each word capital for German, with
           and without a final ".", "!", "?"), the best one counts: the free transcription chose its own capitals and
           punctuation, the target must be allowed the same.  When nothing was transcribed (free text empty): not
           understood.
  either   free OR tf(m)

Whisper jobs for an item: the free call, the prompted call, and the teacher-forced candidates."""
from __future__ import annotations

import hashlib
import json
import os

from . import cache
from .common import CACHE, LANG_OF

WH_LANG = {"en": "en", "fr": "fr", "de": "de"}


def tf_candidates(text: str, lang: str) -> list[str]:
    t = " ".join(text.strip().split())
    core = t.rstrip(".!?… ").rstrip()
    if not core:
        return [t] if t else []
    forms = [core, core[:1].upper() + core[1:], core.lower()]
    if lang == "de":
        forms.append(" ".join(w[:1].upper() + w[1:] for w in core.split(" ")))
    ends = ["", ".", "!", "?"] + ([" ?", " !"] if lang == "fr" else [])
    out = [t]
    for f in forms:
        for e in ends:
            if f + e not in out:
                out.append(f + e)
    return out


def whisper_job(item: dict) -> dict:
    lang = WH_LANG[item["lang"]]
    return {"wav": item["wav"], "lang": lang, "prompts": [item["text"]], "tf": tf_candidates(item["text"], lang)}


def texts(item: dict) -> dict:
    """What the cache holds for the item: {"free": text or None, "prompt": text or None, "lp_free", "lp_target",
    "tf_form": the best surface form}.  None where not computed."""
    lang = WH_LANG[item["lang"]]
    have = cache.wh_all(item["wav"])
    free = have.get(cache.wh_key(lang))
    prompted = have.get(cache.wh_key(lang, item["text"]))
    out = {"free": free["text"] if free else None, "prompt": prompted["text"] if prompted else None,
           "lp_free": None, "lp_target": None, "tf_form": None}
    if free and free["text"]:
        r = have.get(cache.tf_key(lang, free["text"]))
        if r and r.get("lp") is not None:
            out["lp_free"] = r["lp"]
    best = None
    for c in tf_candidates(item["text"], lang):
        r = have.get(cache.tf_key(lang, c))
        if r and r.get("lp") is not None and (best is None or r["lp"] > best[0]):
            best = (r["lp"], c)
    if best:
        out["lp_target"], out["tf_form"] = best
    return out


# ------------------------------------------------------------------ the engine's own "understood" (15 October)
# The rule (the words of the text are the phrase's, or the text has the target's sounds, its German respellings tried)
# is the engine's `understood` / `sameSounds`; the lab asks the engine (`neolingo batch`, lab/batch.py) and remembers
# the answer on disk, keyed by (variant, phrase, target, text).  The batch needs the sounds of every text `sameSounds`
# asks about: the text's respellings (`readings` below: the texts the engine's environment is asked for).
_UFILE = CACHE / "understood.json"
_U: dict | None = None
_UDIRTY = False
_PRIMED = False
_KINDS = [[("a", "e", "ä"), ("A", "e", "Ä")], [("o", "e", "ö"), ("O", "e", "Ö")],
          [("u", "e", "ü"), ("U", "e", "Ü")], [("s", "s", "ß")]]


def _respell(a, b, c, cs):
    out, i = [], 0
    while i < len(cs):
        if i + 1 < len(cs) and cs[i] == a and cs[i + 1] == b:
            out.append(c)
            i += 2
        else:
            out.append(cs[i])
            i += 1
    return out


def readings(variant: str, text: str) -> list[str]:
    """The texts the engine's sameSounds asks the sounds of (German: ae ä, oe ö, ue ü, ss ß, in every combination)."""
    if variant.split("-")[0] != "de":
        return [text]
    acc = [list(text)]
    for k in _KINDS:
        acc = acc + [_respell_all(k, l) for l in acc]
    out = []
    for l in acc:
        s = "".join(l)
        if s not in out:
            out.append(s)
    return out


def _respell_all(k, l):
    x = l
    for (a, b, c) in k:
        x = _respell(a, b, c, x)
    return x


def _ukey(variant, phrase, target, text):
    return hashlib.sha1(json.dumps([variant, phrase, target, text], ensure_ascii=False).encode("utf-8")).hexdigest()


def _uload():
    global _U
    if _U is None:
        try:
            _U = json.loads(_UFILE.read_text("utf-8"))
        except (OSError, ValueError):
            _U = {}
    return _U


def _usave():
    if _UDIRTY and _U is not None:
        CACHE.mkdir(parents=True, exist_ok=True)
        tmp = _UFILE.with_suffix(f".{os.getpid()}.tmp")
        tmp.write_text(json.dumps(_U), "utf-8")
        os.replace(tmp, _UFILE)


import atexit  # noqa: E402
atexit.register(_usave)


def understood_many(asks, target_ipa_fn):
    """asks: [(variant, phrase, target, text)] -> [bool]: the engine's answers (cached)."""
    global _UDIRTY, _PRIMED
    U = _uload()
    if not _PRIMED and any(_ukey(*a) not in U for a in asks):
        _PRIMED = True                       # the first miss: ask once for every item of the lab's data sets
        from .run import items as all_items
        from .analyse import target_of
        prime(all_items(), target_ipa_fn, target_of)
        U = _uload()
    todo = {}
    for (v, ph, tg, tx) in asks:
        k = _ukey(v, ph, tg, tx)
        if k not in U and k not in todo:
            todo[k] = {"id": k, "variant": v, "phrase": ph, "target": tg, "text": tx, "heard": [], "flags": [],
                       "readings": [{"text": r, "ipa": target_ipa_fn(r, v)} for r in readings(v, tx)] if tx else []}
    if todo:
        from . import batch
        from .costs import host_config
        res = batch.run(host_config(), list(todo.values()))
        for k, r in res.items():
            U[k] = bool(r["understood"])
        _UDIRTY = True
    return [U[_ukey(v, ph, tg, tx)] for (v, ph, tg, tx) in asks]


def understood(target_ipa_fn, variant, phrase, target, text) -> bool:
    return understood_many([(variant, phrase, target, text)], target_ipa_fn)[0]


def prime(items, target_ipa_fn, target_of_fn):
    """Ask the engine once for every item's free and prompted texts (one batch run instead of one per item)."""
    asks = []
    for it in items:
        tx = texts(it)
        tgt = it["target"] if it.get("target") else target_of_fn(it["text"], it["variant"])
        for t in (tx["free"], tx["prompt"]):
            if t is not None:
                asks.append((it["variant"], it["text"], tgt, t))
    if asks:
        understood_many(asks, target_ipa_fn)
    _usave()


def decide(rule, item: dict, target, target_ipa_fn, tx: dict | None = None):
    """-> (understood: bool | None, the text shown as heard).  None when the cache lacks what the rule needs."""
    tx = tx or texts(item)
    v, phrase = item["variant"], item["text"]
    kind = rule[0] if isinstance(rule, (tuple, list)) else rule
    if kind == "free":
        if tx["free"] is None:
            return None, None
        return understood(target_ipa_fn, v, phrase, target, tx["free"]), tx["free"]
    if kind == "prompt":
        if tx["prompt"] is None:
            return None, None
        return understood(target_ipa_fn, v, phrase, target, tx["prompt"]), tx["prompt"]
    if kind in ("tf", "either"):
        m = float(rule[1])
        if tx["free"] is None:
            return None, None
        base = understood(target_ipa_fn, v, phrase, target, tx["free"])
        if kind == "either" and base:
            return True, tx["free"]
        if not tx["free"]:
            return False, tx["free"]
        if tx["lp_free"] is None or tx["lp_target"] is None:
            return None, tx["free"]
        return tx["lp_target"] >= tx["lp_free"] - m, tx["free"]
    raise ValueError(f"unknown understood rule {rule!r}")
