"""Tests for DB path resolution."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from miolingo_desktop.data import paths


def test_default_db_path_env_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    target = tmp_path / "custom.db"
    monkeypatch.setenv("MIOLINGO_DB_PATH", str(target))
    assert paths.default_db_path() == target


def test_default_db_path_app_support(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MIOLINGO_DB_PATH", raising=False)
    p = paths.default_db_path()
    assert p.name == "miolingo.db"
    assert p.parent.name == "Miolingo"


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS-specific path")
def test_app_support_dir_on_macos() -> None:
    p = paths.app_support_dir()
    assert "Library/Application Support/Miolingo" in str(p)
