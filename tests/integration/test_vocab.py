"""
Integration tests: Personal Vocabulary Tracker (F2).

Exercises the `vocab_entries` table and `src/vocab.py` helpers against the
real `miolingo_test` database. `enrich=False` everywhere to stay hermetic
(no LLM / espeak calls).
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


def test_capture_and_list_roundtrip(db_conn, make_user):
    import vocab

    u = make_user(username="vocab_alice")
    r = vocab.capture_vocab_entry(
        user_id=u["user_id"],
        language="Portuguese",
        word="saudade",
        source_name="Pessoa: Autopsicografia",
        context_before="Fingidor tão completamente",
        context_line="Que chega a fingir que é dor",
        context_after="A dor que deveras sente.",
    )
    assert r["ok"] is True and r["created"] is True and r["vocab_id"]

    rows = vocab.list_vocab(user_id=u["user_id"], language="Portuguese")
    assert len(rows) == 1
    row = rows[0]
    assert row["word"] == "saudade"
    assert row["display_word"] == "saudade"
    assert row["source_name"] == "Pessoa: Autopsicografia"
    assert row["context_line"] == "Que chega a fingir que é dor"
    assert row["times_seen"] == 1


def test_recapture_bumps_counters_and_fills_nulls(db_conn, make_user):
    import vocab

    u = make_user(username="vocab_bob")

    # First capture — only word + source, no translation
    vocab.capture_vocab_entry(
        user_id=u["user_id"], language="French", word="bonjour",
        source_name="Lesson 1",
    )

    # Re-capture — provide context this time. times_seen bumps, NULL context fills,
    # but source_name (already set) is NOT overwritten.
    r2 = vocab.capture_vocab_entry(
        user_id=u["user_id"], language="French", word="bonjour",
        source_name="Lesson 99 (should not overwrite)",
        context_line="Bonjour, ça va?",
    )
    assert r2["created"] is False

    rows = vocab.list_vocab(user_id=u["user_id"], language="French")
    assert len(rows) == 1
    row = rows[0]
    assert row["times_seen"] == 2
    assert row["source_name"] == "Lesson 1"  # first encounter wins
    assert row["context_line"] == "Bonjour, ça va?"  # was NULL, now filled


def test_multiword_rejected(db_conn, make_user):
    import vocab

    u = make_user(username="vocab_carol")
    r = vocab.capture_vocab_entry(
        user_id=u["user_id"], language="Portuguese", word="boa tarde",
    )
    assert r["ok"] is False
    assert "single words" in r["message"]
    assert vocab.list_vocab(user_id=u["user_id"], language="Portuguese") == []


def test_normalisation_strips_punctuation_and_lowercases_key(db_conn, make_user):
    import vocab

    u = make_user(username="vocab_dan")
    # Capture "Saudade," — trailing comma, capital S
    r1 = vocab.capture_vocab_entry(
        user_id=u["user_id"], language="Portuguese", word="Saudade,",
    )
    assert r1["created"] is True

    # Capture "saudade" — should dedup on lookup key
    r2 = vocab.capture_vocab_entry(
        user_id=u["user_id"], language="Portuguese", word="saudade",
    )
    assert r2["created"] is False
    assert r2["vocab_id"] == r1["vocab_id"]

    rows = vocab.list_vocab(user_id=u["user_id"], language="Portuguese")
    assert len(rows) == 1
    assert rows[0]["word"] == "saudade"  # lowercase key
    assert rows[0]["display_word"] == "Saudade"  # first encounter, punct trimmed


def test_per_language_isolation(db_conn, make_user):
    import vocab

    u = make_user(username="vocab_ellen")
    vocab.capture_vocab_entry(user_id=u["user_id"], language="Portuguese", word="sol")
    vocab.capture_vocab_entry(user_id=u["user_id"], language="French", word="sol")

    pt = vocab.list_vocab(user_id=u["user_id"], language="Portuguese")
    fr = vocab.list_vocab(user_id=u["user_id"], language="French")
    assert len(pt) == 1 and len(fr) == 1
    assert pt[0]["vocab_id"] != fr[0]["vocab_id"]


def test_list_sort_orders(db_conn, make_user):
    import time
    import vocab

    u = make_user(username="vocab_frank")
    vocab.capture_vocab_entry(user_id=u["user_id"], language="Portuguese", word="zebra")
    time.sleep(1.1)  # last_seen_at has second precision; ensure distinct timestamps
    vocab.capture_vocab_entry(user_id=u["user_id"], language="Portuguese", word="abelha")

    alpha = [r["word"] for r in vocab.list_vocab(
        user_id=u["user_id"], language="Portuguese", sort="alpha")]
    assert alpha == ["abelha", "zebra"]

    recent = [r["word"] for r in vocab.list_vocab(
        user_id=u["user_id"], language="Portuguese", sort="recent")]
    assert recent == ["abelha", "zebra"]  # abelha captured last


def test_search_filter(db_conn, make_user):
    import vocab

    u = make_user(username="vocab_gina")
    vocab.capture_vocab_entry(user_id=u["user_id"], language="Portuguese", word="mar")
    vocab.capture_vocab_entry(user_id=u["user_id"], language="Portuguese", word="sol")

    hits = vocab.list_vocab(
        user_id=u["user_id"], language="Portuguese", search="ma")
    assert [r["word"] for r in hits] == ["mar"]


def test_delete_and_notes(db_conn, make_user):
    import vocab

    u = make_user(username="vocab_hank")
    r = vocab.capture_vocab_entry(
        user_id=u["user_id"], language="Portuguese", word="lua")
    vid = r["vocab_id"]

    assert vocab.update_vocab_notes(
        user_id=u["user_id"], vocab_id=vid, notes="moon") is True
    entry = vocab.get_vocab_entry(user_id=u["user_id"], vocab_id=vid)
    assert entry["notes"] == "moon"

    assert vocab.delete_vocab_entry(user_id=u["user_id"], vocab_id=vid) is True
    assert vocab.get_vocab_entry(user_id=u["user_id"], vocab_id=vid) is None


def test_cross_user_isolation(db_conn, make_user):
    import vocab

    u1 = make_user(username="vocab_owner")
    u2 = make_user(username="vocab_intruder")
    r = vocab.capture_vocab_entry(
        user_id=u1["user_id"], language="Portuguese", word="casa")
    # u2 cannot read or delete u1's entry
    assert vocab.get_vocab_entry(user_id=u2["user_id"], vocab_id=r["vocab_id"]) is None
    assert vocab.delete_vocab_entry(
        user_id=u2["user_id"], vocab_id=r["vocab_id"]) is False


def test_bulk_import(db_conn, make_user):
    import vocab

    u = make_user(username="vocab_importer")
    # Format: word | translation | ipa | source | url (5 positional fields)
    text = (
        "# comment line ignored\n"
        "\n"
        "lua | moon | [ˈlu.ɐ] | Cancao da Lua\n"
        "mar | sea || Cancao do Mar\n"
        "boa tarde | good afternoon | | phrases.txt\n"
        "sol | sun | | Lesson 1\n"
    )
    summary = vocab.import_from_file_contents(
        user_id=u["user_id"], language="Portuguese", contents=text)

    assert summary["added"] == 3
    assert summary["updated"] == 0
    assert summary["skipped_not_single"] == ["boa tarde"]

    rows = vocab.list_vocab(user_id=u["user_id"], language="Portuguese")
    assert sorted(r["word"] for r in rows) == ["lua", "mar", "sol"]
    lua = next(r for r in rows if r["word"] == "lua")
    assert lua["translation"] == "moon"
    assert lua["ipa"] == "ˈlu.ɐ"
    assert lua["source_name"] == "Cancao da Lua"


def test_vocab_as_practice_phrases_shape(db_conn, make_user):
    import vocab

    u = make_user(username="vocab_practiser")
    vocab.capture_vocab_entry(user_id=u["user_id"], language="Portuguese", word="lua")
    phrases = vocab.vocab_as_practice_phrases(
        user_id=u["user_id"], language="Portuguese")
    assert len(phrases) == 1
    assert set(phrases[0].keys()) >= {"text", "translation", "ipa"}
    assert phrases[0]["text"] == "lua"
