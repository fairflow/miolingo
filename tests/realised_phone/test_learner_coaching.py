"""Learner model (priors, weighted updates, escalation, honest improvement feedback)
and coaching gating (drafts never reach learners)."""

import pytest

from realised_phone import coaching
from realised_phone.learner import LearnerModel, prior_for
from realised_phone.model import Verdict


def verdict(realised_class, status="confident", context="intervocalic", target="r"):
    return Verdict(target=target, target_class="trill", word="perro", word_index=0,
                   phone_index=2, start=0.1, end=0.2, context=context, status=status,
                   realised_class=realised_class if status != "uncertain" else None,
                   between=["trill", "tap"] if status == "uncertain" else [])


def test_priors_from_research_file():
    a, b, entry = prior_for("en", "es", "r", "intervocalic")
    assert (a, b) == (1.0, 4.0) and entry["difficulty"] == "high"
    assert entry["citation_verified"] is False          # must be reviewed before use
    a, b, _ = prior_for("en", "es", "r", "coda")
    assert a > b                                         # neutralised context: easy
    assert prior_for("en", "es", "zz", "x")[:2] == (1.0, 1.0)


def test_weighted_updates_and_uncertain_ignored():
    m = LearnerModel("en", "es")
    p0 = m.state("r", "intervocalic").p_correct
    m.update(verdict("trill"))
    p1 = m.state("r", "intervocalic").p_correct
    assert p1 > p0
    m.update(verdict(None, status="uncertain"))
    assert m.state("r", "intervocalic").p_correct == p1
    st = m.state("r", "intervocalic")
    before = st.beta
    m.update(verdict("tap", status="tentative"))
    assert st.beta == pytest.approx(before + 0.25)


def test_escalation_and_deescalation():
    m = LearnerModel("en", "es", base_n=3)
    # prior for /r/ is hard (p<0.3) -> escalate after N-1 = 2 failures
    for _ in range(2):
        m.update(verdict("tap"))
    assert m.coaching_rung("r", "tap") == 1
    for _ in range(4):
        m.update(verdict("tap"))
    assert m.coaching_rung("r", "tap") == 3
    m.update(verdict("trill"))
    m.update(verdict("trill"))
    assert m.coaching_rung("r", "tap") == 2


def test_improvement_only_when_supported():
    m = LearnerModel("en", "es")
    for ok in [False] * 9 + [True] + [True] * 6 + [False] * 4:
        m.update(verdict("trill" if ok else "tap"), ts=0)
    msg = m.improvement("r", "intervocalic", class_name="trill")
    assert msg == "trill produced in 6 of your last 10 attempts, up from 1 of 10 before"
    m2 = LearnerModel("en", "es")
    for ok in [False] * 5 + [True] * 5 + [True] * 6 + [False] * 4:
        m2.update(verdict("trill" if ok else "tap"), ts=0)
    assert m2.improvement("r", "intervocalic") is None  # 5 -> 6 is not evidence
    m3 = LearnerModel("en", "es")
    for _ in range(12):
        m3.update(verdict("trill", status="tentative"), ts=0)
    assert m3.improvement("r", "intervocalic") is None  # only confident verdicts count


def test_roundtrip_and_priorities():
    m = LearnerModel("en", "es")
    m.update(verdict("tap"))
    m.update(verdict("trill", context="coda"))
    m2 = LearnerModel.from_dict(m.to_dict())
    assert m2.to_dict() == m.to_dict()
    assert m2.priorities()[0][0] == "r|intervocalic"


def test_draft_coaching_is_refused_without_flag():
    with pytest.raises(coaching.DraftContent):
        coaching.step("en", "es", "r", "tap", 1)
    c = coaching.step("en", "es", "r", "english_r", 1, realised_phone="ɹ", allow_draft=True)
    assert c["name"] == "contrast" and c["status"] == "draft" and c["auto"]
    d = coaching.step("en", "es", "r", "tap", 4, allow_draft=True)
    assert d["name"] == "drills" and d["steps"][0]["step"] == "tap in pero"
    assert coaching.step("en", "es", "r", "tap", 99, allow_draft=True)["name"] == "stabilisation"
    assert coaching.step("en", "es", "r", "uvular", 1, allow_draft=True) is None


def test_panphon_cannot_separate_trill_from_tap():
    assert coaching.feature_contrast("r", "ɾ") == []     # hence the authored manner note
    assert coaching.feature_contrast("r", "ɹ")


def test_uncertain_between_accepted_classes_counts_as_correct():
    v = verdict(None, status="uncertain", context="coda")
    v.accepted_classes = ["trill", "tap"]
    assert v.correct is True
    v2 = verdict(None, status="uncertain")          # intervocalic: only trill accepted
    v2.accepted_classes = ["trill"]
    assert v2.correct is None
    m = LearnerModel("en", "es")
    before = m.state("r", "coda").p_correct
    m.update(v)                                      # uncertain never moves the estimate
    assert m.state("r", "coda").p_correct == before
