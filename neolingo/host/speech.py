"""Speech for `speak`.  The engine is chosen by NEOLINGO_TTS = gtts (default) | say.

  gtts    Google's text-to-speech through the `gtts` package (the ONE network use allowed): MP3.  Language from
          the variant (fr, en with tld co.uk for en-gb and com for en-us, de), `slow=` from the setting.  If the
          call fails: `say`.
  say     macOS `say` with a voice of the right language + afconvert: WAV.

espeak-ng is NOT a voice (the owner, 13 October 2026: too horrible to hear).  If every voice of the chain fails,
`speak` raises SpeechUnavailable and the endpoint answers an error the page can show.  espeak-ng remains the source of
the target sounds (env.target_ipa) and the tests' synthetic voice (`speak(..., only="espeak")` is kept for the tests,
never reached by the chain).

Cached under var/speech/, keyed by the engine that made the file + text + variant + slow.  The log says which
engine answered each request."""
import hashlib
import os
import re
import shutil
import subprocess
import tempfile

import env
from .log import log
from .paths import SPEECH

LOCALE = {"en-gb": "en_GB", "en-us": "en_US", "fr-fr": "fr_FR", "de": "de_DE"}
PREFERRED = ["Daniel", "Samantha", "Thomas", "Anna"]
_voices = None


def say_voices():
    """{locale: [voice names]} of the installed `say` voices."""
    global _voices
    if _voices is None:
        _voices = {}
        if shutil.which("say"):
            r = subprocess.run(["say", "-v", "?"], capture_output=True, text=True)
            for ln in r.stdout.splitlines():
                m = re.match(r"^(.+?)\s{2,}([a-z]{2}_[A-Z]{2})\s", ln)
                if m:
                    _voices.setdefault(m.group(2), []).append(m.group(1).strip())
    return _voices


def pick_voice(variant):
    vs = say_voices().get(LOCALE.get(variant, ""), [])
    for p in PREFERRED:
        if p in vs:
            return p
    return vs[0] if vs else None


GTTS = {"fr-fr": ("fr", "fr"), "en-gb": ("en", "co.uk"), "en-us": ("en", "com"), "de": ("de", "de")}
CHAINS = {"gtts": ["gtts", "say"], "say": ["say"]}
TTS = os.environ.get("NEOLINGO_TTS", "gtts").strip().lower()
if TTS not in CHAINS:
    raise SystemExit(f"NEOLINGO_TTS={TTS!r}: expected gtts or say (espeak is not a voice)")
IN_USE = TTS                    # the engine that answered the latest request (the configured one until then)
CTYPE = {"gtts": "audio/mpeg", "say": "audio/wav", "espeak": "audio/wav"}


def _key(engine, text, variant, slow):
    extra = pick_voice(variant) if engine == "say" else ""
    return hashlib.sha1(f"{engine}\0{text}\0{variant}\0{int(slow)}\0{extra}".encode("utf-8")).hexdigest()[:24]


def _path(engine, text, variant, slow):
    return SPEECH / f"{_key(engine, text, variant, slow)}.{'mp3' if engine == 'gtts' else 'wav'}"


def _make_gtts(text, variant, slow, out):
    from gtts import gTTS
    lang, tld = GTTS[variant]
    with tempfile.TemporaryDirectory(dir=SPEECH) as td:
        tmp = os.path.join(td, "o.mp3")
        gTTS(text=text, lang=lang, tld=tld, slow=bool(slow)).save(tmp)
        if os.path.getsize(tmp) < 500:
            raise RuntimeError("gTTS returned almost nothing")
        os.replace(tmp, out)


def _make_say(text, variant, slow, out):
    voice = pick_voice(variant)
    if not (voice and shutil.which("say") and shutil.which("afconvert")):
        raise RuntimeError("no `say` voice for " + variant)
    with tempfile.TemporaryDirectory(dir=SPEECH) as td:
        tmp, tf, aiff = os.path.join(td, "o.wav"), os.path.join(td, "t.txt"), os.path.join(td, "o.aiff")
        with open(tf, "w", encoding="utf-8") as f:
            f.write(text)
        subprocess.run(["say", "-v", voice, "-r", "110" if slow else "175", "-o", aiff, "-f", tf], check=True)
        subprocess.run(["afconvert", "-f", "WAVE", "-d", "LEI16@22050", "-c", "1", aiff, tmp], check=True)
        os.replace(tmp, out)


def _make_espeak(text, variant, slow, out):
    v = env.variant(variant)
    with tempfile.TemporaryDirectory(dir=SPEECH) as td:
        tmp = os.path.join(td, "o.wav")
        subprocess.run([shutil.which("espeak-ng") or "espeak-ng", "-v", v["espeak"], "-s", "110" if slow else "160",
                        "-w", tmp, "--", text], check=True)
        os.replace(tmp, out)


MAKERS = {"gtts": _make_gtts, "say": _make_say, "espeak": _make_espeak}


class SpeechUnavailable(RuntimeError):
    """Every voice of the chain failed (espeak-ng is never a voice)."""


def speak(text, variant, slow, only=None):
    """(path, content type, engine) of cached speech of `text` in `variant`: the first engine of the chain that
    has it cached or can make it.  `only` restricts the chain to one engine (the tests)."""
    global IN_USE
    env.variant(variant)
    chain = [only] if only else CHAINS[TTS]
    for engine in chain:               # a cached file of an engine earlier in the chain wins: it was made in earnest
        p = _path(engine, text, variant, slow)
        if p.exists():
            IN_USE = engine
            return p, CTYPE[engine], engine
    for engine in chain:
        p = _path(engine, text, variant, slow)
        try:
            MAKERS[engine](text, variant, slow, p)
        except Exception as e:
            log(f"speech: {engine} failed ({type(e).__name__}: {str(e)[:150]})" + ("; falling back" if engine != chain[-1] else ""))
            continue
        IN_USE = engine
        return p, CTYPE[engine], engine
    raise SpeechUnavailable("No voice is available just now: Google's voice needs the network, and the Mac voice failed.")
