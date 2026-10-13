"""One segmentation (protocol 3.1 item 3): do target_ipa, hear and the cost table cut sounds the same way?

    ~/Software/working/miolingo/venv/bin/python neolingo/tests/check_segmentation.py

1. For every phrase (and every vocabulary word) of data/{en,fr,de}.json: the sound strings of
   env.target_ipa that are not keys of the cost table (data/cost_table.json "phones").
2. The same for sounds passed through `phones_of` (the cutter `hear` uses on the recogniser's output): a
   target sound is a fixed point of it (phones_of(s) == [s]) or it is reported.
3. For each phone recogniser the variants use: its token inventory (tokenizer vocabulary, after `norm_word`),
   which tokens are not keys of the cost table, and which tokens `phones_of` would cut into several sounds.
   Models are read from the local cache only (nothing downloaded).
4. Length (protocol 3.1 item 3, since 13 October): the long sounds are cost keys (iː aː uː oː eː yː ...), no sound anywhere is a
   lone length mark, `phones_of` joins a lone "ː" to the sound before it, and the cost list sent to the engine has the pairs
   iː/i, i/iː ... in both directions.
Exit status 1 when a sound of a TARGET is not a cost key (those would cost `costOtherwise` and could never be
a tolerated or accepted pair); the recogniser findings are reported, not failures.
"""
import json
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import env                                                   # noqa: E402
from env import _miolingo as mio                             # noqa: E402

keys = set(json.loads((ROOT / "data" / "cost_table.json").read_text("utf-8"))["phones"])
show = lambda s: f"{s!r} [{' '.join('U+%04X' % ord(c) for c in s)}]"      # noqa: E731
bad = 0

print(f"cost table: {len(keys)} sounds\n")
LONE = lambda s: bool(s) and all(c in "\u02d0\u02d1" for c in s)         # noqa: E731
print("== 0. length ==")
for got, want in ((env.phones_of("iːnən"), ["iː", "n", "ə", "n"]), (env.phones_of(env.norm_word("i ː n")), ["iː", "n"]),
                  (env.join_length(["a", "ː", "n"]), ["aː", "n"]), (env.join_length(["ː", "a"]), ["a"]),
                  (env.phones_of("tʃː"), env.phones_of("tʃː")), (env.phones_of("ɪnən"), ["ɪ", "n", "ə", "n"])):
    if got != want:
        print(f"     WRONG: {got} != {want}")
        bad += 1
if env.norm_word("aˑ") != "aˑ" or env.norm_word("ɑː") != "ɑː":
    print("     norm_word dropped a length mark")
    bad += 1
if env.norm_word("ˈiːnən") != "iːnən":
    print(f"     norm_word('ˈiːnən') = {env.norm_word('ˈiːnən')!r}")
    bad += 1
need = ["iː", "aː", "uː", "oː", "eː", "yː"]
for s_ in need:
    if s_ not in keys or s_[0] not in keys:
        print(f"     NOT A KEY: {s_!r} or {s_[0]!r}")
        bad += 1
if any(LONE(k) for k in keys):
    print("     a lone length mark is a cost key")
    bad += 1
from host.engine_config import build_costs                  # noqa: E402
sent = {(e["target"], e["heard"]) for e in build_costs(json.loads((ROOT / "data" / "cost_table.json").read_text("utf-8")))
        if "lang" not in e}
for s_ in need:
    for pair in ((s_, s_[0]), (s_[0], s_)):
        if pair not in sent:
            print(f"     the cost list has no entry {pair}")
            bad += 1
print(f"long sounds among the cost keys: {sum('ː' in k for k in keys)}; checked {need} and their short partners both ways\n")
print("== 1/2. target sounds of the phrases and words in data/*.json ==")
lost = Counter()
for lang, var in (("en", "en-gb"), ("fr", "fr-fr"), ("de", "de"), ("en", "en-us")):
    d = json.loads((ROOT / "data" / f"{lang}.json").read_text("utf-8"))
    texts = [p["text"] for p in d["phrases"]] + [w["word"] for w in d.get("vocabulary", [])]
    seen, where = Counter(), defaultdict(list)
    for t in texts:
        # characters espeak gave that the segmenter (panphon) dropped: a sound lost silently
        raw = env.norm_word(env.target_ipa.__globals__["_espeak"](" ".join(env.target_ipa.__globals__["_text_words"](t)), env.variant(var)["espeak"]))
        got = "".join("".join(w) for w in env.target_ipa(t, var))
        for ch in set(unicodedata.normalize("NFC", raw.replace(" ", "").replace("\u203f", ""))) - set(got):
            lost[(var, ch)] += 1
        for word in env.target_ipa(t, var):
            for s in word:
                if LONE(s):
                    print(f"     LONE LENGTH MARK in the target of {t!r}")
                    bad += 1
                seen[s] += 1
                if len(where[s]) < 3 and t not in where[s]:
                    where[s].append(t)
    notkey = {s: n for s, n in seen.items() if s not in keys}
    notfixed = {s: env.phones_of(s) for s in seen if env.phones_of(s) != [s]}
    print(f"{var}: {len(texts)} texts, {len(seen)} distinct sounds, {sum(seen.values())} occurrences; "
          f"not a cost key: {len(notkey)}; not fixed by phones_of: {len(notfixed)}")
    for s, n in sorted(notkey.items(), key=lambda x: -x[1]):
        print(f"     NOT A KEY {show(s)} x{n}, e.g. {where[s]}")
        bad += 1
    for s, r in notfixed.items():
        print(f"     phones_of cuts {show(s)} into {r}")

for (var, ch), n in sorted(lost.items()):
    print(f"     LOST by the segmenter: {show(ch)} in {n} texts of {var}")
print("\n== 3. phone recognisers: token inventories ==")
done = {}
for v in env.variants():
    mid = v["phone_model"]
    if mid in done:
        print(f"{v['code']}: same model as {done[mid]} ({mid})")
        continue
    done[mid] = v["code"]
    try:
        proc, _model = mio.phone_recognizer._load(mid)
        vocab = proc.tokenizer.get_vocab() if proc is not None else None
    except Exception as e:                                    # not in the local cache, or no CTC vocabulary
        print(f"{v['code']}: {mid}: cannot load ({type(e).__name__}: {e})")
        continue
    if vocab is None:
        print(f"{v['code']}: {mid}: no CTC vocabulary")
        continue
    toks = [t for t in vocab if mio.sound_check._usable(t)]
    special = [t for t in vocab if t not in toks]
    normed = {t: env.norm_word(t) for t in toks}
    notkey = sorted(t for t, n in normed.items() if n and n not in keys)
    cut = sorted((t, env.phones_of(n)) for t, n in normed.items() if n and len(env.phones_of(n)) != 1)
    combining = sorted(t for t in toks if t and all(unicodedata.combining(c) for c in t))
    print(f"{v['code']}: {mid}: {len(vocab)} tokens ({len(special)} special/unusable), {len(toks)} usable")
    print(f"     usable tokens that are not cost keys ({len(notkey)}): {' '.join(notkey)}")
    print(f"     tokens phones_of cuts into several sounds ({len(cut)}): "
          f"{' '.join(t + '->' + '+'.join(r) for t, r in cut)}")
    print(f"     tokens that are bare combining marks ({len(combining)}): {' '.join(show(t) for t in combining)}")
    withlen = sorted(t for t in vocab if "ː" in t or "ˑ" in t)
    lone = sorted(t for t in toks if LONE(t))
    cutlone = sorted(t for t, n in normed.items() if any(LONE(x) for x in env.phones_of(n)))
    print(f"     tokens carrying a length mark: {len(withlen)} of {len(vocab)}: {' '.join(withlen)}")
    print(f"     tokens that are a lone length mark (joined to the sound before by phones_of): {lone}")
    if cutlone:
        print(f"     LONE LENGTH MARK left by phones_of for: {cutlone}")
        bad += 1

print(f"\nSUMMARY: {bad} target sound string(s) are not cost-table keys")
sys.exit(1 if bad else 0)
