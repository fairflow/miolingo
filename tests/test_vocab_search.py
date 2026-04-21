"""
Unit tests for the vocab search mini-language parser (src/vocab_search.py).

No DB here — the SQL builder is exercised in integration tests. These tests
cover tokenisation, clause parsing, regex-trigger detection, whitespace-
around-colon, quoting, and error cases.
"""
from __future__ import annotations

import pytest

from vocab_search import (
    QueryError,
    _collapse_colon_whitespace,
    _looks_like_regex,
    _split_tokens,
    build_where,
    parse_query,
)


# ── regex trigger detection ────────────────────────────────────────────────

@pytest.mark.parametrize("s, expected", [
    ("sea",        False),  # plain
    ("saudade?",   False),  # trailing ? alone doesn't trigger
    ("see (it)",   False),  # () alone doesn't trigger
    ("foo*bar",    False),  # * alone doesn't trigger
    ("price $5",   False),  # $ not at end
    ("e.g.",       False),  # . alone doesn't trigger
    ("l'amour",    False),
    ("well-being", False),
    ("^a",         True),   # prefix anchor
    ("ção$",       True),   # suffix anchor
    (r"foo\$",     False),  # escaped $ at end
    (r"foo\\$",    True),   # even backslashes → $ is unescaped
    ("[aeiou]",    True),   # bracket class
    ("[a-c]+ão.*", True),   # mixed: bracket present → regex mode
    ("^[aeiou].*r$", True), # all three triggers
])
def test_looks_like_regex(s, expected):
    assert _looks_like_regex(s) is expected


# ── tokenisation & quote handling ──────────────────────────────────────────

def test_split_tokens_plain():
    assert _split_tokens("one two three") == ["one", "two", "three"]


def test_split_tokens_quoted_preserves_space():
    assert _split_tokens('a "b c" d') == ["a", "b c", "d"]


def test_split_tokens_quoted_with_operator_char():
    assert _split_tokens('source:"Pessoa: Auto"') == ['source:Pessoa: Auto']


def test_split_tokens_unterminated_raises():
    with pytest.raises(QueryError, match="Unterminated"):
        _split_tokens('"still open')


def test_collapse_colon_whitespace_forms():
    # All four user-listed forms collapse to the same.
    for variant in ["has:context", "has : context", "has: context", "has :context"]:
        assert _collapse_colon_whitespace(variant) == "has:context"


def test_collapse_ignores_zero_space_colons():
    # URLs and timestamps — no whitespace around `:` — stay intact.
    assert _collapse_colon_whitespace("url:https://ex.com/a:b") == "url:https://ex.com/a:b"


def test_collapse_respects_quotes():
    # A colon between spaces inside a quoted string is NOT collapsed.
    q = 'source:"Pessoa : Autopsicografia"'
    assert _collapse_colon_whitespace(q) == q


# ── parse_query — happy paths ──────────────────────────────────────────────

def test_empty_query_yields_no_clauses():
    assert parse_query("") == []
    assert parse_query("   ") == []


def test_plain_text_clause():
    assert parse_query("sea") == [{"kind": "text", "value": "sea"}]


def test_prefix_and_suffix_anchors_are_word_regex():
    assert parse_query("^a") == [
        {"kind": "word", "value": "^a", "is_regex": True}
    ]
    assert parse_query("ção$") == [
        {"kind": "word", "value": "ção$", "is_regex": True}
    ]


def test_bracket_class_is_word_regex():
    assert parse_query("[a-c]+ão.*") == [
        {"kind": "word", "value": "[a-c]+ão.*", "is_regex": True}
    ]


def test_field_clause_plain_value():
    assert parse_query("source:Pessoa") == [{
        "kind": "field", "field": "source", "value": "Pessoa", "is_regex": False,
    }]


def test_field_clause_regex_value():
    assert parse_query("source:^Pess") == [{
        "kind": "field", "field": "source", "value": "^Pess", "is_regex": True,
    }]


def test_field_clause_only_first_colon_splits():
    # URL value contains further colons — they must stay in the value.
    assert parse_query("url:https://ex.com/a:b") == [{
        "kind": "field", "field": "url",
        "value": "https://ex.com/a:b", "is_regex": False,
    }]


def test_has_and_none():
    assert parse_query("has:url none:ipa") == [
        {"kind": "has", "field": "url"},
        {"kind": "none", "field": "ipa"},
    ]


def test_whitespace_around_colon_all_four_forms():
    for q in ["has:url", "has : url", "has: url", "has :url"]:
        assert parse_query(q) == [{"kind": "has", "field": "url"}]


def test_combination_any_order():
    # All three examples the user asked about.
    a = parse_query("^s o$")
    b = parse_query("has:url ^b")
    c = parse_query("source:^a")
    assert len(a) == 2 and all(cl["kind"] == "word" for cl in a)
    assert b == [
        {"kind": "has", "field": "url"},
        {"kind": "word", "value": "^b", "is_regex": True},
    ]
    assert c == [{
        "kind": "field", "field": "source", "value": "^a", "is_regex": True,
    }]


def test_quoted_value_preserves_spaces():
    assert parse_query('source:"Pessoa: Auto"') == [{
        "kind": "field", "field": "source",
        "value": "Pessoa: Auto", "is_regex": False,
    }]


# ── parse_query — error paths ──────────────────────────────────────────────

def test_unknown_field_raises():
    with pytest.raises(QueryError, match="Unknown field"):
        parse_query("bogus:x")


def test_has_unknown_field_raises():
    with pytest.raises(QueryError, match="unknown field"):
        parse_query("has:bogus")


def test_has_without_field_raises():
    with pytest.raises(QueryError, match="requires a field name"):
        parse_query("has:")


def test_field_without_value_raises():
    with pytest.raises(QueryError, match="requires a value"):
        parse_query("source:")


def test_unterminated_quote_raises():
    with pytest.raises(QueryError, match="Unterminated"):
        parse_query('source:"still open')


# ── SQL builder (structural only — no DB) ──────────────────────────────────

def test_build_where_empty():
    assert build_where([]) == ("", [])


def test_build_where_plain_text_uses_like_on_word_and_translation():
    clauses = parse_query("sea")
    sql, params = build_where(clauses)
    assert "word) LIKE" in sql and "translation" in sql
    assert params == ["%sea%", "%sea%"]


def test_build_where_word_regex_uses_regexp():
    clauses = parse_query("^a")
    sql, params = build_where(clauses)
    assert "word REGEXP" in sql
    assert params == ["^a"]


def test_build_where_field_substring_uses_like_on_correct_col():
    clauses = parse_query("source:Pessoa")
    sql, params = build_where(clauses)
    assert "source_name" in sql and "LIKE" in sql
    assert params == ["%pessoa%"]


def test_build_where_field_regex_uses_regexp_on_correct_col():
    clauses = parse_query("source:^Pess")
    sql, params = build_where(clauses)
    assert "source_name" in sql and "REGEXP" in sql
    assert params == ["^Pess"]


def test_build_where_context_fans_out_to_three_cols():
    clauses = parse_query("context:foo")
    sql, params = build_where(clauses)
    assert "context_before" in sql
    assert "context_line" in sql
    assert "context_after" in sql
    # OR'd together
    assert sql.count("OR") >= 2
    assert params == ["%foo%", "%foo%", "%foo%"]


def test_build_where_has_uses_nullif_not_null():
    clauses = parse_query("has:url")
    sql, _ = build_where(clauses)
    assert "NULLIF(url, '') IS NOT NULL" in sql


def test_build_where_none_uses_nullif_is_null():
    clauses = parse_query("none:ipa")
    sql, _ = build_where(clauses)
    assert "NULLIF(ipa, '') IS NULL" in sql


def test_build_where_and_joins_clauses():
    clauses = parse_query("^a has:url source:Pessoa")
    sql, params = build_where(clauses)
    # All three fragments present, AND-joined.
    assert sql.count(" AND ") == 2
    assert "word REGEXP" in sql
    assert "url" in sql
    assert "source_name" in sql
    # Regex params are not %-wrapped; substring params are.
    assert "^a" in params
    assert "%pessoa%" in params


# ── Design-level note (executable documentation) ───────────────────────────

def test_presence_plus_field_match_equivalence_notes():
    """
    The user observed:
      - `has:X X:foo`  ≡  `X:foo`        (any match implies non-empty)
      - `none:X X:foo` ≡  ∅              (can't both be empty and match)
    We still accept both forms — the parser doesn't collapse them, so the
    "obvious" query works, and the pathological one just costs an extra
    ANDed predicate. Left documented so a future reader doesn't 'optimise'
    the parser and break user expectations.
    """
    # These just need to parse cleanly — no structural assertion.
    parse_query("has:source source:Pessoa")
    parse_query("none:source source:Pessoa")
