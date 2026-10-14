"""Near misses with known ground truth: the voice says B, the target is A, and A and B differ by ONE sound.

    <python> -m lab.build_nearmiss mine            mine the pairs -> var/lab/nearmiss/pairs.json (no audio, no network)
    <python> -m lab.build_nearmiss synth [--gtts]  make the audio (`say`; with --gtts also Google's voice for a third)
                                                   -> var/lab/nearmiss/items.jsonl

Words: data/words_{en,fr,de}.json, the words of the phrases and the vocabulary of data/{en,fr,de}.json, the one-word
keys of data/meanings.json (for English also the one-word English meanings there), and lab/data/extra_words_<lang>.txt
(a short supplement so that the contrasts the check cannot judge occur: German ü/u, ü/i, ö/o; English TRAP and LOT;
French u/ou and the nasal vowels).  The target sounds of every word come from `env.target_ipa`; a pair is two words of
one language whose sound sequences differ by exactly one substitution, one deletion or one insertion (words with the
same sounds count as one).  Which pairs exist is decided by espeak's sounds alone.

Each unordered pair {A, B} gives two near misses (target A / voice B, target B / voice A) and two positives (target A /
voice A, target B / voice B).  Ground truth: the kind of the edit, its place(s) in the target (several when a doubled
sound makes the place ambiguous), the target's sound and the sound said.

Audio: host/speech.py through tests/reference_sweep.py's `synth` (the voice of the language: Daniel, Thomas, Anna;
decoded to 16 kHz mono), with the host's var/ redirected to var/lab/hostvar.  Google's voice only with --gtts, for a
random third of the pairs, at most GTTS_WORDS words a language (the budget: 400 requests in all), spaced by a second;
var/lab/nearmiss/gtts_requests.json counts the requests really made.

CAVEAT: synthetic voices saying single words; "what B sounds like" is espeak's reading of B, not a transcription of
the voice."""
from __future__ import annotations

import collections
import json
import random
import sys
import time
import unicodedata
from pathlib import Path

from . import analyse as A
from . import engine_py as E
from .common import DATA, LAB, LANGS, VARIANT, write_json, write_jsonl

OUT = LAB / "nearmiss"
PAIRS_PER_LANG = 160          # unordered pairs: 320 near misses and up to 320 positives a language
MAX_PER_WORD = 3
GTTS_WORDS = 125              # words a language for Google's voice (3 x 125 = 375 <= 400 requests)
SEED = 20261013
VOWELS = set("aeiouyøœɛɔɪʊʏæɑəɐɜɒʌɚᵻɵʉɨɶɤɯ")


def is_vowel(ph: str) -> bool:
    return unicodedata.normalize("NFD", ph)[0] in VOWELS


def clean(w: str) -> str:
    w = unicodedata.normalize("NFC", w.strip())
    return w.strip(".,;:!?()[]«»\"“”„…/").strip()


def ok_word(w: str) -> bool:
    return len(w) >= 2 and all(c.isalpha() for c in w)


def pool(lang: str) -> dict:
    """word -> source ("lists" | "phrases" | "meanings" | "extra")."""
    out: dict = {}

    def add(w, src):
        w = clean(w)
        if ok_word(w) and w.lower() not in {x.lower() for x in ()}:
            out.setdefault(w, src)
    for g in json.loads((DATA / f"words_{lang}.json").read_text("utf-8")):
        for w in g["words"]:
            add(w, "lists")
    d = json.loads((DATA / f"{lang}.json").read_text("utf-8"))
    for p in d["phrases"]:
        for t in p["text"].replace("’", "'").split():
            if "'" not in t and "-" not in t:
                add(t.lower(), "phrases")
    for v in d.get("vocabulary", []):
        t = v.get("text") or v.get("word") or ""
        if " " not in t:
            add(t, "phrases")
    m = json.loads((DATA / "meanings.json").read_text("utf-8"))
    for k in m.get(lang, {}):
        if " " not in k:
            add(k, "meanings")
    if lang == "en":
        for l2 in ("fr", "de"):
            for k, v in m.get(l2, {}).items():
                g = (v.get("en") or "").strip().lower()
                if g and " " not in g and "/" not in g:
                    add(g, "meanings")
    f = Path(__file__).parent / "data" / f"extra_words_{lang}.txt"
    if f.exists():
        for l in f.read_text("utf-8").splitlines():
            if l.strip() and not l.startswith("#"):
                add(l, "extra")
    # one spelling per lower-case form (the first seen)
    seen, res = set(), {}
    for w, s in out.items():
        if w.lower() not in seen:
            seen.add(w.lower())
            res[w] = s
    return res


def truth_of(a, b):
    """The one edit that turns the target a into what was said b: {"kind", "pos": [...], "t", "s"} or None."""
    if len(a) == len(b):
        d = [i for i in range(len(a)) if a[i] != b[i]]
        if len(d) == 1:
            return {"kind": "sub", "pos": d, "t": a[d[0]], "s": b[d[0]]}
        return None
    if len(a) == len(b) + 1:                       # the voice left a sound out
        pos = [i for i in range(len(a)) if a[:i] + a[i + 1:] == b]
        return {"kind": "del", "pos": pos, "t": a[pos[0]], "s": None} if pos else None
    if len(b) == len(a) + 1:                       # the voice said an extra sound, before target sound pos
        pos = [j for j in range(len(b)) if b[:j] + b[j + 1:] == a]
        return {"kind": "ins", "pos": pos, "t": None, "s": b[pos[0]]} if pos else None
    return None


def mine(lang: str):
    variant = VARIANT[lang]
    words = pool(lang)
    cfg_unrel = set(E.cost_table()["langs"][lang]["unreliable"])
    seqs: dict = {}                                # sound sequence -> (word, source), the first word wins
    bad: list = []
    skipped = collections.Counter()
    order = {"lists": 0, "phrases": 1, "extra": 2, "meanings": 3}
    import env
    from env import _miolingo as mio
    voice = env.variant(variant)["espeak"]
    for w, src in sorted(words.items(), key=lambda kv: (order[kv[1]], kv[0].lower())):
        raw = raw_ipa(w, voice)
        if "?" in raw:                 # espeak-ng has no IPA for one of the word's sounds (German short "ur": "??")
            skipped["espeak wrote ?? for a sound"] += 1
            bad.append(w)
            continue
        t = A.target_of(w, variant)
        if len(t) != 1:
            skipped["not one word of sounds"] += 1
            continue
        s = tuple(t[0])
        if not (2 <= len(s) <= 10):
            skipped["length"] += 1
            continue
        if s in seqs:
            skipped["same sounds as another word"] += 1
            continue
        seqs[s] = (w, src)
    keys = list(seqs)
    by_wild, by_del = collections.defaultdict(list), collections.defaultdict(list)
    for s in keys:
        for i in range(len(s)):
            by_wild[s[:i] + ("*",) + s[i + 1:]].append(s)
            by_del[s[:i] + s[i + 1:]].append(s)
    pairs = set()
    for grp in by_wild.values():
        for x in grp:
            for y in grp:
                if x < y:
                    pairs.add((x, y))
    for s in keys:
        for longer in by_del.get(s, []):
            if longer != s:
                pairs.add((s, longer) if s < longer else (longer, s))
    out = []
    for x, y in sorted(pairs):
        tr = truth_of(list(x), list(y))
        if tr is None:
            continue
        sounds = [p for p in (tr["t"], tr["s"]) if p]
        if tr["kind"] == "sub":
            cls = "vowel" if all(map(is_vowel, sounds)) else "consonant" if not any(map(is_vowel, sounds)) else "mixed"
        else:
            cls = "vowel" if is_vowel(sounds[0]) else "consonant"
        unrel = [p for p in sounds if p in cfg_unrel]
        out.append({"a": seqs[x][0], "b": seqs[y][0], "a_ipa": list(x), "b_ipa": list(y),
                    "kind": "sub" if tr["kind"] == "sub" else "indel", "class": cls, "sounds": sounds,
                    "unreliable": bool(unrel and tr["kind"] == "sub"),
                    "sources": sorted({seqs[x][1], seqs[y][1]})})
    skipped["_words_espeak_wrote_??_for"] = sorted(bad)
    return words, seqs, out, skipped


_RAW_FILE = OUT / "espeak_raw.json"
_RAW: dict | None = None


def raw_ipa(word: str, voice: str) -> str:
    """Miolingo's get_ipa output for a word (with stress marks and whatever espeak wrote), remembered on disk."""
    global _RAW
    if _RAW is None:
        try:
            _RAW = json.loads(_RAW_FILE.read_text("utf-8"))
        except (OSError, ValueError):
            _RAW = {}
    k = f"{voice}|{word}"
    if k not in _RAW:
        from env import _miolingo as mio
        _RAW[k] = mio.phonemes.get_ipa(word, voice)
    return _RAW[k]


def select(pairs, rng):
    """Up to PAIRS_PER_LANG unordered pairs: first those that touch a sound the check cannot judge (at most a
    quarter), then the bucket furthest below its share (vowel substitutions 35%, consonant substitutions 35%, vowel
    and consonant insertions/deletions 15% each); no word in more than MAX_PER_WORD pairs."""
    used = collections.Counter()
    chosen = []

    def take(p):
        if used[p["a"]] >= MAX_PER_WORD or used[p["b"]] >= MAX_PER_WORD:
            return False
        used[p["a"]] += 1
        used[p["b"]] += 1
        chosen.append(p)
        return True
    pool_ = list(pairs)
    rng.shuffle(pool_)
    for p in [p for p in pool_ if p["unreliable"] and p["class"] == "vowel"]:
        if len(chosen) >= PAIRS_PER_LANG // 4:
            break
        take(p)
    buckets = {(c, k): [p for p in pool_ if p["class"] == c and p["kind"] == k and p not in chosen]
               for c in ("vowel", "consonant") for k in ("sub", "indel")}
    share = {("vowel", "sub"): 0.35, ("consonant", "sub"): 0.35, ("vowel", "indel"): 0.15, ("consonant", "indel"): 0.15}
    count = collections.Counter((p["class"], p["kind"]) for p in chosen)
    while len(chosen) < PAIRS_PER_LANG:
        open_ = [b for b in share if buckets[b]]
        if not open_:
            break
        b = min(open_, key=lambda b: count[b] / share[b])          # the bucket furthest below its share
        while buckets[b]:
            if take(buckets[b].pop()):
                count[b] += 1
                break
    return chosen


def cmd_mine():
    OUT.mkdir(parents=True, exist_ok=True)
    res = {}
    for lang in LANGS:
        rng = random.Random(f"{SEED}-{lang}")
        words, seqs, pairs, skipped = mine(lang)
        chosen = select(pairs, rng)
        c_all = collections.Counter((p["class"], p["kind"]) for p in pairs)
        c_sel = collections.Counter((p["class"], p["kind"]) for p in chosen)
        bad = skipped.pop("_words_espeak_wrote_??_for")
        write_json(_RAW_FILE, _RAW or {})
        res[lang] = {"words": len(words), "words_espeak_has_no_ipa_for": bad, "distinct_sound_sequences": len(seqs), "pairs_found": len(pairs),
                     "pairs_found_by_kind": {f"{c} {k}": n for (c, k), n in sorted(c_all.items())},
                     "pairs_chosen": len(chosen),
                     "pairs_chosen_by_kind": {f"{c} {k}": n for (c, k), n in sorted(c_sel.items())},
                     "chosen_touching_unjudged_sound": sum(p["unreliable"] for p in chosen),
                     "chosen_with_a_supplement_word": sum("extra" in p["sources"] for p in chosen),
                     "skipped": dict(skipped), "chosen": chosen}
        print(lang, {k: v for k, v in res[lang].items() if k != "chosen"})
    write_json(OUT / "pairs.json", res, indent=1)


def directed(lang, chosen):
    """[(target word, target sounds, said word, said sounds, truth)] for both directions of each pair."""
    out = []
    for p in chosen:
        for (a, ai, b, bi) in ((p["a"], p["a_ipa"], p["b"], p["b_ipa"]), (p["b"], p["b_ipa"], p["a"], p["a_ipa"])):
            tr = truth_of(ai, bi)
            tr["class"] = p["class"]
            out.append((a, ai, b, bi, tr))
    return out


def cmd_synth(with_gtts: bool):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tests"))
    import reference_sweep as rs                   # host/speech.py + ffmpeg to 16 kHz mono; cache under var/lab/hostvar
    from host import paths
    paths.make_dirs()
    res = json.loads((OUT / "pairs.json").read_text("utf-8"))
    cfg = E.cost_table()
    items, fails = [], []
    req_file = OUT / "gtts_requests.json"
    req = json.loads(req_file.read_text("utf-8")) if req_file.exists() else {"requests": 0, "words": {}}
    for lang in LANGS:
        variant = VARIANT[lang]
        unrel = set(cfg["langs"][lang]["unreliable"])
        chosen = res[lang]["chosen"]
        rng = random.Random(f"{SEED}-gtts-{lang}")
        order = list(range(len(chosen)))
        rng.shuffle(order)
        gwords, gpairs = [], set()
        for k in order[: (len(chosen) + 2) // 3]:              # a random third of the pairs
            need = [w for w in (chosen[k]["a"], chosen[k]["b"]) if w not in gwords]
            if len(gwords) + len(need) > GTTS_WORDS:
                continue
            gwords += need
            gpairs.add(k)
        wav = {"say": {}, "gtts": {}}
        allwords = list(dict.fromkeys(w for p in chosen for w in (p["a"], p["b"])))
        for w in allwords:
            path, _t, err = rs.synth("say", w, variant)
            if path is None:
                fails.append((lang, "say", w, err))
            else:
                wav["say"][w] = str(path)
        if with_gtts:
            for w in gwords:
                key = f"{variant}|{w}"
                before = (rs.SWEEP / "gtts" / variant / (__import__("hashlib").sha1(w.encode("utf-8")).hexdigest()[:16] + ".wav")).exists()
                if not before:
                    if req["requests"] >= 395:
                        fails.append((lang, "gtts", w, "request budget reached"))
                        continue
                    req["requests"] += 1
                    req["words"][key] = time.strftime("%Y-%m-%dT%H:%M:%S")
                    write_json(req_file, req)
                path, _t, err = rs.synth("gtts", w, variant, tries=(0, 10))
                if path is None:
                    fails.append((lang, "gtts", w, err))
                else:
                    wav["gtts"][w] = str(path)
                if not before:
                    time.sleep(1.0)
        else:
            for w in gwords:
                p = rs.SWEEP / "gtts" / variant / (__import__("hashlib").sha1(w.encode("utf-8")).hexdigest()[:16] + ".wav")
                if p.exists():
                    wav["gtts"][w] = str(p)
        for voice in ("say", "gtts"):
            pos_done = set()
            for k, p in enumerate(chosen):
                if voice == "gtts" and k not in gpairs:
                    continue
                for (a, ai, b, bi, tr) in directed(lang, [p]):
                    if a not in wav[voice] or b not in wav[voice]:
                        continue
                    tr["unreliable_target"] = bool(tr["t"] in unrel) if tr["kind"] == "sub" else False
                    items.append({"id": f"nm-{voice}-{lang}-{a}-{b}", "set": "nearmiss", "lang": lang, "variant": variant,
                                  "text": a, "wav": wav[voice][b], "voice": voice, "said": b, "said_ipa": bi,
                                  "truth": tr})
                    if a not in pos_done:
                        pos_done.add(a)
                        items.append({"id": f"pos-{voice}-{lang}-{a}", "set": "positive", "lang": lang,
                                      "variant": variant, "text": a, "wav": wav[voice][a], "voice": voice})
        print(lang, "words", len(allwords), "say", len(wav["say"]), "gtts words", len(gwords), "made", len(wav["gtts"]),
              flush=True)
    write_jsonl(OUT / "items.jsonl", items)
    c = collections.Counter((i["set"], i["lang"], i["voice"]) for i in items)
    for k, v in sorted(c.items()):
        print(v, *k)
    print("gTTS requests made so far:", req["requests"])
    if fails:
        print("FAILED:", fails[:20], f"({len(fails)} in all)")
        write_json(OUT / "synth_failures.json", fails)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "mine"
    if cmd == "mine":
        cmd_mine()
    elif cmd == "synth":
        cmd_synth("--gtts" in sys.argv)
    else:
        sys.exit(__doc__)
