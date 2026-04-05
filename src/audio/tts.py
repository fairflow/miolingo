"""
Text-to-Speech engines: eSpeak, Google Cloud TTS, gTTS.

Each engine function returns (audio_bytes, format_string).
The generate_target_audio() dispatcher handles fallback logic.
"""

import subprocess
import tempfile
import string
from pathlib import Path
from typing import Dict, Optional, Callable, Tuple

import streamlit as st

from config import VOICE_LOCALE_NORMALIZATION, GOOGLE_CLOUD_VOICES
from scoring.phonemes import get_espeak_path

# Optional: API usage logger (no-op if unavailable)
try:
    from api_usage_logger import log_api_call
except ImportError:
    def log_api_call(*args, **kwargs):
        pass


# ---------------------------------------------------------------------------
# Engine: eSpeak (local, offline)
# ---------------------------------------------------------------------------

def speak_text(
    text: str,
    voice: str = "pt-br",
    speed: int = 160,
    pitch: int = 40,
) -> Tuple[bytes, str]:
    """
    Generate speech using eSpeak (returns audio bytes, does not auto-play).

    Args:
        text: Text to speak
        voice: Voice/language code (e.g., 'pt-br', 'fr-fr', 'nl')
        speed: Speech speed in words per minute (80-450)
        pitch: Voice pitch (0-99)

    Returns:
        (audio_bytes, format) where format is 'audio/wav'
    """
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

        log_api_call(
            api_type="espeak",
            text=text,
            language=voice,
            char_count=len(text),
            audio_bytes=len(result.stdout),
            success=True,
            cached=False,
        )

        return result.stdout, "audio/wav"
    except (subprocess.CalledProcessError, FileNotFoundError):
        return b"", "audio/wav"


# ---------------------------------------------------------------------------
# Engine: Google Cloud TTS (REST API, requires API key)
# ---------------------------------------------------------------------------

@st.cache_data(ttl=86400)  # Cache for 24 hours (shared across all users)
def speak_text_google_cloud(
    text: str,
    lang: str = "pt-BR",
    use_wav: bool = False,
    speaking_rate: float = 1.0,
    *,
    api_key: Optional[str] = None,
) -> Tuple[bytes, str]:
    """
    Generate speech using Google Cloud Text-to-Speech REST API.

    Cached for 24 hours and shared across all users to minimise API calls.
    Requires a Google Cloud TTS API key — passed explicitly or read from
    st.secrets['google_cloud_tts_api_key'].

    Args:
        text: Text to speak
        lang: Language code (pt-BR, fr-FR, nl-NL, etc.)
        use_wav: If True, return as WAV format (LINEAR16)
        speaking_rate: Speech speed (0.25 to 4.0, default 1.0)
        api_key: Google Cloud TTS API key (falls back to st.secrets)

    Returns:
        (audio_bytes, format) where format is 'audio/mp3' or 'audio/wav'
    """
    import requests
    import json
    import base64

    if api_key is None:
        try:
            api_key = st.secrets["google_cloud_tts_api_key"]
        except KeyError:
            raise ValueError("google_cloud_tts_api_key not found in secrets")

    voice_name = GOOGLE_CLOUD_VOICES.get(lang, "pt-BR-Standard-A")
    audio_encoding = "LINEAR16" if use_wav else "MP3"

    url = "https://texttospeech.googleapis.com/v1/text:synthesize"
    headers = {
        "X-goog-api-key": api_key,
        "Content-Type": "application/json; charset=utf-8",
    }

    payload = {
        "input": {"text": text},
        "voice": {
            "languageCode": lang[:5],
            "name": voice_name,
        },
        "audioConfig": {
            "audioEncoding": audio_encoding,
            "speakingRate": speaking_rate,
        },
    }

    response = requests.post(url, headers=headers, json=payload)

    if response.status_code != 200:
        error_msg = (
            f"Google Cloud TTS API error {response.status_code}: "
            f"{response.text[:200]}"
        )
        st.warning(f"\u26a0\ufe0f {error_msg}")
        raise Exception(error_msg)

    response_data = response.json()
    audio_content_base64 = response_data.get("audioContent", "")
    audio_bytes = base64.b64decode(audio_content_base64)

    log_api_call(
        api_type="google_cloud_tts",
        text=text,
        language=lang,
        char_count=len(text),
        audio_bytes=len(audio_bytes),
        success=True,
        cached=False,
    )

    format_str = "audio/wav" if use_wav else "audio/mp3"
    return audio_bytes, format_str


# ---------------------------------------------------------------------------
# Engine: gTTS (unofficial Google TTS, no API key required)
# ---------------------------------------------------------------------------

@st.cache_data(ttl=86400)  # Cache for 24 hours (shared across all users)
def speak_text_gtts(
    text: str,
    lang: str = "pt-br",
    use_wav: bool = False,
    slow: bool = False,
) -> Tuple[bytes, str]:
    """
    Generate speech using Google TTS (higher quality than eSpeak).

    Cached for 24 hours and shared across all users to minimise API calls.

    Args:
        text: Text to speak
        lang: Language code (default pt-br)
        use_wav: If True, convert MP3 to WAV for iOS Safari compatibility
        slow: If True, speak at ~50% speed (Google TTS slow mode)

    Returns:
        (audio_bytes, format) where format is 'audio/mp3' or 'audio/wav'
    """
    from gtts import gTTS

    tts = gTTS(text=text, lang=lang.replace("-br", ""), slow=slow)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
        mp3_path = fp.name
        tts.save(mp3_path)

        if use_wav:
            wav_path = mp3_path.replace(".mp3", ".wav")

            result = subprocess.run(
                [
                    "ffmpeg", "-i", mp3_path, "-acodec", "pcm_s16le",
                    "-ar", "22050", "-y", wav_path,
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            if result.returncode == 0:
                with open(wav_path, "rb") as audio_file:
                    audio_bytes = audio_file.read()
                Path(wav_path).unlink()
                Path(mp3_path).unlink()
                return audio_bytes, "audio/wav"
            else:
                with open(mp3_path, "rb") as audio_file:
                    audio_bytes = audio_file.read()
                Path(mp3_path).unlink()
                return audio_bytes, "audio/mp3"
        else:
            with open(mp3_path, "rb") as audio_file:
                audio_bytes = audio_file.read()
            Path(mp3_path).unlink()

            log_api_call(
                api_type="gtts",
                text=text,
                language=lang,
                char_count=len(text),
                audio_bytes=len(audio_bytes),
                success=True,
                cached=False,
            )

            return audio_bytes, "audio/mp3"


# ---------------------------------------------------------------------------
# Dispatcher: choose engine with smart fallback
# ---------------------------------------------------------------------------

def generate_target_audio(
    text: str,
    settings: Dict,
    *,
    warn_fn: Optional[Callable] = None,
) -> Tuple[bytes, str]:
    """
    Generate target pronunciation audio using the configured TTS engine.

    Fallback priority: Google Cloud TTS -> gTTS -> eSpeak

    Args:
        text: Text to speak
        settings: User settings dict (tts_engine, voice, speed, pitch, etc.)
        warn_fn: Optional warning callback (defaults to st.warning)

    Returns:
        (audio_bytes, format)
    """
    if warn_fn is None:
        warn_fn = st.warning

    text_no_punct = text.translate(str.maketrans("", "", string.punctuation))

    tts_engine = settings.get("tts_engine", "google_cloud")

    if tts_engine == "espeak":
        return speak_text(
            text_no_punct,
            voice=settings.get("voice", "pt-br"),
            speed=settings.get("speed", 140),
            pitch=settings.get("pitch", 35),
        )

    elif tts_engine == "google_cloud":
        try:
            cloud_lang = VOICE_LOCALE_NORMALIZATION.get(
                settings.get("voice", "pt-br"), "pt-BR"
            )
            return speak_text_google_cloud(
                text_no_punct,
                lang=cloud_lang,
                use_wav=settings.get("use_wav_audio", False),
                speaking_rate=1.0 if not settings.get("gtts_slow", False) else 0.75,
            )
        except Exception as e:
            warn_fn(
                f"\u26a0\ufe0f Google Cloud TTS unavailable, trying gTTS... "
                f"({str(e)[:80]})"
            )
            try:
                return speak_text_gtts(
                    text_no_punct,
                    lang=settings.get("voice", "pt-br"),
                    use_wav=settings.get("use_wav_audio", False),
                    slow=settings.get("gtts_slow", False),
                )
            except Exception:
                warn_fn("\u26a0\ufe0f All Google TTS options failed, using eSpeak NG")
                return speak_text(
                    text_no_punct,
                    voice=settings.get("voice", "pt-br"),
                    speed=settings.get("speed", 140),
                    pitch=settings.get("pitch", 35),
                )

    else:
        # tts_engine is 'gtts' — but still try Google Cloud first (best quality)
        try:
            cloud_lang = VOICE_LOCALE_NORMALIZATION.get(
                settings.get("voice", "pt-br"), "pt-BR"
            )
            return speak_text_google_cloud(
                text_no_punct,
                lang=cloud_lang,
                use_wav=settings.get("use_wav_audio", False),
                speaking_rate=1.0 if not settings.get("gtts_slow", False) else 0.75,
            )
        except Exception:
            try:
                return speak_text_gtts(
                    text_no_punct,
                    lang=settings.get("voice", "pt-br"),
                    use_wav=settings.get("use_wav_audio", False),
                    slow=settings.get("gtts_slow", False),
                )
            except Exception as e:
                warn_fn(
                    f"\u26a0\ufe0f Google TTS unavailable, using eSpeak NG instead. "
                    f"({str(e)[:100]})"
                )
                return speak_text(
                    text_no_punct,
                    voice=settings.get("voice", "pt-br"),
                    speed=settings.get("speed", 140),
                    pitch=settings.get("pitch", 35),
                )
