"""Realised-phone panel applies to any source language != target (source = learner's L1)."""

import pytest

pytest.importorskip("streamlit")

from ui.realised_phone_panel import pair_for  # noqa: E402


@pytest.mark.parametrize("source,code", [("English", "en"), ("French", "fr"), ("German", "de"),
                                         ("Italian", "it"), ("Dutch", "nl"), ("Portuguese", "pt")])
def test_every_other_source_language_gets_the_panel(source, code):
    assert pair_for({"voice": "es"}, source) == (code, "es")


def test_same_language_or_unsupported_target_gets_none():
    assert pair_for({"voice": "es"}, "Spanish") is None
    assert pair_for({"voice": "fr"}, "English") == ("en", "fr")
    assert pair_for({"voice": "nl-be"}, "English") == ("en", "nl-be")   # Flemish: distinct model
    assert pair_for({"voice": "nl"}, "English") == ("en", "nl")
    assert pair_for({"voice": "nl-be"}, "Dutch") is None                  # same language
    assert pair_for({"voice": "it"}, "English") is None                   # no aligner for it yet
    assert pair_for({"voice": "es"}, "Klingon") is None
