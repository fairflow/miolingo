"""Tests for the Piper voice registry + resolution (no real synthesis).

Real synthesis needs the large .onnx voice files (fetched/bundled, not in git),
so it's a manual test. Here we cover the registry, locale->model-path
resolution against a fake voices dir, and the not-found / piper-missing
fallbacks that drive the dispatcher.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from miolingo_desktop.core import config, piper_voices


def test_every_supported_locale_has_a_voice() -> None:
    # Every locale the app can normalise to should have a Piper voice id, so the
    # default offline TTS works for all seven languages (SPEC §5 / M7 goal).
    target_locales = set(config.VOICE_LOCALE_NORMALIZATION.values())
    missing = target_locales - set(piper_voices.PIPER_VOICE_IDS)
    assert not missing, f"locales without a Piper voice: {missing}"


def test_voices_dir_env_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MIOLINGO_PIPER_VOICES_DIR", str(tmp_path))
    assert piper_voices.voices_dir() == tmp_path


def test_model_path_resolves_when_present(tmp_path: Path) -> None:
    voice_id = piper_voices.PIPER_VOICE_IDS["pt-BR"]
    (tmp_path / f"{voice_id}.onnx").write_bytes(b"fake-model")
    path = piper_voices.model_path_for_locale("pt-BR", directory=tmp_path)
    assert path.name == f"{voice_id}.onnx"


def test_model_path_missing_raises(tmp_path: Path) -> None:
    with pytest.raises(piper_voices.PiperUnavailable):
        piper_voices.model_path_for_locale("pt-BR", directory=tmp_path)


def test_model_path_unknown_locale_raises(tmp_path: Path) -> None:
    with pytest.raises(piper_voices.PiperUnavailable):
        piper_voices.model_path_for_locale("xx-YY", directory=tmp_path)


def test_synthesize_raises_when_voice_absent(tmp_path: Path) -> None:
    # No model file -> PiperUnavailable (dispatcher then falls back).
    with pytest.raises(piper_voices.PiperUnavailable):
        piper_voices.synthesize("ola", "pt-BR", directory=tmp_path)


@pytest.mark.manual
def test_synthesize_real_voice() -> None:
    """Real Piper synthesis — needs a fetched .onnx voice + the piper package."""
    audio = piper_voices.synthesize("olá mundo", "pt-BR")
    assert audio[:4] == b"RIFF"
