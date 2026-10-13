"""`gloss`: a meaning in the learner's own language, from local data only.

Miolingo's translation chain (translation.py / translation_providers.py) has
two providers, Google Translate and OpenAI, both paid network APIs, plus a
database cache.  None is usable here.  What Miolingo does hold locally is its
own translation material: `language_materials/` (dictionaries of French and
German words with English meanings, phrase files, phrasebooks, story scenes,
and `unified/` with each phrase in seven languages).  neolingo/data/
build_data.py / build_words.py extract the first part into data/gloss.json,
and build_meanings.py extracts all of it into data/meanings.json (see
data/README.md for the sources, the pairs and the quality).

Lookup (`gloss(text, own_language, variant)`), case-insensitive, punctuation
as `_key`: the exact form first; then the form without one leading article,
reflexive pronoun or "to" (le, la, l', un, une, der, die, das, ein, eine,
to, the, se, sich ...).  In each step data/meanings.json is consulted, then
data/gloss.json (older, smaller); with NEOLINGO_INVERTED=1 also
data/meanings_inverted.json (English words whose meaning is the one French or
German headword of the dictionaries, one to one; not exact for inflected
forms, so off by default).  Nothing is guessed, translated by machine or
inverted otherwise.  Returns "" when the text is not there."""
from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from pathlib import Path

from .variants import variant

_DATA = Path(__file__).resolve().parent.parent / "data"
_FILE = _DATA / "gloss.json"

# the first token of a key (after `_key`: lower case, apostrophes as spaces) that may be dropped, by practised language
_LEADING = {
    "fr": {"le", "la", "les", "l", "un", "une", "des", "du", "se", "s"},
    "de": {"der", "die", "das", "den", "dem", "des", "ein", "eine", "einen", "einem", "einer", "eines", "sich"},
    "en": {"the", "a", "an", "to"},
}


def _key(text: str) -> str:
    return " ".join(re.sub(r"[^\w]+", " ", text.replace("’", "'").lower()).split())


def _load(name: str) -> dict:
    f = _DATA / name
    return json.loads(f.read_text("utf-8")) if f.exists() else {}


@lru_cache(maxsize=1)
def _table() -> dict:
    return _load("gloss.json")


@lru_cache(maxsize=1)
def _meanings() -> dict:
    return _load("meanings.json")


@lru_cache(maxsize=1)
def _inverted() -> dict:
    return _load("meanings_inverted.json")


def _lookup(lang: str, key: str, own: str) -> str:
    for t in (_meanings(), _table()):
        m = t.get(lang, {}).get(key, {}).get(own, "")
        if m:
            return m
    if os.environ.get("NEOLINGO_INVERTED") == "1":
        return _inverted().get(lang, {}).get(key, {}).get(own, "")
    return ""


def gloss(text: str, own_language: str, variant_code: str) -> str:
    lang = variant(variant_code)["lang"]
    if own_language == lang:
        return ""
    key = _key(text)
    got = _lookup(lang, key, own_language)
    if got:
        return got
    head, _, rest = key.partition(" ")
    if rest and head in _LEADING.get(lang, ()):
        return _lookup(lang, rest, own_language)
    return ""
