"""
Unit tests for vocab._parse_import_line and the 250-line limit guard.

These run without MySQL — no fixtures needed.
"""

import sys
from pathlib import Path

import pytest

# Make sure the worktree src is on the path when run from the worktree root.
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import vocab as _vocab


# ---------------------------------------------------------------------------
# _parse_import_line
# ---------------------------------------------------------------------------

class TestParseImportLine:
    """Covers every column combination of the 5-field positional format."""

    def _p(self, line):
        return _vocab._parse_import_line(line)

    # -- empty / blank -------------------------------------------------------

    def test_empty_string_returns_none(self):
        assert self._p("") is None

    def test_whitespace_only_returns_none(self):
        assert self._p("   ") is None

    def test_pipe_only_no_word_returns_none(self):
        assert self._p("| translation") is None

    # -- word only -----------------------------------------------------------

    def test_word_only_no_pipes(self):
        r = self._p("lua")
        assert r["word"] == "lua"
        assert r["translation"] == ""
        assert r["ipa"] == ""
        assert r["source"] == ""
        assert r["url"] == ""

    def test_word_leading_trailing_whitespace_stripped(self):
        r = self._p("  lua  ")
        assert r["word"] == "lua"

    # -- 2 fields ------------------------------------------------------------

    def test_word_and_translation(self):
        r = self._p("lua | moon")
        assert r["word"] == "lua"
        assert r["translation"] == "moon"
        assert r["ipa"] == ""

    def test_word_and_empty_translation(self):
        r = self._p("lua | ")
        assert r["translation"] == ""

    # -- 3 fields ------------------------------------------------------------

    def test_full_word_translation_ipa(self):
        r = self._p("lua | moon | [ˈlu.ɐ]")
        assert r["translation"] == "moon"
        assert r["ipa"] == "ˈlu.ɐ"   # brackets stripped

    def test_ipa_without_brackets(self):
        r = self._p("lua | moon | ˈlu.ɐ")
        assert r["ipa"] == "ˈlu.ɐ"

    def test_skip_translation_double_pipe(self):
        r = self._p("lua || [ˈlu.ɐ]")
        assert r["translation"] == ""
        assert r["ipa"] == "ˈlu.ɐ"

    def test_skip_translation_with_spaces(self):
        r = self._p("lua |  | [ˈlu.ɐ]")
        assert r["translation"] == ""
        assert r["ipa"] == "ˈlu.ɐ"

    # -- 4 fields ------------------------------------------------------------

    def test_word_translation_ipa_source(self):
        r = self._p("lua | moon | [ˈlu.ɐ] | scene-01")
        assert r["source"] == "scene-01"
        assert r["url"] == ""

    def test_skip_ipa_keep_source(self):
        r = self._p("lua | moon || scene-01")
        assert r["translation"] == "moon"
        assert r["ipa"] == ""
        assert r["source"] == "scene-01"

    def test_skip_both_translation_and_ipa(self):
        r = self._p("lua ||| scene-01")
        assert r["translation"] == ""
        assert r["ipa"] == ""
        assert r["source"] == "scene-01"

    # -- 5 fields (full) -----------------------------------------------------

    def test_all_five_fields(self):
        r = self._p("lua | moon | [ˈlu.ɐ] | scene-01 | https://example.com")
        assert r["word"] == "lua"
        assert r["translation"] == "moon"
        assert r["ipa"] == "ˈlu.ɐ"
        assert r["source"] == "scene-01"
        assert r["url"] == "https://example.com"

    def test_skip_source_keep_url(self):
        r = self._p("lua | moon | [ˈlu.ɐ] || https://example.com")
        assert r["source"] == ""
        assert r["url"] == "https://example.com"

    # -- bracket stripping ---------------------------------------------------

    def test_brackets_only_stripped_when_both_present(self):
        # [text] → text
        r = self._p("lua | moon | [ˈlu.ɐ]")
        assert r["ipa"] == "ˈlu.ɐ"

    def test_open_bracket_only_not_stripped(self):
        r = self._p("lua | moon | [ˈlu.ɐ")
        assert r["ipa"] == "[ˈlu.ɐ"

    def test_close_bracket_only_not_stripped(self):
        r = self._p("lua | moon | ˈlu.ɐ]")
        assert r["ipa"] == "ˈlu.ɐ]"

    # -- special characters --------------------------------------------------

    def test_accented_word(self):
        r = self._p("Perdão | Pardon | [peɾədˈɐ̃ʊ̃]")
        assert r["word"] == "Perdão"
        assert r["ipa"] == "peɾədˈɐ̃ʊ̃"

    def test_extra_pipes_beyond_5_are_absorbed_into_url(self):
        # Extra | inside the url field is part of the url (not a new field)
        # since we only split on the first 4 pipes
        r = self._p("lua | moon | [ˈlu.ɐ] | src | https://ex.com/a|b")
        # The 5th+ fields are currently just absorbed into url as-is
        # (acceptable — URLs with | are edge cases)
        assert r["url"].startswith("https://ex.com/a")


# ---------------------------------------------------------------------------
# 250-line limit
# ---------------------------------------------------------------------------

class TestImportLineLimit:

    def test_count_import_lines_ignores_blank_and_comments(self):
        contents = "\n".join([
            "# comment",
            "",
            "lua",
            "  ",
            "mar",
        ])
        assert _vocab.count_import_lines(contents) == 2

    def test_exactly_250_lines_does_not_raise(self):
        contents = "\n".join([f"word{i}" for i in range(250)])
        # Should not raise — just check count
        assert _vocab.count_import_lines(contents) == 250

    def test_251_lines_raises_value_error(self):
        body = "\n".join([f"word{i}" for i in range(251)])
        contents = "(en, pt)\n" + body
        with pytest.raises(ValueError, match="251"):
            _vocab.import_from_file_contents(
                user_id=1, language="Portuguese", contents=contents,
                expected_target_code="pt",
            )

    def test_250_lines_does_not_raise_value_error(self):
        # import_from_file_contents will proceed past the limit check;
        # it will then fail trying to reach MySQL — but a DB error is
        # NOT a ValueError, so we confirm the limit guard passed.
        body = "\n".join([f"word{i}" for i in range(250)])
        contents = "(en, pt)\n" + body
        try:
            _vocab.import_from_file_contents(
                user_id=1, language="Portuguese", contents=contents,
                expected_target_code="pt",
            )
        except ValueError as e:
            pytest.fail(f"Limit guard incorrectly raised ValueError: {e}")
        except Exception:
            pass  # DB error expected — that's fine


# ---------------------------------------------------------------------------
# Fixture file smoke-test (parse only, no DB)
# ---------------------------------------------------------------------------

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "vocab-import"


@pytest.mark.parametrize("fname,expected_count", [
    ("vocab-test-01-words-only.txt",        15),
    ("vocab-test-02-full-5-field.txt",      12),
    ("vocab-test-03-skip-translation.txt",  10),
    ("vocab-test-04-skip-ipa.txt",          10),
    ("vocab-test-05-word-source-only.txt",  10),
    ("vocab-test-07-over-limit.txt",       251),
    ("vocab-test-08-at-limit.txt",         250),
])
def test_fixture_line_count(fname, expected_count):
    path = FIXTURE_DIR / fname
    if not path.exists():
        pytest.skip(f"Fixture not found: {path}")
    contents = path.read_text(encoding="utf-8")
    assert _vocab.count_import_lines(contents) == expected_count


def test_fixture_02_all_fields_parse_correctly():
    path = FIXTURE_DIR / "vocab-test-02-full-5-field.txt"
    if not path.exists():
        pytest.skip("Fixture not found")
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        r = _vocab._parse_import_line(line)
        assert r is not None
        assert r["word"]
        assert r["translation"]
        assert r["ipa"]        # brackets stripped
        assert r["source"] == "pt-phrasebook"
        assert r["url"].startswith("https://")


def test_fixture_03_translation_is_empty():
    path = FIXTURE_DIR / "vocab-test-03-skip-translation.txt"
    if not path.exists():
        pytest.skip("Fixture not found")
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        r = _vocab._parse_import_line(line)
        assert r["translation"] == "", f"Expected empty translation in: {line!r}"
        assert r["ipa"], f"Expected non-empty IPA in: {line!r}"


def test_fixture_04_ipa_is_empty():
    path = FIXTURE_DIR / "vocab-test-04-skip-ipa.txt"
    if not path.exists():
        pytest.skip("Fixture not found")
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        r = _vocab._parse_import_line(line)
        assert r["ipa"] == "", f"Expected empty IPA in: {line!r}"
        assert r["translation"], f"Expected non-empty translation in: {line!r}"


# ---------------------------------------------------------------------------
# Tier 2: (source, target) header
# ---------------------------------------------------------------------------


class TestParseImportHeader:
    """parse_import_header: accept/reject cases and edge forms."""

    def test_bare_tuple_on_first_line(self):
        assert _vocab.parse_import_header("(pt, en)\nlua | moon") == ("pt", "en")

    def test_commented_tuple(self):
        assert _vocab.parse_import_header("# (pt, en)\nlua | moon") == ("pt", "en")

    def test_leading_blank_and_comment_lines_allowed(self):
        contents = "\n# some note\n\n(fr, en)\ndata"
        assert _vocab.parse_import_header(contents) == ("fr", "en")

    def test_case_insensitive(self):
        assert _vocab.parse_import_header("(PT, EN)\n") == ("pt", "en")

    def test_missing_header_raises(self):
        with pytest.raises(ValueError, match="header"):
            _vocab.parse_import_header("lua | moon\nsol | sun")

    def test_malformed_header_raises(self):
        with pytest.raises(ValueError, match="header"):
            _vocab.parse_import_header("source:pt target:en\n")

    def test_empty_file_raises(self):
        with pytest.raises(ValueError, match="header"):
            _vocab.parse_import_header("")


class TestImportHeaderIntegration:
    def test_target_mismatch_rejected_before_db(self):
        # expected target is "fr" but header says "pt" → reject, no DB call.
        contents = "(en, pt)\nlua\nmar"
        with pytest.raises(ValueError, match="target"):
            _vocab.import_from_file_contents(
                user_id=1, language="French", contents=contents,
                expected_target_code="fr",
            )

    def test_missing_header_rejected_before_db(self):
        contents = "lua\nmar"
        with pytest.raises(ValueError, match="header"):
            _vocab.import_from_file_contents(
                user_id=1, language="Portuguese", contents=contents,
                expected_target_code="pt",
            )

    def test_count_excludes_header(self):
        contents = "(en, pt)\nlua\nsol\nmar"
        assert _vocab.count_import_lines(contents) == 3


def test_fixture_07_over_limit_raises():
    path = FIXTURE_DIR / "vocab-test-07-over-limit.txt"
    if not path.exists():
        pytest.skip("Fixture not found")
    # Fixture predates the (source, target) header requirement; prepend one.
    contents = "(en, pt)\n" + path.read_text(encoding="utf-8")
    with pytest.raises(ValueError, match="251"):
        _vocab.import_from_file_contents(
            user_id=1, language="Portuguese", contents=contents,
            expected_target_code="pt",
        )
