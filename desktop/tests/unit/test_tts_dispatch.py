"""Tests for the TTS dispatcher fallback order (Piper -> Google Cloud -> espeak).

We don't synthesize real audio here; we verify the *selection/fallback* logic by
monkeypatching the engine functions. Full Piper synthesis + per-voice clip tests
land in Milestone 7.
"""

from __future__ import annotations

import pytest

from miolingo_desktop.core import piper_voices, tts


def test_voice_id_missing_raises() -> None:
    with pytest.raises(piper_voices.PiperUnavailable):
        piper_voices.voice_id_for_locale("pt-BR", registry={})


def test_voice_id_present() -> None:
    assert (
        piper_voices.voice_id_for_locale("pt-BR", registry={"pt-BR": "pt_BR-faber"})
        == "pt_BR-faber"
    )


def test_dispatch_prefers_piper(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tts, "synthesize_piper", lambda *a, **k: (b"PIPER", "audio/wav"))
    out = tts.generate_target_audio("ola", {"tts_engine": "piper", "voice": "pt-br"})
    assert out == (b"PIPER", "audio/wav")


def test_dispatch_falls_back_to_google_when_piper_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _no_piper(*a, **k):
        raise tts.PiperUnavailable("no voice")

    monkeypatch.setattr(tts, "synthesize_piper", _no_piper)
    monkeypatch.setattr(
        tts, "speak_text_google_cloud", lambda *a, **k: (b"GOOGLE", "audio/mp3")
    )
    out = tts.generate_target_audio(
        "ola", {"tts_engine": "piper", "voice": "pt-br"}, google_api_key="key"
    )
    assert out == (b"GOOGLE", "audio/mp3")


def test_dispatch_falls_back_to_espeak_when_no_piper_no_google(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _no_piper(*a, **k):
        raise tts.PiperUnavailable("no voice")

    monkeypatch.setattr(tts, "synthesize_piper", _no_piper)
    monkeypatch.setattr(tts, "speak_text", lambda *a, **k: (b"ESPEAK", "audio/wav"))
    # No google_api_key -> skip Google, go straight to espeak.
    out = tts.generate_target_audio("ola", {"tts_engine": "piper", "voice": "pt-br"})
    assert out == (b"ESPEAK", "audio/wav")


def test_dispatch_explicit_espeak(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tts, "speak_text", lambda *a, **k: (b"ESPEAK", "audio/wav"))
    out = tts.generate_target_audio("ola", {"tts_engine": "espeak", "voice": "pt-br"})
    assert out == (b"ESPEAK", "audio/wav")


def test_google_cloud_requires_api_key() -> None:
    with pytest.raises(ValueError):
        tts.speak_text_google_cloud.__wrapped__("hi", api_key=None)
