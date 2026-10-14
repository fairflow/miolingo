"""The flick deck of the recommended configuration: one card per LEARNER take, most changed against the baseline first.

    <python> -m lab.deck        -> var/flick/deck-results.json   (the flick server on 8812 picks it up by itself)

Card: {"id", "kind": "result", "audio": "/take/<token>.wav", "variant", "phrase", "heardText", "understood", "score",
       "words": [{"text": the phrase's word with its punctuation, "sounds": [{"t", "h", "k"}]}],
       "before": {"score", "different"}}   (before = the baseline: the live pipeline)
k: ok | near | off | missing | added | unjudged;  t is "" only for added, h is "" only for missing.
The file is validated against this description before it is written; every audio path must exist under
var/archive/takes/.  Nothing of the owner's notes is read."""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime

from . import analyse as A
from . import datasets
from . import recommend as R
from .common import ARCHIVE, VAR, write_json
from .run import all_variants, model_of

OUT = VAR / "flick" / "deck-results.json"
KINDS = {"ok", "near", "off", "missing", "added", "unjudged"}


def word_names(text: str, n: int) -> list[str]:
    toks = text.split()
    if len(toks) != n:
        toks = [t for t in toks if any(c.isalnum() for c in t)]
    if len(toks) != n:
        return [text] + [""] * (n - 1)
    return toks


def card(it, rec, base):
    groups = A.word_columns(rec)
    names = word_names(it["text"], len(groups))
    words = []
    for name, g in zip(names, groups):
        words.append({"text": name, "sounds": [{"t": t or "", "h": h or "", "k": k} for (t, h, k) in g]})
    return {"id": it["id"], "kind": "result", "audio": f"/take/{it['id']}.wav", "variant": it["variant"],
            "phrase": it["text"], "heardText": rec["heard_text"] or "", "understood": bool(rec["understood"]),
            "score": int(rec["score"]), "words": words,
            "before": {"score": int(base["score"]), "different": int(base["n_diff"])}}


def change(rec, base) -> tuple:
    cols_changed = sum(1 for a, b in zip(rec["columns"], base["columns"]) if a != b) + \
        abs(len(rec["columns"]) - len(base["columns"]))
    return (abs(rec["score"] - base["score"]) + 5 * abs(rec["n_diff"] - base["n_diff"]) + cols_changed
            + 10 * (rec["understood"] != base["understood"]),)


def validate(deck) -> list[str]:
    errs = []
    if not isinstance(deck.get("title"), str) or not isinstance(deck.get("made"), str) or \
            not isinstance(deck.get("config"), str) or not isinstance(deck.get("cards"), list):
        errs.append("top level: title, made, config must be strings and cards a list")
    try:
        datetime.fromisoformat(deck["made"])
    except Exception:                                       # noqa: BLE001
        errs.append(f"made is not an ISO time: {deck.get('made')!r}")
    ids = set()
    for c in deck.get("cards", []):
        cid = c.get("id")
        where = f"card {cid}"
        if not (isinstance(cid, str) and re.fullmatch(r"t[0-9a-f]{16}", cid)):
            errs.append(f"{where}: id is not a take token")
        if cid in ids:
            errs.append(f"{where}: duplicate id")
        ids.add(cid)
        if c.get("kind") != "result":
            errs.append(f"{where}: kind != result")
        if c.get("audio") != f"/take/{cid}.wav":
            errs.append(f"{where}: audio {c.get('audio')!r}")
        elif not (ARCHIVE / "takes" / f"{cid}.wav").is_file():
            errs.append(f"{where}: audio file missing under var/archive/takes/")
        for k, ty in (("variant", str), ("phrase", str), ("heardText", str), ("understood", bool), ("score", int)):
            if not isinstance(c.get(k), ty) or (ty is int and isinstance(c.get(k), bool)):
                errs.append(f"{where}: {k} must be {ty.__name__}")
        if isinstance(c.get("score"), int) and not 0 <= c["score"] <= 100:
            errs.append(f"{where}: score out of range")
        b = c.get("before")
        if not (isinstance(b, dict) and isinstance(b.get("score"), int) and isinstance(b.get("different"), int)):
            errs.append(f"{where}: before must be {{score: int, different: int}}")
        ws = c.get("words")
        if not isinstance(ws, list) or not ws:
            errs.append(f"{where}: words must be a non-empty list")
            continue
        for w in ws:
            if not isinstance(w.get("text"), str) or not isinstance(w.get("sounds"), list):
                errs.append(f"{where}: a word lacks text or sounds")
                continue
            for s in w["sounds"]:
                t, h, k = s.get("t"), s.get("h"), s.get("k")
                if set(s) != {"t", "h", "k"} or not isinstance(t, str) or not isinstance(h, str) or k not in KINDS:
                    errs.append(f"{where}: bad sound {s!r}")
                    continue
                if (t == "") != (k == "added"):
                    errs.append(f"{where}: t empty iff added violated: {s!r}")
                if (h == "") != (k == "missing"):
                    errs.append(f"{where}: h empty iff missing violated: {s!r}")
                if k in ("ok", "unjudged") and t != h:
                    errs.append(f"{where}: {k} with t != h: {s!r}")
                if k in ("near", "off") and (t == h or not t or not h):
                    errs.append(f"{where}: {k} must have two different sounds: {s!r}")
    return errs


def main():
    allv = all_variants()
    cards, order = [], []
    for it in datasets.archive_items():
        if it["source"] != "learner":
            continue
        name = R.RECOMMENDED[it["lang"]]
        cfg = {**A.BASELINE, **allv[name]}
        m = model_of(cfg, it["lang"])
        rec = A.analyse(it, {**cfg, "model": m})
        base = A.analyse(it, {"model": model_of({}, it["lang"])})
        c = card(it, rec, base)
        cards.append(c)
        order.append((change(rec, base), it.get("time") or ""))
    idx = sorted(range(len(cards)), key=lambda i: (-order[i][0][0], order[i][1]))
    deck = {"title": "Lab: the recommended analysis of every learner take",
            "made": datetime.now().astimezone().isoformat(timespec="seconds"),
            "config": R.DECK_CONFIG,
            "cards": [cards[i] for i in idx]}
    errs = validate(deck)
    if errs:
        print("DECK NOT WRITTEN, it fails the description:\n  " + "\n  ".join(errs[:40]))
        sys.exit(1)
    write_json(OUT, deck, indent=1)
    changed = sum(1 for i in idx if order[i][0][0] > 0)
    print(f"{OUT}: {len(cards)} cards ({changed} changed against the baseline); validated: OK")


if __name__ == "__main__":
    main()
