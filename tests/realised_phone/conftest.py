"""Shared helpers for realised-phone tests (src/ is on sys.path via tests/conftest.py)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

pytest.importorskip("parselmouth")
pytest.importorskip("yaml")

from realised_phone.model import AlignedInterval, Alignment  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"


def perro_alignment(seg, total, target="r", word="perro"):
    """Fake aligner output matching synth.vrv(): [e] target [o] inside one word."""
    return Alignment(
        words=[AlignedInterval(0.0, total, word)],
        phones=[AlignedInterval(0.0, seg[0], "e", 0),
                AlignedInterval(seg[0], seg[1], target, 0),
                AlignedInterval(seg[1], total, "o", 0)],
        source_id="fake-aligner", version="0", status="candidate")
