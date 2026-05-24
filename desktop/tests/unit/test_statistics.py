"""Tests for the pure statistics aggregators."""

from __future__ import annotations

from miolingo_desktop.core import statistics as stats

ATTEMPTS = [
    {"language_code": "pt", "similarity_score": 100.0, "perfect_match": 1, "created_at": "2026-05-20T10:00:00"},
    {"language_code": "pt", "similarity_score": 80.0, "perfect_match": 0, "created_at": "2026-05-20T11:00:00"},
    {"language_code": "pt", "similarity_score": 60.0, "perfect_match": 0, "created_at": "2026-05-21T09:00:00"},
    {"language_code": "fr", "similarity_score": 90.0, "perfect_match": 1, "created_at": "2026-05-21T09:30:00"},
]


def test_summarise_by_language() -> None:
    summaries = stats.summarise_by_language(ATTEMPTS)
    by_code = {s.language_code: s for s in summaries}
    assert by_code["pt"].attempts == 3
    assert by_code["pt"].perfect == 1
    assert by_code["pt"].average_score == 80.0  # (100+80+60)/3
    assert by_code["fr"].attempts == 1
    assert by_code["fr"].average_score == 90.0
    # Sorted by code.
    assert [s.language_code for s in summaries] == ["fr", "pt"]


def test_summarise_empty() -> None:
    assert stats.summarise_by_language([]) == []


def test_accuracy_trend_all_languages() -> None:
    trend = stats.accuracy_trend(ATTEMPTS)
    assert [p.date for p in trend] == ["2026-05-20", "2026-05-21"]
    assert trend[0].attempts == 2
    assert trend[0].average_score == 90.0  # (100+80)/2
    assert trend[1].attempts == 2
    assert trend[1].average_score == 75.0  # (60+90)/2


def test_accuracy_trend_filtered_by_language() -> None:
    trend = stats.accuracy_trend(ATTEMPTS, language_code="pt")
    assert [p.date for p in trend] == ["2026-05-20", "2026-05-21"]
    assert trend[1].attempts == 1
    assert trend[1].average_score == 60.0


def test_overall_average() -> None:
    assert stats.overall_average(ATTEMPTS) == 82.5  # (100+80+60+90)/4
    assert stats.overall_average([]) == 0.0
