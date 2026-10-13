"""`gloss`: a meaning in the learner's own language, from local data only.

Miolingo's translation chain (translation.py / translation_providers.py) has
two providers, Google Translate and OpenAI, both paid network APIs, plus a
database cache.  None is usable here.  What Miolingo does hold locally is its
own phrase material: `language_materials/unified/phrases/*.json` (each phrase
in seven languages) and the per-language dictionaries.  neolingo/data/
build_data.py extracts those into data/gloss.json; this function is a lookup
in it.  Returns "" when the text is not there."""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from .variants import variant

_FILE = Path(__file__).resolve().parent.parent / "data" / "gloss.json"


def _key(text: str) -> str:
    return " ".join(re.sub(r"[^\w]+", " ", text.replace("’", "'").lower()).split())


@lru_cache(maxsize=1)
def _table() -> dict:
    if not _FILE.exists():
        return {}
    return json.loads(_FILE.read_text("utf-8"))


def gloss(text: str, own_language: str, variant_code: str) -> str:
    lang = variant(variant_code)["lang"]
    if own_language == lang:
        return ""
    return _table().get(lang, {}).get(_key(text), {}).get(own_language, "")
