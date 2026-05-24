"""Qt tests for History + Settings views (offscreen)."""

from __future__ import annotations

from pathlib import Path

import pytest

from miolingo_desktop.core.controller import PracticeController
from miolingo_desktop.data import Database
from miolingo_desktop.main import create_app
from miolingo_desktop.ui.history_view import HistoryView
from miolingo_desktop.ui.settings_view import SettingsView


@pytest.fixture
def controller(tmp_path: Path) -> PracticeController:
    db = Database(tmp_path / "m4.db")
    yield PracticeController(db)
    db.close()


def _seed(controller: PracticeController) -> None:
    controller.practice_repo.save_attempt(
        language_code="pt", target_phrase="ola", recognized_phrase="ola",
        similarity_score=100.0, perfect_match=True,
    )
    controller.practice_repo.save_attempt(
        language_code="fr", target_phrase="bonjour", recognized_phrase="bonsoir",
        similarity_score=72.5, perfect_match=False,
    )


def test_history_renders_seeded_rows(qtbot, controller: PracticeController) -> None:
    create_app([])
    _seed(controller)
    view = HistoryView(controller)
    qtbot.addWidget(view)
    assert view.row_count() == 2
    # Newest first; columns populated.
    assert view.table.item(0, 1).text() in {"pt", "fr"}
    assert "%" in view.table.item(0, 4).text()


def test_history_refresh_picks_up_new_rows(qtbot, controller: PracticeController) -> None:
    create_app([])
    view = HistoryView(controller)
    qtbot.addWidget(view)
    assert view.row_count() == 0
    _seed(controller)
    view.refresh()
    assert view.row_count() == 2


def test_history_persists_across_restart(qtbot, tmp_path: Path) -> None:
    create_app([])
    path = tmp_path / "persist.db"
    db1 = Database(path)
    PracticeController(db1).practice_repo.save_attempt(
        language_code="pt", target_phrase="ola", recognized_phrase="ola",
        similarity_score=100.0, perfect_match=True,
    )
    db1.close()

    db2 = Database(path)
    view = HistoryView(PracticeController(db2))
    qtbot.addWidget(view)
    assert view.row_count() == 1
    db2.close()


def test_settings_round_trip(qtbot, controller: PracticeController) -> None:
    create_app([])
    view = SettingsView(controller)
    qtbot.addWidget(view)
    view._set_combo(view.whisper_combo, "base")
    view._set_combo(view.tts_combo, "espeak")
    view.duration_spin.setValue(7)
    view.save()

    stored = controller.effective_settings()
    assert stored["whisper_model_size"] == "base"
    assert stored["tts_engine"] == "espeak"
    assert stored["duration"] == 7


def test_settings_restored_on_relaunch(qtbot, tmp_path: Path) -> None:
    create_app([])
    path = tmp_path / "settings.db"
    db1 = Database(path)
    c1 = PracticeController(db1)
    v1 = SettingsView(c1)
    qtbot.addWidget(v1)
    v1._set_combo(v1.whisper_combo, "small")
    v1.save()
    db1.close()

    db2 = Database(path)
    v2 = SettingsView(PracticeController(db2))
    qtbot.addWidget(v2)
    assert v2.whisper_combo.currentText() == "small"
    db2.close()
