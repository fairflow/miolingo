"""Guardrail test: the ported ``core/`` package must be UI-framework-free.

It walks every ``.py`` file under ``miolingo_desktop/core/`` and asserts no
module imports ``streamlit`` or ``PySide6``. This is a hard project rule
(``desktop/CLAUDE.md`` §1) — keeping core decoupled is what makes it headlessly
testable and reusable.
"""

from __future__ import annotations

import ast
from pathlib import Path

import miolingo_desktop.core as core_pkg

CORE_DIR = Path(core_pkg.__file__).resolve().parent
FORBIDDEN_ROOTS = {"streamlit", "PySide6", "PyQt5", "PyQt6"}


def _imported_roots(source: str) -> set[str]:
    roots: set[str] = set()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.level == 0:
                roots.add(node.module.split(".")[0])
    return roots


def test_core_has_no_ui_framework_imports() -> None:
    offenders: dict[str, set[str]] = {}
    for py_file in CORE_DIR.rglob("*.py"):
        roots = _imported_roots(py_file.read_text(encoding="utf-8"))
        bad = roots & FORBIDDEN_ROOTS
        if bad:
            offenders[py_file.name] = bad
    assert not offenders, f"UI-framework imports found in core/: {offenders}"
