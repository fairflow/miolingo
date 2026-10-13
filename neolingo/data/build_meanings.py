"""Build data/meanings.json (and data/meanings_inverted.json) from Miolingo's own translation material.

    venv/bin/python neolingo/data/build_meanings.py [--survey]

Reads (never writes) `language_materials/` and a few small files of the parent checkout (see materials.py); never
`data/user-data`, never a database.  Plain text and JSON; no model, no machine translation, no network.

meanings.json   {practised language: {normalised text: {own language: meaning}}}  for en, fr, de (both ways, never the same
                language).  The meaning is as the source wrote it ("way, path"; "hello / good day").  When several sources give a
                meaning for one text, the first of PRIORITY wins; the others are counted as conflicts (printed), not merged.
meanings_inverted.json
                English -> French and English -> German word meanings made by inverting the French and German dictionaries
                where the inversion is one word to one word in both directions (the English word is the meaning of exactly one
                headword, and that headword has exactly one meaning).  The dictionaries' meanings are not inflection-aware
                ("recommandez | recommend"), so a sample of the inversions is not all right; `env.gloss` reads this file
                only when NEOLINGO_INVERTED=1.
--survey        also prints, per source, entries / IPA / pair (used for the table in the report).
"""
from __future__ import annotations

import collections
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
import materials                              # noqa: E402
from env.gloss import _key                    # noqa: E402

OFFERED = ("en", "fr", "de")
# earlier wins.  The level files come first: hand-picked for the phrase lists ("cherche | look for", "bureau | desk"), where
# the dictionary was made from the story's context ("cherche | search", "cartes | maps").  `gen` (scripts/language-generation) is NOT used: its English lines are misaligned with the French.
PRIORITY = ["levels", "dict", "swift", "topics", "phrasebook", "phrases", "scenes", "unified", "ustories"]
# `ustories` localises place names per language (a German line says Berlin where the French says Paris), so it is
# used only for French <-> English, where both keep the same names.
USTORIES_PAIRS = {("fr", "en"), ("en", "fr")}
WORD = re.compile(r"[^\W\d_]+(?:[-'][^\W\d_]+)*$")


def main():
    survey = "--survey" in sys.argv
    table: dict[str, dict[str, dict[str, tuple[int, str]]]] = {}
    conflicts = collections.Counter()
    seen_src = collections.defaultdict(lambda: [0, 0])
    one_word: dict[tuple[str, str], dict[str, set]] = {}          # for the inversion: (lang, own) -> headword -> {meanings}
    for r in materials.sources():
        seen_src[(r["src"], r["lang"], r["own"])][0] += 1
        seen_src[(r["src"], r["lang"], r["own"])][1] += bool(r["ipa"])
        lang, own = r["lang"], r["own"]
        if lang not in OFFERED or own not in OFFERED or lang == own or r["src"] not in PRIORITY:
            continue
        if r["src"] == "ustories" and (lang, own) not in USTORIES_PAIRS:
            continue
        key, meaning = _key(r["text"]), " ".join(r["meaning"].split())
        if not key or not meaning:
            continue
        rank = PRIORITY.index(r["src"])
        slot = table.setdefault(lang, {}).setdefault(key, {})
        old = slot.get(own)
        if old is None or rank < old[0]:
            if old is not None and _key(old[1]) != _key(meaning):
                conflicts[(lang, own)] += 1
            slot[own] = (rank, meaning)
        elif _key(old[1]) != _key(meaning):
            conflicts[(lang, own)] += 1
        if r["src"] in ("dict", "levels", "swift") and r["kind"] == "word" and own == "en":
            one_word.setdefault((lang, own), {}).setdefault(key, set()).add(meaning.lower())

    out = {l: {k: {o: v[1] for o, v in sorted(d.items())} for k, d in sorted(table.get(l, {}).items())} for l in OFFERED}
    body = json.dumps(out, ensure_ascii=False, separators=(",", ":"))
    (HERE / "meanings.json").write_text(body, "utf-8")

    # inversion: English meaning -> the French / German headword, only where it is exactly one to one
    inv: dict[str, dict[str, dict[str, str]]] = {"en": {}}
    for lang in ("fr", "de"):
        heads = one_word[(lang, "en")]
        by_meaning = collections.defaultdict(set)
        for h, gs in heads.items():
            for g in gs:
                by_meaning[g].add(h)
        n_one = 0
        for g, hs in by_meaning.items():
            (h,) = tuple(hs)[:1] if len(hs) == 1 else (None,)
            if h is None or not WORD.match(g) or not WORD.match(h) or len(heads[h]) != 1:
                continue
            n_one += 1
            inv["en"].setdefault(_key(g), {})[lang] = h
        print(f"inversion {lang}: {len(heads)} headwords, {len(by_meaning)} distinct English meanings, {n_one} one-to-one "
              f"({100 * n_one / len(by_meaning):.0f}% of the meanings)")
    (HERE / "meanings_inverted.json").write_text(
        json.dumps({"en": dict(sorted(inv["en"].items()))}, ensure_ascii=False, separators=(",", ":")), "utf-8")

    print(f"meanings.json: {len(body.encode()) // 1024} KiB")
    for lang in OFFERED:
        per = collections.Counter(o for d in out[lang].values() for o in d)
        print(f"  practised {lang}: {len(out[lang])} texts; entries by own language {dict(per)}")
    print("conflicts (different meaning for the same text in a lower-priority source; first kept):", dict(conflicts))
    if survey:
        for k, (n, i) in sorted(seen_src.items()):
            print("survey", *k, n, i)


if __name__ == "__main__":
    main()
