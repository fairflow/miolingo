"""Tests for language-materials discovery and loading.

These run against the real bundled ``language_materials/`` tree (located via
``get_data_dir()``), asserting structural invariants rather than exact
filenames so they stay stable as content evolves. A synthetic temp tree
exercises the parser edge cases deterministically.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from miolingo_desktop.core import materials


def test_get_data_dir_exists() -> None:
    data_dir = materials.get_data_dir()
    assert data_dir.exists(), f"language_materials not found at {data_dir}"
    assert data_dir.name == "language_materials"


def test_available_languages_includes_core_set() -> None:
    langs = set(materials.get_available_languages())
    # The bundled content always ships at least these.
    assert {"pt", "fr", "de", "es", "it", "nl"} <= langs


def test_language_structure_has_phrases_or_words() -> None:
    structure = materials.get_language_structure("pt")
    assert structure, "expected non-empty structure for pt"
    assert any(k in structure for k in ("phrases", "words"))


def test_get_data_dir_env_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    materials.get_data_dir.cache_clear()
    monkeypatch.setenv("MIOLINGO_MATERIALS_DIR", str(tmp_path))
    try:
        assert materials.get_data_dir() == tmp_path
    finally:
        materials.get_data_dir.cache_clear()


def _write(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def test_load_phrase_file_txt(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    materials.get_data_dir.cache_clear()
    monkeypatch.setenv("MIOLINGO_MATERIALS_DIR", str(tmp_path))
    try:
        f = tmp_path / "fr" / "phrases" / "phr-01.txt"
        _write(
            f,
            "# a comment\n(fr, en)\nbonjour | hello | [bɔ̃ʒuʁ]\nmerci | thank you\nau revoir\n",
        )
        rows = materials.load_phrase_file(str(f))
        assert len(rows) == 3  # comment + header line filtered out
        assert rows[0] == {"text": "bonjour", "translation": "hello", "ipa": "[bɔ̃ʒuʁ]"}
        assert rows[1] == {"text": "merci", "translation": "thank you", "ipa": None}
        assert rows[2] == {"text": "au revoir", "translation": None, "ipa": None}
    finally:
        materials.get_data_dir.cache_clear()


def test_load_phrase_file_rejects_path_traversal(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    materials.get_data_dir.cache_clear()
    monkeypatch.setenv("MIOLINGO_MATERIALS_DIR", str(tmp_path / "data"))
    try:
        (tmp_path / "data").mkdir()
        outside = tmp_path / "secret.txt"
        outside.write_text("nope", encoding="utf-8")
        with pytest.raises(ValueError):
            materials.load_phrase_file(str(outside))
    finally:
        materials.get_data_dir.cache_clear()


def test_load_unified_phrase_file(tmp_path: Path) -> None:
    f = tmp_path / "u.json"
    doc = {
        "meta": {"languages": ["fr", "en"]},
        "phrases": [
            {"text": {"fr": "chat", "en": "cat"}, "ipa": {"fr": "ʃa"}},
            {"text": {"en": "only english"}},  # skipped: no fr
        ],
    }
    f.write_text(json.dumps(doc), encoding="utf-8")
    rows = list(materials.load_unified_phrase_file(str(f), "fr", "en"))
    assert rows == [{"text": "chat", "translation": "cat", "ipa": "ʃa"}]


def test_format_language_name() -> None:
    assert materials.format_language_name("fr") == "French"
    assert materials.format_language_name("xx") == "XX"
