"""Regenerate data/{en,fr,de}.json and data/gloss.json from Miolingo's material.

Run with the Miolingo venv:  venv/bin/python neolingo/data/build_data.py
Reads (never writes) Miolingo's `language_materials/` in the parent checkout
(branch with `unified/`; the `main` snapshot lacks it).  Never reads
`data/user-data`.  Needs espeak-ng (target IPA is computed, not copied)."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import env                                  # noqa: E402
from env.gloss import _key                  # noqa: E402

MIO = Path(os.environ.get("NEOLINGO_MIOLINGO_ROOT",
                          Path.home() / "Software/working/miolingo"))
MAT = MIO / "language_materials"
VARIANT = {"en": "en-gb", "fr": "fr-fr", "de": "de"}
PHRASE_FILES = ["phrases-001", "phrases-003", "phrases-004", "phrases-005"]
PER_FILE = 12          # phrases taken from each file, evenly spaced
N_VOCAB = 40


def rows(path: Path):
    """(first column, second column) of `a | b | [ipa]` lines."""
    for line in path.read_text("utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("("):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) >= 2 and parts[0]:
            yield parts[0], parts[1]


def spread(items: list, n: int) -> list:
    if len(items) <= n:
        return items
    return [items[int(i * len(items) / n)] for i in range(n)]


def main():
    glosses: dict[str, dict[str, dict[str, str]]] = {}
    # 1. gloss table from the unified phrase files (each phrase in 7 languages)
    for f in sorted((MAT / "unified" / "phrases").glob("common-phrases-*.json")):
        for ph in json.loads(f.read_text("utf-8"))["phrases"]:
            for lang, text in ph["text"].items():
                if lang.count("_"):
                    continue
                d = glosses.setdefault(lang, {}).setdefault(_key(text), {})
                for other, t in ph["text"].items():
                    if other != lang and "_" not in other:
                        d[other] = t
    # 2. word glosses (own language English) from the fr and de dictionaries
    for lang in ("fr", "de"):
        for w, g in rows(MAT / lang / "words" / "dictionary-complete.txt"):
            d = glosses.setdefault(lang, {}).setdefault(_key(w), {})
            d.setdefault("en", g)
    (HERE / "gloss.json").write_text(
        json.dumps({l: glosses[l] for l in ("en", "fr", "de")}, ensure_ascii=False,
                   separators=(",", ":"), sort_keys=True), "utf-8")

    for lang in ("en", "fr", "de"):
        gl_lang = "fr" if lang == "en" else "en"     # the phrase files' gloss column
        phrases = []
        for stem in PHRASE_FILES:
            src = MAT / lang / "phrases" / f"{stem}.txt"
            rs = list(rows(src))
            for text, g in spread(rs, PER_FILE):
                phrases.append({"text": text, "gloss": g, "gloss_language": gl_lang,
                                "source": f"language_materials/{lang}/phrases/{stem}.txt",
                                "ipa": env.target_ipa(text, VARIANT[lang])})
        if lang == "en":
            vsrcs = [MAT / "en" / "words" / f"dictionary{i}.txt" for i in (1, 2, 3, 4)]
            vgl = "pt"
        else:
            vsrcs = [MAT / lang / "words" / "dictionary-complete.txt"]
            vgl = "en"
        vrows = [(w, g, s) for s in vsrcs for (w, g) in rows(s)
                 if w.isalpha() and len(w) >= 3 and g]
        vocab = [{"word": w, "gloss": g, "gloss_language": vgl,
                  "source": f"language_materials/{s.relative_to(MAT)}"}
                 for (w, g, s) in spread(vrows, N_VOCAB)]
        dump = lambda o: json.dumps(o, ensure_ascii=False)
        body = ('{\n "language": %s,\n "variant": %s,\n "phrases": [\n  %s\n ],\n "vocabulary": [\n  %s\n ]\n}\n'
                % (dump(lang), dump(VARIANT[lang]),
                   ",\n  ".join(dump(x) for x in phrases),
                   ",\n  ".join(dump(x) for x in vocab)))
        (HERE / f"{lang}.json").write_text(body, "utf-8")
        print(lang, len(phrases), "phrases", len(vocab), "words")


if __name__ == "__main__":
    main()
