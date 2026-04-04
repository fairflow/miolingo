"""
IPA and phoneme extraction via espeak.

Extracted from app.py (Phase 1.3 of refactor).
Runtime dependency: espeak must be installed (binary name 'espeak' locally,
'espeak-ng' on Debian/Ubuntu/Streamlit Cloud).
"""

import re
import subprocess
from pathlib import Path


def get_espeak_path() -> str:
    """
    Get espeak binary path (local build or system-wide).

    Platform differences:
    - macOS (MacPorts): Binary is "espeak" at /opt/local/bin/espeak
    - Debian/Ubuntu (Streamlit Cloud): Binary is "espeak-ng" from espeak-ng package
    """
    local_path = "/opt/local/bin/espeak"
    if Path(local_path).exists():
        return local_path

    try:
        subprocess.run(["espeak-ng", "--version"], capture_output=True, check=True)
        return "espeak-ng"
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    return "espeak"


def get_phonemes(text: str, voice: str = "pt-br") -> str:
    """Get phoneme representation of text using espeak."""
    try:
        espeak_cmd = get_espeak_path()
        result = subprocess.run(
            [espeak_cmd, "-v", voice, "-q", "--phonout=/dev/stdout", "-x", text],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        return f"[phonemes unavailable: {e}]"


def normalize_for_phoneme_scoring(s: str) -> str:
    """
    Normalize eSpeak phoneme strings for pronunciation scoring.

    Removes all whitespace (word boundaries) and pause phonemes
    (_: _! _| _:: etc.) inserted by eSpeak for punctuation, so scoring
    is based purely on pronunciation phonemes.
    """
    if not s:
        return ""
    s = re.sub(r"\s+", "", s.strip())
    s = re.sub(r'_[:!|]+', '', s)
    return s


def get_ipa(text: str, voice: str = "pt-br") -> str:
    """
    Get IPA transcription for text.

    eSpeak converts punctuation into newlines in IPA output;
    we normalize these to spaces for consistent comparison.
    """
    try:
        espeak_cmd = get_espeak_path()
        result = subprocess.run(
            [espeak_cmd, "-v", voice, "--ipa", "-q", text],
            capture_output=True,
            text=True,
            check=True
        )
        ipa = result.stdout.strip()
        ipa = ' '.join(ipa.split())
        return ipa
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        return "[IPA unavailable]"


def get_ipa_from_espeak(text: str, lang_code: str) -> str:
    """
    Generate IPA transcription using espeak for a given language code.

    Args:
        text: Text to transcribe
        lang_code: Language code (pt, fr, nl, de, it, es, en)

    Returns:
        IPA transcription or '[error]' on failure
    """
    ESPEAK_LANG_MAP = {
        'pt': 'pt-br',
        'fr': 'fr-fr',
        'nl': 'nl',
        'de': 'de',
        'it': 'it',
        'es': 'es',
        'en': 'en',
    }

    espeak_lang = ESPEAK_LANG_MAP.get(lang_code, lang_code)
    espeak_cmd = get_espeak_path()

    try:
        result = subprocess.run(
            [espeak_cmd, '-v', espeak_lang, '-q', '--ipa', text],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            ipa = result.stdout.strip()
            ipa = ' '.join(ipa.split())
            return ipa
        return '[error]'
    except subprocess.TimeoutExpired:
        return '[timeout]'
    except Exception as e:
        return f'[error: {str(e)}]'


def format_ipa(ipa_text: str, size: str = "1.0em", weight: int = 400,
               brackets: bool = True) -> str:
    """Format IPA text with consistent delimiters and HTML styling."""
    if not ipa_text:
        return ""

    # Remove any existing delimiters
    ipa_clean = ipa_text.strip().strip('[]/()')

    # Add brackets if requested
    display_text = f"[{ipa_clean}]" if brackets else ipa_clean

    return (
        f'<span style="font-size: {size}; font-weight: {weight}; '
        f"font-family: 'Doulos SIL', 'Charis SIL', 'Gentium Plus', "
        f"'DejaVu Sans', sans-serif;\">{display_text}</span>"
    )
