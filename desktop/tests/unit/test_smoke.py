"""Milestone 0 smoke tests: the package imports and the main window constructs.

GUI tests run under ``QT_QPA_PLATFORM=offscreen`` (set in ``conftest.py``).
``qtbot`` comes from pytest-qt and ensures proper widget teardown.
"""

from __future__ import annotations

import miolingo_desktop


def test_package_imports() -> None:
    assert miolingo_desktop.APP_NAME == "Miolingo"
    assert isinstance(miolingo_desktop.__version__, str)


def test_main_window_constructs(qtbot) -> None:
    # Imported lazily so the non-Qt import test above stays independent of Qt.
    from miolingo_desktop.main import MainWindow, create_app

    create_app([])  # ensure a QApplication exists
    window = MainWindow()
    qtbot.addWidget(window)

    assert window.windowTitle() == "Miolingo"
    assert window.centralWidget() is not None


def test_create_app_is_singleton() -> None:
    from miolingo_desktop.main import create_app

    first = create_app([])
    second = create_app([])
    assert first is second
