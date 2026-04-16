#!/usr/bin/env python3
"""Small Streamlit app to demonstrate process-global vs session-local state.

- `st.session_state.first_run` is per Streamlit session (per browser tab).
- `counter` is a module-level global that we *only* modify when a button is pressed,
  so we can see whether changes to it are shared across sessions.
- We also display `globals().keys()` so we can see what the module namespace
  looks like on each run.
"""

import time

import streamlit as st


# Per-session (per-tab) state
if "first_run" not in st.session_state:
    st.session_state.first_run = time.time()

st.markdown("### Module globals() keys")
# Show a sorted snapshot of globals to see what the module namespace contains
st.code("\n".join(sorted(globals().keys())))


# Process-global (module-global) state candidate
if "counter" not in globals():
    counter = 0


st.title("Streamlit Session vs Process-Global State Demo")

# Interaction to modify the global counter
if st.button("Increment GLOBAL counter"):
    counter += 1
    st.write("Button clicked – attempted to increment global counter.")

st.write("**Per-tab first_run (from st.session_state):**", st.session_state.first_run)
st.write("**Global counter (module-level):**", counter)

st.markdown("### Module globals() keys")
# Show a sorted snapshot of globals to see what the module namespace contains
st.code("\n".join(sorted(globals().keys())))

st.markdown(
    """
    **How to interpret this:**

    - `first_run` should be different per browser tab (session-local).
    - `counter` is a module-level variable:
      - If module globals persist across reruns and sessions in the same
        server process, then clicking the button in *one* tab should change
        `counter` for **all** tabs.
      - If module globals are effectively reset per session/rerun in this
        environment, then `counter` will behave as if it were local to each
        session and may stay at 0 (or not share changes).
    - The `globals()` dump shows exactly what names exist at module scope on
      each run, so we can see whether `counter` is really present/persisting.
    """
)
