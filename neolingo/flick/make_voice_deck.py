"""Build var/flick/deck-voices.json: which of two voices would you rather imitate?

    <miolingo venv python> flick/make_voice_deck.py [--per 6]

For each language (en-gb, fr-fr, de) a few phrases of the built-in lists, each spoken by Google's voice (gTTS,
the host's own cache; a network call only for a phrase not yet cached) and by the Mac's voice (`say`, no
network).  Which engine is A and which is B is decided by a hash of the phrase, so the listener cannot tell
from the position; the engine is recorded in the card (`a.engine`, `b.engine`) for the tally, and the page
shows only "A" and "B"."""
import argparse
import subprocess
import tempfile
import hashlib
import json
import re
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from host import speech                      # noqa: E402

VAR = ROOT / "var" / "flick"
AUDIO = VAR / "audio"
LANGS = [("en", "en-gb"), ("fr", "fr-fr"), ("de", "de")]
# The Mac voices to compare with Google's: Apple's Premium voices where installed (System Settings > Accessibility >
# Spoken Content), else the compact voice the host picks.  Spoken at the host's own rate (175), kept at full quality.
MAC = {"en-gb": "Serena (Premium)", "fr-fr": "Audrey (Premium)", "de": "Petra (Premium)"}


def mac_voice(variant):
    want = MAC.get(variant)
    installed = [v for vs in speech.say_voices().values() for v in vs]
    return want if want in installed else speech.pick_voice(variant)


def say_to(text, voice, out):
    """`say` with a named voice to an AAC file (no network)."""
    with tempfile.TemporaryDirectory() as td:
        tf, aiff = Path(td) / "t.txt", Path(td) / "o.aiff"
        tf.write_text(text, "utf-8")
        subprocess.run(["say", "-v", voice, "-r", "175", "-o", str(aiff), "-f", str(tf)], check=True)
        subprocess.run(["afconvert", "-f", "m4af", "-d", "aac", str(aiff), str(out)], check=True)


def phrases(lang, per, round_no=1):
    """`per` phrases of the list, evenly spread; another round takes other phrases."""
    items = json.loads((ROOT / "data" / f"{lang}.json").read_text("utf-8"))["phrases"]
    ok = [p["text"] for p in items if not re.search(r"[()/]|\.\.\.|…", p["text"]) and 2 <= len(p["text"].split()) <= 7]
    step = max(1, len(ok) // per)
    first = (step // 2 + (round_no - 1) * max(1, step // 3)) % step
    return ok[first::step][:per]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per", type=int, default=6)
    ap.add_argument("--round", type=int, default=1, help="1 = deck-voices.json; N > 1 = deck-voicesN.json, other phrases, the other order")
    a = ap.parse_args()
    tag = "voices" if a.round == 1 else f"voices{a.round}"
    AUDIO.mkdir(parents=True, exist_ok=True)
    cards = []
    for lang, variant in LANGS:
        for n, text in enumerate(phrases(lang, a.per, a.round)):
            got = {}
            p, _ctype, _used = speech.speak(text, variant, False, only="gtts")
            got["gtts"] = f"{tag}-{lang}-{n}-gtts{Path(p).suffix}"
            shutil.copyfile(p, AUDIO / got["gtts"])
            got["say"] = f"{tag}-{lang}-{n}-mac.m4a"
            say_to(text, mac_voice(variant), AUDIO / got["say"])
            first = "gtts" if (int(hashlib.sha1(text.encode("utf-8")).hexdigest(), 16) + a.round) % 2 == 1 else "say"
            second = "say" if first == "gtts" else "gtts"
            cards.append({"id": f"{tag}-{lang}-{n}", "kind": "voice", "variant": variant, "phrase": text,
                          "a": {"label": "Voice A", "audio": f"/audio/{got[first]}", "engine": first,
                                "voice": "Google" if first == "gtts" else mac_voice(variant)},
                          "b": {"label": "Voice B", "audio": f"/audio/{got[second]}", "engine": second,
                                "voice": "Google" if second == "gtts" else mac_voice(variant)}})
    deck = {"title": "Which voice would you rather imitate?" + ("" if a.round == 1 else f" Round {a.round}, other phrases"), "made": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "config": f"gTTS (Google) against macOS say ({', '.join(str(mac_voice(v)) for _l, v in LANGS)}), "
                      "normal speed; A/B order by hash of the phrase",
            "cards": cards}
    (VAR / f"deck-{tag}.json").write_text(json.dumps(deck, ensure_ascii=False, indent=1), "utf-8")
    print(len(cards), "cards;", deck["config"])
    for c in cards:
        print(" ", c["variant"], c["phrase"], "| A =", c["a"]["engine"])


if __name__ == "__main__":
    main()
