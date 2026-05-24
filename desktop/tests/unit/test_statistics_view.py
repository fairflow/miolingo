"""Qt smoke test for the Statistics view (offscreen)."""

from __future__ import annotations

from pathlib import Path

import pytest

from miolingo_desktop.core.controller import PracticeController
from miolingo_desktop.data import Database
from miolingo_desktop.main import create_app
from miolingo_desktop.ui.statistics_view import StatisticsView


@pytest.fixture
def controller(tmp_path: Path) -> PracticeController:
    db = Database(tmp_path / "stats.db")
    yield PracticeController(db)
    db.close()


def _seed(controller: PracticeController) -> None:
    controller.practice_repo.save_attempt(
        language_code="pt", target_phrase="ola", recognized_phrase="ola",
        similarity_score=100.0, perfect_match=True,
    )
    controller.practice_repo.save_attempt(
        language_code="pt", target_phrase="bom", recognized_phrase="bem",
        similarity_score=70.0, perfect_match=False,
    )


def test_statistics_view_renders_summary(qtbot, controller: PracticeController) -> None:
    create_app([])
    _seed(controller)
    view = StatisticsView(controller)
    qtbot.addWidget(view)
    # One language summary row (pt) with two attempts.
    assert view.summary_table.rowCount() == 1
    assert view.summary_table.item(0, 0).text() == "pt"
    assert view.summary_table.item(0, 1).text() == "2"
    assert "%" in view.overall_label.text()


def test_statistics_view_empty(qtbot, controller: PracticeController) -> None:
    create_app([])
    view = StatisticsView(controller)
    qtbot.addWidget(view)
    assert view.summary_table.rowCount() == 0


def test_statistics_view_refresh(qtbot, controller: PracticeController) -> None:
    create_app([])
    view = StatisticsView(controller)
    qtbot.addWidget(view)
    _seed(controller)
    view.refresh()
    assert view.summary_table.rowCount() == 1
