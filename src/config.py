"""
Miolingo configuration: language definitions, voice mappings, and user settings.

Extracted from app.py (Phase 1.1 of refactor).
"""

import json
import os
from pathlib import Path
from typing import Dict

# ---------------------------------------------------------------------------
# Version metadata
# ---------------------------------------------------------------------------

__version__ = "7.8.16-claude-dev"
__app_name__ = "Pronunciation Trainer"
__author__ = "Matthew Fairtlough & Contributors"
__license__ = "GPL-3.0"

# ---------------------------------------------------------------------------
# Language configuration
# ---------------------------------------------------------------------------

LANGUAGE_CONFIG = {
    "English": {
        "code": "en",
        "display_name": "English Pronunciation Trainer",
        "voices": {
            "google_cloud": ["en-gb", "en-us"],
            "gtts": ["en"],
            "espeak": ["en-gb", "en"]
        }
    },
    "Portuguese": {
        "code": "pt",
        "display_name": "Portuguese Pronunciation Trainer",
        "voices": {
            "google_cloud": ["pt-br", "pt"],
            "gtts": ["pt-br", "pt"],
            "espeak": ["pt-br", "pt"]
        }
    },
    "Dutch": {
        "code": "nl",
        "display_name": "Dutch/Flemish Pronunciation Trainer",
        "voices": {
            "google_cloud": ["nl", "nl-be"],
            "gtts": ["nl"],
            "espeak": ["nl"]
        }
    },
    "French": {
        "code": "fr",
        "display_name": "French Pronunciation Trainer",
        "voices": {
            "google_cloud": ["fr", "fr-fr"],
            "gtts": ["fr"],
            "espeak": ["fr-fr"]
        }
    },
    "German": {
        "code": "de",
        "display_name": "German Pronunciation Trainer",
        "voices": {
            "google_cloud": ["de", "de-de"],
            "gtts": ["de"],
            "espeak": ["de"]
        }
    },
    "Italian": {
        "code": "it",
        "display_name": "Italian Pronunciation Trainer",
        "voices": {
            "google_cloud": ["it", "it-it"],
            "gtts": ["it"],
            "espeak": ["it"]
        }
    },
    "Spanish": {
        "code": "es",
        "display_name": "Spanish Pronunciation Trainer",
        "voices": {
            "google_cloud": ["es", "es-es"],
            "gtts": ["es"],
            "espeak": ["es"]
        }
    }
}

# Voice locale normalization: lowercase codes → BCP 47 format
VOICE_LOCALE_NORMALIZATION = {
    'en': 'en-US',
    'en-gb': 'en-GB',
    'en-us': 'en-US',
    'pt-br': 'pt-BR',
    'pt': 'pt-PT',
    'fr': 'fr-FR',
    'fr-fr': 'fr-FR',
    'nl': 'nl-NL',
    'nl-be': 'nl-BE',
    'de': 'de-DE',
    'de-de': 'de-DE',
    'it': 'it-IT',
    'it-it': 'it-IT',
    'es': 'es-ES',
    'es-es': 'es-ES'
}

# Google Cloud TTS voice names per locale
GOOGLE_CLOUD_VOICES = {
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
# Default settings
# ---------------------------------------------------------------------------

DEFAULT_SETTINGS = {
    "speed": 140,
    "pitch": 35,
    "voice": "pt-br",
    "model": "base",
    "duration": 3,
    "comparison_algorithm": "edit_distance",
    "asr_engine": "whisper",
    "whisper_model_size": "base",
    "silence_threshold": 0.01,
    "use_wav_audio": False,
    "tts_engine": "google_cloud",
    "gtts_slow": False,
    "source_language": "English",
    "debug_mode": False,
}

# ---------------------------------------------------------------------------
# Material-code → Training-language mapping
# ---------------------------------------------------------------------------

# Maps short material language codes (used in filenames, session state) to the
# full language names used by LANGUAGE_CONFIG / TTS / ASR.
MATERIAL_TO_TRAINING: dict[str, str] = {
    'en': 'English',
    'de': 'German',
    'es': 'Spanish',
    'fr': 'French',
    'it': 'Italian',
    'nl': 'Dutch',
    'pt': 'Portuguese',
}

# Languages available as source (practice-from) language.
# Includes English plus all supported practice languages.
SOURCE_LANGUAGE_OPTIONS: list[str] = [
    "English", "French", "German", "Spanish", "Italian", "Dutch", "Portuguese"
]

# ---------------------------------------------------------------------------
# Language helpers
# ---------------------------------------------------------------------------

def get_language_code(language_name: str) -> str:
    """Map a language name to its short code."""
    if language_name.lower() == "english":
        return "en"
    if language_name in LANGUAGE_CONFIG:
        return LANGUAGE_CONFIG[language_name].get("code", language_name.lower())
    return language_name.lower()


def get_language_for_provider(provider: str, language_name: str) -> str:
    """Get the language identifier expected by a translation provider."""
    if provider == "google":
        return get_language_code(language_name)
    return language_name


# ---------------------------------------------------------------------------
# Settings persistence
# ---------------------------------------------------------------------------

def load_settings(session_state=None, db_module=None):
    """
    Load user settings from database (if authenticated) or local config file.

    Args:
        session_state: Streamlit session state (or dict-like). If None, uses
                       local config file only.
        db_module:     Database module with get_user_settings(). If None, skips
                       database lookup.
    """
    settings = dict(DEFAULT_SETTINGS)

    # If authenticated, load from database
    if (session_state
            and session_state.get('authenticated', False)
            and 'user' in session_state):
        try:
            if db_module:
                user_id = session_state['user']['user_id']
                db_settings = db_module.get_user_settings(user_id)
                if db_settings:
                    settings.update(db_settings)
                    return settings
        except Exception:
            pass  # fall through to local config

    # Fall back to local config file
    config_file = Path("practice_config.json")
    if config_file.exists():
        try:
            with open(config_file) as f:
                saved = json.load(f)
                settings.update(saved)
        except Exception:
            pass

    return settings


def save_settings(settings: Dict, session_state=None, db_module=None,
                  error_callback=None):
    """
    Save settings to database (if authenticated) or local config file.

    Args:
        settings:       Settings dict to save.
        session_state:  Streamlit session state (or dict-like).
        db_module:      Database module with save_user_setting().
        error_callback: Called with error message string on failure.
    """
    if (session_state
            and session_state.get('authenticated', False)
            and 'user' in session_state):
        try:
            if db_module:
                user_id = session_state['user']['user_id']
                for key, value in settings.items():
                    db_module.save_user_setting(user_id, key, value)
                return
        except Exception as e:
            if error_callback:
                error_callback(f"Could not save settings to database: {e}")
            return

    try:
        with open("practice_config.json", 'w') as f:
            json.dump(settings, f, indent=2)
    except Exception as e:
        if error_callback:
            error_callback(f"Could not save settings: {e}")
