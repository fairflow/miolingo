"""Regression test for the (source, target) header filter in
get_file_metadata.

Before the fix, the header line leaked into `content_lines`:
  - line_count was inflated by 1
  - `sample = content_lines[0]` was the header tuple, so
    `'|' in sample` and `'[' in sample and ']' in sample` were both
    False → has_translations and has_ipa were incorrectly reported as
    False for any file authored with the new header convention.

This test exercises a real bundled file (en/phrases/phrases-001.txt)
which carries a `(fr, en)` header and verifies both the count and the
format detection come out right.
"""
from __future__ import annotations

from app_language_materials import get_file_metadata


def test_metadata_filters_header_line():
    meta = get_file_metadata(
        language="en",
        category="phrases",
        filename="phrases-001.txt",
        source_language="fr",
    )
    assert meta, "expected metadata dict"
    # The file has 51 non-blank / non-comment lines, one of which is the
    # `(fr, en)` header. Post-fix we count only the 50 data rows.
    assert meta["line_count"] == 50, (
        f"expected 50 data rows after stripping the header, got "
        f"{meta['line_count']}"
    )
    # The header does NOT contain '|' or '[', so if it leaked through
    # as the first content line these flags would both be False.
    assert meta["has_translations"] is True
    assert meta["has_ipa"] is True
    # Preview must not begin with the header tuple.
    preview = meta.get("preview") or []
    assert preview, "expected a non-empty preview"
    assert "(fr, en)" not in preview[0]
