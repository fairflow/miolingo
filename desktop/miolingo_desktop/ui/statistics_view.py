"""Statistics view — what the Streamlit app never finished (Milestone 6).

Shows, computed from local SQLite via the pure ``core.statistics`` aggregators:
- a per-language summary table (attempts, perfect, average score), and
- an accuracy-over-time trend.

Charts use ``PySide6.QtCharts`` when available; it's an optional Qt module, so
if it's missing the trend degrades to a small table (the smoke test passes
either way). All data is local — no network.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..core import statistics as stats
from ..core.controller import PracticeController


def _qtcharts_available() -> bool:
    try:
        import PySide6.QtCharts  # noqa: F401
    except Exception:  # noqa: BLE001
        return False
    return True


class StatisticsView(QWidget):
    """Per-language summary + accuracy trend from local data."""

    def __init__(self, controller: PracticeController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._controller = controller
        self._chart_view = None  # type: ignore[var-annotated]

        root = QVBoxLayout(self)
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.setObjectName("statsRefreshButton")
        self.refresh_button.clicked.connect(self.refresh)
        root.addWidget(self.refresh_button)

        self.overall_label = QLabel("")
        self.overall_label.setObjectName("statsOverallLabel")
        root.addWidget(self.overall_label)

        self.summary_table = QTableWidget(0, 4)
        self.summary_table.setObjectName("statsSummaryTable")
        self.summary_table.setHorizontalHeaderLabels(
            ["Language", "Attempts", "Perfect", "Avg score"]
        )
        self.summary_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.summary_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        root.addWidget(self.summary_table)

        root.addWidget(QLabel("Accuracy over time:"))
        self._trend_container = QVBoxLayout()
        root.addLayout(self._trend_container, stretch=1)

        # Fallback trend table (used when QtCharts is unavailable).
        self.trend_table = QTableWidget(0, 3)
        self.trend_table.setObjectName("statsTrendTable")
        self.trend_table.setHorizontalHeaderLabels(["Date", "Attempts", "Avg score"])
        self.trend_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.trend_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        self.refresh()

    # -- data --------------------------------------------------------------

    def refresh(self) -> None:
        attempts = self._controller.practice_repo.list_history(limit=100000)
        self._render_summary(stats.summarise_by_language(attempts))
        self.overall_label.setText(
            f"Total attempts: {len(attempts)}    "
            f"Overall average: {stats.overall_average(attempts):.1f}%"
        )
        self._render_trend(stats.accuracy_trend(attempts))

    def _render_summary(self, summaries: list[stats.LanguageSummary]) -> None:
        self.summary_table.setRowCount(len(summaries))
        for r, s in enumerate(summaries):
            values = [s.language_code, str(s.attempts), str(s.perfect), f"{s.average_score:.1f}%"]
            for c, value in enumerate(values):
                self.summary_table.setItem(r, c, QTableWidgetItem(value))

    def _render_trend(self, trend: list[stats.TrendPoint]) -> None:
        if _qtcharts_available():
            self._render_trend_chart(trend)
        else:
            self._render_trend_table(trend)

    def _render_trend_chart(self, trend: list[stats.TrendPoint]) -> None:
        from PySide6.QtCharts import QChart, QChartView, QLineSeries

        series = QLineSeries()
        series.setName("Avg score (%)")
        for i, point in enumerate(trend):
            series.append(float(i), float(point.average_score))

        chart = QChart()
        chart.addSeries(series)
        chart.createDefaultAxes()
        chart.setTitle("Accuracy over time")

        if self._chart_view is None:
            self._chart_view = QChartView(chart)
            self._chart_view.setObjectName("statsChartView")
            self._trend_container.addWidget(self._chart_view)
        else:
            self._chart_view.setChart(chart)

    def _render_trend_table(self, trend: list[stats.TrendPoint]) -> None:
        if self.trend_table.parent() is None:
            self._trend_container.addWidget(self.trend_table)
        self.trend_table.setRowCount(len(trend))
        for r, point in enumerate(trend):
            values = [point.date, str(point.attempts), f"{point.average_score:.1f}%"]
            for c, value in enumerate(values):
                self.trend_table.setItem(r, c, QTableWidgetItem(value))
