"""`cost_table()` and the score-curve parameters, as data.

Everything the engine needs to reproduce Miolingo's `weighted_phone` scorer
(`scoring/phone_distance.py`, `score`) as a function of data:

  cost[a][b]   base substitution cost between phones a and b, in thousandths:
               round(1000 * sum_i |f_i(a) - f_i(b)| / 48) over panphon's 24
               features (0 for a = b); symmetric.  A phone not in `phones`
               costs `unknown_cost` against anything else.
  per language (en, fr, de):
    tolerated  pairs that cost 0 (espeak allophone fold-map; none for de)
    accept     data/sound_check.yaml accept lists: {target: {heard: weight}},
               weight in thousandths; the cost is multiplied by (1 - weight)
    unreliable targets the recogniser cannot judge in this language: cost 0
    sound_check  ok/off thresholds (thousandths) of the sound check
  indel        1000;  significant   340 (a substitution >= this is "significant")
  curve        the ACCURACY channel's stretched curve:
                 each substitution cost c (in 0..1) becomes min(1, (gain*c)**exp)
                 (0 stays 0); insert/delete stay 1; the total distance is divided
                 by norm_factor*sqrt(max(m, n)); similarity = max(0, 1 - that).
               gain 4, exp 0.6, norm_factor 1.5.  (sqrt and 0.6 power have no
               exact integer form: that is the part the spec says is still
               to be calibrated.)
  legacy_curve the comprehensibility curve: gain 1, exp 1, divide by max(m, n).

Which phones: the union over en, fr, de of (a) the sound-check inventories
(data/sound_check_calibrated.yaml), (b) Miolingo's fold-map inventories (en,
fr), (c) every phone that occurs in a tolerated pair or accept list, (d) the
phones of the target IPA of the phrases in neolingo/data, and (e) the phones
of the vocabularies of the phone models for en, fr, de (tokens segmented the
way the scorer segments).  (e) needs the tokenizers in the local cache; when
they are absent it is skipped and `meta.vocab_included` says so.
"""
from __future__ import annotations

import json
import unicodedata
from pathlib import Path

from . import _miolingo as mio
from .ipa import phones_of, norm_word
from .variants import variants, variant

N_FEATURES = 24
LANGS = ("en", "fr", "de")
DATA = Path(__file__).resolve().parent.parent / "data"

CURVE = {"gain": 4.0, "exp": 0.6, "norm_factor": 1.5, "norm": "sqrt"}
LEGACY_CURVE = {"gain": 1.0, "exp": 1.0, "norm_factor": 1.0, "norm": "linear"}


def _nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def _vec(phone: str):
    return mio.phone_distance._vector(unicodedata.normalize("NFD", phone))


def _inventory_phones(lang: str) -> set[str]:
    out: set[str] = set()
    cfg = mio.sound_check.lang_config(lang)
    for t in cfg.get("inventory") or []:
        out |= set(phones_of(norm_word(t)))
    for a, d in (cfg.get("accept") or {}).items():
        out |= set(phones_of(norm_word(a)))
        for b in d:
            out |= set(phones_of(norm_word(b)))
    for t in cfg.get("unreliable") or []:
        out |= set(phones_of(norm_word(t)))
    try:
        for t in mio.fold_map.inventory(lang):
            out |= set(phones_of(norm_word(t)))
        for pr in mio.fold_map.tolerated_pairs(lang):
            for t in pr:
                out |= set(phones_of(norm_word(t)))
    except KeyError:
        pass
    return out


def _data_phones() -> set[str]:
    out: set[str] = set()
    for l in LANGS:
        f = DATA / f"{l}.json"
        if not f.exists():
            continue
        d = json.loads(f.read_text("utf-8"))
        for item in d.get("phrases", []):
            for w in item.get("ipa", []):
                out |= set(w)
    return out


def _vocab_phones() -> tuple[set[str], bool]:
    try:
        from transformers import AutoTokenizer
    except Exception:
        return set(), False
    out: set[str] = set()
    ok = False
    for mid in sorted({v["phone_model"] for v in variants() if v["lang"] in LANGS}):
        try:
            tok = AutoTokenizer.from_pretrained(mid)
        except Exception:
            continue
        ok = True
        for t in tok.get_vocab():
            if t.startswith("<") or t.startswith("[") or t in ("|",):
                continue
            n = norm_word(t)
            if n:
                out |= set(phones_of(n))
    return out, ok


def cost_table(include_vocab: bool = True) -> dict:
    phones = set()
    for l in LANGS:
        phones |= _inventory_phones(l)
    phones |= _data_phones()
    vocab_ok = False
    if include_vocab:
        vp, vocab_ok = _vocab_phones()
        phones |= vp
    phones = sorted(p for p in map(_nfc, phones) if p and _vec(p) is not None)
    vecs = [list(_vec(p)) for p in phones]
    cost = []
    for i, a in enumerate(vecs):
        cost.append([0 if i == j else round(1000 * sum(abs(x - y) for x, y in zip(a, b)) / (2 * N_FEATURES))
                     for j, b in enumerate(vecs)])
    langs = {}
    for l in LANGS:
        cfg = mio.sound_check.lang_config(l)
        # Keys are passed through `norm` (no length marks), since the engine's
        # phones are normalised; Miolingo's own tables keep e.g. "yː".  Where
        # two raw keys collapse to one, the larger weight wins.
        def n(x):
            if x == mio.sound_check.DEL:       # "deleted": kept as the symbol itself
                return x
            r = norm_word(x)
            return _nfc(r) if phones_of(r) else ""
        try:
            tol = sorted({tuple(sorted(n(x) for x in p)) for p in mio.fold_map.tolerated_pairs(l)
                          if len({n(x) for x in p}) == 2 and "" not in {n(x) for x in p}})
            tol = [list(p) for p in tol]
        except KeyError:
            tol = []
        acc: dict = {}
        for a, d in (cfg.get("accept") or {}).items():
            for b, w in d.items():
                if n(a) and n(b) and n(a) != n(b):
                    cur = acc.setdefault(n(a), {})
                    cur[n(b)] = max(cur.get(n(b), 0), round(1000 * float(w)))
        langs[l] = {
            "tolerated": tol,
            "accept": acc,
            "unreliable": sorted({n(x) for x in (cfg.get("unreliable") or []) if n(x)}),
            "sound_check": {"ok": round(1000 * float(cfg.get("ok_threshold", 0.5))),
                            "off": round(1000 * float(cfg.get("off_threshold", 0.15)))},
        }
    return {
        "meta": {"source": "Miolingo scoring/phone_distance.py (panphon feature table), "
                           "ipa/fold_map.py, scoring/data/sound_check*.yaml",
                 "n_features": N_FEATURES, "vocab_included": vocab_ok,
                 "variant_language": {v["code"]: v["lang"] for v in variants() if v["lang"] in LANGS}},
        "phones": phones,
        "features": list(mio.phone_distance._FT.names) if hasattr(mio.phone_distance._FT, "names") else [],
        "vectors": vecs,
        "cost": cost,
        "unknown_cost": 1000,
        "indel": 1000,
        "significant": round(1000 * mio.phone_distance._SIGNIFICANT),
        "curve": CURVE,
        "legacy_curve": LEGACY_CURVE,
        "langs": langs,
    }


def write_cost_table(path: str, **kw) -> dict:
    t = cost_table(**kw)
    Path(path).write_text(json.dumps(t, ensure_ascii=False, separators=(",", ":")), "utf-8")
    return t


def reference_score(heard: list[list[str]], target: list[list[str]], variant_code: str,
                    accuracy: bool = True) -> dict:
    """Miolingo's own score of `heard` against `target` (the ACCURACY curve by
    default), for checking an engine's reimplementation against the original."""
    v = variant(variant_code)
    u = " ".join("".join(w) for w in heard)
    t = " ".join("".join(w) for w in target)
    kw = dict(gain=4.0, exp=0.6, sqrt_norm=True) if accuracy else {}
    r = mio.phone_distance.score(u, t, v["espeak"], **kw)
    return {"percent": round(100 * r.similarity), "similarity": r.similarity,
            "distance": r.distance, "exact": r.exact_match}
