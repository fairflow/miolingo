"""Tidy-up after the first German trials (2026-10-09): grouping of the recognizer's
phones into words, German r variants in the weighted score, quiet endings kept by the
silence trim, raw-microphone injection."""

import io

import numpy as np
import pytest
import soundfile as sf

from scoring.phone_distance import group_by_target_words, score


def test_user_phones_grouped_into_target_words():
    target = "ɪç mˈœçtə ˌaɪnən tɛɾmˈiːn fɛɾˈaɪnbɑːrən"
    user = "ɪ ç m œ ç t ə aɪ n ə n t ɛ r m iː n f ɛ r aɪ n b a r r ə n"
    assert group_by_target_words(user, target) == "ɪç mœçtə aɪnən tɛrmiːn fɛraɪnbarrən"


def test_grouping_with_missing_ending_and_empty_inputs():
    target = "ɪç mˈœçtə fɛɾˈaɪnbɑːrən"
    assert group_by_target_words("ɪ ç m œ ç t ə f ɛ r aɪ n", target) == "ɪç mœçtə fɛraɪn"
    assert group_by_target_words("", target) == ""
    assert group_by_target_words("a b", "") == "a b"


def test_german_trilled_r_is_not_a_substitution():
    r = score("tɛrmiːn", "tɛɾmiːn", "de")
    assert r.exact_match or r.distance == pytest.approx(0.0)
    english = score("tɛɹmiːn", "tɛɾmiːn", "de")
    assert english.distance > 0                      # English r still costs


def _wav(x, sr=16000):
    b = io.BytesIO(); sf.write(b, x, sr, format="WAV"); return b.getvalue()


def test_trim_keeps_a_quiet_ending_after_a_loud_start():
    from scoring.practice import trim_silence
    sr = 16000
    t = np.arange(int(0.6 * sr)) / sr
    loud = 0.9 * np.sin(2 * np.pi * 200 * t[: int(0.15 * sr)])        # loud first word
    mid = 0.25 * np.sin(2 * np.pi * 200 * t)                           # normal speech
    quiet = 0.04 * np.sin(2 * np.pi * 200 * t[: int(0.4 * sr)])        # fading "-baren"
    x = np.concatenate([np.zeros(sr // 4), loud, mid, mid, quiet, np.zeros(sr)])
    trimmed, _ = trim_silence(_wav(x), silence_threshold=0.01)
    y, _ = sf.read(io.BytesIO(trimmed))
    end_of_quiet = (sr // 4 + len(loud) + 2 * len(mid) + len(quiet)) / sr
    assert len(y) / sr >= end_of_quiet - 0.25 + 0.2    # quiet tail (plus padding) kept


def test_raw_mic_injection_follows_setting(monkeypatch):
    from ui import raw_mic
    seen = []
    monkeypatch.setattr(raw_mic, "embed_hidden", lambda html: seen.append(html))
    raw_mic.apply({"raw_microphone": True})
    raw_mic.apply({"raw_microphone": False})
    assert "__mioRawMic = true" in seen[0] and "__mioRawMic = false" in seen[1]
    assert "autoGainControl: false" in seen[0] and "noiseSuppression: false" in seen[0]


def test_recognized_display_drops_punctuation_and_follows_target_case():
    from scoring.comparison import display_recognized
    assert display_recognized("ich möchte einen termin vereinbaren.",
                              "Ich möchte einen Termin vereinbaren") == "Ich möchte einen Termin vereinbaren"
    assert display_recognized("wo ist der bahnhof", "Wo ist der Bahnhof?") == "Wo ist der Bahnhof"
    assert display_recognized("ich möchte einen termin vereinen.",
                              "Ich möchte einen Termin vereinbaren") == "Ich möchte einen Termin vereinen"
    assert display_recognized("c'est la vie!", "C’est la vie") == "C'est la vie"


def test_quiet_recording_is_levelled_but_silence_is_not_blown_up():
    from scoring.practice import trim_silence
    sr = 16000
    t = np.arange(sr) / sr
    quiet = 0.02 * np.sin(2 * np.pi * 200 * t)
    y, _ = sf.read(io.BytesIO(trim_silence(_wav(np.concatenate([np.zeros(sr // 2), quiet, np.zeros(sr // 2)])))[0]))
    assert 0.3 < np.max(np.abs(y)) <= 0.75                    # x20 cap -> 0.4
    loud = 0.8 * np.sin(2 * np.pi * 200 * t)
    y, _ = sf.read(io.BytesIO(trim_silence(_wav(loud))[0]))
    assert np.max(np.abs(y)) == pytest.approx(0.8, abs=0.01)  # already loud: untouched


def test_weighted_score_follows_sound_check_rules():
    # German ö is "not judged" (the recognizer writes ə even for natives): no cost
    r = score("məçtə", "mœçtə", "de")
    assert r.distance == pytest.approx(0.0)
    # partly accepted variant costs proportionally less than an unrelated vowel
    part = score("baːn", "bɑːn", "de").distance          # aː for ɑː: accepted 1 -> free
    short = score("ban", "bɑːn", "de").distance          # a for ɑː: accepted 0.6
    wrong = score("bin", "bɑːn", "de").distance
    assert part == pytest.approx(0.0) and 0 < short < wrong
