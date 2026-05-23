"""PySide6 entry point for the Miolingo desktop app.

Milestone 0: an empty-but-runnable main window. Later milestones add the
Practice / History / Vocabulary / Statistics / Settings views.
"""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication, QLabel, QMainWindow

from . import APP_NAME, __version__


class MainWindow(QMainWindow):
    """The application's top-level window.

    Kept deliberately minimal in M0 — it must construct without a display
    (``QT_QPA_PLATFORM=offscreen``) so it can be smoke-tested headlessly.
    """

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1024, 720)

        placeholder = QLabel(
            f"{APP_NAME} desktop — scaffold (v{__version__})\n"
            "Practice, History, Vocabulary, and Statistics arrive in later milestones."
        )
        placeholder.setObjectName("scaffoldPlaceholder")
        placeholder.setContentsMargins(24, 24, 24, 24)
        self.setCentralWidget(placeholder)


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
