"""Readers for Miolingo's own translation material (`language_materials/` in the parent checkout).

Shared by build_meanings.py (builds the meaning table) and study_ipa.py (compares the material's IPA with espeak's).
Read-only; plain text and JSON only; never reads `data/user-data` or any database.  No models, no network.

`sources()` yields one record per (source file, entry) as a dict:
    src      short source id (see SOURCES)
    kind     "word" (a dictionary headword) or "phrase"
    lang     the language of `text`        (en, fr, de, ...)
    text     the headword or phrase
    own      the language of `meaning`
    meaning  the meaning as written in the source
    ipa      the source's IPA for `text` ("" if none), brackets and slashes removed
    file     path relative to the Miolingo root
"""
from __future__ import annotations

import csv
import json
import os
import re
from pathlib import Path

MIO = Path(os.environ.get("NEOLINGO_MIOLINGO_ROOT", Path.home() / "Software/working/miolingo"))
MAT = MIO / "language_materials"

# id -> (description, quality order: lower is preferred when two sources give a meaning for the same text)
SOURCES = {
    "dict": "<lang>/words/dictionary-complete.txt: word | meaning | [ipa]",
    "levels": "fr/words/words-001..004.txt, pt/words (level files): word | meaning | [ipa]",
    "wordsen": "en/words/words-00N.txt, dictionary*.txt, words-<lang>/: English word | Portuguese | [ipa]",
    "topics": "<lang>/phrasebook-topics/*.txt: phrase | meaning | [ipa]",
    "phrasebook": "<lang>/phrasebook_complete.json",
    "phrases": "<lang>/phrases/phrases-00N.txt: phrase | meaning | [ipa]",
    "scenes": "<lang>/story-scenes-json/*.json: text, english, ipa",
    "unified": "unified/phrases and unified/phrasebook: each phrase in 7 languages with IPA",
    "ustories": "unified/stories: each story phrase in 7 languages (place names localised per language)",
    "swift": "swift/Miolingo/Sources/Miolingo/Resources/lexicon.json",
    "csv": "language_materials/dictionary_pt.csv",
    "gen": "scripts/language-generation/*translated.json",
    "practice": "data/practice-sets/*.txt",
}


def clean_ipa(s: str) -> str:
    s = (s or "").strip()
    if s.startswith("[") and s.endswith("]"):
        s = s[1:-1]
    elif s.startswith("/") and s.endswith("/"):
        s = s[1:-1]
    return s.strip()


def pipe_rows(path: Path):
    """(a, b, ipa) of `a | b | [ipa]` lines; comment lines (#), blank lines and `(x, y)` pair headers skipped."""
    for line in path.read_text("utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or (line.startswith("(") and line.endswith(")") and "|" not in line):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) >= 2 and parts[0]:
            yield parts[0], parts[1], clean_ipa(parts[2]) if len(parts) > 2 else ""


def rel(p: Path) -> str:
    return str(p.relative_to(MIO))


def rec(src, kind, lang, text, own, meaning, ipa, file):
    return {"src": src, "kind": kind, "lang": lang, "text": text, "own": own, "meaning": meaning, "ipa": ipa, "file": file}


def sources():
    # 1. dictionaries: headword | English | [ipa]   (English's carries Portuguese)
    for lang in ("fr", "de", "es", "it", "nl", "pt"):
        f = MAT / lang / "words" / "dictionary-complete.txt"
        for w, g, ipa in pipe_rows(f):
            yield rec("dict", "word", lang, w, "en", g, ipa, rel(f))
    f = MAT / "en" / "words" / "dictionary-complete.txt"
    for w, g, ipa in pipe_rows(f):
        yield rec("dict", "word", "en", w, "pt", g, ipa, rel(f))
    # 2. level files
    for lang in ("fr", "pt"):
        for f in sorted((MAT / lang / "words").glob("words-00*.txt")):
            for w, g, ipa in pipe_rows(f):
                yield rec("levels", "word", lang, w, "en", g, ipa, rel(f))
    for f in sorted((MAT / "en" / "words").glob("words-00*.txt")) + sorted((MAT / "en" / "words").glob("dictionary[0-9].txt")):
        for w, g, ipa in pipe_rows(f):
            yield rec("wordsen", "word", "en", w, "pt", g, ipa, rel(f))
    for l in ("fr", "de", "es", "it", "nl", "pt"):
        for f in sorted((MAT / "en" / f"words-{l}").glob("*.txt")):
            for w, g, ipa in pipe_rows(f):
                yield rec("wordsen", "word", "en", w, l, g, ipa, rel(f))     # empty meanings except pt
    # 3. phrase files and phrasebook topics (fr, de: phrase | English; en: English | French)
    for lang in ("fr", "de", "en", "es", "it", "nl", "pt"):
        own = "fr" if lang == "en" else "en"
        for f in sorted((MAT / lang / "phrases").glob("*.txt")):
            for t, g, ipa in pipe_rows(f):
                yield rec("phrases", "phrase", lang, t, own, g, ipa, rel(f))
        for f in sorted((MAT / lang / "phrasebook-topics").glob("*.txt")):
            for t, g, ipa in pipe_rows(f):
                yield rec("topics", "phrase", lang, t, own, g, ipa, rel(f))
    # 4. phrasebook_complete.json
    for lang, key in (("fr", "french"), ("de", "german"), ("en", "english"), ("es", "spanish"), ("it", "italian"),
                      ("nl", "dutch"), ("pt", "portuguese")):
        f = MAT / lang / "phrasebook_complete.json"
        for p in json.loads(f.read_text("utf-8"))["phrases"]:
            if lang == "en":
                yield rec("phrasebook", "phrase", "en", p["english"], "fr", p["french"], "", rel(f))   # ipa there is French's
            else:
                yield rec("phrasebook", "phrase", lang, p[key], "en", p["english"], clean_ipa(p.get("ipa", "")), rel(f))
    # 5. story scenes
    for lang in ("fr", "de", "es", "it", "nl", "pt"):
        for f in sorted((MAT / lang / "story-scenes-json").glob("*.json")):
            d = json.loads(f.read_text("utf-8"))
            for p in d.get(lang, []):
                if p.get(lang) and p.get("english"):
                    yield rec("scenes", "phrase", lang, p[lang], "en", p["english"], clean_ipa(p.get("ipa", "")), rel(f))
    # 6. unified: each phrase in 7 languages
    for sub, sid in (("phrases", "unified"), ("phrasebook", "unified"), ("stories", "ustories")):
        for f in sorted((MAT / "unified" / sub).glob("*.json")):
            for p in json.loads(f.read_text("utf-8"))["phrases"]:
                texts = {k: v for k, v in p["text"].items() if "_" not in k}
                ipas = p.get("ipa", {})
                for a, ta in texts.items():
                    for b, tb in texts.items():
                        if a != b and ta and tb:
                            yield rec(sid, "phrase", a, ta, b, tb, clean_ipa(ipas.get(a, "")), rel(f))
    # 7. small extras
    f = MIO / "swift/Miolingo/Sources/Miolingo/Resources/lexicon.json"
    for lang, d in json.loads(f.read_text("utf-8")).items():
        if isinstance(d, dict):
            for t, g in d.items():
                yield rec("swift", "word" if " " not in t else "phrase", lang, t, "en", g, "", rel(f))
    f = MAT / "dictionary_pt.csv"
    with f.open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            yield rec("csv", "word", "pt", r["original"], "en", r["translation"], clean_ipa(r["ipa"]), rel(f))
    for f in sorted((MIO / "scripts/language-generation").glob("*translated.json")):
        d = json.loads(f.read_text("utf-8"))
        items = d if isinstance(d, list) else next((v for v in d.values() if isinstance(v, list)), [])
        for p in items:
            if isinstance(p, dict) and p.get("french") and p.get("english") and "[TO TRANSLATE" not in p["english"]:
                yield rec("gen", "phrase", "fr", p["french"], "en", p["english"], clean_ipa(p.get("ipa", "")), rel(f))
    for f in sorted((MIO / "data/practice-sets").glob("*translations*.txt")):
        for t, g, ipa in pipe_rows(f):
            yield rec("practice", "phrase", "pt", t, "en", g, ipa, rel(f))
