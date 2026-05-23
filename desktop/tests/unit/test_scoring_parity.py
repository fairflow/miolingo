"""Scoring parity regression.

Two layers of protection that the ported scoring matches the source app:

1. Hardcoded fixtures (``tests/fixtures/scoring_parity.json``) with certain,
   hand-verifiable expected outputs.
2. A cross-check of the ported edit-distance against an INDEPENDENT reference
   Levenshtein implementation over a broad set (including multi-edit and
   unicode phoneme strings). This proves the algorithm is correct without
   trusting hand-computed edit distances for tricky cases.

SPEC acceptance: "the score produced by the ported scoring code matches the
source app's output for a fixed (audio, reference) fixture set." Audio->phoneme
extraction needs espeak + a real recording (a manual test); the pure scoring
layer — where parity is deterministically provable headlessly — is locked here.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from miolingo_desktop.core.comparison import compare_phonemes_edit_distance

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "scoring_parity.json"


def _ref_levenshtein(a: str, b: str) -> int:
    """Independent reference implementation (different code path than the port)."""
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        curr = [i]
        for j, cb in enumerate(b, 1):
            curr.append(
                min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + (0 if ca == cb else 1))
            )
        prev = curr
    return prev[-1]


def _load_cases() -> list[dict]:
    with open(FIXTURE, encoding="utf-8") as f:
        return json.load(f)["cases"]


@pytest.mark.parametrize("case", _load_cases())
def test_fixture_parity(case: dict) -> None:
    exact, similarity, distance = compare_phonemes_edit_distance(
        case["user"], case["correct"]
    )
    assert exact is case["exact"]
    assert distance == case["distance"]
    assert similarity == pytest.approx(case["similarity"])


@pytest.mark.parametrize(
    ("user", "correct"),
    [
        ("bõʒuʁ", "bõʒuʁ"),
        ("bõʒu", "bõʒuʁ"),
        ("saudʒi", "saʊde"),
        ("ɐ̃tɐ̃u", "ɐ̃tɐ̃w"),
        ("obrigadu", "obrigado"),
        ("", ""),
        ("abc", ""),
    ],
)
def test_ported_matches_independent_reference(user: str, correct: str) -> None:
    exact, similarity, distance = compare_phonemes_edit_distance(user, correct)
    expected_distance = _ref_levenshtein(user, correct)
    assert distance == expected_distance
    assert exact is (user == correct)
    if len(correct) == 0:
        assert similarity == 0.0
    else:
        max_len = max(len(user), len(correct))
        assert similarity == pytest.approx(1.0 - expected_distance / max_len)
