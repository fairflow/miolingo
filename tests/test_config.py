"""
Tests for configuration and language utilities.

These test pure data lookups from LANGUAGE_CONFIG — no Streamlit needed.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# LANGUAGE_CONFIG is defined at module level in app.py but requires Streamlit
# to fully import. We replicate the lookup functions here as a baseline.
# Post-refactor, these import from config.py directly.

LANGUAGE_CONFIG = {
    "Portuguese": {"code": "pt"},
    "Dutch": {"code": "nl"},
    "French": {"code": "fr"},
    "German": {"code": "de"},
    "Spanish": {"code": "es"},
    "Italian": {"code": "it"},
}


def get_language_code(language_name: str) -> str:
    """Copied from app.py:302"""
    if language_name.lower() == "english":
        return "en"
    if language_name in LANGUAGE_CONFIG:
        return LANGUAGE_CONFIG[language_name].get("code", language_name.lower())
    return language_name.lower()


class TestGetLanguageCode:
    def test_known_languages(self):
        assert get_language_code("Portuguese") == "pt"
        assert get_language_code("French") == "fr"
        assert get_language_code("Dutch") == "nl"

    def test_english_special_case(self):
        assert get_language_code("english") == "en"
        assert get_language_code("English") == "en"

    def test_unknown_falls_back_to_lowercase(self):
        assert get_language_code("Swahili") == "swahili"
