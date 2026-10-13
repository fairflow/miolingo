"""`env.gloss` and the meaning table (data/meanings.json), then `addWord` over HTTP on a scratch host.  No speech models
(the scratch host is started without --preload and nothing is recorded):

    <miolingo venv python> tests/check_gloss.py

Each pair (practised language -> own language) is checked on 20 texts whose meanings are known (written here by hand, not
read back from the table); the article stripping; unknown texts give ""; a text in its own language gives "".  The scratch
host keeps its database in a temporary folder; the running host (port 8810) is not touched."""
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.pop("NEOLINGO_INVERTED", None)
import env                                          # noqa: E402

fails = []
VARIANT = {"en": "en-gb", "fr": "fr-fr", "de": "de"}


def check(cond, what):
    print(("  ok   " if cond else "  FAIL ") + what)
    if not cond:
        fails.append(what)


# (text, a lower-case string the meaning must contain).  Each is right by the author's knowledge of the languages.
CASES = {
    ("fr", "en"): [("pharmacie", "pharmacy"), ("quartier", "neighbo"), ("plafond", "ceiling"), ("équipe", "team"),
                   ("boulot", "job"), ("réflexion", "reflection"), ("excitée", "excited"), ("choisi", "chosen"),
                   ("maison", "house"), ("eau", "water"), ("pain", "bread"), ("ami", "friend"), ("nuit", "night"),
                   ("acheter", "buy"), ("payer", "pay"), ("santé", "health"), ("appartement", "apartment"),
                   ("plainte", "complaint"), ("loyer", "rent"), ("oui", "yes")],
    ("de", "en"): [("geld", "money"), ("nachmittag", "afternoon"), ("richtung", "direction"), ("wunsch", "wish"),
                   ("problem", "problem"), ("arbeit", "work"), ("allein", "alone"), ("taschen", "bags"),
                   ("geschichten", "stories"), ("limit", "limit"), ("trennen", "separate"), ("wartet", "wait"),
                   ("frau", "woman"), ("nervös", "nervous"), ("geburtstag", "birthday"), ("nebel", "fog"),
                   ("konto", "account"), ("stunde", "hour"), ("berge", "mountains"), ("ja", "yes")],
    ("en", "fr"): [("hello", "bonjour"), ("goodbye", "au revoir"), ("no", "non"), ("hi", "salut"), ("maybe", "peut-être"),
                   ("now", "maintenant"), ("here", "ici"), ("already", "déjà"), ("later", "plus tard"), ("pardon", "pardon"),
                   ("opposite", "en face"), ("good evening", "bonsoir"), ("good night", "bonne nuit"),
                   ("excuse me", "excusez-moi"), ("not bad", "pas mal"), ("not yet", "pas encore"),
                   ("merry christmas", "joyeux noël"), ("over there", "là-bas"), ("congratulations", "félicitations"),
                   ("happy birthday", "bon anniversaire")],
    ("en", "de"): [("hello", "guten tag"), ("hi", "hallo"), ("no", "nein"), ("maybe", "vielleicht"), ("now", "jetzt"),
                   ("here", "hier"), ("already", "schon"), ("later", "später"), ("soon", "bald"), ("thank you", "danke"),
                   ("good night", "gute nacht"), ("good evening", "guten abend"), ("goodbye", "auf wiedersehen"),
                   ("excuse me", "entschuldigen sie"), ("not bad", "nicht schlecht"), ("not yet", "noch nicht"),
                   ("merry christmas", "frohe weihnachten"), ("over there", "dort"), ("straight ahead", "geradeaus"),
                   ("congratulations", "herzlichen glückwunsch")],
    ("fr", "de"): [("bonjour", "guten tag"), ("bonsoir", "guten abend"), ("au revoir", "auf wiedersehen"), ("demain", "morgen"),
                   ("hier", "gestern"), ("ici", "hier"), ("aujourd'hui", "heute"), ("bientôt", "bald"), ("bien", "gut"),
                   ("déjà", "schon"), ("désolé", "tut mir leid"), ("félicitations", "glückwunsch"), ("bonne nuit", "gute nacht"),
                   ("bon appétit", "guten appetit"), ("bon voyage", "gute reise"), ("d'accord", "einverstanden"),
                   ("de rien", "keine ursache"), ("en face", "gegenüber"), ("attention", "achtung"), ("bienvenue", "willkommen")],
    ("de", "fr"): [("danke", "merci"), ("bitte", "s'il vous plaît"), ("hallo", "salut"), ("guten tag", "bonjour"),
                   ("guten abend", "bonsoir"), ("gute nacht", "bonne nuit"), ("auf wiedersehen", "au revoir"), ("bald", "bientôt"),
                   ("bis morgen", "à demain"), ("dort", "là-bas"), ("einverstanden", "d'accord"), ("gestern", "hier"),
                   ("heute", "aujourd'hui"), ("hier", "ici"), ("immer", "toujours"), ("jetzt", "maintenant"), ("ja", "oui"),
                   ("jedenfalls", "bref"), ("geradeaus", "tout droit"), ("gerne", "volontiers")],
}


def main():
    print("=== known meanings, 20 per pair ===")
    for (lang, own), cases in CASES.items():
        assert len(cases) == 20, (lang, own)
        wrong = []
        for text, want in cases:
            got = env.gloss(text, own, VARIANT[lang])
            if want not in got.lower():
                wrong.append((text, want, got))
        check(not wrong, f"{lang} -> {own}: 20 of 20 right" + (f"  WRONG: {wrong}" if wrong else ""))

    print("\n=== case and article stripping ===")
    g = lambda t, o, v: env.gloss(t, o, v)
    check(g("EAU", "en", "fr-fr") == g("eau", "en", "fr-fr") == "water", "case does not matter (EAU, eau)")
    check(g("l'eau", "en", "fr-fr") == "water", "l'eau -> water (apostrophe, article l)")
    check(g("l’eau", "en", "fr-fr") == "water", "l’eau with the typographic apostrophe")
    check(g("la pharmacie", "en", "fr-fr") == g("pharmacie", "en", "fr-fr") != "", "la pharmacie = pharmacie")
    check(g("une maison", "en", "fr-fr") == g("maison", "en", "fr-fr") != "", "une maison = maison")
    check(g("un ami", "en", "fr-fr") == g("ami", "en", "fr-fr") != "", "un ami = ami")
    check(g("le plafond", "en", "fr-fr") == g("plafond", "en", "fr-fr") != "", "le plafond = plafond")
    check(g("die Frau", "en", "de") == g("frau", "en", "de") == "woman", "die Frau -> woman")
    check(g("der Nebel", "en", "de") == g("nebel", "en", "de") != "", "der Nebel = nebel")
    check(g("das Konto", "en", "de") == g("konto", "en", "de") != "", "das Konto = konto")
    check(g("ein Wunsch", "en", "de") == g("wunsch", "en", "de") != "", "ein Wunsch = wunsch")
    check(g("eine Stunde", "en", "de") == g("stunde", "en", "de") != "", "eine Stunde = stunde")
    check(g("the later", "fr", "en-gb") == g("later", "fr", "en-gb") != "", "the later = later (the; a mechanism case)")
    check(g("to later", "fr", "en-us") == g("later", "fr", "en-us") != "", "to later = later (to)")
    check(g("a hello", "de", "en-gb") == g("hello", "de", "en-gb") != "", "a hello = hello (a)")
    check(g("bonjour", "en", "fr-fr") != "", "a text that has no article is not altered")

    print("\n=== unknown words and the same language give \"\" ===")
    for t, o, v in [("xyzzyplugh", "en", "fr-fr"), ("la xyzzyplugh", "en", "fr-fr"), ("der Xyzzyplugh", "en", "de"),
                    ("the xyzzyplugh", "fr", "en-gb"), ("", "en", "fr-fr"), ("   ", "en", "de"), ("?!", "en", "fr-fr"),
                    ("recommend", "fr", "en-gb"), ("morning", "de", "en-us")]:
        check(g(t, o, v) == "", f"{t!r} ({v}, own {o}) -> \"\"")
    check(g("maison", "fr", "fr-fr") == "" and g("geld", "de", "de") == "" and g("hello", "en", "en-gb") == "",
          "the practised language as own language -> \"\"")
    check(env.gloss("recommend", "fr", "en-gb") == "", "no inversion of a dictionary by default (recommend -> \"\")")

    print("\n=== several meanings are kept as written ===")
    check(g("bonjour", "en", "fr-fr") == "hello / good day", f"bonjour -> {g('bonjour', 'en', 'fr-fr')!r}")
    check(g("bureau", "en", "fr-fr") == "desk", f"bureau -> {g('bureau', 'en', 'fr-fr')!r}")

    print("\n=== the table ===")
    t = json.loads((ROOT / "data" / "meanings.json").read_text("utf-8"))
    n = {(l, o): sum(1 for d in t[l].values() if o in d) for l in t for o in ("en", "fr", "de") if o != l}
    print("   entries (practised, own):", n)
    check(n[("fr", "en")] >= 1500 and n[("de", "en")] >= 1500, "at least 1500 French and 1500 German texts with English meanings")
    check(all(m for l in t for d in t[l].values() for m in d.values()), "no empty meaning in the table")
    check(all(o != l for l in t for d in t[l].values() for o in d), "no text is given a meaning in its own language")
    check((ROOT / "data" / "meanings.json").stat().st_size < 5_000_000, "data/meanings.json is under 5 MB")

    print("\n=== addWord over HTTP, on a scratch host ===")
    http()
    if fails:
        sys.exit(f"{len(fails)} FAILED: {fails}")
    print("\nall checks passed")


def http():
    import check_host as ch
    tmp = Path(tempfile.mkdtemp(prefix="neolingo_gloss_"))
    ch.VAR = tmp
    h = ch.Host()
    try:
        print(f"   scratch host on port {h.port}, var in {tmp}; started in {h.start():.1f} s (no --preload)")
        h.press(cmd="start")
        h.setting("practised", "fr-fr")
        frj = json.loads((ROOT / "data" / "fr.json").read_text("utf-8"))
        listed = {w.lower() for x in json.loads((ROOT / "data" / "words_fr.json").read_text("utf-8")) for w in x["words"]}
        listed |= {p["text"].lower() for p in frj["phrases"]} | {v["word"].lower() for v in frj["vocabulary"]}
        words = [("équipe", "team"), ("boulot", "job"), ("réflexion", "reflection"), ("excitée", "excited"), ("choisi", "chosen")]
        check(all(w not in listed for w, _ in words), "the five words are in none of the built-in French lists")
        d = h.press(press="show", session=1, input="Vocabulary")
        for w, want in words:
            d = h.press(press="addWord", session=1, input=w)
            check(d["step"], f"addWord {w}: {d['message']!r}")
        d = h.press(press="show", session=1, input="Vocabulary")
        rows = ch.body(d)["rows"]
        text = json.dumps(rows, ensure_ascii=False).lower()
        for w, want in words:
            row = next((r for r in rows if w in json.dumps(r, ensure_ascii=False).lower()), None)
            check(row is not None and want in json.dumps(row, ensure_ascii=False).lower(),
                  f"vocabulary row for {w} carries the meaning {want!r}: {json.dumps(row, ensure_ascii=False)[:160] if row else None}")
        log = (tmp / "host.log").read_text("utf-8")
        check("question fill" in log and "FAILED" not in log, "the engine asked `fill` and no question failed")
    finally:
        h.stop()
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
