"""
Tests for configuration and language utilities.

Now imports from the extracted config module directly.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from config import LANGUAGE_CONFIG, get_language_code, DEFAULT_SETTINGS


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


class TestLanguageConfig:
    def test_all_languages_have_code(self):
        for lang, cfg in LANGUAGE_CONFIG.items():
            assert "code" in cfg, f"{lang} missing 'code'"

    def test_all_languages_have_voices(self):
        for lang, cfg in LANGUAGE_CONFIG.items():
            assert "voices" in cfg, f"{lang} missing 'voices'"
            for engine in ("google_cloud", "gtts", "espeak"):
                assert engine in cfg["voices"], f"{lang} missing voice for {engine}"


class TestDefaultSettings:
    def test_has_required_keys(self):
        required = ["tts_engine", "asr_engine", "comparison_algorithm", "voice"]
        for key in required:
            assert key in DEFAULT_SETTINGS, f"Missing default setting: {key}"
