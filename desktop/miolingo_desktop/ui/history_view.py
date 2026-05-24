"""History view — past practice attempts from SQLite (Milestone 4).

A read-only table (date, language, target, heard, score, match) populated from
``PracticeRepository`` via the controller. ``refresh()`` re-queries, so the view
stays current after new attempts and across app restarts (rows are persisted).
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHeaderView,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..core.controller import PracticeController

_COLUMNS = ["Date", "Language", "Target", "Heard", "Score", "Match"]


class HistoryView(QWidget):
    """Lists past practice attempts."""

    def __init__(self, controller: PracticeController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._controller = controller

        root = QVBoxLayout(self)
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.setObjectName("historyRefreshButton")
        self.refresh_button.clicked.connect(self.refresh)
        root.addWidget(self.refresh_button)

        self.table = QTableWidget(0, len(_COLUMNS))
        self.table.setObjectName("historyTable")
        self.table.setHorizontalHeaderLabels(_COLUMNS)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        root.addWidget(self.table)

        self.refresh()

    def refresh(self) -> None:
        rows = self._controller.recent_history(limit=200)
        self.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            score = row.get("similarity_score")
            score_text = f"{float(score):.1f}%" if score is not None else ""
            match_text = "perfect" if row.get("perfect_match") else ""
            values = [
                str(row.get("created_at", "")),
                str(row.get("language_code", "")),
                str(row.get("target_phrase", "")),
                str(row.get("recognized_phrase", "")),
                score_text,
                match_text,
            ]
            for c, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.UserRole, row.get("id"))
                self.table.setItem(r, c, item)

    def row_count(self) -> int:
        """Convenience for tests."""
        return self.table.rowCount()
