"""
Sound check: which sounds of the target phrase were probably off, and what was
probably said instead. Language-agnostic; uses the same per-language phone
recognizer as the accuracy channel.

Method (research/phonetics/mdd/README.md, speechocean762 learner benchmark,
2026-10-08): for each expected phone, the CTC likelihood of the whole phrase
with that phone is compared against the same phrase with the phone replaced by
each other sound of the language, or deleted. The softmax over those hypotheses
gives the probability that the expected sound was said. On learner English this
ranked real errors below accepted sounds 92% of the time (AUC 0.92) with xlsr-53.

Listeners accept many phonetic variants (e.g. vocalised German r). Per-language
accept lists (data/sound_check.yaml) add the probability of accepted variants
to the expected sound before flagging. Thresholds come from native speakers
(scripts/sound_check/calibrate.py): with them, few native sounds are flagged.

The check reports *likely*: it is a ranking aid, not a verdict.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Optional

import yaml

DATA = Path(__file__).parent / "data" / "sound_check.yaml"
CALIBRATED = Path(__file__).parent / "data" / "sound_check_calibrated.yaml"
STRIP = {"ˈ", "ˌ", "‿", "͡", ".", "|", "‖", "-", "ː̆"}
DEL = "∅"


@dataclass
class PhoneVerdict:
    phone: str                  # expected sound (recognizer token)
    word_index: int             # index into the phrase's words
    p_ok: float                 # probability the expected or an accepted sound was said
    level: str                  # "ok" | "check" | "off" | "unchecked" (unreliable for this language)
    heard: Optional[str]        # most likely other sound (DEL = left out), when not ok
    p_heard: float = 0.0


@dataclass
class SoundCheck:
    language: str
    model_id: str
    phones: list[PhoneVerdict] = field(default_factory=list)
    words: list[str] = field(default_factory=list)   # espeak words (IPA)
    note: str = ""

    @property
    def flagged(self) -> list[PhoneVerdict]:
        return [p for p in self.phones if p.level in ("check", "off")]

    @property
    def unchecked(self) -> list[str]:
        return sorted({p.phone for p in self.phones if p.level == "unchecked"})


@lru_cache(maxsize=None)
def config() -> dict:
    def load(p):
        return yaml.safe_load(p.read_text(encoding="utf-8")) or {} if p.exists() else {}
    return {"hand": load(DATA), "calibrated": load(CALIBRATED)}


def lang_config(voice: str) -> dict:
    """defaults <- calibrated (inventory, thresholds, accept_learned) <- hand-written.
    `accept` = learned-from-natives entries overridden by hand-written ones."""
    v = voice.lower()
    out = dict(config()["hand"].get("defaults", {}))
    for src in ("calibrated", "hand"):
        langs = config()[src].get("languages", {})
        for key in (v.split("-")[0], v):
            out.update(langs.get(key) or {})
    acc = {k: dict(d) for k, d in (out.get("accept_learned") or {}).items()}
    for k, d in (out.get("accept") or {}).items():
        acc.setdefault(k, {}).update(d)
    out["accept"] = acc
    return out


VOWEL_START = set("aeiouyøœɛɔɪʊʏæɑəɐɜɒ")


def _with_glottal_onsets(ref: list[tuple[str, int]]) -> list[tuple[str, int]]:
    """Insert an optional [ʔ] before word-initial vowels (German): speakers produce it,
    espeak does not write it. Its deletion is accepted and it is never displayed."""
    out, prev_w = [], None
    for t, wi in ref:
        if wi != prev_w and t[0] in VOWEL_START:
            out.append(("ʔ", wi))
        out.append((t, wi)); prev_w = wi
    return out


NO_MERGE = {"əl", "ən", "əm", "ɚl"}   # espeak syllabic clusters the recognizer emits split


def _usable(tok: str) -> bool:
    return tok not in NO_MERGE and not any(c in "?<>.!,:;\"'[]^0123456789" for c in tok)


def tokenize(ipa: str, vocab: dict[str, int]) -> list[tuple[str, int]]:
    """Greedy longest-match of espeak IPA into recognizer tokens: [(token, word_index)]."""
    vocab = {t: i for t, i in vocab.items() if _usable(t)}
    longest = max(len(t) for t in vocab)
    out = []
    for wi, word in enumerate(ipa.split()):
        w = unicodedata.normalize("NFC", "".join(c for c in word if c not in STRIP))
        i = 0
        while i < len(w):
            for n in range(min(longest, len(w) - i), 0, -1):
                if w[i:i + n] in vocab:
                    out.append((w[i:i + n], wi)); i += n
                    break
            else:
                i += 1                      # symbol the recognizer has no token for
    return out


def _nll(lp, seqs, blank, chunk=192):
    import numpy as np
    import torch
    import torch.nn.functional as F
    T, out = lp.shape[0], []
    for s in range(0, len(seqs), chunk):
        part = seqs[s:s + chunk]
        tgt = torch.tensor([t for q in part for t in q], dtype=torch.long)
        lens = torch.tensor([len(q) for q in part], dtype=torch.long)
        x = lp[:, None, :].expand(T, len(part), lp.shape[1])
        out.append(F.ctc_loss(x, tgt, torch.full((len(part),), T, dtype=torch.long), lens,
                              blank=blank, reduction="none", zero_infinity=True).numpy())
    return np.concatenate(out) if out else np.zeros(0)


def score(log_probs, vocab: dict[str, int], blank: int, correct_ipa: str, voice: str,
          model_id: str = "") -> SoundCheck:
    """Per-phone verdicts from recognizer log-probs (T, V) and the target's espeak IPA."""
    import numpy as np
    import torch

    cfg = lang_config(voice)
    lp = log_probs if isinstance(log_probs, torch.Tensor) else torch.from_numpy(np.asarray(log_probs, dtype=np.float32))
    ref = tokenize(correct_ipa, vocab)
    hidden = set()
    if cfg.get("glottal_onsets") and "ʔ" in vocab:
        ref = _with_glottal_onsets(ref)
        hidden = {i for i, (t, _) in enumerate(ref) if t == "ʔ"}
    res = SoundCheck(voice, model_id, words=correct_ipa.split())
    if not ref or lp.shape[0] < 2 * len(ref):
        res.note = "too short to check"
        return res
    # hypotheses: the language's sounds that the recogniser gives any real weight to
    inv = [t for t in (cfg.get("inventory") or []) if t in vocab]
    seen = set(torch.nonzero(lp.max(0).values > np.log(cfg.get("min_peak", 0.02))).flatten().tolist())
    hyps = [t for t in inv if vocab[t] in seen]
    accept = cfg.get("accept") or {}
    ids = [vocab[t] for t, _ in ref]
    seqs, where = [], []
    for i, (t, _) in enumerate(ref):
        cands = set(hyps) | {t} | set((accept.get(t) or {}))
        cands = [c for c in cands if c in vocab and c != DEL]
        for c in cands:
            seqs.append(ids[:i] + [vocab[c]] + ids[i + 1:]); where.append((i, c))
        if len(ref) > 1:
            seqs.append(ids[:i] + ids[i + 1:]); where.append((i, DEL))
    ll = -_nll(lp, seqs, blank)
    per = [dict() for _ in ref]
    for (i, c), l in zip(where, ll):
        per[i][c] = float(l)
    ok_t, bad_t = float(cfg.get("ok_threshold", 0.5)), float(cfg.get("off_threshold", 0.15))
    unreliable = set(cfg.get("unreliable") or [])
    for i, (t, wi) in enumerate(ref):
        if i in hidden:
            continue
        d = per[i]
        ks = list(d)
        a = np.array([d[k] for k in ks]); a = np.exp(a - a.max()); a /= a.sum()
        post = dict(zip(ks, a))
        acc = accept.get(t) or {}
        p_ok = post.get(t, 0.0) + sum(float(w) * post.get(k, 0.0) for k, w in acc.items())
        p_ok = float(min(1.0, p_ok))
        level = "ok" if p_ok >= ok_t else "check" if p_ok >= bad_t else "off"
        if t in unreliable:
            level = "unchecked"
        others = [k for k in ks if k != t and float(acc.get(k, 0)) < 1.0]
        heard = max(others, key=lambda k: post[k]) if others and level in ("check", "off") else None
        res.phones.append(PhoneVerdict(t, wi, round(p_ok, 3), level, heard,
                                       round(float(post[heard]), 3) if heard else 0.0))
    return res


def check_audio(audio_file: str, correct_ipa: str, voice: str) -> Optional[SoundCheck]:
    """Run the voice's recognizer on a WAV and score the target IPA. None if unsupported."""
    from audio.phone_recognizer import log_probs_from_audio
    out = log_probs_from_audio(audio_file, voice)
    if out is None:
        return None
    lp, vocab, blank, model_id = out
    return score(lp, vocab, blank, correct_ipa, voice, model_id)


def as_dict(sc: SoundCheck) -> dict:
    from dataclasses import asdict
    cfg = lang_config(sc.language)
    return {**asdict(sc), "native_flag_rate": cfg.get("native_test_flag_rate"),
            "unchecked": sc.unchecked,
            "calibrated": "calibrated_on" in cfg}


def describe(sc: SoundCheck, words: Optional[list[str]] = None) -> list[str]:
    """Plain-text lines for the flagged sounds: 'ʁ in "rot": likely off (heard ɹ?)'."""
    lines = []
    for p in sc.flagged:
        w = (words[p.word_index] if words and p.word_index < len(words) else
             sc.words[p.word_index] if p.word_index < len(sc.words) else "")
        heard = ("left out" if p.heard == DEL else f"sounded like [{p.heard}]") if p.heard else ""
        lvl = "probably off" if p.level == "off" else "worth checking"
        lines.append(f"[{p.phone}] in “{w}”: {lvl}" + (f" — {heard}?" if heard else ""))
    return lines
