"""Miolingo configuration: language definitions, voice mappings, default settings.

Ported from ``src/config.py``. The language/voice tables are copied verbatim
(pure data). The Streamlit/DB-coupled ``load_settings``/``save_settings`` are
NOT ported here — settings persistence is owned by the SQLite storage layer
(Milestone 2/4). This module only provides ``DEFAULT_SETTINGS`` and the pure
language-helper functions.

Default changes vs the source app (per DECISIONS.md):
- ``whisper_model_size`` defaults to ``"medium"`` (was ``"base"``).
- ``tts_engine`` defaults to ``"piper"`` (offline neural; was ``"google_cloud"``).
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Language configuration
# ---------------------------------------------------------------------------

LANGUAGE_CONFIG: dict[str, dict] = {
    "English": {
        "code": "en",
        "display_name": "English Pronunciation Trainer",
        "voices": {
            "google_cloud": ["en-gb", "en-us"],
            "gtts": ["en"],
            "espeak": ["en-gb", "en"],
        },
    },
    "Portuguese": {
        "code": "pt",
        "display_name": "Portuguese Pronunciation Trainer",
        "voices": {
            "google_cloud": ["pt-br", "pt"],
            "gtts": ["pt-br", "pt"],
            "espeak": ["pt-br", "pt"],
        },
    },
    "Dutch": {
        "code": "nl",
        "display_name": "Dutch/Flemish Pronunciation Trainer",
        "voices": {
            "google_cloud": ["nl", "nl-be"],
            "gtts": ["nl"],
            "espeak": ["nl"],
        },
    },
    "French": {
        "code": "fr",
        "display_name": "French Pronunciation Trainer",
        "voices": {
            "google_cloud": ["fr", "fr-fr"],
            "gtts": ["fr"],
            "espeak": ["fr-fr"],
        },
    },
    "German": {
        "code": "de",
        "display_name": "German Pronunciation Trainer",
        "voices": {
            "google_cloud": ["de", "de-de"],
            "gtts": ["de"],
            "espeak": ["de"],
        },
    },
    "Italian": {
        "code": "it",
        "display_name": "Italian Pronunciation Trainer",
        "voices": {
            "google_cloud": ["it", "it-it"],
            "gtts": ["it"],
            "espeak": ["it"],
        },
    },
    "Spanish": {
        "code": "es",
        "display_name": "Spanish Pronunciation Trainer",
        "voices": {
            "google_cloud": ["es", "es-es"],
            "gtts": ["es"],
            "espeak": ["es"],
        },
    },
}

# Voice locale normalization: lowercase codes -> BCP 47 format
VOICE_LOCALE_NORMALIZATION: dict[str, str] = {
    "en": "en-US",
    "en-gb": "en-GB",
    "en-us": "en-US",
    "pt-br": "pt-BR",
    "pt": "pt-PT",
    "fr": "fr-FR",
    "fr-fr": "fr-FR",
    "nl": "nl-NL",
    "nl-be": "nl-BE",
    "de": "de-DE",
    "de-de": "de-DE",
    "it": "it-IT",
    "it-it": "it-IT",
    "es": "es-ES",
    "es-es": "es-ES",
}

# Google Cloud TTS voice names per locale (optional online engine).
GOOGLE_CLOUD_VOICES: dict[str, str] = {
    "en-GB": "en-GB-Standard-A",
    "en-US": "en-US-Standard-A",
    "pt-BR": "pt-BR-Standard-A",
    "pt-PT": "pt-PT-Standard-A",
    "fr-FR": "fr-FR-Standard-A",
    "nl-NL": "nl-NL-Standard-A",
    "nl-BE": "nl-BE-Standard-A",
    "de-DE": "de-DE-Standard-A",
    "it-IT": "it-IT-Standard-A",
    "es-ES": "es-ES-Standard-A",
}

# ---------------------------------------------------------------------------
# Default settings (desktop)
# ---------------------------------------------------------------------------

DEFAULT_SETTINGS: dict[str, object] = {
    "speed": 140,
    "pitch": 35,
    "voice": "pt-br",
    "model": "medium",
    "duration": 3,
    "comparison_algorithm": "edit_distance",
    "asr_engine": "whisper",
    "whisper_model_size": "medium",  # DECISIONS.md: accuracy over size
    "silence_threshold": 0.01,
    "use_wav_audio": False,
    "tts_engine": "piper",  # DECISIONS.md: Piper offline neural is the default
    "gtts_slow": False,
    "source_language": "English",
    "debug_mode": False,
}

# ---------------------------------------------------------------------------
# Material-code -> Training-language mapping
# ---------------------------------------------------------------------------

MATERIAL_TO_TRAINING: dict[str, str] = {
    "en": "English",
    "de": "German",
    "es": "Spanish",
    "fr": "French",
    "it": "Italian",
    "nl": "Dutch",
    "pt": "Portuguese",
}

SOURCE_LANGUAGE_OPTIONS: list[str] = [
    "English",
    "French",
    "German",
    "Spanish",
    "Italian",
    "Dutch",
    "Portuguese",
]


# ---------------------------------------------------------------------------
# Language helpers (pure)
# ---------------------------------------------------------------------------


def get_language_code(language_name: str) -> str:
    """Map a language name to its short code."""
    if language_name.lower() == "english":
        return "en"
    if language_name in LANGUAGE_CONFIG:
        return str(LANGUAGE_CONFIG[language_name].get("code", language_name.lower()))
    return language_name.lower()


def get_language_for_provider(provider: str, language_name: str) -> str:
    """Get the language identifier expected by a translation provider."""
    if provider == "google":
        return get_language_code(language_name)
    return language_name


def default_settings() -> dict[str, object]:
    """Return a fresh copy of the default settings dict."""
    return dict(DEFAULT_SETTINGS)


# ---------------------------------------------------------------------------
# Option lists for the Settings UI (kept here so the UI holds no choices itself)
# ---------------------------------------------------------------------------

WHISPER_MODEL_SIZES: list[str] = ["tiny", "base", "small", "medium", "large"]
TTS_ENGINES: list[str] = ["piper", "google_cloud", "espeak"]
COMPARISON_ALGORITHMS: list[str] = ["edit_distance"]


def voices_for_language(language_name: str) -> list[str]:
    """All distinct voice codes configured for *language_name* across engines."""
    cfg = LANGUAGE_CONFIG.get(language_name)
    if not cfg:
        return []
    seen: list[str] = []
    for codes in cfg.get("voices", {}).values():
        for code in codes:
            if code not in seen:
                seen.append(code)
    return seen
