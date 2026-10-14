"""The data sets, as lists of items.  An item is a dict:

    {"id", "set", "lang", "variant", "text" (the phrase to be said), "wav" (absolute path), ...}

  archive     every line of var/archive/checks.jsonl (the stored line under "stored", WITHOUT the judgement's note:
              only "verdict"), "source": "learner" | "test-voice", "uid", "reconstructed"
  reference   the 48 phrases a language of data/{en,fr,de}.json spoken by gTTS and by `say` (var/sweep/, made by
              tests/reference_sweep.py), "voice": "gtts" | "say"
  nearmiss    var/lab/nearmiss/items.jsonl (lab/build_nearmiss.py): the voice says B, the target is A; with "truth"
  positive    the matching positives: the voice says A, the target is A
  cp          var/lab/cp/items.jsonl (lab/build_cp.py): Common Phone natives reading a sentence
  cpflip      the same audio with ONE expected sound changed to a typical English-speaker error (roles reversed)

Notes of the owner on his takes are never loaded here."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .common import ARCHIVE, DATA, LAB, LANG_OF, LANGS, SWEEP, VARIANT, read_jsonl

TEST_FILE = ARCHIVE / "overseer_takes.txt"


def test_voice_tokens() -> set:
    out = set()
    if TEST_FILE.exists():
        for l in TEST_FILE.read_text("utf-8").splitlines():
            l = l.strip()
            if l and not l.startswith("#"):
                out.add(l.split()[0])
    return out


def verdicts() -> dict:
    """take -> verdict ("fair" | "harsh" | "generous"): the LAST line of a take wins.  The note is not read."""
    d = {}
    for j in read_jsonl(ARCHIVE / "judgements.jsonl"):
        if isinstance(j, dict) and isinstance(j.get("take"), str):
            d[j["take"]] = j.get("verdict")
    return d


def archive_items() -> list[dict]:
    test = test_voice_tokens()
    vd = verdicts()
    out = []
    for l in read_jsonl(ARCHIVE / "checks.jsonl"):
        wav = ARCHIVE / "takes" / f"{l['take']}.wav"
        if not wav.exists():
            continue
        out.append({"id": l["take"], "set": "archive", "lang": LANG_OF[l["variant"]], "variant": l["variant"],
                    "text": l["text"], "wav": str(wav), "time": l.get("time"),
                    "source": "test-voice" if l["take"] in test else "learner",
                    "uid": l.get("uid") or "me", "uid_recorded": bool(l.get("uid")),
                    "reconstructed": bool(l.get("reconstructed")),
                    "verdict": vd.get(l["take"]) or "unjudged",
                    "stored": {k: l.get(k) for k in ("target", "hear", "sounds", "score", "understood", "flags",
                                                     "columns", "version", "phone_model", "droppedFlags")}})
    return out


def reference_items(langs=LANGS, voices=("gtts", "say", "premium")) -> list[dict]:
    """voice: "gtts" (Google), "say" (the compact macOS voices Daniel / Thomas / Anna), "premium" (Apple's premium
    voices Serena / Audrey / Petra, made by lab/premium.py)."""
    out = []
    for lang in langs:
        variant = VARIANT[lang]
        phrases = json.loads((DATA / f"{lang}.json").read_text("utf-8"))["phrases"]
        for voice in voices:
            for i, p in enumerate(phrases):
                key = hashlib.sha1(p["text"].encode("utf-8")).hexdigest()[:16]      # as tests/reference_sweep.py
                wav = (LAB / "premium" if voice == "premium" else SWEEP / voice) / variant / f"{key}.wav"
                if wav.exists():
                    out.append({"id": f"ref-{voice}-{lang}-{i}", "set": "reference", "lang": lang, "variant": variant,
                                "text": p["text"], "wav": str(wav), "voice": voice})
    return out


def _file_items(path: Path, sets=None) -> list[dict]:
    if not path.exists():
        return []
    rows = read_jsonl(path)
    return [r for r in rows if sets is None or r["set"] in sets]


def nearmiss_items(sets=("nearmiss", "positive")) -> list[dict]:
    return _file_items(LAB / "nearmiss" / "items.jsonl", sets)


def cp_items(sets=("cp", "cpflip")) -> list[dict]:
    return _file_items(LAB / "cp" / "items.jsonl", sets)


def all_items() -> list[dict]:
    return archive_items() + reference_items() + nearmiss_items() + cp_items()


def write_wav_list(items, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(dict.fromkeys(i["wav"] for i in items)) + "\n", "utf-8")
    return path


if __name__ == "__main__":
    import collections
    its = all_items()
    c = collections.Counter((i["set"], i["lang"]) for i in its)
    for k, v in sorted(c.items()):
        print(v, *k)
    lists = LAB / "lists"
    for lang in LANGS:
        for s in ("archive", "reference", "nearmiss", "positive", "cp", "cpflip"):
            sel = [i for i in its if i["lang"] == lang and i["set"] == s]
            if sel:
                write_wav_list(sel, lists / f"{s}-{lang}.txt")
    print("lists written to", lists)
