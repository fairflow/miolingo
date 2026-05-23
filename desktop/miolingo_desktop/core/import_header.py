"""Shared parsing for the ``(source, target)`` language-pair header.

Ported verbatim from ``src/import_header.py`` (pure, no UI coupling). Used when
filtering bundled language-material files so the header line does not leak into
previews or counts.

Accepted forms::

    (pt, en)
    # (pt, en)
    (  FR  ,  EN  )
"""

from __future__ import annotations

import re

HEADER_RE = re.compile(
    r"^\s*#?\s*\(\s*([a-z]{2,5})\s*,\s*([a-z]{2,5})\s*\)\s*$",
    re.IGNORECASE,
)


def is_header_line(raw: str) -> bool:
    """Return True if *raw* is a ``(source, target)`` header tuple."""
    return bool(HEADER_RE.match(raw))


def parse_header(raw: str) -> tuple[str, str] | None:
    """Return ``(source_code, target_code)`` lowercased, or ``None``. Never raises."""
    m = HEADER_RE.match(raw)
    return (m.group(1).lower(), m.group(2).lower()) if m else None
