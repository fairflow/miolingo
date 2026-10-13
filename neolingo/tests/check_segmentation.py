"""One segmentation (protocol 3.1 item 3): do target_ipa, hear and the cost table cut sounds the same way?

    ~/Software/working/miolingo/venv/bin/python neolingo/tests/check_segmentation.py

1. For every phrase (and every vocabulary word) of data/{en,fr,de}.json: the sound strings of
   env.target_ipa that are not keys of the cost table (data/cost_table.json "phones").
2. The same for sounds passed through `phones_of` (the cutter `hear` uses on the recogniser's output): a
   target sound is a fixed point of it (phones_of(s) == [s]) or it is reported.
3. For each phone recogniser the variants use: its token inventory (tokenizer vocabulary, after `norm_word`),
   which tokens are not keys of the cost table, and which tokens `phones_of` would cut into several sounds.
   Models are read from the local cache only (nothing downloaded).
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

print(f"\nSUMMARY: {bad} target sound string(s) are not cost-table keys")
sys.exit(1 if bad else 0)
