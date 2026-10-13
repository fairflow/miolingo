"""Build var/flick/deck-voices.json: which of two voices would you rather imitate?

    <miolingo venv python> flick/make_voice_deck.py [--per 6]

For each language (en-gb, fr-fr, de) a few phrases of the built-in lists, each spoken by Google's voice (gTTS,
the host's own cache; a network call only for a phrase not yet cached) and by the Mac's voice (`say`, no
network).  Which engine is A and which is B is decided by a hash of the phrase, so the listener cannot tell
from the position; the engine is recorded in the card (`a.engine`, `b.engine`) for the tally, and the page
shows only "A" and "B"."""
import argparse
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


def phrases(lang, per):
    items = json.loads((ROOT / "data" / f"{lang}.json").read_text("utf-8"))["phrases"]
    ok = [p["text"] for p in items if not re.search(r"[()/]|\.\.\.|…", p["text"]) and 2 <= len(p["text"].split()) <= 7]
    step = max(1, len(ok) // per)
    return ok[step // 2::step][:per]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per", type=int, default=6)
    a = ap.parse_args()
    AUDIO.mkdir(parents=True, exist_ok=True)
    cards = []
    for lang, variant in LANGS:
        for n, text in enumerate(phrases(lang, a.per)):
            got = {}
            for engine in ("gtts", "say"):
                p, _ctype, used = speech.speak(text, variant, False, only=engine)
                name = f"voices-{lang}-{n}-{engine}{Path(p).suffix}"
                shutil.copyfile(p, AUDIO / name)
                got[engine] = name
            first = "gtts" if int(hashlib.sha1(text.encode("utf-8")).hexdigest(), 16) % 2 == 0 else "say"
            second = "say" if first == "gtts" else "gtts"
            cards.append({"id": f"voices-{lang}-{n}", "kind": "voice", "variant": variant, "phrase": text,
                          "a": {"label": "Voice A", "audio": f"/audio/{got[first]}", "engine": first},
                          "b": {"label": "Voice B", "audio": f"/audio/{got[second]}", "engine": second}})
    deck = {"title": "Which voice would you rather imitate?", "made": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "config": f"gTTS (Google) against macOS say ({', '.join(str(speech.pick_voice(v)) for _l, v in LANGS)}), "
                      "normal speed; A/B order by hash of the phrase",
            "cards": cards}
    (VAR / "deck-voices.json").write_text(json.dumps(deck, ensure_ascii=False, indent=1), "utf-8")
    print(len(cards), "cards;", deck["config"])
    for c in cards:
        print(" ", c["variant"], c["phrase"], "| A =", c["a"]["engine"])


if __name__ == "__main__":
    main()
