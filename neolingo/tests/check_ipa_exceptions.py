"""Unit cases of data/ipa_exceptions.json as applied by env.target_ipa (word by word).  Needs espeak-ng, no models:
    <miolingo venv python> tests/check_ipa_exceptions.py
Exits 1 on failure.

Each case is named by the fault it guards (locus docs/neolingo-test-design.md 4D): "F1 13 Oct" for the fault below,
"designed 13 Oct" for a case written with the table (3816056), no fault of it recorded.
  F1  13 Oct (the owner's take of the word list's "Toiletten"; fixed in 3816056, 19:37): espeak-ng read the loanword
      by German letter rules, [toːiːlɛtən] for [toalɛtən], and 19 other loanwords likewise.  Watched 15 Oct: with
      the table's lookup removed from target_ipa, the 3 F1 cases fail and the designed ones pass.
The table in the data is linted as well (tests/check_data.py, D2: a listed word of a practised text has the
table's target)."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import env                                                   # noqa: E402

bad = []
F1, D = "F1 13 Oct: ", "designed 13 Oct: "


def check(cond, what):
    print(("ok   " if cond else "FAIL ") + what)
    if not cond:
        bad.append(what)


j = lambda words: ["".join(w) for w in words]               # noqa: E731

t = j(env.target_ipa("Toiletten", "de"))
check(len(t) == 1 and "oːiː" not in t[0] and t[0] == "toalɛtən", F1 + f"Toiletten (de) = {t}")
check(j(env.target_ipa("Toiletten!", "de")) == t, D + "punctuation and case are ignored: 'Toiletten!'")
check(j(env.target_ipa("TOILETTE.", "de")) == ["toalɛtə"], F1 + "TOILETTE. (de)")

# a native word is unchanged: equals what espeak alone gives
from env import ipa as ipa_mod                               # noqa: E402
raw = "".join(env.phones_of(env.norm_word(ipa_mod._espeak("Garten", env.variant("de")["espeak"]))))
check(j(env.target_ipa("Garten", "de")) == [raw], D + f"Garten unchanged = {raw}")

# a phrase mixing both keeps word order and the word count
words = j(env.target_ipa("Wo ist die Toilette bitte", "de"))
check(len(words) == 5 and words[3] == "toalɛtə", F1 + f"mixed phrase = {words}")
native = j(env.target_ipa("Wo ist die", "de"))
check(words[:3] == native, D + f"the native words of the mixed phrase are as without the loanword: {native}")
check(j(env.target_ipa("Toilette Garten Orange", "de"))[1] == raw, D + "order: Toilette Garten Orange")

# other languages are not touched
check(j(env.target_ipa("Toilette", "fr-fr")) == j(env.target_ipa("toilette", "fr-fr")), D + "French unaffected (same for any case)")
check("toalɛtə" not in j(env.target_ipa("Toilette", "fr-fr")), D + "French Toilette is not the German exception")

# the file: every sound of every entry is a key of the cost table (no unseen symbol)
keys = set(json.loads((ROOT / "data" / "cost_table.json").read_text("utf-8"))["phones"])
exc = json.loads((ROOT / "data" / "ipa_exceptions.json").read_text("utf-8"))
check("_note" in exc and "2026-10-13" in exc["_note"], D + "_note present")
for lang, m in exc.items():
    if lang.startswith("_"):
        continue
    for w, ipa in m.items():
        unk = [s for s in env.phones_of(env.norm_word(ipa)) if s not in keys]
        check(not unk, D + f"{lang}/{w} {ipa}: sounds not in the cost table: {unk}")

print("\nFAILED: " + "; ".join(bad) if bad else "\nall ok")
sys.exit(1 if bad else 0)
