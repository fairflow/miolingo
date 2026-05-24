"""PySide6 entry point for the Miolingo desktop app.

Opens the main window with a tab bar; Milestone 3 wires the Quick Practice
vertical slice. History / Vocabulary / Statistics / Settings tabs are added in
later milestones.
"""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget

from . import APP_NAME, __version__
from .core.controller import PracticeController
from .data import Database
from .ui.history_view import HistoryView
from .ui.practice_view import PracticeView
from .ui.settings_view import SettingsView
from .ui.statistics_view import StatisticsView
from .ui.vocabulary_view import VocabularyView


class MainWindow(QMainWindow):
    """The application's top-level window.

    Owns the SQLite ``Database`` and the ``PracticeController`` shared by views.
    Constructs without a display (``QT_QPA_PLATFORM=offscreen``) so it can be
    smoke-tested headlessly; the DB path may be overridden via ``MIOLINGO_DB_PATH``.
    """

    def __init__(self, db: Database | None = None) -> None:
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1024, 720)

        self.db = db if db is not None else Database()
        self.controller = PracticeController(self.db)

        self.tabs = QTabWidget()
        self.tabs.setObjectName("mainTabs")
        self.practice_view = PracticeView(self.controller)
        self.history_view = HistoryView(self.controller)
        self.vocabulary_view = VocabularyView(self.controller)
        self.statistics_view = StatisticsView(self.controller)
        self.settings_view = SettingsView(self.controller)
        self.tabs.addTab(self.practice_view, "Quick Practice")
        self.tabs.addTab(self.history_view, "History")
        self.tabs.addTab(self.vocabulary_view, "Vocabulary")
        self.tabs.addTab(self.statistics_view, "Statistics")
        self.tabs.addTab(self.settings_view, "Settings")
        self.tabs.currentChanged.connect(self._on_tab_changed)
        self.vocabulary_view.practiceRequested.connect(self._on_practice_requested)
        self.setCentralWidget(self.tabs)

    def _on_tab_changed(self, index: int) -> None:
        # Refresh data views when they become visible so new attempts show up.
        widget = self.tabs.widget(index)
        if widget is self.history_view:
            self.history_view.refresh()
        elif widget is self.statistics_view:
            self.statistics_view.refresh()

    def _on_practice_requested(self, language_code: str, word: str) -> None:
        # Practice-from-vocab: hand the word to the Practice tab and switch to it.
        self.practice_view.set_adhoc_phrase(language_code, word)
        self.tabs.setCurrentWidget(self.practice_view)

    def closeEvent(self, event: object) -> None:  # noqa: N802 - Qt override
        self.db.close()
        super().closeEvent(event)  # type: ignore[arg-type]


def create_app(argv: list[str] | None = None) -> QApplication:
    """Return a ``QApplication``, reusing the singleton if one already exists.

    Reusing the existing instance keeps this safe to call repeatedly from tests
    (Qt forbids constructing more than one ``QApplication``).
    """
    existing = QApplication.instance()
    if existing is not None:
        return existing  # type: ignore[return-value]
    app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)
    return app


def main(argv: list[str] | None = None) -> int:
    """Launch the desktop app. Returns the Qt event-loop exit code."""
    app = create_app(argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
