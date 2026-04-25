"""Static regression test for the sidebar-ownership invariant.

Stage 2 step 6 of the sidebar-ownership plan.

Invariant
---------
The four language-pair session-state keys are owned by the sidebar:

    source_language, material_language, target_language, language

The only modules that may write them are:

    src/ui/sidebar.py     (the canonical owner)
    src/app.py            (startup seed from saved DB prefs)
    src/auth.py           (login-time seed from user choice)

Any other module writing one of these keys is a sidebar-reset bug
waiting to happen — the symptom is "click X in main panel; sidebar
language reverts to default." This test scans every Python source
file under src/ and fails if any non-allowlisted module assigns to
one of the keys.

The runtime tripwire in src/ui/language_state.py catches dynamic
writes when debug mode is on; this test catches static writes in CI.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC = PROJECT_ROOT / "src"

OWNED_KEYS = ("source_language", "material_language", "target_language", "language")

# Modules permitted to write these keys.
ALLOWED_FILES = {
    SRC / "ui" / "sidebar.py",
    SRC / "ui" / "language_state.py",  # defines the keys + read API
    SRC / "app.py",
    SRC / "auth.py",
}

# Match assignments of the form:
#   st.session_state['language'] = ...
#   st.session_state["language"] = ...
#   st.session_state.language = ...
# but NOT comparisons (== / !=), reads (.get), or dict literals.
WRITE_PATTERNS = [
    re.compile(
        r"st\.session_state\[\s*['\"]" + re.escape(k) + r"['\"]\s*\]\s*="
        r"(?!=)"
    )
    for k in OWNED_KEYS
] + [
    re.compile(
        r"st\.session_state\." + re.escape(k) + r"\s*="
        r"(?!=)"
    )
    for k in OWNED_KEYS
]


def _iter_python_files(root: Path):
    for p in root.rglob("*.py"):
        if "__pycache__" in p.parts:
            continue
        yield p


def _strip_comments_and_strings(src: str) -> str:
    """Remove Python ``#`` line comments and triple-quoted strings so
    docstrings / commented-out code don't trigger false positives."""
    # Triple-quoted strings (either kind), non-greedy.
    src = re.sub(r'""".*?"""', "", src, flags=re.DOTALL)
    src = re.sub(r"'''.*?'''", "", src, flags=re.DOTALL)
    # Line comments — strip from `#` to end of line.
    src = re.sub(r"#[^\n]*", "", src)
    return src


def test_no_non_sidebar_writes_to_language_keys():
    offenders: list[str] = []
    for path in _iter_python_files(SRC):
        if path in ALLOWED_FILES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        cleaned = _strip_comments_and_strings(text)
        for lineno, line in enumerate(cleaned.splitlines(), start=1):
            for pat in WRITE_PATTERNS:
                if pat.search(line):
                    rel = path.relative_to(PROJECT_ROOT)
                    offenders.append(f"{rel}:{lineno}: {line.strip()}")

    assert not offenders, (
        "Non-sidebar writes to language-pair session keys detected.\n"
        "These keys are owned by the sidebar; main-panel code must\n"
        "read, never write. See the sidebar-ownership plan for the\n"
        "tripwire and the allowlist (sidebar, language_state, app, "
        "auth).\n\n"
        "Offending lines:\n  "
        + "\n  ".join(offenders)
    )


@pytest.mark.parametrize("path", sorted(ALLOWED_FILES))
def test_allowlist_files_actually_exist(path):
    """Sanity check — the allowlist must point at real files. If
    sidebar.py gets renamed and the allowlist is not updated, this
    test will fail loudly rather than silently letting all writes
    through."""
    assert path.exists(), f"Allowlisted file does not exist: {path}"
