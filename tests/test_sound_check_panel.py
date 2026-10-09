"""Sound check panel renders flagged sounds and degrades quietly."""

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

RESULT = {
    "target": "Ich möchte",
    "sound_check": {
        "language": "de", "model_id": "x", "note": "", "words": ["ɪç", "mˈœçtə"],
        "native_flag_rate": 0.06, "calibrated": True,
        "phones": [
            {"phone": "ɪ", "word_index": 0, "p_ok": 0.9, "level": "ok", "heard": None, "p_heard": 0},
            {"phone": "ç", "word_index": 0, "p_ok": 0.05, "level": "off", "heard": "k", "p_heard": 0.9},
            {"phone": "m", "word_index": 1, "p_ok": 0.99, "level": "ok", "heard": None, "p_heard": 0},
            {"phone": "œ", "word_index": 1, "p_ok": 0.3, "level": "check", "heard": "ɜ", "p_heard": 0.6},
        ],
    },
}


def _app(result):
    def script(result):
        import sys
        sys.path.insert(0, "src")
        from ui.sound_check_panel import render
        render(result)
    return AppTest.from_function(script, args=(result,)).run()


def test_flags_listed_with_heard_sound():
    at = _app(RESULT)
    text = " ".join(m.value for m in at.markdown)
    assert "[ç]** in *Ich*: probably off — sounded like **[k]**" in text
    assert "[œ]** in *möchte*: worth checking" in text
    assert "about 6%" in " ".join(c.value for c in at.caption)


def test_error_and_missing_are_quiet():
    assert not _app({"target": "x"}).markdown
    at = _app({"target": "x", "sound_check": {"error": "boom"}})
    assert "unavailable" in at.caption[0].value
