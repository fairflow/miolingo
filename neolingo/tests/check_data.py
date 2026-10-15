"""The data lint (D1 to D4; D1 to D3 of locus docs/neolingo-test-design.md, section 4E) on the committed data, and the lint
watched failing on the faults that occurred.  Needs espeak-ng, no models, about 15 s:

    <miolingo venv python> tests/check_data.py

The checks are data/build_data.py's own functions (the same ones refuse a rebuild):
  D1  a practised text has no bracket, no slash, no digit;
  D2  every word of a practised text has a target (one per word, none empty, each sound a key of the cost table), a
      word listed in data/ipa_exceptions.json has the table's target, and the stored target of a phrase is the one
      the host computes (env.target_ipa);
  D3  a rebuild only adds keys to gloss.json (checked over the file's history in git, and against the working copy);
  D4  a word written in capitals in a practised phrase (an abbreviation) has a target listed in ipa_exceptions.json.
The targets the host computes are checked for every variant of a language (English: en-gb and en-us).
Exits 1 on failure."""
import copy
import json
import os
import subprocess
import sys
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "data"))
import env                                                   # noqa: E402
from env import ipa as env_ipa                               # noqa: E402
import build_data as B                                       # noqa: E402

bad = []


def check(cond, what):
    print(("ok   " if cond else "FAIL ") + what)
    if not cond:
        bad.append(what)


def clean_run(faults, what):
    check(not faults, f"{what}" + (f": {len(faults)} fault(s)" if faults else ""))
    B.show_faults(faults, 10)


def refused(faults, kind, what):
    """A planted fault must be found, by a check of its kind."""
    check(any(f.startswith(kind) for f in faults), f"refused, {what}: " + (faults[0] if faults else "NOT FOUND"))


LANGS = ("en", "fr", "de")
DATA = {l: json.loads((ROOT / "data" / f"{l}.json").read_text("utf-8")) for l in LANGS}
WORDS = {l: json.loads((ROOT / "data" / f"words_{l}.json").read_text("utf-8")) for l in LANGS}
KEYS = B.cost_keys()
VARIANTS = {l: [v["code"] for v in env.variants() if v["lang"] == l] for l in LANGS}

print("== D1: every practised text (phrases, vocabulary, word lists) ==")
for l in LANGS:
    texts = ([(f"{l} phrase", p["text"]) for p in DATA[l]["phrases"]]
             + [(f"{l} word", v["word"]) for v in DATA[l]["vocabulary"]]
             + [(f"{l} list {w['name']!r}", x) for w in WORDS[l] for x in w["words"]])
    clean_run(B.lint_texts(texts), f"D1 {l}: {len(texts)} texts")

print("\n== D2: the stored targets of the phrases ==")
for l in LANGS:
    ph = DATA[l]["phrases"]
    clean_run(B.lint_targets(l, [(f"{l} phrase", p["text"], p["ipa"]) for p in ph], KEYS), f"D2 {l}: {len(ph)} stored targets")

print("\n== D2: the targets the host computes (env.target_ipa), every variant ==")
for l in LANGS:
    in_lists = sorted({x for w in WORDS[l] for x in w["words"] if env_ipa.listed_ipa(l, x) is not None})
    for v in VARIANTS[l]:
        items = ([(f"{v} phrase", p["text"], env.target_ipa(p["text"], v)) for p in DATA[l]["phrases"]]
                 + [(f"{v} word", w["word"], env.target_ipa(w["word"], v)) for w in DATA[l]["vocabulary"]]
                 + [(f"{v} listed word of a word list", x, env.target_ipa(x, v)) for x in in_lists])
        clean_run(B.lint_targets(l, items, KEYS),
                  f"D2 {v}: {len(items)} targets (phrases, vocabulary, the word lists' listed loanwords {in_lists})")
    stale = [f"D2 {l} phrase {p['text']!r}: stored [{' '.join(map(''.join, p['ipa']))}], computed "
             f"[{' '.join(map(''.join, t))}]"
             for p in DATA[l]["phrases"] for t in [env.target_ipa(p["text"], B.VARIANT[l])] if t != p["ipa"]]
    clean_run(stale, f"D2 {l}: each stored target is the one the host computes for {B.VARIANT[l]}")

print("\n== D4: a word written in capitals in a phrase has a listed target ==")
for l in LANGS:
    ph = DATA[l]["phrases"]
    clean_run(B.lint_capitals(l, [(f"{l} phrase", p["text"]) for p in ph]),
              f"D4 {l}: {len(ph)} phrases, words in capitals {sorted({w for p in ph for w in env_ipa._text_words(p['text']) if B.capitals(w)})}")

print("\n== D3: gloss.json only gains keys, over its history ==")


def git(*a):
    r = subprocess.run(["git", "-C", str(ROOT), *a], capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


commits = (git("log", "--format=%h", "--reverse", "--", "data/gloss.json") or "").split()
if not commits:
    print("   skipped: no git history here")
else:
    versions = [(c, json.loads(git("show", f"{c}:./data/gloss.json"))) for c in commits]
    versions.append(("working copy", json.loads((ROOT / "data" / "gloss.json").read_text("utf-8"))))
    for (c0, g0), (c1, g1) in zip(versions, versions[1:]):
        n0 = sum(len(m) for t in g0.values() for m in t.values())
        n1 = sum(len(m) for t in g1.values() for m in t.values())
        clean_run(B.lint_gloss(g0, g1), f"D3 {c0} -> {c1}: {n0} -> {n1} meanings")

print("\n== the lint watched failing: each planted fault must be refused ==")
# D1, 13 October ("Bad import"): the texts as the first build practised them (943b80e)
for t in ("And you? (formal)", "Okay / Agreed", "I'm lost (m)"):
    refused(B.lint_texts([("planted", t)]), "D1", f"13 Oct, a note or an alternative practised: {t!r}")
refused(B.lint_texts([("planted", "Gate 7")]), "D1", "designed, a digit: 'Gate 7'")

# D2, 13 October (the owner's take): the word list's "toiletten" as espeak reads it without the table (before 3816056)
saved = env_ipa._EXC
env_ipa._EXC = {}
try:
    raw = env.target_ipa("toiletten", "de")
finally:
    env_ipa._EXC = saved
refused(B.lint_targets("de", [("planted", "toiletten", raw)], KEYS), "D2",
        f"13 Oct, a listed loanword with espeak's target [{''.join(raw[0])}]")
# D2, 13 Oct 14:46 to 14 Oct 10:26 (fd26f26 to 48ffb80): the stored targets lacked the length marks the host keeps
p = next(p for p in DATA["de"]["phrases"] if any("ː" in s for w in p["ipa"] for s in w))
old = [[s.replace("ː", "") for s in w] for w in p["ipa"]]
stale = [p["text"]] if old != env.target_ipa(p["text"], "de") else []
check(bool(stale), f"refused, 13-14 Oct, a stored target without the length marks: {p['text']!r} "
                   f"[{' '.join(map(''.join, old))}] is not the computed target")
good = env.target_ipa("Wo ist die Toilette bitte", "de")
refused(B.lint_targets("de", [("planted", "Wo ist die Toilette bitte", good[:-1])], KEYS), "D2", "designed, a word without a target")
refused(B.lint_targets("de", [("planted", "Wo ist die Toilette bitte", good[:-1] + [[]])], KEYS), "D2",
        "designed, an empty target")
refused(B.lint_targets("en", [("planted", "water", [["w", "ɔː", "ɾ", "ɚ"]])], KEYS), "D2",
        "designed, a sound that is not a key of the cost table ([ɚ], en-us)")

# D4, 13 October (the audit's sweep): "PIN" spelled out; the table without its PIN entries (before 15 October)
saved = env_ipa._EXC
env_ipa._EXC = {l: {k: v for k, v in m.items() if k.lower() not in ("pin", "pincode")} if isinstance(m, dict) else m
                for l, m in json.loads((ROOT / "data" / "ipa_exceptions.json").read_text("utf-8")).items()}
try:
    f4 = [f for l in LANGS for f in B.lint_capitals(l, [(f"{l} phrase", p["text"]) for p in DATA[l]["phrases"]])]
finally:
    env_ipa._EXC = saved
refused(f4, "D4", f"13 Oct, PIN spelled out, with the table's PIN entries removed ({len(f4)} phrases)")
refused(B.lint_capitals("en", [("planted", "Where is the ATM?")]), "D4", "designed, another abbreviation: 'ATM'")
check(not B.lint_capitals("en", [("planted", "I'm lost")]) and not B.lint_capitals("de", [("planted", "Wo ist die Toilette")]),
      "designed, not an abbreviation: one capital ('I'm'), a capitalised noun ('Toilette')")

# D3, 13 October: a rebuild from the material alone, which drops the meanings build_words.py added (own language pt)
g = json.loads((ROOT / "data" / "gloss.json").read_text("utf-8"))
cut = copy.deepcopy(g)
for m in cut["en"].values():
    m.pop("pt", None)
cut["en"].pop(min(cut["en"]))                                # and one key whatever its meanings
f3 = B.lint_gloss(g, cut)
refused(f3, "D3", f"13 Oct, the word meanings build_words.py added dropped by a rebuild ({len(f3)} meanings)")
changed = copy.deepcopy(g)
k = next(iter(changed["fr"]))
changed["fr"][k] = {o: m + " (changed)" for o, m in changed["fr"][k].items()}
refused(B.lint_gloss(g, changed), "D3", "designed, a meaning changed by a rebuild")

print("\nFAILED: " + "; ".join(bad) if bad else "\nall ok")
sys.exit(1 if bad else 0)
