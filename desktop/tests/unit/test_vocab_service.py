"""Tests for the UI-free vocabulary services (CSV + IPA autofill)."""

from __future__ import annotations

import csv
import io

from miolingo_desktop.core import vocab_service


def test_rows_to_csv_header_and_rows() -> None:
    rows = [
        {"word": "chat", "translation": "cat", "ipa": "ʃa", "language_code": "fr"},
        {"word": "chien", "translation": "dog", "language_code": "fr"},
    ]
    text = vocab_service.rows_to_csv(rows)
    parsed = list(csv.DictReader(io.StringIO(text)))
    assert parsed[0]["word"] == "chat"
    assert parsed[0]["translation"] == "cat"
    assert parsed[1]["word"] == "chien"
    # Header includes the documented fields.
    assert text.splitlines()[0].split(",")[:3] == ["word", "display_word", "translation"]


def test_rows_to_csv_empty() -> None:
    text = vocab_service.rows_to_csv([])
    assert text.splitlines()[0].startswith("word,")


def test_autofill_ipa_handles_error(monkeypatch) -> None:
    monkeypatch.setattr(vocab_service, "get_ipa_from_espeak", lambda w, c: "[error]")
    assert vocab_service.autofill_ipa("chat", "fr") is None


def test_autofill_ipa_success(monkeypatch) -> None:
    monkeypatch.setattr(vocab_service, "get_ipa_from_espeak", lambda w, c: "ʃa")
    assert vocab_service.autofill_ipa("chat", "fr") == "ʃa"


def test_language_name_for_code() -> None:
    assert vocab_service.language_name_for_code("fr") == "French"
    assert vocab_service.language_name_for_code("zz") is None
