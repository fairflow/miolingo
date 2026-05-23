"""Tests for the SQLite storage layer: migrations + repository CRUD round-trips.

Each test uses a temp-file DB (not in-memory) so restart-persistence and WAL
behaviour are exercised the way the real app uses them.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from miolingo_desktop.data import (
    Database,
    PracticeRepository,
    SettingsRepository,
    VocabularyRepository,
)
from miolingo_desktop.data.migrations import MIGRATIONS, current_version


@pytest.fixture
def db(tmp_path: Path) -> Database:
    database = Database(tmp_path / "test.db")
    yield database
    database.close()


# ---- migrations -----------------------------------------------------------


def test_migration_applies_to_latest_version(db: Database) -> None:
    latest = max(v for v, _ in MIGRATIONS)
    assert current_version(db.connection) == latest


def test_migration_is_idempotent(tmp_path: Path) -> None:
    path = tmp_path / "idem.db"
    Database(path).close()
    # Re-open: migrations must not error or duplicate schema.
    db2 = Database(path)
    latest = max(v for v, _ in MIGRATIONS)
    assert current_version(db2.connection) == latest
    db2.close()


def test_db_created_on_first_run(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "dir" / "miolingo.db"
    assert not path.exists()
    Database(path).close()
    assert path.exists()


# ---- settings -------------------------------------------------------------


def test_settings_round_trip(db: Database) -> None:
    repo = SettingsRepository(db)
    assert repo.get("voice", "default") == "default"
    repo.set("voice", "pt-br")
    repo.set("whisper_model_size", "medium")
    assert repo.get("voice") == "pt-br"
    assert repo.get_all()["whisper_model_size"] == "medium"


def test_settings_persist_across_reopen(tmp_path: Path) -> None:
    path = tmp_path / "persist.db"
    db1 = Database(path)
    SettingsRepository(db1).set("voice", "fr-fr")
    db1.close()

    db2 = Database(path)
    assert SettingsRepository(db2).get("voice") == "fr-fr"
    db2.close()


def test_settings_update_overwrites(db: Database) -> None:
    repo = SettingsRepository(db)
    repo.set("voice", "a")
    repo.set("voice", "b")
    assert repo.get("voice") == "b"
    # Only one live row for the key.
    assert len(repo.get_all()) == 1


# ---- practice attempts ----------------------------------------------------


def test_practice_save_and_list(db: Database) -> None:
    repo = PracticeRepository(db)
    repo.save_attempt(
        language_code="pt",
        target_phrase="ola",
        recognized_phrase="ola",
        similarity_score=100.0,
        perfect_match=True,
    )
    repo.save_attempt(
        language_code="fr",
        target_phrase="bonjour",
        recognized_phrase="bonsoir",
        similarity_score=80.0,
        perfect_match=False,
    )
    all_rows = repo.list_history()
    assert len(all_rows) == 2
    fr_rows = repo.list_history(language_code="fr")
    assert len(fr_rows) == 1
    assert fr_rows[0]["target_phrase"] == "bonjour"
    assert fr_rows[0]["perfect_match"] == 0


def test_practice_save_from_result(db: Database) -> None:
    repo = PracticeRepository(db)
    result = {
        "target": "ola",
        "recognized": "olha",
        "similarity": 0.6667,
        "exact_match": False,
        "correct_phonemes_normalized": "ola",
        "user_phonemes_normalized": "olja",
    }
    repo.save_from_result("pt", result)
    row = repo.list_history()[0]
    assert row["target_phrase"] == "ola"
    assert row["similarity_score"] == pytest.approx(66.67)
    assert row["perfect_match"] == 0


def test_practice_persists_across_reopen(tmp_path: Path) -> None:
    path = tmp_path / "hist.db"
    db1 = Database(path)
    PracticeRepository(db1).save_attempt(
        language_code="pt", target_phrase="ola", recognized_phrase="ola",
        similarity_score=100.0, perfect_match=True,
    )
    db1.close()
    db2 = Database(path)
    assert len(PracticeRepository(db2).list_history()) == 1
    db2.close()


def test_practice_soft_delete_hides_row(db: Database) -> None:
    repo = PracticeRepository(db)
    attempt_id = repo.save_attempt(
        language_code="pt", target_phrase="ola", recognized_phrase="ola",
        similarity_score=100.0, perfect_match=True,
    )
    repo.soft_delete(attempt_id)
    assert repo.list_history() == []
    assert len(repo.list_history(include_deleted=True)) == 1


# ---- vocabulary -----------------------------------------------------------


def test_vocab_capture_creates_then_bumps(db: Database) -> None:
    repo = VocabularyRepository(db)
    first = repo.capture(language_code="fr", word="chat", translation="cat")
    assert first["created"] is True
    second = repo.capture(language_code="fr", word="chat")
    assert second["created"] is False
    assert second["id"] == first["id"]
    row = repo.get(first["id"])
    assert row is not None
    assert row["times_seen"] == 2
    # First-encounter translation preserved (not overwritten by NULL).
    assert row["translation"] == "cat"


def test_vocab_capture_fills_null_fields_only(db: Database) -> None:
    repo = VocabularyRepository(db)
    rid = repo.capture(language_code="fr", word="chat")["id"]
    repo.capture(language_code="fr", word="chat", translation="cat", ipa="ʃa")
    row = repo.get(rid)
    assert row["translation"] == "cat"
    assert row["ipa"] == "ʃa"


def test_vocab_update(db: Database) -> None:
    repo = VocabularyRepository(db)
    rid = repo.capture(language_code="fr", word="chat")["id"]
    repo.update(rid, translation="kitty", url="http://x")
    row = repo.get(rid)
    assert row["translation"] == "kitty"
    assert row["url"] == "http://x"
    # Unknown fields ignored.
    repo.update(rid, not_a_column="x")


def test_vocab_list_search_and_sort(db: Database) -> None:
    repo = VocabularyRepository(db)
    repo.capture(language_code="fr", word="banane", translation="banana")
    repo.capture(language_code="fr", word="chat", translation="cat")
    repo.capture(language_code="de", word="hund", translation="dog")

    fr = repo.list(language_code="fr")
    assert [r["word"] for r in fr] == ["banane", "chat"]  # alpha sort
    found = repo.list(language_code="fr", search="cat")
    assert len(found) == 1 and found[0]["word"] == "chat"


def test_vocab_soft_delete_and_resurrect(db: Database) -> None:
    repo = VocabularyRepository(db)
    rid = repo.capture(language_code="fr", word="chat")["id"]
    repo.soft_delete(rid)
    assert repo.list(language_code="fr") == []
    # Re-capturing the same word resurrects the row.
    again = repo.capture(language_code="fr", word="chat")
    assert again["id"] == rid
    assert len(repo.list(language_code="fr")) == 1


def test_vocab_export_csv_rows(db: Database) -> None:
    repo = VocabularyRepository(db)
    repo.capture(language_code="fr", word="chat", translation="cat")
    rows = list(repo.export_csv_rows(language_code="fr"))
    assert len(rows) == 1
    assert rows[0]["word"] == "chat"
