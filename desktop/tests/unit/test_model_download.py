"""Tests for the first-run Whisper model-availability helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from miolingo_desktop.core import model_download


def test_cache_dir_respects_xdg(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    assert model_download.whisper_cache_dir() == tmp_path / "whisper"


def test_is_model_cached_true(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    (tmp_path / "whisper").mkdir(parents=True)
    (tmp_path / "whisper" / "medium.pt").write_bytes(b"x")
    assert model_download.is_model_cached("medium") is True


def test_is_model_cached_false(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    assert model_download.is_model_cached("medium") is False
    assert model_download.is_model_cached("nonsense") is False


def test_ensure_model_announces_download_when_uncached(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    # Stub the actual loader so no model is fetched.
    from miolingo_desktop.core import asr

    monkeypatch.setattr(asr, "get_whisper_model", lambda name, progress_fn=None: f"model:{name}")
    messages: list[str] = []
    out = model_download.ensure_model("medium", progress_fn=messages.append)
    assert out == "model:medium"
    assert messages and "Downloading" in messages[0]
