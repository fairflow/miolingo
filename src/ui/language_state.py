"""
Single source of truth for language-pair session keys.

The sidebar is the sole owner of the following keys:

    - source_language     (e.g. "English")  — user's native language
    - material_language   (e.g. "pt")       — target language code
    - target_language     (e.g. "pt")       — mirror of material_language
    - language            (e.g. "Portuguese") — training map full name

Every other surface reads; nothing else writes. This module provides:

1. Typed read helpers (optional to adopt — existing `st.session_state.get`
   reads keep working).
2. A diagnostic tripwire `assert_sidebar_owner(key)` to be called
   immediately before a legitimate write. Callers that are NOT on the
   legitimate-writer list surface a warning in the debug banner and the
   server log. Non-blocking — the tripwire exists to localise the
   culprit when an unintended write happens.

The legitimate writers are: the sidebar itself (initial render + user
interaction), `app.py` (startup seed from DB-saved prefs), and
`auth.py` (login-time seed). Anything else is a bug.
"""
from __future__ import annotations

import inspect
import logging

import streamlit as st

log = logging.getLogger(__name__)

# Canonical set of session_state keys owned by the sidebar.
SIDEBAR_OWNED_KEYS: frozenset[str] = frozenset({
    "source_language",
    "material_language",
    "target_language",
    "language",
})

# Modules allowed to write these keys. Names compared against the caller's
# `__name__`, normalised by stripping a leading "src." if present.
#
# "__main__" covers `streamlit run src/app.py` — Streamlit assigns
# ``__name__ = "__main__"`` to the entry script, so writes that live
# directly in app.py appear under that module rather than "app".
_LEGITIMATE_WRITERS: frozenset[str] = frozenset({
    "ui.sidebar", "sidebar",
    "app", "__main__",
    "auth",
})

# Session-state key where tripwire messages accumulate between render and
# debug-banner display. Rendered + cleared by `drain_tripwire_messages`.
_TRIPWIRE_BUFFER_KEY = "_debug_lang_tripwire"


# ── Read API ──────────────────────────────────────────────────────────────

def read_source_lang(default: str = "English") -> str:
    """Return the user's source (native) language name."""
    return st.session_state.get("source_language", default)


def read_target_code(default: str = "fr") -> str:
    """Return the current target language code (e.g. 'pt', 'fr')."""
    return st.session_state.get("material_language", default)


def read_training_lang(default: str = "French") -> str:
    """Return the training-map full name for the current target."""
    return st.session_state.get("language", default)


# ── Debug-mode write tripwire ─────────────────────────────────────────────

def _is_debug_mode() -> bool:
    """Local copy of the debug-mode check to avoid a top-level import of
    ui.sidebar (which would create a cycle)."""
    try:
        return bool(
            st.session_state.get("settings", {}).get("debug_mode", False)
        )
    except Exception:
        return False


def assert_sidebar_owner(key: str) -> None:
    """Flag a warning if a non-sidebar caller is about to write *key*.

    Call this immediately before any assignment to one of
    :data:`SIDEBAR_OWNED_KEYS`. Legitimate writers (sidebar, app, auth)
    pass through silently; anything else surfaces a tripwire message in
    the debug banner and the server log. Non-blocking — the function
    never raises.

    Resolves to a no-op in production (debug mode off) so overhead is a
    single dict lookup per call.
    """
    if key not in SIDEBAR_OWNED_KEYS:
        return
    if not _is_debug_mode():
        return

    # Walk up to the first frame outside this module.
    caller_mod = "<unknown>"
    frame = inspect.currentframe()
    try:
        f = frame.f_back if frame else None
        if f is not None:
            caller_mod = f.f_globals.get("__name__", "<unknown>")
    finally:
        del frame

    short = caller_mod
    if short.startswith("src."):
        short = short[len("src."):]
    if short in _LEGITIMATE_WRITERS:
        return

    # Wrap both strings in backticks so st.warning()'s markdown renderer
    # does not mangle underscores — without this, "__main__" shows up in
    # the banner as "main" (double underscore = bold), which is actively
    # misleading when diagnosing a tripwire.
    msg = (
        f"Unexpected write to session key `{key}` from module "
        f"`{caller_mod}`. The sidebar is the sole owner of language "
        "keys; see the sidebar-ownership plan for details."
    )
    log.warning("[language_state] %s", msg)
    st.session_state.setdefault(_TRIPWIRE_BUFFER_KEY, []).append(msg)


def drain_tripwire_messages() -> list[str]:
    """Return and clear any tripwire messages accumulated this run.

    Called by the sidebar's debug banner code once per render. Returns an
    empty list if none have accumulated.
    """
    msgs = st.session_state.pop(_TRIPWIRE_BUFFER_KEY, [])
    return list(msgs) if msgs else []
