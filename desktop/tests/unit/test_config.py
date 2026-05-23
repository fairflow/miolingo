"""Tests for ported config + the desktop default-setting overrides."""

from __future__ import annotations

from miolingo_desktop.core import config


def test_default_whisper_model_is_medium() -> None:
    assert config.DEFAULT_SETTINGS["whisper_model_size"] == "medium"


def test_default_tts_engine_is_piper() -> None:
    assert config.DEFAULT_SETTINGS["tts_engine"] == "piper"


def test_default_settings_returns_fresh_copy() -> None:
    a = config.default_settings()
    a["voice"] = "mutated"
    b = config.default_settings()
    assert b["voice"] != "mutated"


def test_get_language_code() -> None:
    assert config.get_language_code("English") == "en"
    assert config.get_language_code("Portuguese") == "pt"
    assert config.get_language_code("Klingon") == "klingon"


def test_language_config_covers_supported_languages() -> None:
    codes = {cfg["code"] for cfg in config.LANGUAGE_CONFIG.values()}
    assert {"en", "pt", "fr", "de", "es", "it", "nl"} <= codes


def test_voices_for_language_dedupes() -> None:
    voices = config.voices_for_language("Portuguese")
    assert "pt-br" in voices
    assert len(voices) == len(set(voices))
    assert config.voices_for_language("Klingon") == []


def test_option_lists_present() -> None:
    assert "medium" in config.WHISPER_MODEL_SIZES
    assert config.TTS_ENGINES[0] == "piper"
    assert "edit_distance" in config.COMPARISON_ALGORITHMS
