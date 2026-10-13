"""`sounds`: Miolingo's sound check, GIVEN the target."""
from __future__ import annotations

import unicodedata

from . import _miolingo as mio
from .hearing import _LOCK
from .ipa import norm_word
from .variants import variant

STRIP = mio.sound_check.STRIP
DEL = mio.sound_check.DEL


def _map_tokens_to_phones(words: list[list[str]], ref: list[tuple[str, int]],
                          hidden: set[int]) -> dict[int, tuple[int, int]]:
    """Map index in the recogniser's token list -> (flat index of the first
    target phone it covers, flat index of the last), by character offset
    within the word."""
    spans: list[tuple[int, int, int, int]] = []   # (word, start, end, flat)
    flat = 0
    for wi, ph in enumerate(words):
        pos = 0
        for p in ph:
            q = unicodedata.normalize("NFC", "".join(c for c in p if c not in STRIP))
            spans.append((wi, pos, pos + len(q), flat))
            pos += len(q)
            flat += 1
    out: dict[int, tuple[int, int]] = {}
    cur_word, off = None, 0
    for i, (tok, wi) in enumerate(ref):
        if i in hidden:
            continue
        if wi != cur_word:
            cur_word, off = wi, 0
        end = off + len(tok)
        cover = [f for (w, a, b, f) in spans if w == wi and a < end and b > off]
        if not cover:                        # beyond what is left: last phone of the word
            cover = [max((f for (w, a, b, f) in spans if w == wi), default=0)]
        out[i] = (min(cover), max(cover))
        off = end
    return out


def sounds(wav_path: str, target: list[list[str]], variant_code: str) -> list[dict]:
    """The sound check.  `target` is `target_ipa(...)`.

    Returns, for each target sound flagged:
      at    index of the sound in the flat sequence of the target's phones
            (word 0's phones, then word 1's, ...); if the recogniser's token
            covers several phones ("ju" for j + u) it is the first of them
            and `span` is how many;
      off   True = "probably off", False = "worth checking";
      like  what it sounded like ("" if left out or unknown);
      left_out  True if the sound sounded left out;
      sound the target sound as the recogniser's token (normalised);
            Miolingo's French model writes a nasal vowel as two tokens
            (vowel, then U+0303), so that gives two flags at one `at`;
      word  index of the word it is in.
    Length marks are kept (a long sound is another sound): `sound` and `like` carry them
    attached ("iː"); a flag whose `like` equals its `sound` is dropped.
    [] when nothing is flagged, or when the check cannot run (a model
    without a CTC vocabulary, or a take too short for the target)."""
    v = variant(variant_code)
    words = [w for w in target if w]
    ipa_str = " ".join("".join(w) for w in words)
    if not ipa_str:
        return []
    with _LOCK:
        got = mio.phone_recognizer.log_probs_from_audio(wav_path, v["espeak"])
        if got is None:
            return []
        lp, vocab, blank, model_id = got
        res = mio.sound_check.score(lp, vocab, blank, ipa_str, v["espeak"], model_id)
    if not res.phones:
        return []
    ref = mio.sound_check.tokenize(ipa_str, vocab)
    hidden: set[int] = set()
    cfg = mio.sound_check.lang_config(v["espeak"])
    if cfg.get("glottal_onsets") and "ʔ" in vocab:
        ref = mio.sound_check._with_glottal_onsets(ref)
        hidden = {i for i, (t, _) in enumerate(ref) if t == "ʔ"}
    visible = [i for i in range(len(ref)) if i not in hidden]   # res.phones skips hidden
    place = _map_tokens_to_phones(words, ref, hidden)
    out = []
    for pv, i in zip(res.phones, visible):
        if pv.level not in ("check", "off"):
            continue
        first, last = place.get(i, (0, 0))
        like = "" if pv.heard in (None, DEL) else norm_word(pv.heard)
        sound = norm_word(pv.phone) or pv.phone
        if like and like == sound:
            continue
        out.append({"at": first, "span": last - first + 1, "off": pv.level == "off",
                    "like": like, "left_out": pv.heard == DEL,
                    "sound": sound, "word": pv.word_index})
    return out
