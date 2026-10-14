"""The "understood" rules (part D) and the Whisper jobs they need.

  free     the live rule: the words of the free transcription equal the target's, or the transcription has the same
           sounds (German respellings tried): `engine_py.understood`
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

from . import cache
from . import engine_py as E
from .common import LANG_OF

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


def decide(rule, item: dict, target, target_ipa_fn, tx: dict | None = None):
    """-> (understood: bool | None, the text shown as heard).  None when the cache lacks what the rule needs."""
    tx = tx or texts(item)
    v, phrase = item["variant"], item["text"]
    kind = rule[0] if isinstance(rule, (tuple, list)) else rule
    if kind == "free":
        if tx["free"] is None:
            return None, None
        return E.understood(target_ipa_fn, v, phrase, target, tx["free"]), tx["free"]
    if kind == "prompt":
        if tx["prompt"] is None:
            return None, None
        return E.understood(target_ipa_fn, v, phrase, target, tx["prompt"]), tx["prompt"]
    if kind in ("tf", "either"):
        m = float(rule[1])
        if tx["free"] is None:
            return None, None
        base = E.understood(target_ipa_fn, v, phrase, target, tx["free"])
        if kind == "either" and base:
            return True, tx["free"]
        if not tx["free"]:
            return False, tx["free"]
        if tx["lp_free"] is None or tx["lp_target"] is None:
            return None, tx["free"]
        return tx["lp_target"] >= tx["lp_free"] - m, tx["free"]
    raise ValueError(f"unknown understood rule {rule!r}")
