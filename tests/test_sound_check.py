"""Sound check: per-sound feedback from recognizer log-probs (src/scoring/sound_check.py)."""

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from scoring import sound_check as sc  # noqa: E402

VOCAB = {"<pad>": 0, "a": 1, "ɾ": 2, "ɹ": 3, "t": 4, "ʁ": 5, "ʔ": 6, "aɪ": 7, "n": 8}


def _lp(tokens, frames_per=4):
    """Log-probs where each listed token is clearly emitted, separated by blanks."""
    rows = []
    for t in tokens:
        for k in range(frames_per):
            p = np.full(len(VOCAB), 0.002)
            p[VOCAB[t] if k < 2 else 0] = 0.98
            rows.append(p / p.sum())
    return torch.from_numpy(np.log(np.array(rows, dtype=np.float32)))


@pytest.fixture
def cfg(monkeypatch):
    c = {"inventory": ["a", "ɾ", "ɹ", "t", "ʁ", "n", "aɪ"], "min_peak": 0.02,
         "ok_threshold": 0.5, "off_threshold": 0.15,
         "accept": {"ɾ": {"ʁ": 1}, "ʔ": {"∅": 1}}, "glottal_onsets": True}
    monkeypatch.setattr(sc, "lang_config", lambda v: c)
    return c


def test_tokenize_greedy_longest_and_strips_stress():
    toks = sc.tokenize("ˈaɪn ɾˈat", VOCAB)
    assert toks == [("aɪ", 0), ("n", 0), ("ɾ", 1), ("a", 1), ("t", 1)]


def test_correct_phrase_is_all_ok(cfg):
    r = sc.score(_lp(["ɾ", "a", "t"]), VOCAB, 0, "ɾat", "de")
    assert [p.level for p in r.phones] == ["ok", "ok", "ok"] and not r.flagged


def test_english_r_is_flagged_with_what_was_heard(cfg):
    r = sc.score(_lp(["ɹ", "a", "t"]), VOCAB, 0, "ɾat", "de")
    first = r.phones[0]
    assert first.level == "off" and first.heard == "ɹ"
    assert all(p.level == "ok" for p in r.phones[1:])
    assert "sounded like [ɹ]" in sc.describe(r, ["Rat"])[0]


def test_accepted_variant_is_not_flagged(cfg):
    r = sc.score(_lp(["ʁ", "a", "t"]), VOCAB, 0, "ɾat", "de")       # uvular r for espeak ɾ
    assert r.phones[0].level == "ok"


def test_glottal_onset_is_optional_and_hidden(cfg):
    with_q = sc.score(_lp(["ʔ", "aɪ", "n"]), VOCAB, 0, "aɪn", "de")
    without = sc.score(_lp(["aɪ", "n"]), VOCAB, 0, "aɪn", "de")
    for r in (with_q, without):
        assert [p.phone for p in r.phones] == ["aɪ", "n"]          # ʔ never shown
        assert all(p.level == "ok" for p in r.phones)


def test_deleted_sound_is_reported_as_left_out(cfg):
    r = sc.score(_lp(["ɾ", "a"]), VOCAB, 0, "ɾat", "de")
    assert r.phones[2].level != "ok" and r.phones[2].heard == sc.DEL


def test_too_short_audio_is_not_checked(cfg):
    r = sc.score(_lp(["a"], frames_per=1), VOCAB, 0, "ɾat", "de")
    assert r.phones == [] and r.note


def test_shipped_config_merges_hand_and_learned():
    c = sc.lang_config("de")
    assert c["accept"]["ɾ"]["ʁ"] == 1 and c["glottal_onsets"] is False
    assert ["ɾ", "ɹ"] in c["english_l1_errors"]
    assert sc.lang_config("de-de")["accept"]["ɾ"]["ʁ"] == 1        # dialect falls back to base
