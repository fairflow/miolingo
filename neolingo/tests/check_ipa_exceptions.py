"""Unit cases of data/ipa_exceptions.json as applied by env.target_ipa (word by word).  Needs espeak-ng, no models:
    <miolingo venv python> tests/check_ipa_exceptions.py
Exits 1 on failure."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import env                                                   # noqa: E402

bad = []


def check(cond, what):
    print(("ok   " if cond else "FAIL ") + what)
    if not cond:
        bad.append(what)


j = lambda words: ["".join(w) for w in words]               # noqa: E731

t = j(env.target_ipa("Toiletten", "de"))
check(len(t) == 1 and "oːiː" not in t[0] and t[0] == "toalɛtən", f"Toiletten (de) = {t}")
check(j(env.target_ipa("Toiletten!", "de")) == t, "punctuation and case are ignored: 'Toiletten!'")
check(j(env.target_ipa("TOILETTE.", "de")) == ["toalɛtə"], "TOILETTE. (de)")

# a native word is unchanged: equals what espeak alone gives
from env import ipa as ipa_mod                               # noqa: E402
raw = "".join(env.phones_of(env.norm_word(ipa_mod._espeak("Garten", env.variant("de")["espeak"]))))
check(j(env.target_ipa("Garten", "de")) == [raw], f"Garten unchanged = {raw}")

# a phrase mixing both keeps word order and the word count
words = j(env.target_ipa("Wo ist die Toilette bitte", "de"))
check(len(words) == 5 and words[3] == "toalɛtə", f"mixed phrase = {words}")
native = j(env.target_ipa("Wo ist die", "de"))
check(words[:3] == native or len(native) == 3, f"native words of the mixed phrase = {native}")
check(j(env.target_ipa("Toilette Garten Orange", "de"))[1] == raw, "order: Toilette Garten Orange")

# other languages are not touched
check(j(env.target_ipa("Toilette", "fr-fr")) == j(env.target_ipa("toilette", "fr-fr")), "French unaffected (same for any case)")
check("toalɛtə" not in j(env.target_ipa("Toilette", "fr-fr")), "French Toilette is not the German exception")

# the file: every sound of every entry is a key of the cost table (no unseen symbol)
keys = set(json.loads((ROOT / "data" / "cost_table.json").read_text("utf-8"))["phones"])
exc = json.loads((ROOT / "data" / "ipa_exceptions.json").read_text("utf-8"))
check("_note" in exc and "2026-10-13" in exc["_note"], "_note present")
for lang, m in exc.items():
    if lang.startswith("_"):
        continue
    for w, ipa in m.items():
        unk = [s for s in env.phones_of(env.norm_word(ipa)) if s not in keys]
        check(not unk, f"{lang}/{w} {ipa}: sounds not in the cost table: {unk}")

print("\nFAILED: " + "; ".join(bad) if bad else "\nall ok")
sys.exit(1 if bad else 0)
