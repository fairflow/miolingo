"""Statistics aggregation over practice attempts (pure, UI-free).

These functions take the plain attempt dicts returned by ``PracticeRepository``
and compute the figures the Statistics view renders: per-language totals and a
daily accuracy trend. Kept pure so they're fully unit-testable headlessly; the
Qt view only turns the returned data into charts.

Attempt dicts carry ``language_code``, ``similarity_score`` (0..100),
``perfect_match`` (0/1), and ``created_at`` (ISO-8601 ``YYYY-MM-DDTHH:MM:SS``).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, NamedTuple


class LanguageSummary(NamedTuple):
    language_code: str
    attempts: int
    perfect: int
    average_score: float


class TrendPoint(NamedTuple):
    date: str  # YYYY-MM-DD
    attempts: int
    average_score: float


def _day(created_at: str) -> str:
    return (created_at or "")[:10]


def summarise_by_language(attempts: Sequence[dict[str, Any]]) -> list[LanguageSummary]:
    """Per-language attempt count, perfect count, and mean score (sorted by code)."""
    buckets: dict[str, list[float]] = {}
    perfects: dict[str, int] = {}
    for a in attempts:
        code = a.get("language_code", "")
        buckets.setdefault(code, []).append(float(a.get("similarity_score", 0.0)))
        perfects[code] = perfects.get(code, 0) + (1 if a.get("perfect_match") else 0)

    summaries = [
        LanguageSummary(
            language_code=code,
            attempts=len(scores),
            perfect=perfects.get(code, 0),
            average_score=round(sum(scores) / len(scores), 2) if scores else 0.0,
        )
        for code, scores in buckets.items()
    ]
    return sorted(summaries, key=lambda s: s.language_code)


def accuracy_trend(
    attempts: Sequence[dict[str, Any]], *, language_code: str | None = None
) -> list[TrendPoint]:
    """Daily attempt count + mean score, ascending by date.

    When ``language_code`` is given, only that language's attempts are counted.
    """
    by_day: dict[str, list[float]] = {}
    for a in attempts:
        if language_code is not None and a.get("language_code") != language_code:
            continue
        day = _day(str(a.get("created_at", "")))
        if not day:
            continue
        by_day.setdefault(day, []).append(float(a.get("similarity_score", 0.0)))

    return [
        TrendPoint(
            date=day,
            attempts=len(scores),
            average_score=round(sum(scores) / len(scores), 2) if scores else 0.0,
        )
        for day, scores in sorted(by_day.items())
    ]


def overall_average(attempts: Sequence[dict[str, Any]]) -> float:
    """Mean similarity score across all attempts (0.0 if none)."""
    scores = [float(a.get("similarity_score", 0.0)) for a in attempts]
    return round(sum(scores) / len(scores), 2) if scores else 0.0
