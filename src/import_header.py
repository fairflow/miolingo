"""
Shared parsing for the ``(source, target)`` language-pair header.

Used by:
  - vocab imports (``src/vocab.py``) — header is mandatory on uploads
  - bundled language-material file metadata
    (``src/app_language_materials.py``) — header must be filtered out
    of content so it does not leak into preview / counts.

Accepted forms::

    (pt, en)
    # (pt, en)
    (  FR  ,  EN  )

The codes are 2–5 lowercase letters; the comparison is case-insensitive.
"""
from __future__ import annotations

import re
from typing import Optional, Tuple

HEADER_RE = re.compile(
    r"^\s*#?\s*\(\s*([a-z]{2,5})\s*,\s*([a-z]{2,5})\s*\)\s*$",
    re.IGNORECASE,
)


def is_header_line(raw: str) -> bool:
    """Return True if *raw* is a ``(source, target)`` header tuple."""
    return bool(HEADER_RE.match(raw))


def parse_header(raw: str) -> Optional[Tuple[str, str]]:
    """Return ``(source_code, target_code)`` lowercased, or ``None``.

    Never raises — the caller decides what to do when the header is
    absent. For the strict (raising) vocab-import variant see
    :func:`vocab.parse_import_header`.
    """
    m = HEADER_RE.match(raw)
    return (m.group(1).lower(), m.group(2).lower()) if m else None
