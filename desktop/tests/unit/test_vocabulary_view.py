"""Qt tests for the Vocabulary view (offscreen): CRUD, export, practice-from-vocab."""

from __future__ import annotations

from pathlib import Path

import pytest

from miolingo_desktop.core.controller import PracticeController
from miolingo_desktop.data import Database
from miolingo_desktop.main import create_app
from miolingo_desktop.ui.vocabulary_view import VocabularyView


@pytest.fixture
def controller(tmp_path: Path) -> PracticeController:
    db = Database(tmp_path / "vocab.db")
    yield PracticeController(db)
    db.close()


def test_add_and_list(qtbot, controller: PracticeController) -> None:
    create_app([])
    view = VocabularyView(controller)
    qtbot.addWidget(view)
    view.language_combo.setCurrentText("fr")
    view.word_edit.setText("chat")
    view.translation_edit.setText("cat")
    view.add_button.click()
    assert view.list_widget.count() == 1
    assert "chat" in view.list_widget.item(0).text()


def test_delete_hides_word(qtbot, controller: PracticeController) -> None:
    create_app([])
    view = VocabularyView(controller)
    qtbot.addWidget(view)
    view.language_combo.setCurrentText("fr")
    controller.vocab_repo.capture(language_code="fr", word="chat")
    view.refresh()
    view.list_widget.setCurrentRow(0)
    view.delete_button.click()
    assert view.list_widget.count() == 0


def test_export_csv_writes_file(qtbot, controller: PracticeController, tmp_path: Path, monkeypatch) -> None:
    create_app([])
    view = VocabularyView(controller)
    qtbot.addWidget(view)
    view.language_combo.setCurrentText("fr")
    controller.vocab_repo.capture(language_code="fr", word="chat", translation="cat")
    out = tmp_path / "vocab.csv"

    from PySide6.QtWidgets import QFileDialog

    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (str(out), ""))
    view.export_button.click()
    assert out.exists()
    assert "chat" in out.read_text(encoding="utf-8")


def test_practice_requested_signal(qtbot, controller: PracticeController) -> None:
    create_app([])
    view = VocabularyView(controller)
    qtbot.addWidget(view)
    view.language_combo.setCurrentText("fr")
    controller.vocab_repo.capture(language_code="fr", word="chat")
    view.refresh()
    view.list_widget.setCurrentRow(0)

    with qtbot.waitSignal(view.practiceRequested, timeout=1000) as blocker:
        view.practice_button.click()
    assert blocker.args == ["fr", "chat"]


def test_search_filters(qtbot, controller: PracticeController) -> None:
    create_app([])
    view = VocabularyView(controller)
    qtbot.addWidget(view)
    view.language_combo.setCurrentText("fr")
    controller.vocab_repo.capture(language_code="fr", word="chat", translation="cat")
    controller.vocab_repo.capture(language_code="fr", word="chien", translation="dog")
    view.refresh()
    assert view.list_widget.count() == 2
    view.search_edit.setText("chat")
    assert view.list_widget.count() == 1
