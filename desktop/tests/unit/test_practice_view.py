"""Qt smoke + threading tests for the Practice vertical slice (offscreen).

- The view constructs, populates language/category/file/phrase widgets, and
  exposes the selected phrase.
- The Worker runs its callable on a NON-GUI thread (proves transcription won't
  freeze the UI — SPEC §7), reports progress, and delivers the result.
"""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from miolingo_desktop.core.controller import PracticeController
from miolingo_desktop.data import Database
from miolingo_desktop.main import MainWindow, create_app
from miolingo_desktop.ui.practice_view import PracticeView
from miolingo_desktop.ui.workers import Worker


@pytest.fixture
def controller(tmp_path: Path) -> PracticeController:
    db = Database(tmp_path / "view.db")
    yield PracticeController(db)
    db.close()


def test_practice_view_constructs_and_populates(qtbot, controller: PracticeController) -> None:
    create_app([])
    view = PracticeView(controller)
    qtbot.addWidget(view)
    # Languages loaded from bundled materials.
    assert view.language_combo.count() > 0
    # Selecting a language populates categories; a category populates files.
    view.language_combo.setCurrentText("pt")
    assert view.category_combo.count() > 0
    if view.file_combo.count():
        # A loaded set yields selectable phrases (or at least no crash).
        assert isinstance(view.selected_phrase_text(), (str, type(None)))


def test_main_window_has_practice_tab(qtbot, tmp_path: Path) -> None:
    create_app([])
    db = Database(tmp_path / "main.db")
    window = MainWindow(db=db)
    qtbot.addWidget(window)
    assert window.tabs.count() >= 1
    assert window.tabs.tabText(0) == "Quick Practice"


def test_worker_runs_off_gui_thread(qtbot) -> None:
    create_app([])
    main_thread = threading.get_ident()
    captured: dict = {}

    def _work(progress_fn=None):
        if progress_fn:
            progress_fn("working")
        captured["thread"] = threading.get_ident()
        return "done"

    results: list = []
    progresses: list = []
    worker = Worker(_work, pass_progress=True)
    worker.signals.finished.connect(results.append)
    worker.signals.progress.connect(progresses.append)

    from PySide6.QtCore import QThreadPool

    with qtbot.waitSignal(worker.signals.finished, timeout=5000):
        QThreadPool.globalInstance().start(worker)

    assert results == ["done"]
    assert progresses == ["working"]
    # The work ran on a different thread than the GUI/main thread.
    assert captured["thread"] != main_thread


def test_worker_reports_error(qtbot) -> None:
    create_app([])

    def _boom():
        raise RuntimeError("kaboom")

    errors: list = []
    worker = Worker(_boom)
    worker.signals.error.connect(errors.append)

    from PySide6.QtCore import QThreadPool

    with qtbot.waitSignal(worker.signals.error, timeout=5000):
        QThreadPool.globalInstance().start(worker)

    assert errors and "kaboom" in errors[0]
