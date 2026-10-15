"""Regenerate data/{en,fr,de}.json and data/gloss.json from Miolingo's material, linted before anything is written.

Run with the Miolingo venv:  venv/bin/python neolingo/data/build_data.py [--out DIR]
Reads (never writes) Miolingo's `language_materials/` in the parent checkout
(branch with `unified/`; the `main` snapshot lacks it).  Never reads
`data/user-data`.  Needs espeak-ng (target IPA is computed, not copied).
`--out DIR` writes there instead of data/ (a scratch rebuild; D3 then compares with DIR/gloss.json).

THE DATA LINT (locus docs/neolingo-test-design.md, section 4E).  Nothing is written when any check fails; the same
functions run on the committed files in tests/check_data.py.
  D1  a practised text (a phrase, a vocabulary word) has no bracket, no slash and no digit.  Guards 13 October
      (the owner: "was I meant to say (formal)?  Bad import."): "And you? (formal)" and "Okay / Agreed" were practised
      with the note and the alternative read aloud.
  D2  every word of a practised text has a target: one target per word of the text, none empty, each sound a key of
      the cost table; and a word listed in data/ipa_exceptions.json has the table's target.  Guards 13 October (the
      owner's take): espeak read the loanword "Toiletten" by German letter rules, [toːiːlɛtən].
  D3  a rebuild only adds keys to gloss.json: every (language, text, own language) of the file being replaced is
      in the new one with the same meaning.  Guards 13 October: a rebuild from the material alone dropped the
      meanings build_words.py had added (the English word meanings)."""
from __future__ import annotations

import argparse
import json
import re
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import env                                  # noqa: E402
from env import ipa as env_ipa              # noqa: E402
from env.gloss import _key                  # noqa: E402

MIO = Path(os.environ.get("NEOLINGO_MIOLINGO_ROOT",
                          Path.home() / "Software/working/miolingo"))
MAT = MIO / "language_materials"
VARIANT = {"en": "en-gb", "fr": "fr-fr", "de": "de"}
PHRASE_FILES = ["phrases-001", "phrases-003", "phrases-004", "phrases-005"]
PER_FILE = 12          # phrases taken from each file, evenly spaced
N_VOCAB = 40


# ---------------------------------------------------------------- the data lint (D1, D2, D3); each returns faults

NOT_SAID = re.compile(r"[()\[\]{}/]|\d")      # brackets, a slash (" / " marks alternatives), digits


def lint_texts(items) -> list[str]:
    """D1 over [(where, text)]: a practised text has no bracket, no slash, no digit."""
    out = []
    for where, text in items:
        bad = sorted(set(NOT_SAID.findall(text)))
        if bad:
            out.append(f"D1 {where}: {text!r} has {' '.join(bad)}")
    return out


def cost_keys() -> set[str]:
    return set(json.loads((HERE / "cost_table.json").read_text("utf-8"))["phones"])


def table_targets(lang: str) -> dict[str, list[str]]:
    """{word key: target sounds} of data/ipa_exceptions.json for a language, cut as target_ipa cuts them."""
    return {k: env.phones_of(env.norm_word(v.replace(" ", ""))) for k, v in env_ipa.ipa_exceptions(lang).items()}


def lint_targets(lang: str, items, keys: set[str]) -> list[str]:
    """D2 over [(where, text, target)], `target` as env.target_ipa gives it (a list of words, each a list of
    sounds): one target per word of the text, none empty, each sound a key of the cost table, and a listed loanword
    with the table's target."""
    listed = table_targets(lang)
    out = []
    for where, text, target in items:
        words = env_ipa._text_words(text)
        if len(target) != len(words):
            out.append(f"D2 {where}: {text!r}: {len(words)} word(s), {len(target)} target(s)")
            continue
        for w, t in zip(words, target):
            if not t:
                out.append(f"D2 {where}: {text!r}: {w!r} has no target")
            unknown = [s for s in t if s not in keys]
            if unknown:
                out.append(f"D2 {where}: {text!r}: {w!r} [{''.join(t)}]: not keys of the cost table: {unknown}")
            k = env_ipa._word_key(w)
            if k in listed and t != listed[k]:
                out.append(f"D2 {where}: {text!r}: {w!r} is listed in ipa_exceptions.json as "
                           f"[{''.join(listed[k])}], its target is [{''.join(t)}]")
    return out


def lint_gloss(old: dict, new: dict) -> list[str]:
    """D3: every (language, text, own language) of `old` is in `new` with the same meaning."""
    out = []
    for lang, texts in old.items():
        for key, means in texts.items():
            for own, m in means.items():
                got = new.get(lang, {}).get(key, {}).get(own)
                if got != m:
                    out.append(f"D3 gloss.json {lang} {key!r} -> {own}: "
                               + ("dropped" if got is None else f"{m!r} changed to {got!r}"))
    return out


def show_faults(faults: list[str], most: int = 20) -> None:
    for f in faults[:most]:
        print("  " + f)
    if len(faults) > most:
        print(f"  ... and {len(faults) - most} more")


# ---------------------------------------------------------------- the build

def rows(path: Path):
    """(first column, second column) of `a | b | [ipa]` lines."""
    for line in path.read_text("utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("("):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) >= 2 and parts[0]:
            yield parts[0], parts[1]


def clean(text: str) -> tuple[str, str]:
    """(the phrase to practise, a note): a bracketed note ("And you? (formal)", "I'm lost (m)") is not part of what
    one says, and of alternatives "A / B" ("Okay / Agreed") the first is practised; both go into the note.  The owner,
    13 October: "was I meant to say (formal)? I don't think so!  Bad import." """
    notes = re.findall(r"\(([^)]*)\)", text)
    t = re.sub(r"\s*\([^)]*\)", "", text).strip()
    alts = [a.strip() for a in t.split(" / ")]
    t = alts[0]
    if len(alts) > 1:
        notes.append("also: " + " / ".join(alts[1:]))
    return t, "; ".join(n for n in notes if n)


def spread(items: list, n: int) -> list:
    if len(items) <= n:
        return items
    return [items[int(i * len(items) / n)] for i in range(n)]


def material_glosses() -> dict:
    """The gloss table as the material alone gives it."""
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
    return glosses


def keep_later_additions(glosses: dict, kept: dict) -> dict:
    """gloss.json has been EXTENDED since by other work (build_words.py, meanings for words added by hand): a rebuild
    keeps every key already there, with its value, and only adds what the material has that the file lacks."""
    return {l: {**glosses.get(l, {}), **kept.get(l, {})} for l in ("en", "fr", "de")}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=Path, default=HERE, help="write here instead of data/ (default: data/)")
    out_dir = ap.parse_args(argv).out
    try:
        kept = json.loads((out_dir / "gloss.json").read_text("utf-8"))
    except FileNotFoundError:
        kept = {}
    glosses = keep_later_additions(material_glosses(), kept)
    faults = lint_gloss(kept, glosses)
    keys = cost_keys()

    bodies = {}
    for lang in ("en", "fr", "de"):
        gl_lang = "fr" if lang == "en" else "en"     # the phrase files' gloss column
        phrases = []
        for stem in PHRASE_FILES:
            src = MAT / lang / "phrases" / f"{stem}.txt"
            rs = list(rows(src))
            for raw, g in spread(rs, PER_FILE):
                text, note = clean(raw)
                item = {"text": text, "gloss": g, "gloss_language": gl_lang,
                        "source": f"language_materials/{lang}/phrases/{stem}.txt",
                        "ipa": env.target_ipa(text, VARIANT[lang])}
                if note:
                    item["note"] = note
                phrases.append(item)
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
        faults += lint_texts([(f"{lang} phrase", p["text"]) for p in phrases]
                             + [(f"{lang} word", v["word"]) for v in vocab])
        faults += lint_targets(lang, [(f"{lang} phrase", p["text"], p["ipa"]) for p in phrases]
                               + [(f"{lang} word", v["word"], env.target_ipa(v["word"], VARIANT[lang])) for v in vocab],
                               keys)
        dump = lambda o: json.dumps(o, ensure_ascii=False)
        bodies[lang] = ('{\n "language": %s,\n "variant": %s,\n "phrases": [\n  %s\n ],\n "vocabulary": [\n  %s\n ]\n}\n'
                        % (dump(lang), dump(VARIANT[lang]),
                           ",\n  ".join(dump(x) for x in phrases),
                           ",\n  ".join(dump(x) for x in vocab)))
        print(lang, len(phrases), "phrases", len(vocab), "words")

    if faults:
        print(f"THE DATA LINT FAILED ({len(faults)}):")
        show_faults(faults)
        sys.exit(f"nothing written to {out_dir}")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "gloss.json").write_text(
        json.dumps({l: glosses[l] for l in ("en", "fr", "de")}, ensure_ascii=False,
                   separators=(",", ":"), sort_keys=True), "utf-8")
    for lang, body in bodies.items():
        (out_dir / f"{lang}.json").write_text(body, "utf-8")
    print(f"the data lint passed (D1, D2, D3); written to {out_dir}")


if __name__ == "__main__":
    main()
