"""Detailed phoneme analysis uses the scorer's alignment, grouped into words."""

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

RESULT = {
    "target": "Ich möchte einen Termin vereinbaren",
    "recognized": "ich möchte einen termin vereinbaren.",
    "correct_ipa": "ɪç mˈœçtə ˌaɪnən tɛɾmˈiːn fɛɾˈaɪnbɑːrən",
    "user_ipa": "ɪ ç m ə ç t ə aɪ n ə n t ɛ r m iː n f ɛ r aɪ n b a r ə n",
    "accuracy_ipa": "ɪ ç m ə ç t ə aɪ n ə n t ɛ r m iː n f ɛ r aɪ n b a r ə n",
    "correct_phonemes": "", "user_phonemes": "", "exact_match": False,
    "similarity": 0.97, "accuracy_similarity": 0.97, "edit_distance": 0.031,
    "comprehensibility_similarity": 1.0,
}


def _script(result):
    import sys
    sys.path.insert(0, "src")
    import streamlit as st
    st.session_state.settings = {"voice": "de", "comparison_algorithm": "weighted_phone",
                                 "sound_check": False}
    from ui.practice_tab import render_practice_results
    render_practice_results(result, key_prefix="t")


def test_detail_section_counts_accepted_variants_and_groups_words():
    at = AppTest.from_function(_script, args=(RESULT,)).run(timeout=60)
    assert not at.exception, at.exception
    box = [c for c in at.checkbox if "detailed phoneme analysis" in c.label][0]
    at = box.check().run(timeout=60)
    assert not at.exception, at.exception
    text = " ".join(m.value for m in at.markdown)
    assert "2 accepted" in text or "3 accepted" in text            # œ→ə (not judged), ɾ→r ×2
    assert "1 substitutions" in text                                # ɑː→a (partly accepted)
    assert "aɪnən" in text and "a ɪ" not in text                   # words kept together
    assert any("Weighted distance" in m.value for m in at.markdown)
