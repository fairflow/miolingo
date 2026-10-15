"""Paths and small helpers for the lab (the offline experiment bench).

Everything the lab writes goes under var/lab/ (git-ignored); the only other file written is var/flick/deck-results.json
(lab/deck.py).  The lab never talks to the live host and never starts one.  Hugging Face is offline: a model that is not
in the local cache is recorded as "not available"."""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

ROOT = Path(__file__).resolve().parent.parent          # neolingo/
VAR = ROOT / "var"
LAB = VAR / "lab"                                        # results and caches
CACHE = LAB / "cache"
ARCHIVE = VAR / "archive"
SWEEP = VAR / "sweep"
DATA = ROOT / "data"
PY = sys.executable

# `host.paths` reads NEOLINGO_VAR at import: anything of the host's code that the lab imports (speech synthesis, the
# scratch engine session of tests/replay_archive.py) then writes its cache and log under var/lab/hostvar, never into the
# live host's var/.  The archive and the sweep audio are read from the real var/ by explicit paths.
HOSTVAR = LAB / "hostvar"
os.environ["NEOLINGO_VAR"] = str(HOSTVAR)

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

LANGS = ("en", "fr", "de")
VARIANT = {"en": "en-gb", "fr": "fr-fr", "de": "de"}
LANG_OF = {"en-gb": "en", "en-us": "en", "fr-fr": "fr", "de": "de"}

XLSR = "facebook/wav2vec2-xlsr-53-espeak-cv-ft"
LV60 = "facebook/wav2vec2-lv-60-espeak-cv-ft"
CNAM = "Cnam-LMSSC/wav2vec2-french-phonemizer"
HKDE = "HK0712/Wav2Vec2_German_IPA"
PKL = "pklumpp/Wav2Vec2_CommonPhone"
BASE_MODEL = {"en": XLSR, "fr": CNAM, "de": XLSR}       # what the live host uses (env.variants.phone_model)


def mkdirs():
    for d in (LAB, CACHE, HOSTVAR):
        d.mkdir(parents=True, exist_ok=True)


_SHA_INDEX: dict | None = None
_SHA_FILE = CACHE / "sha_index.json"


def wav_sha(path) -> str:
    """Content hash (sha1 of the bytes) of a file; remembered by (path, size, mtime) so a file is read once."""
    global _SHA_INDEX
    p = Path(path)
    st = p.stat()
    key = f"{p}|{st.st_size}|{st.st_mtime_ns}"
    if _SHA_INDEX is None:
        try:
            _SHA_INDEX = json.loads(_SHA_FILE.read_text("utf-8"))
        except (OSError, ValueError):
            _SHA_INDEX = {}
    h = _SHA_INDEX.get(key)
    if h is None:
        h = hashlib.sha1(p.read_bytes()).hexdigest()
        _SHA_INDEX[key] = h
    return h


def save_sha_index():
    if _SHA_INDEX is not None:
        CACHE.mkdir(parents=True, exist_ok=True)
        tmp = _SHA_FILE.with_suffix(f".{os.getpid()}.tmp")
        tmp.write_text(json.dumps(_SHA_INDEX), "utf-8")
        os.replace(tmp, _SHA_FILE)


def read_jsonl(path):
    out = []
    with open(path, encoding="utf-8") as f:
        for l in f:
            l = l.strip()
            if l:
                try:
                    out.append(json.loads(l))
                except ValueError:
                    pass
    return out


def write_jsonl(path, rows):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(str(path) + f".{os.getpid()}.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    os.replace(tmp, path)


def write_json(path, obj, **kw):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(str(path) + f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, **kw), "utf-8")
    os.replace(tmp, path)


def slug(model_id: str) -> str:
    return model_id.replace("/", "--")


# the protocol's normalisation of sounds (section 5: stress marks and punctuation are not sounds; empty sounds and
# empty words dropped).  The engine applies the same `norm` to everything it is given; the lab applies it to its targets
# and readings so that its indices of target sounds are the engine's.
def no_sound(c: str) -> bool:
    return c in "ˈˌ" or (ord(c) < 128 and not c.isalpha()) or c in "‿‖"


def norm(ipa):
    out = []
    for w in ipa or []:
        ww = ["".join(c for c in ph if not no_sound(c)) for ph in w]
        ww = [p for p in ww if p]
        if ww:
            out.append(ww)
    return out


def flat(ipa):
    return [p for w in ipa or [] for p in w]
