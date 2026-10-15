"""`norm` and `target_ipa`."""
from __future__ import annotations

import json
import logging
import re
import unicodedata
from collections import Counter
from pathlib import Path

from . import _miolingo as mio
from .variants import variant

# The engine's `norm` (since 13 October): stress marks and punctuation removed; kept: letters, the linking
# mark U+203F, the tie bars U+0361/U+035C (combining), and LENGTH MARKS (U+02D0 ː, U+02D1 ˑ): a long sound is
# another sound ("iː" is not "i"), and the mark belongs to its sound as ONE string (see `join_length`).
_STRESS = set("ˈˌ")
LENGTH = "ːˑ"
_KEEP = {"‿"}


def norm_word(s: str) -> str:
    """Normalise one word of IPA (a string); no spaces inside."""
    out = []
    for ch in unicodedata.normalize("NFC", s):
        if ch in _KEEP:
            out.append(ch)
        elif ch in _STRESS:
            continue
        elif ord(ch) < 128 and not ch.isalpha():   # ASCII non-letters
            continue
        elif unicodedata.category(ch).startswith("P") or unicodedata.category(ch) == "Zs":
            continue
        else:
            out.append(ch)
    return "".join(out)


def join_length(segs: list[str]) -> list[str]:
    """THE one place where a length mark is attached to its sound: a segment that is only length marks (a
    recogniser token "ː", or what a cutter leaves) is joined to the sound before it; one with no sound before
    it is dropped.  Every path that produces sounds ends here (`phones_of`), so no lone "ː" is ever a sound."""
    out: list[str] = []
    for s in segs:
        if s and all(c in LENGTH for c in s):
            if out and out[-1] != "‿":
                out[-1] += s
            continue
        if s:
            out.append(s)
    return out


# Symbols that espeak (en-us) and the phone recogniser (xlsr-53 espeak: tokens ɚ, ᵻ, aɪɚ) write and the segmenter does
# not know, each written as the sound espeak's British English gives in the same place (15 October; before, they were
# dropped): ɚ as ə ("better" en-us [bɛɾɚ], en-gb [bɛtə]; "doctor" [dɑːktɚ] / [dɒktə]; "hour" [aʊɚ] / [aʊə]), ᵻ as ɪ
# ("roses" en-us [ɹoʊzᵻz], en-gb [ɹəʊzɪz]; "wanted" [wɔntᵻd] / [wɒntɪd]).  So an American unstressed -er is judged as
# the British one: its r colouring is not judged (ɚ as ə followed by ɹ would judge it, but the same recogniser serves
# German, whose -er is ɐ with splits to r/ɾ and ə: a choice for the owner).
EQUIVALENT = {"ɚ": "ə", "ᵻ": "ɪ"}

_LOG = logging.getLogger("neolingo.env.ipa")
# Every symbol the segmenter could not place, as (symbol, word), since the process started: a symbol is never
# dropped silently (15 October: espeak's en-us ɚ and ᵻ were dropped without a word).  Each is also logged as a warning.
DROPPED: list[tuple[str, str]] = []


def phones_of(word: str) -> list[str]:
    """Cut a normalised word into phones with Miolingo's own segmenter
    (panphon), as its scorer does.  The linking mark is kept as an element of
    its own only if present.  ɚ and ᵻ are first written as ə and ɪ (EQUIVALENT).  A symbol the segmenter does not
    know is dropped, but never silently: it is logged as a warning and recorded in DROPPED."""
    parts = word.split("‿")
    segs: list[str] = []
    for k, part in enumerate(parts):
        if k > 0:
            segs.append("‿")
        nfd = unicodedata.normalize("NFD", "".join(EQUIVALENT.get(c, c) for c in part))
        got = mio.phone_distance._FT.ipa_segs(nfd)
        lost = Counter(nfd) - Counter("".join(got))
        for c in sorted(lost):
            DROPPED.append((unicodedata.normalize("NFC", c), word))
            _LOG.warning("a symbol the segmenter does not know was dropped: %r (U+%04X) in [%s]", c, ord(c), word)
        segs += [unicodedata.normalize("NFC", s) for s in got]
    return join_length([s for s in segs if s])


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


_EXC_FILE = Path(__file__).resolve().parent.parent / "data" / "ipa_exceptions.json"
_EXC: dict | None = None


def _word_key(token: str, keep_case: bool = False) -> str:
    """The token with everything but letters and digits removed, lower-cased unless `keep_case` (the key forms of
    ipa_exceptions.json)."""
    s = "".join(c for c in token if c.isalnum())
    return s if keep_case else s.lower()


def ipa_exceptions(lang: str) -> dict[str, str]:
    """{word key: IPA} that replaces espeak's output for those words (data/ipa_exceptions.json; keys not
    starting with "_" are language codes).  A key written in lower case matches the word in any case ("toiletten",
    "Toiletten!"); a key with a capital letter, an abbreviation, matches only the word written so (since 15 October:
    "PIN" is [pin] in French, while the word "pin", pine, stays espeak's [pɛ̃])."""
    global _EXC
    if _EXC is None:
        _EXC = json.loads(_EXC_FILE.read_text("utf-8")) if _EXC_FILE.exists() else {}
    return {(_word_key(w, True) if any(c.isupper() for c in w) else _word_key(w)): i
            for w, i in _EXC.get(lang, {}).items()}


def listed_ipa(lang: str, token: str) -> str | None:
    """The IPA data/ipa_exceptions.json lists for this word of a text, or None: the key written with capitals first
    (the word exactly as written), then the lower-case key."""
    exc = ipa_exceptions(lang)
    exact = _word_key(token, True)
    if any(c.isupper() for c in exact) and exact in exc:
        return exc[exact]
    return exc.get(_word_key(token))          # a lower-case key (a key with capitals is never all lower case)


def target_ipa(text: str, variant_code: str) -> list[list[list[str]]]:
    """The target sounds of a phrase: a list of words, each a list of phones.

    espeak-ng is run on the whole phrase (so liaison and elision are as
    Miolingo's `get_ipa` gives them).  A "word" is a space-separated token
    of the text.  If espeak's words do not line up one-to-one with the
    text's tokens (it can merge or split across a space), each token is
    transcribed on its own instead, so `len(result) == number of tokens`
    always holds.  Normalised by `norm_word`: no stress, no punctuation; length marks kept,
    attached to their sound ("iː").
    A word listed in data/ipa_exceptions.json for the variant's language uses the listed IPA (word by word)."""
    v = variant(variant_code)
    toks = _text_words(text)
    if not toks:
        return []
    whole = _espeak(" ".join(toks), v["espeak"]).split()
    if len(whole) != len(toks):
        whole = [w for t in toks for w in [" ".join(_espeak(t, v["espeak"]).split())]]
    out = []
    for t, w in zip(toks, whole):        # words espeak reads wrongly (loanwords, abbreviations): the listed IPA instead
        listed = listed_ipa(v["lang"], t)
        out.append(phones_of(norm_word((w if listed is None else listed).replace(" ", ""))))
    return out
