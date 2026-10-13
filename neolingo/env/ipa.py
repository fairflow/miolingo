"""`norm` and `target_ipa`."""
from __future__ import annotations

import re
import unicodedata

from . import _miolingo as mio
from .variants import variant

# The spec's `norm`: stress marks, length marks and punctuation removed; kept:
# letters, the linking mark U+203F, the tie bars U+0361/U+035C (combining).
_STRESS_LENGTH = set("ˈˌːˑ")
_KEEP = {"‿"}


def norm_word(s: str) -> str:
    """Normalise one word of IPA (a string); no spaces inside."""
    out = []
    for ch in unicodedata.normalize("NFC", s):
        if ch in _KEEP:
            out.append(ch)
        elif ch in _STRESS_LENGTH:
            continue
        elif ord(ch) < 128 and not ch.isalpha():   # ASCII non-letters
            continue
        elif unicodedata.category(ch).startswith("P") or unicodedata.category(ch) == "Zs":
            continue
        else:
            out.append(ch)
    return "".join(out)


def phones_of(word: str) -> list[str]:
    """Cut a normalised word into phones with Miolingo's own segmenter
    (panphon), as its scorer does.  The linking mark is kept as an element of
    its own only if present."""
    parts = word.split("‿")
    segs: list[str] = []
    for k, part in enumerate(parts):
        if k > 0:
            segs.append("‿")
        segs += [unicodedata.normalize("NFC", s)
                 for s in mio.phone_distance._FT.ipa_segs(
                     unicodedata.normalize("NFD", part))]
    return [s for s in segs if s]


def _text_words(text: str) -> list[str]:
    """Words of the text: split at spaces; tokens with no letter or digit
    (a lone '/' or '-') are dropped."""
    return [t for t in text.replace("’", "'").split()
            if any(c.isalnum() for c in t)]


def _espeak(text: str, espeak_voice: str) -> str:
    s = mio.phonemes.get_ipa(text, espeak_voice)   # lru-cached in Miolingo
    if s.startswith("[IPA unavailable"):
        raise RuntimeError(f"espeak-ng failed on {text!r} ({espeak_voice})")
    return s


def target_ipa(text: str, variant_code: str) -> list[list[list[str]]]:
    """The target sounds of a phrase: a list of words, each a list of phones.

    espeak-ng is run on the whole phrase (so liaison and elision are as
    Miolingo's `get_ipa` gives them).  A "word" is a space-separated token
    of the text.  If espeak's words do not line up one-to-one with the
    text's tokens (it can merge or split across a space), each token is
    transcribed on its own instead, so `len(result) == number of tokens`
    always holds.  Normalised by `norm_word`: no stress, no length marks,
    no punctuation."""
    v = variant(variant_code)
    toks = _text_words(text)
    if not toks:
        return []
    whole = _espeak(" ".join(toks), v["espeak"]).split()
    if len(whole) != len(toks):
        whole = [w for t in toks for w in [" ".join(_espeak(t, v["espeak"]).split())]]
    out = [phones_of(norm_word(w.replace(" ", ""))) for w in whole]
    return out
