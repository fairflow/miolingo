"""Streamlit-free engine shells: Whisper ASR + the TTS dispatch chain.

Thin rewrites of the shells of src/audio/asr.py and src/audio/tts.py (which
import streamlit at module level). The parameters, fallback order, and the
hallucination detection are kept exactly; only the caching moves from
st.session_state / st.cache_data to module-level caches. Provenance comments
point at the mirrored lines.
"""
from __future__ import annotations

import os
import string
import subprocess
import tempfile
import warnings
from pathlib import Path

from scoring.phonemes import get_espeak_path
from config import GOOGLE_CLOUD_VOICES, VOICE_LOCALE_NORMALIZATION

REPO = Path(__file__).resolve().parents[2]

# ---------------------------------------------------------------------------
# Whisper (asr.py:20-133) — module cache instead of st.session_state
# ---------------------------------------------------------------------------

_WHISPER: dict[str, object] = {}


def whisper_status() -> tuple[str | None, bool]:
    """(model_name, loaded) for /api/health."""
    names = list(_WHISPER)
    return (names[0], True) if names else (None, False)


def get_whisper_model(model_name: str):
    if model_name not in _WHISPER:
        import whisper

        _WHISPER.clear()  # hold at most one size, like the app session did
        _WHISPER[model_name] = whisper.load_model(model_name)
    return _WHISPER[model_name]


def transcribe_whisper(audio_file: str, model_name: str, lang_code: str) -> str:
    """Whisper transcription incl. hallucination detection (asr.py:69-133)."""
    model = get_whisper_model(model_name)
    result = model.transcribe(
        audio=audio_file,
        language=lang_code,
        task="transcribe",
        temperature=0.0,
        no_speech_threshold=0.6,
        logprob_threshold=-1.0,
        condition_on_previous_text=False,
        word_timestamps=False,
        compression_ratio_threshold=2.4,
    )

    detected = result.get("language", "unknown")
    if detected != lang_code:
        warnings.warn(f"Whisper detected language {detected!r} instead of {lang_code!r}")

    text = result["text"].strip().lower()

    words = text.split()
    if len(words) > 20:
        for pattern_len in (2, 3, 4):
            if len(words) >= pattern_len * 10:
                pattern = " ".join(words[:pattern_len])
                reps = text.count(pattern)
                if reps >= 10:
                    return f"[hallucination detected: '{pattern}' x{reps}]"
        if len(words) > 100:
            return f"[error: transcription too long - {len(words)} words, possible hallucination]"

    return text


# ---------------------------------------------------------------------------
# TTS (tts.py) — espeak / gTTS / Google Cloud + the fallback dispatcher
# ---------------------------------------------------------------------------


_SECRETS: dict | None = None


def load_secrets() -> dict:
    """The repo's .streamlit/secrets.toml as a plain dict (empty if absent).
    The creds source for TTS and translation provider keys; cached."""
    global _SECRETS
    if _SECRETS is None:
        try:
            import tomllib

            _SECRETS = tomllib.loads(
                (REPO / ".streamlit" / "secrets.toml").read_text("utf-8")
            )
        except (OSError, ValueError):
            _SECRETS = {}
    return _SECRETS


def _google_api_key() -> str | None:
    """Env first, then secrets.toml."""
    return os.environ.get("MIOLINGO_GOOGLE_TTS_KEY") or load_secrets().get(
        "google_cloud_tts_api_key"
    )


def translate_available() -> bool:
    """Whether the configured translation provider has a usable key."""
    try:
        from translation import get_translation_provider, validate_translation_api_key

        secrets = load_secrets()
        ok, _ = validate_translation_api_key(get_translation_provider(secrets), secrets)
        return bool(ok)
    except Exception:  # noqa: BLE001 - degrade to "not available"
        return False


def translate(text: str, source_lang: str, target_lang: str) -> str:
    """Translate via src/translation.py's provider chain (language NAMES).
    Stateless: no cache module. Raises RuntimeError on provider errors."""
    from translation import get_translation_from_llm

    result = get_translation_from_llm(
        text, source_lang, target_lang, secrets=load_secrets(), db_module=None
    )
    if result.startswith("[error:"):
        raise RuntimeError(result)
    return result


def tts_espeak(text: str, voice: str, speed: int = 140, pitch: int = 35) -> tuple[bytes, str]:
    """eSpeak --stdout (tts.py:31-75); always available offline."""
    result = subprocess.run(
        [get_espeak_path(), "-v", voice, "-s", str(speed), "-p", str(pitch), "--stdout", text],
        capture_output=True,
        check=True,
    )
    return result.stdout, "audio/wav"


def tts_gtts(text: str, voice: str, slow: bool = False) -> tuple[bytes, str]:
    """gTTS mp3 (tts.py:172-238); browsers play mp3, so no ffmpeg wav step."""
    from gtts import gTTS

    tts = gTTS(text=text, lang=voice.replace("-br", ""), slow=slow)
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as fp:
        path = fp.name
    try:
        tts.save(path)
        return Path(path).read_bytes(), "audio/mpeg"
    finally:
        Path(path).unlink(missing_ok=True)


def tts_google_cloud(text: str, voice: str, slow: bool = False) -> tuple[bytes, str]:
    """Google Cloud TTS REST (tts.py:83-164); raises when no key/API error."""
    import base64

    import requests

    api_key = _google_api_key()
    if not api_key:
        raise ValueError("google_cloud_tts_api_key not configured")

    cloud_lang = VOICE_LOCALE_NORMALIZATION.get(voice, "pt-BR")
    payload = {
        "input": {"text": text},
        "voice": {
            "languageCode": cloud_lang[:5],
            "name": GOOGLE_CLOUD_VOICES.get(cloud_lang, "pt-BR-Standard-A"),
        },
        "audioConfig": {"audioEncoding": "MP3", "speakingRate": 0.75 if slow else 1.0},
    }
    resp = requests.post(
        "https://texttospeech.googleapis.com/v1/text:synthesize",
        headers={"X-goog-api-key": api_key, "Content-Type": "application/json; charset=utf-8"},
        json=payload,
        timeout=20,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Google Cloud TTS {resp.status_code}: {resp.text[:200]}")
    return base64.b64decode(resp.json().get("audioContent", "")), "audio/mpeg"


def generate_tts(
    text: str,
    voice: str,
    engine: str | None = None,
    speed: int = 140,
    slow: bool = False,
) -> tuple[bytes, str, str]:
    """(audio, media_type, engine_used) with the app's fallback chain
    google_cloud → gtts → espeak (tts.py:245-341). An explicit engine request
    starts the chain at that engine; espeak is the guaranteed floor."""
    clean = text.translate(str.maketrans("", "", string.punctuation))
    chain = ["google_cloud", "gtts", "espeak"]
    if engine in chain:
        chain = chain[chain.index(engine):]
    last: Exception | None = None
    for eng in chain:
        try:
            if eng == "espeak":
                audio, media = tts_espeak(clean, voice, speed=speed)
            elif eng == "gtts":
                audio, media = tts_gtts(clean, voice, slow=slow)
            else:
                audio, media = tts_google_cloud(clean, voice, slow=slow)
            if audio:
                return audio, media, eng
        except Exception as e:  # noqa: BLE001 - fall through the chain
            last = e
    raise RuntimeError(f"all TTS engines failed: {last}")
