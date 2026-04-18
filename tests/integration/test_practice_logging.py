"""
Integration tests: practice-session logging and stats roll-up against real MySQL.

Exercises save_practice → get_user_progress / get_user_stats round-trips,
plus activity logging. Uses the real `user_progress` and `activity_log`
tables in `miolingo_test`.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


def test_save_practice_roundtrip(db_conn, make_user):
    import app_mysql

    u = make_user(username="frank")
    assert app_mysql.save_practice(
        user_id=u["user_id"],
        language_code="pt-BR",
        target_phrase="bom dia",
        recognized_phrase="bom dia",
        similarity_score=98.5,
        perfect_match=True,
        target_phonemes="bõ ˈdʒi.ɐ",
        user_phonemes="bõ ˈdʒi.ɐ",
    ) is True

    rows = app_mysql.get_user_progress(u["user_id"], "pt-BR", limit=10)
    assert len(rows) == 1
    row = rows[0]
    assert row["target_phrase"] == "bom dia"
    assert row["recognized_phrase"] == "bom dia"
    assert float(row["similarity_score"]) == pytest.approx(98.5)
    assert bool(row["perfect_match"]) is True


def test_user_stats_aggregates(db_conn, make_user):
    import app_mysql

    u = make_user(username="gina")
    scores = [(50.0, False), (80.0, False), (100.0, True), (90.0, False)]
    for score, perfect in scores:
        app_mysql.save_practice(
            user_id=u["user_id"],
            language_code="fr-FR",
            target_phrase="bonjour",
            recognized_phrase="bonjour",
            similarity_score=score,
            perfect_match=perfect,
        )

    stats = app_mysql.get_user_stats(u["user_id"], "fr-FR")
    assert stats["total"] == 4
    assert stats["perfect_count"] == 1
    assert stats["avg_score"] == pytest.approx(80.0)
    assert stats["recent_avg"] == pytest.approx(80.0)


def test_progress_scoped_by_language(db_conn, make_user):
    import app_mysql

    u = make_user(username="hank")
    app_mysql.save_practice(u["user_id"], "pt-BR", "a", "a", 100.0, True)
    app_mysql.save_practice(u["user_id"], "fr-FR", "b", "b", 100.0, True)

    pt = app_mysql.get_user_progress(u["user_id"], "pt-BR")
    fr = app_mysql.get_user_progress(u["user_id"], "fr-FR")
    assert len(pt) == 1 and pt[0]["target_phrase"] == "a"
    assert len(fr) == 1 and fr[0]["target_phrase"] == "b"


def test_activity_log_records_events(db_conn, make_user):
    import app_mysql

    u = make_user(username="ivy")
    app_mysql.log_activity(u["user_id"], "TEST_EVENT", "hello", "pytest")

    rows = app_mysql.get_user_activity_log(u["user_id"], limit=10)
    assert any(r["action"] == "TEST_EVENT" and r["details"] == "hello" for r in rows)
