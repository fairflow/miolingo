"""
Tests for bi-directional language feature.

Validates config exports, default settings, and import smoke tests
for the new source language infrastructure.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from config import (
    SOURCE_LANGUAGE_OPTIONS,
    DEFAULT_SETTINGS,
    LANGUAGE_CONFIG,
    MATERIAL_TO_TRAINING,
)


class TestSourceLanguageOptions:
    def test_exported_from_config(self):
        assert isinstance(SOURCE_LANGUAGE_OPTIONS, list)

    def test_contains_english(self):
        assert "English" in SOURCE_LANGUAGE_OPTIONS

    def test_contains_all_practice_languages(self):
        for lang_name in LANGUAGE_CONFIG:
            assert lang_name in SOURCE_LANGUAGE_OPTIONS, f"{lang_name} missing from SOURCE_LANGUAGE_OPTIONS"

    def test_english_is_first(self):
        assert SOURCE_LANGUAGE_OPTIONS[0] == "English"

    def test_no_duplicates(self):
        assert len(SOURCE_LANGUAGE_OPTIONS) == len(set(SOURCE_LANGUAGE_OPTIONS))


class TestDefaultSettingsSourceLanguage:
    def test_has_source_language_key(self):
        assert "source_language" in DEFAULT_SETTINGS

    def test_defaults_to_english(self):
        assert DEFAULT_SETTINGS["source_language"] == "English"


class TestSourceLanguageFlagMapping:
    """Sidebar uses _SOURCE_FLAGS — ensure every SOURCE_LANGUAGE_OPTIONS entry has one."""

    def test_all_options_have_flags(self):
        # Mirror the dict from sidebar.py
        _SOURCE_FLAGS = {
            "English": "🇬🇧", "French": "🇫🇷", "German": "🇩🇪",
            "Spanish": "🇪🇸", "Italian": "🇮🇹", "Dutch": "🇳🇱", "Portuguese": "🇵🇹",
        }
        for lang in SOURCE_LANGUAGE_OPTIONS:
            assert lang in _SOURCE_FLAGS, f"No flag for {lang}"


class TestFreeTextModeImport:
    def test_render_free_text_mode_importable(self):
        from ui.quick_practice_tab import _render_free_text_mode
        assert callable(_render_free_text_mode)


class TestMaterialToTrainingMapping:
    def test_all_language_config_languages_have_code_mapping(self):
        """Every language in LANGUAGE_CONFIG should appear in MATERIAL_TO_TRAINING values."""
        for lang_name in LANGUAGE_CONFIG:
            assert lang_name in MATERIAL_TO_TRAINING.values(), f"{lang_name} not in MATERIAL_TO_TRAINING values"

    def test_reverse_mapping_works(self):
        """Code → name mapping should be invertible for target language resolution."""
        code_map = {v: k for k, v in MATERIAL_TO_TRAINING.items()}
        assert code_map["French"] == "fr"
        assert code_map["Portuguese"] == "pt"
