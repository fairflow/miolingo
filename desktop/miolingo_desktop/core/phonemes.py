"""IPA and phoneme extraction via espeak.

Ported from ``src/scoring/phonemes.py`` (already pure). The HTML-producing
``format_ipa`` helper was intentionally NOT ported — HTML/markup is a UI concern
and belongs in the Qt layer, keeping ``core/`` framework-free.

Runtime dependency: an espeak binary must be on PATH (``espeak`` on macOS via
MacPorts, ``espeak-ng`` on Debian/Ubuntu). espeak is used only for IPA/phoneme
*scoring*, not for audio playback (that is Piper — see ``tts.py``).
"""

from __future__ import annotations

import functools
import re
import shutil
import subprocess
from pathlib import Path

ESPEAK_LANG_MAP: dict[str, str] = {
    "pt": "pt-br",
    "fr": "fr-fr",
    "nl": "nl",
    "de": "de",
    "it": "it",
    "es": "es",
    "en": "en",
}


@functools.lru_cache(maxsize=1)
def get_espeak_path() -> str:
    """Resolve the espeak binary path.

    Order: MacPorts local path, then ``espeak``/``espeak-ng`` on PATH. Falls
    back to the bare name ``espeak`` so callers still get a sensible command
    (and a clean FileNotFoundError) if nothing is installed.
    """
    local_path = "/opt/local/bin/espeak"
    if Path(local_path).exists():
        return local_path

    for name in ("espeak", "espeak-ng"):
        found = shutil.which(name)
        if found:
            return found

    return "espeak"


@functools.lru_cache(maxsize=256)
def get_phonemes(text: str, voice: str = "pt-br") -> str:
    """Get the phoneme representation of *text* using espeak."""
    try:
        result = subprocess.run(
            [get_espeak_path(), "-v", voice, "-q", "--phonout=/dev/stdout", "-x", text],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        return f"[phonemes unavailable: {e}]"


def normalize_for_phoneme_scoring(s: str) -> str:
    """Strip whitespace and espeak pause phonemes (``_:`` ``_!`` ``_|`` ...).

    Leaves only pronunciation phonemes so scoring ignores word boundaries and
    punctuation-induced pauses.
    """
    if not s:
        return ""
    s = re.sub(r"\s+", "", s.strip())
    s = re.sub(r"_[:!|]+", "", s)
    return s


@functools.lru_cache(maxsize=256)
def get_ipa(text: str, voice: str = "pt-br") -> str:
    """Get IPA transcription for *text* (espeak newlines normalised to spaces)."""
    try:
        result = subprocess.run(
            [get_espeak_path(), "-v", voice, "--ipa", "-q", text],
            capture_output=True,
            text=True,
            check=True,
        )
        ipa = result.stdout.strip()
        return " ".join(ipa.split())
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "[IPA unavailable]"


def get_ipa_from_espeak(text: str, lang_code: str) -> str:
    """Generate IPA for *text* given a short language code (pt, fr, nl, ...)."""
    espeak_lang = ESPEAK_LANG_MAP.get(lang_code, lang_code)
    try:
        result = subprocess.run(
            [get_espeak_path(), "-v", espeak_lang, "-q", "--ipa", text],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode == 0:
            return " ".join(result.stdout.strip().split())
        return "[error]"
    except subprocess.TimeoutExpired:
        return "[timeout]"
    except Exception as e:  # noqa: BLE001 - mirror source's broad guard
        return f"[error: {e}]"
