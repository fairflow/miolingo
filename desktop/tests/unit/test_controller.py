"""Integration tests for the UI-free PracticeController.

Drives the full record(stub)->transcribe(stub)->score->save flow and asserts a
row lands in SQLite — the M3 acceptance check, headless and model-free.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from miolingo_desktop.core import practice
from miolingo_desktop.core.controller import PracticeController
from miolingo_desktop.data import Database


@pytest.fixture
def controller(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> PracticeController:
    # Deterministic phonemes so scoring doesn't need espeak.
    monkeypatch.setattr(
        practice, "get_phonemes", lambda text, voice="": "abc" if text == "ola" else "abd"
    )
    monkeypatch.setattr(practice, "get_ipa", lambda text, voice="": "[x]")
    db = Database(tmp_path / "ctrl.db")
    yield PracticeController(db)
    db.close()


def test_effective_settings_merges_defaults(controller: PracticeController) -> None:
    settings = controller.effective_settings()
    assert settings["whisper_model_size"] == "medium"  # default
    controller.settings_repo.set("whisper_model_size", "base")
    assert controller.effective_settings()["whisper_model_size"] == "base"  # stored wins


def test_run_practice_scores_and_persists(controller: PracticeController) -> None:
    result = controller.run_practice(
        target_text="ola",
        audio_bytes=b"fake-wav-bytes",
        language="Portuguese",
        transcribe_fn=lambda *a, **k: "olha",
    )
    assert result is not None
    assert "attempt_id" in result
    assert result["target"] == "ola"

    history = controller.recent_history(language="Portuguese")
    assert len(history) == 1
    assert history[0]["target_phrase"] == "ola"
    assert history[0]["language_code"] == "pt"


def test_recent_history_filters_language(controller: PracticeController) -> None:
    controller.run_practice(
        target_text="ola", audio_bytes=b"x", language="Portuguese",
        transcribe_fn=lambda *a, **k: "ola",
    )
    assert controller.recent_history(language="French") == []
    assert len(controller.recent_history()) == 1


def test_available_languages_nonempty(controller: PracticeController) -> None:
    langs = controller.available_languages()
    assert "pt" in langs
