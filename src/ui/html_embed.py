"""Invisible HTML/JS embeds (sound effects, raw-mic shim).

st.components.v1.html is deprecated in favour of st.iframe (same-origin, scripts
allowed). Use st.iframe when this Streamlit has it, else fall back.
"""

from __future__ import annotations

import streamlit as st


def embed_hidden(html: str) -> None:
    if hasattr(st, "iframe"):
        st.iframe(html, height=1)          # st.iframe requires height >= 1
    else:
        import streamlit.components.v1 as components
        components.html(html, height=0)
