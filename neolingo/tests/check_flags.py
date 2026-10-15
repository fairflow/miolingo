"""Unit cases of host.engine.flags_out: findings on tokens that cover several target sounds.
No models are loaded:  <miolingo venv python> tests/check_flags.py

Each case is named by the fault it guards (locus docs/neolingo-test-design.md 4D): "F1 13 Oct" for the fault below,
"designed 13 Oct" for a case written with the rule, no fault of it recorded.
  F1  13 Oct (the owner's note on his take of "Entschuldigen Sie"; fixed in 7eeeace, 15:54): a finding on a
      recogniser token that covers several target sounds was copied onto each of them: [tʃ] heard as [ʃ] gave
      "[t] sounded like [ʃ]" and "[ʃ] sounded like [ʃ]".  Watched 15 Oct: with the flags_out of before 7eeeace,
      the 18 F1 cases fail and the 6 designed ones pass.
The designed French nasal cases came with 9e56a5e (13 Oct 14:20): the findings at one sound merged into one flag,
so that the engine drops none (no dropped flag of this kind was recorded)."""
import os
import sys
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from host.engine import flags_out, distribute   # noqa: E402

bad = []
F1, D = "F1 13 Oct: ", "designed 13 Oct: "


def check(got, want, what):
    ok = got == want
    print(("ok   " if ok else "FAIL ") + what + ("" if ok else f"\n     got  {got}\n     want {want}"))
    if not ok:
        bad.append(what)


def finding(at, span, sound, like, off=True, left_out=False):
    return {"at": at, "span": span, "off": off, "like": like, "left_out": left_out, "sound": sound, "word": 0}


def F(at, sound, heard, off=True):
    return {"at": at, "sound": sound, "heardAs": heard, "off": off}


DE = [["ɛ", "n", "t", "ʃ", "ʊ"], ["z", "iː"]]            # "Entschuldigen Sie", cut
check(flags_out([finding(2, 2, "tʃ", "ʃ")], DE), [F(2, "t", None)],
      F1 + "tʃ heard as ʃ: [t] left out, nothing on [ʃ] (the owner's take)")
check(flags_out([finding(2, 2, "tʃ", "tʃ")], DE), [], F1 + "tʃ heard as tʃ: no complaint")
check(flags_out([finding(2, 2, "tʃ", "t")], DE), [F(3, "ʃ", None)], F1 + "tʃ heard as t: [ʃ] left out")
check(flags_out([finding(2, 2, "tʃ", "ts")], DE), [F(3, "ʃ", "s")], F1 + "tʃ heard as ts: [ʃ] sounded like [s]")
check(flags_out([finding(2, 2, "tʃ", "s")], DE), [F(2, "t", "s")],
      F1 + "tʃ heard as s (nothing in common, other length): first sound only, whole token, no 'left out' on [ʃ]")
check(flags_out([finding(2, 2, "tʃ", "", left_out=True)], DE), [F(2, "t", None), F(3, "ʃ", None)],
      D + "tʃ left out: both left out")
check(flags_out([finding(2, 2, "tʃ", "dʒ")], DE), [F(2, "t", "d"), F(3, "ʃ", "ʒ")], F1 + "tʃ heard as dʒ: sound by sound")
check(flags_out([finding(2, 2, "tʃ", "", off=False)], DE), [F(2, "t", None, False)],
      F1 + "unknown 'like' on a span: first sound only, heardAs None (as returned), 'worth checking'")

EN = [["dʒ", "ʌ"], ["ts", "a"], ["p", "f", "a"]]            # a target may hold the affricate as one sound or two
T = [["d", "ʒ", "ʌ"], ["t", "s", "a"], ["p", "f", "a"]]
check(flags_out([finding(0, 2, "dʒ", "dʒ")], T), [], F1 + "dʒ heard as dʒ: none")
check(flags_out([finding(0, 2, "dʒ", "ʒ")], T), [F(0, "d", None)], F1 + "dʒ heard as ʒ: [d] left out")
check(flags_out([finding(0, 2, "dʒ", "tʃ")], T), [F(0, "d", "t"), F(1, "ʒ", "ʃ")], F1 + "dʒ heard as tʃ: [d]->[t], [ʒ]->[ʃ]")
check(flags_out([finding(3, 2, "ts", "ts")], T), [], F1 + "ts heard as ts: none")
check(flags_out([finding(3, 2, "ts", "s")], T), [F(3, "t", None)], F1 + "ts heard as s: [t] left out")
check(flags_out([finding(6, 2, "pf", "pf")], T), [], F1 + "pf heard as pf: none")
check(flags_out([finding(6, 2, "pf", "f")], T), [F(6, "p", None)], F1 + "pf heard as f: [p] left out")
check(flags_out([finding(6, 2, "pf", "p")], T), [F(7, "f", None)], F1 + "pf heard as p: [f] left out")

AI = [["m", "a", "ɪ", "n"]]                                 # diphthong aɪ as two target sounds
check(flags_out([finding(1, 2, "aɪ", "aɪ")], AI), [], F1 + "aɪ heard as aɪ: none")
check(flags_out([finding(1, 2, "aɪ", "a")], AI), [F(2, "ɪ", None)], F1 + "aɪ heard as a: [ɪ] left out")
check(flags_out([finding(1, 2, "aɪ", "ɛ")], AI), [F(1, "a", "ɛ")], F1 + "aɪ heard as ɛ: first sound, whole token")
check(flags_out([finding(1, 1, "aɪ", "eɪ")], [["m", "aɪ", "n"]]), [F(1, "aɪ", "eɪ")],
      D + "aɪ as ONE target sound: unchanged, one flag")

FR = [["b", "ɔ̃", "ʒ", "u", "ʁ"]]                           # the French nasal: two tokens, one 'at' (already handled)
check(flags_out([finding(1, 1, "ɔ", "o"), finding(1, 1, "̃", "", left_out=True)], FR),
      [F(1, "ɔ̃", "o")], D + "French nasal: o + (U+0303 left out) merged into one flag")
check(flags_out([finding(1, 1, "ɔ", "", left_out=True)], FR), [F(1, "ɔ̃", "̃")], D + "French nasal: vowel left out keeps the mark")
check(flags_out([finding(0, 1, "b", "p")], FR), [F(0, "b", "p")], D + "single sound: unchanged")
check(distribute(["t", "ʃ"], "tʃ"), ["t", "ʃ"], D + "distribute: equal")

print("\n%d failed" % len(bad) if bad else "\nall flag cases ok")
sys.exit(1 if bad else 0)
