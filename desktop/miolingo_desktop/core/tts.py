"""Text-to-Speech engines and dispatcher.

Ported from ``src/audio/tts.py`` with Streamlit removed:
- ``@st.cache_data`` -> ``functools.lru_cache`` (in-process).
- ``st.secrets[...]`` -> an explicit ``api_key`` argument (no global secrets).
- ``st.warning`` -> an optional ``warn_fn`` (defaults to logging).

Per SPEC §5 / DECISIONS.md the dispatcher priority is **Piper (offline neural)
-> Google Cloud (optional, online) -> espeak (last resort)**. This differs from
the source app, whose default was Google Cloud.

Each engine returns ``(audio_bytes, mime_format)``. Full Piper voice coverage
and bundled voice files land in Milestone 7; this module wires the engine and
the fallback order. ``synthesize_piper`` raises ``PiperUnavailable`` when no
voice is resolvable so the dispatcher can fall back cleanly — this keeps the
dispatcher logic testable in M1 without bundled voices.
"""

from __future__ import annotations

import functools
import logging
import string
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path

from .config import GOOGLE_CLOUD_VOICES, VOICE_LOCALE_NORMALIZATION
# Re-export PiperUnavailable so the dispatcher (and existing callers/tests) keep
# using ``tts.PiperUnavailable``; Piper itself lives in core/piper_voices.py.
from .piper_voices import PiperUnavailable

logger = logging.getLogger(__name__)

WarnFn = Callable[[str], None]
AudioResult = tuple[bytes, str]

__all__ = ["PiperUnavailable"]


def _default_warn(msg: str) -> None:
    logger.warning(msg)


# ---------------------------------------------------------------------------
# Engine: Piper (local, offline neural) — default
# ---------------------------------------------------------------------------


def synthesize_piper(
    text: str,
    locale: str = "pt-BR",
    *,
    voices: dict[str, str] | None = None,
    use_wav: bool = True,
) -> AudioResult:
    """Synthesize *text* with the locale's bundled Piper voice.

    Delegates to ``core.piper_voices.synthesize`` (loads the local ``.onnx``
    voice, fully offline). Raises :class:`PiperUnavailable` when the voice or the
    piper package isn't available, so the dispatcher falls back. ``voices``, if
    given, overrides the locale->voice-id registry (used by tests).
    """
    from . import piper_voices

    audio = piper_voices.synthesize(text, locale, registry=voices)
    return audio, "audio/wav"


# ---------------------------------------------------------------------------
# Engine: eSpeak (local, offline) — last resort
# ---------------------------------------------------------------------------


def speak_text(
    text: str,
    voice: str = "pt-br",
    speed: int = 160,
    pitch: int = 40,
) -> AudioResult:
    """Generate speech with espeak. Returns ``(wav_bytes, 'audio/wav')``."""
    from .phonemes import get_espeak_path

    try:
        result = subprocess.run(
            [
                get_espeak_path(),
                "-v", voice,
                "-s", str(speed),
                "-p", str(pitch),
                "--stdout",
                text,
            ],
            capture_output=True,
            check=True,
        )
        return result.stdout, "audio/wav"
    except (subprocess.CalledProcessError, FileNotFoundError):
        return b"", "audio/wav"


# ---------------------------------------------------------------------------
# Engine: Google Cloud TTS (REST, optional online upgrade)
# ---------------------------------------------------------------------------


@functools.lru_cache(maxsize=512)
def speak_text_google_cloud(
    text: str,
    lang: str = "pt-BR",
    use_wav: bool = False,
    speaking_rate: float = 1.0,
    *,
    api_key: str | None = None,
) -> AudioResult:
    """Generate speech via Google Cloud TTS REST API. Requires an explicit api_key."""
    import base64

    import requests

    if api_key is None:
        raise ValueError("Google Cloud TTS requires an api_key (no global secrets)")

    voice_name = GOOGLE_CLOUD_VOICES.get(lang, "pt-BR-Standard-A")
    audio_encoding = "LINEAR16" if use_wav else "MP3"

    url = "https://texttospeech.googleapis.com/v1/text:synthesize"
    headers = {
        "X-goog-api-key": api_key,
        "Content-Type": "application/json; charset=utf-8",
    }
    payload = {
        "input": {"text": text},
        "voice": {"languageCode": lang[:5], "name": voice_name},
        "audioConfig": {"audioEncoding": audio_encoding, "speakingRate": speaking_rate},
    }

    response = requests.post(url, headers=headers, json=payload, timeout=30)
    if response.status_code != 200:
        raise RuntimeError(
            f"Google Cloud TTS API error {response.status_code}: {response.text[:200]}"
        )

    audio_bytes = base64.b64decode(response.json().get("audioContent", ""))
    return audio_bytes, ("audio/wav" if use_wav else "audio/mp3")


# ---------------------------------------------------------------------------
# Dispatcher: Piper -> Google Cloud -> espeak
# ---------------------------------------------------------------------------


def generate_target_audio(
    text: str,
    settings: dict,
    *,
    warn_fn: WarnFn | None = None,
    google_api_key: str | None = None,
    piper_voices: dict[str, str] | None = None,
) -> AudioResult:
    """Generate target pronunciation audio with graceful degradation.

    Priority: Piper (offline) -> Google Cloud (if ``google_api_key`` and online)
    -> espeak (last resort). The configured ``tts_engine`` selects the preferred
    engine but fallbacks always apply.
    """
    if warn_fn is None:
        warn_fn = _default_warn

    text_no_punct = text.translate(str.maketrans("", "", string.punctuation))
    voice = str(settings.get("voice", "pt-br"))
    locale = VOICE_LOCALE_NORMALIZATION.get(voice, "pt-BR")
    use_wav = bool(settings.get("use_wav_audio", False))
    rate = 0.75 if settings.get("gtts_slow", False) else 1.0
    engine = str(settings.get("tts_engine", "piper"))

    def _espeak() -> AudioResult:
        return speak_text(
            text_no_punct,
            voice=voice,
            speed=int(settings.get("speed", 140)),
            pitch=int(settings.get("pitch", 35)),
        )

    def _google() -> AudioResult:
        return speak_text_google_cloud(
            text_no_punct, lang=locale, use_wav=use_wav, speaking_rate=rate,
            api_key=google_api_key,
        )

    def _piper() -> AudioResult:
        return synthesize_piper(text_no_punct, locale=locale, voices=piper_voices,
                                use_wav=use_wav)

    # If the user explicitly forces espeak, honour it directly.
    if engine == "espeak":
        return _espeak()

    # Default path: Piper first, then Google Cloud (if configured), then espeak.
    try:
        return _piper()
    except PiperUnavailable as e:
        warn_fn(f"Piper unavailable ({e}); trying Google Cloud TTS")

    if google_api_key:
        try:
            return _google()
        except Exception as e:  # noqa: BLE001 - degrade to espeak on any failure
            warn_fn(f"Google Cloud TTS unavailable ({str(e)[:80]}); using espeak")

    return _espeak()
