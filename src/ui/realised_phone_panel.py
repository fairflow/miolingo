"""
Debug-only "Realised phones (experimental)" panel under Practice results
(HANDOFF §2 see/hear + §3 coaching, beads miolingo-6vo.3).

Shown only when debug mode is on AND the target language is one the pipeline
supports (es) AND the source language has a pair inventory (en). Runs with
allow_candidates=True, i.e. on models NOT yet approved -- so it is labelled as
such and never shown to learners. Reuses Whisper's transcript from the result
(gate only) instead of transcribing again.
"""

from __future__ import annotations

import os
import tempfile

import streamlit as st

_L1_CODES = {"English": "en"}


def _l2_code(settings: dict) -> str:
    return (settings.get("voice") or "").lower().split("-")[0]


def render(result: dict, key_prefix: str = "practice") -> None:
    settings = st.session_state.get("settings", {})
    if not settings.get("debug_mode", False) or not result:
        return
    l2 = _l2_code(settings)
    l1 = _L1_CODES.get(st.session_state.get("source_language", "English"))
    if l2 != "es" or l1 is None:
        return
    with st.expander("🔬 Realised phones (experimental, debug only)", expanded=False):
        st.caption("Models/detectors here are NOT approved (model_registry.yaml) — "
                   "output is for testing only and is never shown to learners.")
        if not st.button("Analyse this attempt", key=f"{key_prefix}_rp_run"):
            return
        audio = result.get("user_audio_trimmed_bytes") or result.get("user_audio_bytes")
        if not audio:
            st.info("No audio on this result.")
            return
        _analyse_and_show(audio, result, l1, l2, key_prefix)


def _analyse_and_show(audio: bytes, result: dict, l1: str, l2: str, key_prefix: str) -> None:
    import soundfile as sf
    from realised_phone import coaching
    from realised_phone.learner import LearnerModel
    from realised_phone.pipeline import analyse
    from realised_phone.view import native_exemplar, segment_view

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    tmp.write(audio)
    tmp.close()
    try:
        with st.spinner("Aligning (MFA) and measuring…"):
            a = analyse(tmp.name, result.get("target", ""), l1, l2,
                        transcript=result.get("recognized", ""), allow_candidates=True)
        x, sr = sf.read(tmp.name, dtype="float64")
    finally:
        os.unlink(tmp.name)
    if x.ndim > 1:
        x = x.mean(axis=1)

    g = a.gate
    st.write(f"**Gate:** {'passed' if g.passed else 'failed'} — word recall {g.word_recall:.0%}"
             + (f" ({g.reason})" if g.reason else ""))
    for n in a.notes:
        st.caption(f"• {n}")
    if not a.verdicts:
        st.info("No rhotic targets analysed in this attempt.")
        return

    lm_key = f"rp_learner_{l1}_{l2}"
    if lm_key not in st.session_state:
        st.session_state[lm_key] = LearnerModel(l1, l2)
    lm: LearnerModel = st.session_state[lm_key]

    st.table([{"word": v.word, "target": f"/{v.target}/", "context": v.context,
               "verdict": v.describe().split(": ", 1)[1], "confidence": v.confidence}
              for v in a.verdicts])

    for i, v in enumerate(a.verdicts):
        lm.update(v)
        if v.correct is True or (v.correct is None and v.status != "uncertain"):
            continue          # show see/hear for errors and for unresolved uncertainty
        wd = a.alignment.words[v.word_index]
        sv = segment_view(x, sr, v, (wd.start, wd.end))
        st.markdown(f"#### '{v.word}': target [{v.target}] vs "
                    + (f"realised [{sv['realised']}]" if sv["realised"]
                       else "uncertain between " + " / ".join(v.between)))
        c1, c2 = st.columns(2)
        with c1:
            st.caption("You — word / sound / slowed")
            st.audio(sv["audio"]["word"], format="audio/wav")
            st.audio(sv["audio"]["sound"], format="audio/wav")
            st.audio(sv["audio"]["sound_slow"], format="audio/wav")
        with c2:
            nat = native_exemplar(v.word, l2, v.target)
            st.caption("Native — word / sound / slowed")
            if nat:
                st.audio(nat["word"], format="audio/wav")
                if "sound" in nat:
                    st.audio(nat["sound"], format="audio/wav")
                    st.audio(nat["sound_slow"], format="audio/wav")
            else:
                st.info("No native exemplar in MIO_NATIVE_BANK for this word.")
        _charts(sv, key=f"{key_prefix}_rp_{i}")
        if v.realised_class:
            rung = max(1, lm.coaching_rung(v.target, v.realised_class))
            try:
                c = coaching.step(l1, l2, v.target, v.realised_class, rung,
                                  v.realised_phone, allow_draft=True)
            except coaching.DraftContent:
                c = None
            if c:
                st.markdown(f"**Coaching (rung {c['rung']}: {c['name']}, {c['status']})**")
                st.json({k: val for k, val in c.items() if k not in ("rung", "name", "status")})
    with st.expander("Raw analysis (JSON)"):
        st.json(a.to_dict())


def _charts(sv: dict, key: str) -> None:
    import altair as alt
    import pandas as pd

    s, e = sv["segment"]
    seg = pd.DataFrame({"start": [s], "end": [e]})
    band = alt.Chart(seg).mark_rect(opacity=0.12, color="orange").encode(x="start:Q", x2="end:Q")

    env = pd.DataFrame({"t": sv["envelope"]["t"], "dB": sv["envelope"]["db"]})
    env_c = alt.Chart(env).mark_line().encode(x=alt.X("t:Q", title="s"), y=alt.Y("dB:Q", title="voiced-band dB"))
    occ = pd.DataFrame({"t": sv["envelope"]["occlusions"]})
    occ_c = alt.Chart(occ).mark_rule(color="red").encode(x="t:Q")

    f3 = pd.DataFrame({"t": sv["f3"]["t"], "Hz": sv["f3"]["hz"]}).dropna()
    f3_c = alt.Chart(f3).mark_point(size=12).encode(x="t:Q", y=alt.Y("Hz:Q", title="F3 Hz"))
    layers = [band, f3_c]
    if sv["f3"]["lowered_below_hz"]:
        thr = pd.DataFrame({"y": [sv["f3"]["lowered_below_hz"]]})
        layers.append(alt.Chart(thr).mark_rule(strokeDash=[4, 4], color="gray").encode(y="y:Q"))

    sp = sv["spectrogram"]
    rows = [{"t": t + sv["offset"], "f": f, "dB": sp["db"][fi][ti]}
            for fi, f in enumerate(sp["f"]) for ti, t in enumerate(sp["t"])]
    spec_c = alt.Chart(pd.DataFrame(rows)).mark_rect().encode(
        x=alt.X("t:Q", bin=alt.Bin(maxbins=len(sp["t"])), title="s"),
        y=alt.Y("f:Q", bin=alt.Bin(maxbins=len(sp["f"])), title="Hz"),
        color=alt.Color("dB:Q", scale=alt.Scale(scheme="greys", reverse=True), legend=None))

    st.caption("Spectrogram (segment shaded in the plots below)")
    st.altair_chart(spec_c.properties(height=160), use_container_width=True)
    st.caption("Occlusions (red): trill = 2+ regular dips, tap = 1")
    st.altair_chart((band + env_c + occ_c).properties(height=140), use_container_width=True)
    st.caption("F3 — English r pulls it below the dashed line")
    st.altair_chart(alt.layer(*layers).properties(height=140), use_container_width=True)
    st.caption("Measurements: " + ", ".join(f"{k}={v}" for k, v in sv["measurements"].items()
                                            if k != "occlusions"))
