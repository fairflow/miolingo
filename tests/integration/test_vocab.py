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


# ── update_vocab_entry / autofill_vocab_entry (Task 2) ─────────────────────

def _capture_simple(user_id, word="saudade", language="Portuguese", **kw):
    import vocab
    r = vocab.capture_vocab_entry(
        user_id=user_id, language=language, word=word, **kw
    )
    assert r["ok"] and r["vocab_id"]
    return r["vocab_id"]


def test_update_vocab_entry_partial(db_conn, make_user):
    import vocab
    u = make_user(username="vocab_upd_partial")
    vid = _capture_simple(
        u["user_id"], translation="longing", ipa="sawˈdad.ʒi",
        source_name="Pessoa",
    )
    assert vocab.update_vocab_entry(
        user_id=u["user_id"], vocab_id=vid, translation="nostalgia"
    )
    row = vocab.get_vocab_entry(user_id=u["user_id"], vocab_id=vid)
    assert row["translation"] == "nostalgia"
    assert row["ipa"] == "sawˈdad.ʒi"
    assert row["source_name"] == "Pessoa"


def test_update_vocab_entry_cross_user_isolation(db_conn, make_user):
    import vocab
    u1 = make_user(username="vocab_upd_owner")
    u2 = make_user(username="vocab_upd_intruder")
    vid = _capture_simple(u1["user_id"], translation="orig")
    assert vocab.update_vocab_entry(
        user_id=u2["user_id"], vocab_id=vid, translation="hacked"
    ) is False
    row = vocab.get_vocab_entry(user_id=u1["user_id"], vocab_id=vid)
    assert row["translation"] == "orig"


def test_update_vocab_entry_clears_field_with_empty_string(db_conn, make_user):
    import vocab
    u = make_user(username="vocab_upd_clear")
    vid = _capture_simple(u["user_id"], url="https://example.com")
    assert vocab.update_vocab_entry(
        user_id=u["user_id"], vocab_id=vid, url=""
    )
    row = vocab.get_vocab_entry(user_id=u["user_id"], vocab_id=vid)
    assert row["url"] is None


def test_update_vocab_entry_display_word_casing_accepted(db_conn, make_user):
    import vocab
    u = make_user(username="vocab_upd_casing")
    vid = _capture_simple(u["user_id"], word="saudade")
    assert vocab.update_vocab_entry(
        user_id=u["user_id"], vocab_id=vid, display_word="Saudade"
    )
    row = vocab.get_vocab_entry(user_id=u["user_id"], vocab_id=vid)
    assert row["display_word"] == "Saudade"
    assert row["word"] == "saudade"  # lookup key unchanged


def test_update_vocab_entry_display_word_rejects_key_change(db_conn, make_user):
    import vocab
    u = make_user(username="vocab_upd_keychange")
    vid = _capture_simple(u["user_id"], word="saudade")
    with pytest.raises(ValueError, match="lookup key"):
        vocab.update_vocab_entry(
            user_id=u["user_id"], vocab_id=vid, display_word="saudades"
        )


def test_update_vocab_entry_rejects_unknown_field(db_conn, make_user):
    import vocab
    u = make_user(username="vocab_upd_unknown")
    vid = _capture_simple(u["user_id"])
    with pytest.raises(ValueError, match="Unknown"):
        vocab.update_vocab_entry(
            user_id=u["user_id"], vocab_id=vid, times_seen=999
        )


def test_update_vocab_entry_noop_when_unchanged(db_conn, make_user):
    import vocab
    u = make_user(username="vocab_upd_noop")
    vid = _capture_simple(u["user_id"], translation="x")
    before = vocab.get_vocab_entry(user_id=u["user_id"], vocab_id=vid)
    assert vocab.update_vocab_entry(
        user_id=u["user_id"], vocab_id=vid, translation="x"
    ) is True
    after = vocab.get_vocab_entry(user_id=u["user_id"], vocab_id=vid)
    assert before["times_seen"] == after["times_seen"]
    assert before["translation"] == after["translation"]


def test_autofill_only_fills_missing(db_conn, make_user, monkeypatch):
    import vocab
    u = make_user(username="vocab_autofill_partial")
    vid = _capture_simple(u["user_id"], translation="already-set")

    monkeypatch.setattr(vocab, "_enrich",
                        lambda *a, **kw: ("SHOULD-NOT-OVERWRITE", "ˈstub"))

    result = vocab.autofill_vocab_entry(
        user_id=u["user_id"], vocab_id=vid,
        language="Portuguese", source_language="English", secrets=None,
    )
    assert result == {"filled": {"ipa": "ˈstub"}}
    row = vocab.get_vocab_entry(user_id=u["user_id"], vocab_id=vid)
    assert row["translation"] == "already-set"
    assert row["ipa"] == "ˈstub"


def test_autofill_noop_when_complete(db_conn, make_user, monkeypatch):
    import vocab
    u = make_user(username="vocab_autofill_complete")
    vid = _capture_simple(u["user_id"], translation="t", ipa="i")

    called = {"n": 0}
    def _stub(*a, **kw):
        called["n"] += 1
        return ("X", "Y")
    monkeypatch.setattr(vocab, "_enrich", _stub)

    result = vocab.autofill_vocab_entry(
        user_id=u["user_id"], vocab_id=vid,
        language="Portuguese", source_language="English", secrets=None,
    )
    assert result == {"filled": {}}
    assert called["n"] == 0  # short-circuits before calling _enrich


def test_autofill_noop_when_enrich_returns_none(db_conn, make_user, monkeypatch):
    import vocab
    u = make_user(username="vocab_autofill_empty")
    vid = _capture_simple(u["user_id"])

    monkeypatch.setattr(vocab, "_enrich", lambda *a, **kw: (None, None))

    result = vocab.autofill_vocab_entry(
        user_id=u["user_id"], vocab_id=vid,
        language="Portuguese", source_language="English", secrets=None,
    )
    assert result == {"filled": {}}
    row = vocab.get_vocab_entry(user_id=u["user_id"], vocab_id=vid)
    assert row["translation"] is None
    assert row["ipa"] is None


# ── search mini-language (v7.8.0) ──────────────────────────────────────────

def _capture(user_id, word, language="Portuguese", **kw):
    import vocab
    r = vocab.capture_vocab_entry(
        user_id=user_id, language=language, word=word, **kw
    )
    assert r["ok"], r
    return r["vocab_id"]


@pytest.fixture
def vocab_corpus(db_conn, make_user):
    """Seed a user with a small, diverse corpus for search tests."""
    import vocab
    u = make_user(username="vocab_search_user")
    uid = u["user_id"]
    _capture(uid, "abelha", translation="bee", ipa="aˈβe.ʎɐ",
             source_name="Apiology 101")
    _capture(uid, "ação", translation="action", ipa="aˈsɐ̃w",
             source_name="Notícias")
    _capture(uid, "canção", translation="song",
             source_name="Pessoa: Canção")
    _capture(uid, "mar", translation="sea", ipa="ˈmaɾ",
             url="https://example.com/mar")  # no source
    _capture(uid, "sol", translation="sun",
             source_name="Lesson 1")  # no ipa, no url
    _capture(uid, "zebra", source_name="Zoo")  # no translation, no ipa
    return u


def test_search_prefix_anchor(vocab_corpus):
    import vocab
    hits = {r["word"] for r in vocab.list_vocab(
        user_id=vocab_corpus["user_id"], language="Portuguese", search="^a")}
    assert hits == {"abelha", "ação"}


def test_search_suffix_anchor(vocab_corpus):
    import vocab
    hits = {r["word"] for r in vocab.list_vocab(
        user_id=vocab_corpus["user_id"], language="Portuguese", search="ção$")}
    assert hits == {"ação", "canção"}


def test_search_bracket_regex(vocab_corpus):
    import vocab
    # [aeiou]ção → vowel immediately before 'ção'.
    # ação matches (a+ção); canção does NOT (n+ção) — exactly what a class is for.
    hits = {r["word"] for r in vocab.list_vocab(
        user_id=vocab_corpus["user_id"], language="Portuguese",
        search="[aeiou]ção")}
    assert hits == {"ação"}

    # And a broader class to prove the operator itself works over multiple words.
    hits2 = {r["word"] for r in vocab.list_vocab(
        user_id=vocab_corpus["user_id"], language="Portuguese",
        search="^[az]")}
    assert hits2 == {"abelha", "ação", "zebra"}


def test_search_field_substring(vocab_corpus):
    import vocab
    hits = {r["word"] for r in vocab.list_vocab(
        user_id=vocab_corpus["user_id"], language="Portuguese",
        search="source:Pessoa")}
    assert hits == {"canção"}


def test_search_field_regex(vocab_corpus):
    import vocab
    hits = {r["word"] for r in vocab.list_vocab(
        user_id=vocab_corpus["user_id"], language="Portuguese",
        search="source:^Lesson")}
    assert hits == {"sol"}


def test_search_has_url(vocab_corpus):
    import vocab
    hits = {r["word"] for r in vocab.list_vocab(
        user_id=vocab_corpus["user_id"], language="Portuguese",
        search="has:url")}
    assert hits == {"mar"}


def test_search_none_ipa(vocab_corpus):
    import vocab
    hits = {r["word"] for r in vocab.list_vocab(
        user_id=vocab_corpus["user_id"], language="Portuguese",
        search="none:ipa")}
    assert hits == {"sol", "zebra", "canção"}


def test_search_combined_AND(vocab_corpus):
    import vocab
    # ^a AND has:ipa → abelha, ação
    hits = {r["word"] for r in vocab.list_vocab(
        user_id=vocab_corpus["user_id"], language="Portuguese",
        search="^a has:ipa")}
    assert hits == {"abelha", "ação"}


def test_search_plain_text_backcompat(vocab_corpus):
    import vocab
    # Plain text still matches word OR translation substring.
    hits = {r["word"] for r in vocab.list_vocab(
        user_id=vocab_corpus["user_id"], language="Portuguese", search="sea")}
    assert hits == {"mar"}  # 'sea' is mar's translation


def test_search_whitespace_around_colon(vocab_corpus):
    import vocab
    hits = {r["word"] for r in vocab.list_vocab(
        user_id=vocab_corpus["user_id"], language="Portuguese",
        search="has : url")}
    assert hits == {"mar"}


def test_search_unknown_field_raises(vocab_corpus):
    import vocab, vocab_search
    with pytest.raises(vocab_search.QueryError):
        vocab.list_vocab(
            user_id=vocab_corpus["user_id"], language="Portuguese",
            search="bogus:x")


def test_vocab_as_practice_phrases_shape(db_conn, make_user):
    import vocab

    u = make_user(username="vocab_practiser")
    vocab.capture_vocab_entry(user_id=u["user_id"], language="Portuguese", word="lua")
    phrases = vocab.vocab_as_practice_phrases(
        user_id=u["user_id"], language="Portuguese")
    assert len(phrases) == 1
    assert set(phrases[0].keys()) >= {"text", "translation", "ipa"}
    assert phrases[0]["text"] == "lua"
