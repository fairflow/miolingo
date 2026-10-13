"""Make data/words_{en,fr,de}.json (the word lists offered under "Upload a list of words") and extend data/gloss.json
with the meanings of those words.  Run AFTER build_data.py (which rewrites gloss.json from scratch):

    venv/bin/python neolingo/data/build_words.py

Reads (never writes) Miolingo's `language_materials/` in the parent checkout; never reads `data/user-data`.
Nothing is computed with models; plain text only.  See data/README.md for the sources of each list.

  fr  the level files fr/words/words-001..004.txt (levels A to D), word | English meaning
  de  de has no level files of its own; its levels are those of its phrase files: the words of
      de/phrases/phrases-001, -003, -004, -005 (the same four files build_data.py uses), each word in the first
      level where it occurs, kept when de/words/dictionary-complete.txt has it (that is where the English comes from)
  en  the level files en/words/words-001..004.txt (A to D), then 200 further words spread evenly over
      en/words/dictionary-complete.txt in alphabetical order, in four chunks of 50.  The English files' meanings
      are PORTUGUESE (their paired language); they enter gloss.json as own language "pt".
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from env.gloss import _key                  # noqa: E402

MIO = Path(os.environ.get("NEOLINGO_MIOLINGO_ROOT", Path.home() / "Software/working/miolingo"))
MAT = MIO / "language_materials"
# letters only: the model's upload splits a word at an apostrophe ("c'est", "geht's" lose a piece) and turns a hyphen into a
# space ("e-mail" becomes "e mail"), so words with either are not offered
WORD = re.compile(r"[^\W\d_]+")
LEVELS = "ABCD"
PHRASE_FILES = ["phrases-001", "phrases-003", "phrases-004", "phrases-005"]
NAMES = {"en": "English", "fr": "French", "de": "German"}
GLOSS_LANG = {"en": "pt", "fr": "en", "de": "en"}      # the language of the meanings the material holds


def rows(path: Path):
    for line in path.read_text("utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("("):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) >= 2 and parts[0]:
            yield parts[0], parts[1]


def good(w):
    return len(w) >= 2 and WORD.fullmatch(w) is not None


def level_words(lang):
    """[(name, source files, [(word, meaning)])] for the level lists of one language."""
    out = []
    if lang in ("fr", "en"):
        for i, lv in enumerate(LEVELS, 1):
            f = MAT / lang / "words" / f"words-00{i}.txt"
            out.append((f"{NAMES[lang]} words, level {lv}", [f], [(w, g) for w, g in rows(f) if good(w)]))
    else:
        dic = {w.lower(): g for w, g in rows(MAT / "de" / "words" / "dictionary-complete.txt")}
        seen = set()
        for lv, stem in zip(LEVELS, PHRASE_FILES):
            f = MAT / "de" / "phrases" / f"{stem}.txt"
            ws = []
            for text, _g in rows(f):
                for w in WORD.findall(text):
                    w = w.lower()
                    if good(w) and w in dic and w not in seen:
                        seen.add(w)
                        ws.append((w, dic[w]))
            out.append((f"German words, level {lv}", [f, MAT / "de" / "words" / "dictionary-complete.txt"], ws))
    return out


def chunks_en(taken):
    f = MAT / "en" / "words" / "dictionary-complete.txt"
    rest = sorted({(w.lower(), g) for w, g in rows(f) if good(w) and len(w) >= 3 and w.lower() not in taken})
    pick = [rest[int(i * len(rest) / 200)] for i in range(200)]
    out = []
    for k in range(4):
        part = pick[k * 50:(k + 1) * 50]
        out.append((f"English words, {part[0][0]} to {part[-1][0]}", [f], part))
    return out


def main():
    gloss = json.loads((HERE / "gloss.json").read_text("utf-8"))
    for lang in ("en", "fr", "de"):
        lists = level_words(lang)
        if lang == "en":
            lists += chunks_en({w.lower() for _n, _f, ws in lists for w, _g in ws})
        seen, out, added = set(), [], 0
        for name, files, ws in lists:
            words = []
            for w, g in ws:
                if _key(w) in seen:
                    continue
                seen.add(_key(w))
                words.append(w)
                if g:
                    d = gloss.setdefault(lang, {}).setdefault(_key(w), {})
                    if GLOSS_LANG[lang] not in d:
                        d[GLOSS_LANG[lang]] = g
                        added += 1
            out.append({"name": name, "lang": lang, "words": words,
                        "source": [str(f.relative_to(MIO)) for f in files]})
        body = "[\n " + ",\n ".join(json.dumps(x, ensure_ascii=False) for x in out) + "\n]\n"
        (HERE / f"words_{lang}.json").write_text(body, "utf-8")
        print(lang, [(x["name"], len(x["words"])) for x in out], "meanings added to gloss.json:", added)
    (HERE / "gloss.json").write_text(
        json.dumps({l: gloss[l] for l in ("en", "fr", "de")}, ensure_ascii=False, separators=(",", ":"), sort_keys=True), "utf-8")


if __name__ == "__main__":
    main()
