"""`analyse(item, config) -> record`: one take against one target under one configuration.

A configuration (all keys optional; the defaults are the live pipeline):

    model      phone model id; default: the language's (env.variants.phone_model)
    heard      "greedy" | "V1" | "V2" | "V3" | "V4"         what counts as heard (part A)
    tau        V4: keep an edit iff its likelihood ratio >= tau
    ins        "all" | "edges" | "lr"                         extra heard sounds
    tau_ins    for ins == "lr"
    unchecked  "baseline" | "unjudged" | "phoneme" | "phoneme_lr"   target sounds the check marks unchecked
    tau_unrel  for "phoneme_lr" (default 2.0)
    converse   bool: where greedy agrees with the target but the check says off, take the check's alternative
    del_accept bool: leaving out a target sound costs 1000 x (1 - w), w the weight of "∅" on that sound's accept list
               (German ə, ʔ, ɜ; English ə; French ə); the engine itself has one deletion cost, 1000
    keep_del   bool: the heard rule (V1 to V4) applies to substitutions only; every deletion of the greedy reading is kept
    zero_equal bool: a heard sound that the language's table makes free for the target (tolerated, or accepted at
               full weight; not an `unreliable` target) is shown as the target sound (display only: the score is the same)
    cost       "raw" | "stretched" | ("tx", p, F, k, extra)   (part B; the tuple: the third run, host/engine_config.apply_candidate)
    curve      "sqrt" | "linear"
    scale      the sqrt curve's scale (default the live 2250000)
    vocal_r12  bool, German only (third run, B): the engine's splits (data/splits.json: ɜ/ɐ heard as r or ɾ with a
               schwa, cost 0) in the configuration; until 15 October the lab emulated them
    length     "v2" (live: a substitution that differs only by a length mark is kept, like any other, only where
               the check flags the sound) | "count" (third run, C: every such substitution of the free reading kept)
    understood "free" | "prompt" | ("tf", m) | ("either", m)  (part D)

The steps:
  1. target sounds: env.target_ipa, then the engine's norm
  2. greedy heard sounds: the phone model's own decode, cut as env.hear cuts it
  3. the sound check per target sound (lab/check.py)
  4. the alignment of the target with the greedy sounds (the engine's `align` under the configuration's costs)
  5. each difference of that alignment is an EDIT at a target sound (a substitution, a deletion) or between two
     (an insertion); the configuration decides which edits are kept; an edit not kept is undone (the heard sound there
     is taken to be the target's; an extra sound is dropped)
  6. the FINAL heard sequence, its score and its alignment (the engine's `score` and `align` again)
  7. per target sound a kind: ok | near | off | missing | unjudged, and the `added` sounds
  An empty greedy reading is the engine's "nothing recognised": score 0, no columns, under every configuration.

Rules of step 5, for an edit at target sound i with the check's level L (lab/check.py) and alternative A:
  greedy  keep
  V1      keep iff L == off
  V2      keep iff L in (check, off)
  V3      keep iff L == off, or L == check and A agrees with the greedy sound (the same sound; "left out" for a deletion)
  V4      keep iff LR(edit) >= tau
  For V1 to V3 a sound with NO verdict (L None: the check could not run) or an `unchecked` one keeps the greedy edit:
  there is nothing to verify it with.  For V4 an edit whose ratio cannot be computed is kept.
  unchecked == "unjudged": every target sound with L == unchecked is not judged: heard := target, kind `unjudged`.
  unchecked == "phoneme":  a substitution at such a sound is kept (at the plain panphon cost) iff the greedy sound is a
                           full vowel of the language that is not a rendering of the target (PHONEME_KEEP); otherwise the
                           sound is `unjudged`; a deletion there follows the rule above.
  unchecked == "phoneme_lr": as "phoneme", and the substitution must also pass the likelihood-ratio test of V4 with
                           threshold tau_unrel (log P(target with the sound replaced) - log P(target) >= tau_unrel).

`near`: the sounds differ and the pair costs under 340 thousandths under the configuration's costs, or the language's
table accepts it (lowers its cost).  `off`: they differ and it costs 340 or more."""
from __future__ import annotations

import atexit
import json
from functools import lru_cache

from . import align as AL
from . import cache, check
from . import costs as K
from . import understood as U
from .common import BASE_MODEL, CACHE, PKL, flat, norm

SIGNIFICANT = 340          # the lab's own near / off line on its columns (Miolingo's _SIGNIFICANT, thousandths)
NOT_ENGINE = ("del_accept",)   # a lab variant the engine cannot be given (one deletion cost): it needed lab/archive/engine_py.py

BASELINE = {"heard": "greedy", "ins": "all", "unchecked": "baseline", "converse": False, "cost": "raw",
            "curve": "sqrt", "understood": "free"}

# Full vowels of each language in the target's (espeak) symbols, and the classes that are "another rendering".
FRONT_ROUNDED = {"y", "yː", "ʏ", "ʏː", "ø", "øː", "œ", "œː", "ɵ", "ʉ", "ʉː"}
FULL_VOWELS = {
    "de": {"i", "iː", "ɪ", "e", "eː", "ɛ", "ɛː", "a", "aː", "ɑ", "ɑː", "u", "uː", "ʊ", "o", "oː", "ɔ"},
    "en": {"i", "iː", "ɪ", "ɛ", "a", "æ", "ɑː", "ɒ", "ɔː", "ʊ", "uː", "ʌ", "ɜː", "e", "o", "u", "ɑ", "ɔ"},
    "fr": set(),
}

# ------------------------------------------------------------------ target sounds (cached on disk: espeak is slow)
_TFILE = CACHE / "target_ipa.json"
_TCACHE: dict | None = None
_TDIRTY = False


def _save_targets():
    if _TDIRTY and _TCACHE is not None:
        import os
        CACHE.mkdir(parents=True, exist_ok=True)
        tmp = _TFILE.with_suffix(f".{os.getpid()}.tmp")
        tmp.write_text(json.dumps(_TCACHE, ensure_ascii=False), "utf-8")
        os.replace(tmp, _TFILE)


atexit.register(_save_targets)


def target_ipa(text: str, variant: str):
    """env.target_ipa(text, variant), remembered on disk (the data file ipa_exceptions.json is part of the key)."""
    global _TCACHE, _TDIRTY
    if _TCACHE is None:
        try:
            _TCACHE = json.loads(_TFILE.read_text("utf-8"))
        except (OSError, ValueError):
            _TCACHE = {}
        import hashlib
        from .common import DATA
        stamp = hashlib.sha1((DATA / "ipa_exceptions.json").read_bytes()).hexdigest()[:8]
        if _TCACHE.get("_exceptions") != stamp:
            _TCACHE = {"_exceptions": stamp}
    k = f"{variant}|{text}"
    if k not in _TCACHE:
        import env
        _TCACHE[k] = env.target_ipa(text, variant)
        _TDIRTY = True
    return _TCACHE[k]


def target_of(text: str, variant: str):
    return norm(target_ipa(text, variant))


# ------------------------------------------------------------------ greedy heard sounds
@lru_cache(maxsize=None)
def _cut(decode: str) -> tuple:
    import env
    joined = "".join(env.norm_word(c) for c in decode.split())
    return tuple(flat(norm([env.phones_of(joined)] if joined else [])))


_DECODE: dict = {}


def greedy_of(wav, model_id: str) -> list[str]:
    k = (wav, model_id)
    if k not in _DECODE:                      # the decode string only (the third run analyses an item many times)
        _DECODE[k] = cache.get_lp(wav, model_id)["decode"]
    return list(_cut(_DECODE[k]))


@lru_cache(maxsize=None)
def _phones(s: str) -> tuple:
    import env
    return tuple(env.phones_of(env.norm_word(s)))


class ConfigCosts:
    """A lab cost variant for one language: the engine configuration it stands for (lab/costs.config_for; the engine
    aligns and costs with it), and the table's data the lab's own rules read (`unreliable`, `accepted_any`, `accepted`)
    and the cost the configuration gives a pair (`cost(t, h)`: the language's entry, else the generic one, else
    costOtherwise; the configuration's data, as protocol section 5 orders it)."""

    def __init__(self, lang, kind, unrel):
        self.lang, self.kind = lang, kind
        self.mode = "phoneme" if unrel in ("phoneme", "phoneme_lr") else "zero"
        self._cfg, self._cfg_split, self._idx = None, None, None
        tab = K.table(lang)
        self.unreliable = tab.unreliable
        self.accepted_any = tab.accepted_any
        plain = K.config_for("raw", self.mode)
        self._plain_lang = {(e["target"], e["heard"]): e["cost"] for e in plain["costs"] if e.get("lang") == lang}
        self._plain_gen = {(e["target"], e["heard"]): e["cost"] for e in plain["costs"] if "lang" not in e}
        self._plain_other = plain["costOtherwise"]

    def config(self, splits=False):
        if splits:
            if self._cfg_split is None:
                self._cfg_split = K.config_for(self.kind, self.mode, True)
            return self._cfg_split
        if self._cfg is None:
            self._cfg = K.config_for(self.kind, self.mode)
        return self._cfg

    def __call__(self, t, h):
        if t == h:
            return 0
        if self._idx is None:
            c = self.config()
            self._idx = ({(e["target"], e["heard"]): e["cost"] for e in c["costs"] if e.get("lang") == self.lang},
                         {(e["target"], e["heard"]): e["cost"] for e in c["costs"] if "lang" not in e},
                         c["costOtherwise"])
        lang, gen, other = self._idx
        x = lang.get((t, h))
        return gen.get((t, h), other) if x is None else x

    def accepted(self, t, h):
        """The language's table lowers this pair (on the plain costs, before any candidate transform)."""
        return t != h and (t, h) in self._plain_lang and \
            self._plain_lang[(t, h)] < self._plain_gen.get((t, h), self._plain_other)


@lru_cache(maxsize=None)
def costs_for(lang: str, kind, unrel: str):
    return ConfigCosts(lang, kind, unrel)


def engine_align(cost, variant, target, heard, splits=False):
    """The engine's own alignment (lab/align.py) under the variant's configuration -> [(t, h, cost)], a split's heard
    sounds a tuple."""
    a = AL.aligner("lab")
    a.configure(cost.config(splits))
    return AL.pairs(a.align(variant, target, list(heard)))


def phoneme_keep(lang: str, t: str, h: str, costs) -> bool:
    """unchecked == "phoneme": is the greedy sound h a different full vowel of the language (not a rendering of t)?"""
    if h not in FULL_VOWELS.get(lang, ()):
        return False
    if t in FRONT_ROUNDED and h in FRONT_ROUNDED:
        return False
    return not costs.accepted_any(t, h)


def unreliable_subs(lang: str, target, greedy: list[str], phones: list[dict], lr_of, tau: float = 2.0,
                    variant: str = None, aligner=None) -> list:
    """The A5 "phoneme+lr" rule ALONE (unchecked == "phoneme_lr", as in `analyse`): the substitutions of the free
    reading `greedy` at target sounds the check leaves `unchecked` that the rule KEEPS: the greedy sound is a full vowel
    of the language that is not a rendering of the target (`phoneme_keep`) AND log P(target with that vowel) -
    log P(target) >= tau.  `phones`: the per-sound verdicts (check.phones_from_tokens); `lr_of(edits)` gives the ratios
    (check.lr_from_lp on the take's log-probabilities).  The alignment is the ENGINE's (`align`, protocol section 2;
    15 October): `aligner(variant, target, heard)` answers it, the host's own engine connection on the real host;
    without one, the lab's engine given the host's configuration (lab/align.py).  -> [(i, heard sound, ratio)], i the
    flat index of the target sound.  The host's env.sounds emits a flag for each (German), so that the engine's V2 keeps
    exactly these substitutions."""
    tab = K.table(lang)
    T = flat(target)
    variant = variant or lang
    if aligner is None:
        a = AL.aligner("host")
        a.configure(K.host_config())
        aligner = a.align
    ph = list(phones)
    for a, p in enumerate(ph):                   # as in `analyse`: no verdict at an `unreliable` target -> unchecked
        if p["level"] is None and a < len(T) and T[a] in tab.unreliable:
            ph[a] = {**p, "level": "unchecked"}
    subs, i = [], 0
    for (t, h, _c) in AL.pairs(aligner(variant, target, list(greedy))):
        if t is None:
            continue
        if isinstance(h, str) and h != t and i < len(ph) and ph[i]["level"] == "unchecked" and phoneme_keep(lang, t, h, tab):
            subs.append((i, h))
        i += 1
    if not subs:
        return []
    vals = lr_of([("sub", i, h) for (i, h) in subs])
    return [(i, h, v) for (i, h), v in zip(subs, vals) if v is not None and v >= tau]


def length_only(t: str, h) -> bool:
    """t and h differ, and only by length marks (iː / i, a / aː)."""
    return h is not None and h != t and h.replace("ː", "").replace("ˑ", "") == t.replace("ː", "").replace("ˑ", "")


# ------------------------------------------------------------------ the analysis
def analyse(item: dict, config: dict | None = None) -> dict:
    cfg = {**BASELINE, **(config or {})}
    lang, variant, wav = item["lang"], item["variant"], item["wav"]
    model = cfg.get("model") or BASE_MODEL[lang]
    target = item["target"] if item.get("target") else target_of(item["text"], variant)
    T = flat(target)
    G = greedy_of(wav, model)
    cost = costs_for(lang, cfg["cost"], cfg["unchecked"])
    if any(cfg.get(k) for k in NOT_ENGINE):
        raise NotImplementedError(f"{[k for k in NOT_ENGINE if cfg.get(k)]}: not a configuration of the engine")
    splits = bool(cfg.get("vocal_r12")) and lang == "de"     # the engine's splits (data/splits.json) since 15 October
    has_check = model != PKL
    chk = check.verdicts(wav, model, target, variant) if (has_check and T) else \
        {"ran": False, "note": "no check for this model", "tokens": [], "flags": [], "dropped": 0,
         "phones": [{"level": None, "p_ok": None, "alt": None} for _ in T]}
    ph = chk["phones"]
    # the free reading's alignment, the engine's own; a split that costs nothing is the target's sound (the engine
    # draws an unflagged split so, and a flagged one at cost 0 costs nothing)
    a0 = engine_align(cost, variant, target, G, splits) if G else [(t, None, 1000) for t in T]
    al0 = [(t, t) if (isinstance(h, tuple) and c == 0) else (t, h) for (t, h, c) in a0]
    cost0 = [c for (_t, _h, c) in a0]

    # the edits of the greedy alignment
    edits, i = [], 0                                        # (kind, i, h, column index)
    for c, (t, h) in enumerate(al0):
        if t is None:
            edits.append(("ins", i, h, c))
        else:
            if h is None:
                edits.append(("del", i, None, c))
            elif h != t:
                edits.append(("sub", i, h, c))
            i += 1
    # a target sound the check cannot judge: level "unchecked"; where the check gave no verdict at all (too short to
    # check, no token covering it) the language's `unreliable` list decides, so that A5 does not depend on the check
    # having run
    for a, p in enumerate(ph):
        if p["level"] is None and a < len(T) and T[a] in cost.unreliable:
            ph[a] = {**p, "level": "unchecked"}

    need_lr = cfg["heard"] == "V4" or cfg["ins"] == "lr" or cfg["unchecked"] == "phoneme_lr"
    lr = {}
    if need_lr and edits and has_check:
        ask = edits
        if cfg["heard"] != "V4" and cfg["ins"] != "lr":
            # only the ü/ö rule reads ratios: those of substitutions at `unchecked` sounds (each edit's ratio is
            # computed on its own, so asking fewer changes no value; it keeps the cache key stable when costs move
            # the other edits: the third run)
            ask = [e for e in edits if e[0] == "sub" and e[1] < len(ph) and ph[e[1]]["level"] == "unchecked"]
        ask = [e for e in ask if not isinstance(e[2], tuple)]       # a split has no ratio
        if ask:
            vals = check.lr_edits(wav, model, target, variant,
                                  [(k, i) if k == "del" else (k, i, h) for (k, i, h, _c) in ask])
            lr = {e[3]: v for e, v in zip(ask, vals)}
    unj = set()
    if cfg["unchecked"] in ("unjudged", "phoneme", "phoneme_lr"):
        unj = {a for a, p in enumerate(ph) if p["level"] == "unchecked"}
    keep = {}
    for (k, i, h, c) in edits:
        if k == "ins":
            if cfg["ins"] == "edges":
                keep[c] = 0 < i < len(T)
            elif cfg["ins"] == "lr" and not isinstance(h, tuple):
                v = lr.get(c)
                keep[c] = v is None or v >= cfg.get("tau_ins", 0.0)
            else:
                keep[c] = True
            continue
        L = ph[i]["level"] if i < len(ph) else None
        if L == "unchecked" and cfg["unchecked"] == "unjudged":
            keep[c] = False
            continue
        if L == "unchecked" and cfg["unchecked"] in ("phoneme", "phoneme_lr") and k == "sub":
            keep[c] = phoneme_keep(lang, T[i], h, cost)
            if keep[c] and cfg["unchecked"] == "phoneme_lr":        # ... and the likelihood ratio confirms it
                v = lr.get(c)
                keep[c] = v is not None and v >= cfg.get("tau_unrel", 2.0)
            if keep[c]:
                unj.discard(i)
            continue
        rule = cfg["heard"]
        if k == "del" and cfg.get("keep_del"):        # lab variant: the verified rules judge substitutions only
            rule = "greedy"
        if k == "sub" and cfg.get("length") == "count" and length_only(T[i], h):
            rule = "greedy"                           # third run, C: a length-only difference is counted unflagged too
        if rule == "greedy":
            keep[c] = True
        elif rule == "V4":
            v = lr.get(c)
            keep[c] = v is None or v >= cfg.get("tau", 0.0)
        elif L is None or L == "unchecked":
            keep[c] = True
        elif rule == "V1":
            keep[c] = L == "off"
        elif rule == "V2":
            keep[c] = L in ("check", "off")
        elif rule == "V3":
            alt = ph[i]["alt"]
            agrees = (alt == "" and k == "del") or (k == "sub" and alt == h)
            keep[c] = L == "off" or (L == "check" and agrees)
        else:
            raise ValueError(f"unknown heard rule {rule!r}")
        if L == "unchecked" and cfg["unchecked"] in ("phoneme", "phoneme_lr") and keep[c]:
            unj.discard(i)

    # the final heard sequence
    H, i = [], 0
    for c, (t, h) in enumerate(al0):
        if t is None:
            if keep[c]:
                H.append(h)
            continue
        if h == t:
            p = ph[i] if i < len(ph) else {}
            if cfg["converse"] and p.get("level") == "off" and p.get("alt") is not None:
                if p["alt"] != "":
                    alt = list(_phones(p["alt"]))
                    H += alt if alt and alt != [t] else [t]
            else:
                H.append(t)
        elif keep[c]:
            if h is not None:
                # zero_equal: a pair the language's table makes free (tolerated, or accepted at full weight) is
                # shown as the target sound; an `unreliable` target is left to the A5 rule
                if cfg.get("zero_equal") and cost0[c] == 0 and t not in cost.unreliable:
                    H.append(t)
                elif isinstance(h, tuple):
                    H.extend(h)                 # a split kept: its two heard sounds
                else:
                    H.append(h)
        else:
            H.append(t)
        i += 1

    nothing = not G
    if nothing:
        # the recogniser heard nothing: the engine answers "nothing recognised", score 0, no columns (checked on the
        # real engine).  No heard rule may fill the target in from nothing (the check, given the target, can still
        # rate its sounds "ok" when nothing was heard): every variant keeps this case as it is.
        H = []
    # the final heard sequence: aligned and costed by the engine; the score is the configuration's curve of that
    # distance (protocol section 5)
    afin = engine_align(cost, variant, target, H, splits) if not nothing else []
    al = [(t, "‿".join(h) if isinstance(h, tuple) else h) for (t, h, _c) in afin]
    cfin = [c for (_t, _h, c) in afin]
    d = sum(cfin)
    n = max(len(T), len(H))
    sc = K.curve(d, n, cfg["curve"], cfg.get("scale") or K.SCALE) if not nothing else 0
    kinds, i = [], 0
    for (t, h), cc in zip(al, cfin):
        if t is None:
            kinds.append("added")
            continue
        if h is None:
            kinds.append("missing")
        elif h == t:
            kinds.append("unjudged" if i in unj else "ok")
        else:
            kinds.append("near" if (cc < SIGNIFICANT or ("‿" not in h and cost.accepted(t, h))) else "off")
        i += 1
    cols = [(t, h, k) for (t, h), k in zip(al, kinds)]
    judged = [p["p_ok"] for p in ph if p["level"] in ("ok", "check", "off")]
    tx = U.texts(item)
    und, heard_text = U.decide(cfg["understood"], item, target, target_ipa, tx)
    return {
        "id": item["id"], "set": item["set"], "lang": lang, "variant": variant, "text": item["text"], "model": model,
        "target": target, "greedy": G, "heard": H, "score": sc, "dist": d, "n": n,
        "understood": und, "heard_text": heard_text,
        "align0": al0, "kept": [keep.get(c) for c in range(len(al0))],
        "lr": [lr.get(c) for c in range(len(al0))] if need_lr else None,
        "columns": cols, "check": ph, "check_ran": chk["ran"], "flags": chk["flags"], "dropped_flags": chk["dropped"],
        "score_check": round(100 * sum(judged) / len(judged)) if judged else None,
        "n_diff": sum(k in ("near", "off", "missing", "added") for k in kinds),
        "n_cost": sum(1 for (t, h), cc in zip(al, cfin) if t is None or h is None or (t != h and cc > 0)),
        "costs": cfin,
        "n_unjudged": sum(k == "unjudged" for k in kinds),
        "n_warn": len(chk["flags"]),
        "nothing": nothing,
    }


def word_columns(rec: dict):
    """The record's columns by the target's words, for a lab deck: [[(t, h, kind)]]: a column with a target sound in
    that sound's word, an added sound with the word of the paired column before it (the first word when none).  The
    engine's own picture (by word) is what lab/batch.py returns; this groups the lab's records the same way."""
    lens = [len(w) for w in rec["target"]]
    out = [[] for _ in range(max(1, len(lens)))]

    def word_of(k):
        tot = 0
        for w, n in enumerate(lens):
            tot += n
            if k < tot:
                return w
        return len(lens) - 1

    k, lastw = 0, 0
    for (t, h, kind) in rec["columns"]:
        if t is not None and h is not None:
            w = word_of(k)
            out[w].append((t, h, kind))
            k, lastw = k + 1, w
        elif t is not None:
            out[word_of(k)].append((t, h, kind))
            k += 1
        else:
            out[lastw].append((t, h, kind))
    return out
