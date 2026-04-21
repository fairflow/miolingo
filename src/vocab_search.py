"""
Vocab search mini-language parser (v7.8.0+).

A tiny query language for the personal vocabulary tracker. Plain text keeps
doing what it has always done; operators are opt-in sugar.

Grammar (informal)
------------------
    query       := clause ( WHITESPACE clause )*
    clause      := present | field_clause | regex_clause | text_clause
    present     := ("has" | "none") ":" field_name
    field_clause:= field_name ":" value
    regex_clause:= value-that-triggers-regex  (against `word`)
    text_clause := value                       (substring on word + translation)

Whitespace around `:` is collapsed so `has : url`, `has: url`, `has :url`
all parse identically. Only the FIRST colon in a token separates field
from value — the rest is part of the value (URLs keep working).
Values may be double-quoted to include whitespace or operator chars.

Regex trigger (conservative — ordinary punctuation never triggers):
  - clause starts with `^`           → regex
  - clause ends with unescaped `$`   → regex
  - clause contains a `[...]` pair   → regex
Anything else is plain substring.

Valid fields: word / translation / ipa / source / url / note / context.
For `has:` and `none:`, `word` is not allowed (always present). `context`
matches any of the three context columns OR'd.

All clauses AND together; clause order is irrelevant.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple


# Public column aliases used in the query language and in UI messages.
FIELDS = ("word", "translation", "ipa", "source", "url", "note", "context")
# Subset that allows `has:` / `none:` — `word` is always present.
PRESENCE_FIELDS = ("translation", "ipa", "source", "url", "note", "context")

# Map user-facing field names to DB columns. `context` is special
# (fans out to three columns); the SQL builder handles that.
_FIELD_TO_COL: Dict[str, str] = {
    "word": "word",
    "translation": "translation",
    "ipa": "ipa",
    "source": "source_name",
    "url": "url",
    "note": "notes",
    # "context" handled specially in SQL builder
}

# Regex-trigger characters — see module docstring.
_REGEX_META = set("^$[]*+?|()\\")


class QueryError(ValueError):
    """Raised when the query string is malformed (bad field, bad quoting, ...)."""


# ── tokenisation ────────────────────────────────────────────────────────────

def _collapse_colon_whitespace(q: str) -> str:
    """
    Replace `\\s+:\\s*` or `\\s*:\\s+` with `:` — but only outside quotes.
    Leaves zero-whitespace colons (URLs, timestamps) completely alone.
    """
    out: List[str] = []
    i, n = 0, len(q)
    in_quote = False
    buf: List[str] = []
    while i < n:
        ch = q[i]
        if ch == '"':
            in_quote = not in_quote
            buf.append(ch)
            i += 1
            continue
        if in_quote:
            buf.append(ch)
            i += 1
            continue
        # Try to match `\s+:\s*` or `\s*:\s+` starting at i.
        m = re.match(r"(\s+:\s*|\s*:\s+)", q[i:])
        if m:
            buf.append(":")
            i += m.end()
            continue
        buf.append(ch)
        i += 1
    if in_quote:
        raise QueryError("Unterminated quote in query")
    out.append("".join(buf))
    return "".join(out)


def _split_tokens(q: str) -> List[str]:
    """Whitespace-split, honouring double-quoted segments.

    Inside quotes, whitespace is preserved. A quote that closes a token
    strips the surrounding quotes. Unterminated quotes raise.
    """
    tokens: List[str] = []
    buf: List[str] = []
    in_quote = False
    had_quote = False  # token contained quoted content (preserves empty tokens)

    def flush():
        if buf or had_quote:
            tokens.append("".join(buf))
        buf.clear()

    i, n = 0, len(q)
    while i < n:
        ch = q[i]
        if ch == '"':
            in_quote = not in_quote
            had_quote = True
            i += 1
            continue
        if ch.isspace() and not in_quote:
            flush()
            had_quote = False
            i += 1
            continue
        buf.append(ch)
        i += 1
    if in_quote:
        raise QueryError("Unterminated quote in query")
    flush()
    return tokens


# ── regex-trigger detection ─────────────────────────────────────────────────

def _looks_like_regex(s: str) -> bool:
    """Conservative: `^` at start, unescaped `$` at end, or `[...]` present."""
    if not s:
        return False
    if s[0] == "^":
        return True
    # Unescaped `$` at end: preceding char (if any) is not a backslash,
    # or is an even number of backslashes.
    if s[-1] == "$":
        # Count trailing backslashes before the final `$`.
        j = len(s) - 2
        backs = 0
        while j >= 0 and s[j] == "\\":
            backs += 1
            j -= 1
        if backs % 2 == 0:
            return True
    # `[...]` pair present (non-empty, in order). Use simple regex — a
    # hand-written scan would flag `[` alone, which isn't what we want.
    if re.search(r"\[[^\]]*\]", s):
        return True
    return False


# ── clause parsing ──────────────────────────────────────────────────────────

def _parse_clause(tok: str) -> Dict[str, object]:
    """
    Returns a dict of one of these shapes:
      {"kind": "has",    "field": <field>}
      {"kind": "none",   "field": <field>}
      {"kind": "field",  "field": <field>, "value": <str>, "is_regex": bool}
      {"kind": "word",   "value": <str>, "is_regex": True}       # ^foo / foo$ / [ab]
      {"kind": "text",   "value": <str>}                          # plain
    """
    # First colon split (if any). Field name must be non-empty and match known
    # operator / field names; otherwise treat the whole token as a value.
    if ":" in tok:
        head, _, rest = tok.partition(":")
        head_lc = head.lower()
        if head_lc in ("has", "none"):
            field = rest.lower()
            if not field:
                raise QueryError(f"'{head_lc}:' requires a field name")
            if field not in PRESENCE_FIELDS:
                raise QueryError(
                    f"'{head_lc}:{field}' — unknown field. "
                    f"Try: {', '.join(PRESENCE_FIELDS)}"
                )
            return {"kind": head_lc, "field": field}
        if head_lc in FIELDS:
            if not rest:
                raise QueryError(f"'{head_lc}:' requires a value")
            return {
                "kind": "field",
                "field": head_lc,
                "value": rest,
                "is_regex": _looks_like_regex(rest),
            }
        # Unknown prefix with `:` — be strict so typos surface.
        raise QueryError(
            f"Unknown field '{head}'. "
            f"Known: {', '.join(FIELDS)} | has:<field> | none:<field>"
        )

    # No colon. Plain text unless it triggers regex mode.
    if _looks_like_regex(tok):
        return {"kind": "word", "value": tok, "is_regex": True}
    return {"kind": "text", "value": tok}


def parse_query(q: str) -> List[Dict[str, object]]:
    """Parse a query string into a list of AND-combined clauses.

    Empty / whitespace-only input returns []. Raises QueryError on
    syntactic issues (unknown field, unterminated quote, empty value).
    """
    if not q or not q.strip():
        return []
    normalised = _collapse_colon_whitespace(q.strip())
    tokens = _split_tokens(normalised)
    return [_parse_clause(tok) for tok in tokens if tok]


# ── SQL builder ─────────────────────────────────────────────────────────────

# Context fans out to these three columns.
_CONTEXT_COLS = ("context_before", "context_line", "context_after")


def build_where(clauses: List[Dict[str, object]]) -> Tuple[str, List[object]]:
    """Convert parsed clauses into a `(where_sql, params)` pair.

    Always AND-combined; returns ``("", [])`` for an empty clause list.
    All column references are whitelisted (no interpolation of user data
    into SQL); all values go through parameters.
    """
    if not clauses:
        return "", []
    parts: List[str] = []
    params: List[object] = []

    def _col(field: str) -> str:
        # Only reached after validation in parse_query, so KeyError is a bug.
        return _FIELD_TO_COL[field]

    def _fanout_has_not_null(field: str, negate: bool = False) -> str:
        """Build a (NOT) NULL+empty test across one or many columns."""
        if field == "context":
            cols = _CONTEXT_COLS
        else:
            cols = (_col(field),)
        # "has" means ANY col is non-empty; "none" means ALL cols empty.
        joiner = " OR " if not negate else " AND "
        per_col = []
        for c in cols:
            if negate:
                per_col.append(f"(NULLIF({c}, '') IS NULL)")
            else:
                per_col.append(f"(NULLIF({c}, '') IS NOT NULL)")
        return "(" + joiner.join(per_col) + ")"

    def _fanout_match(field: str, value: str, is_regex: bool) -> Tuple[str, List[object]]:
        """Match `value` against one or (for context) three columns."""
        cols = _CONTEXT_COLS if field == "context" else (_col(field),)
        per_col: List[str] = []
        pp: List[object] = []
        for c in cols:
            if is_regex:
                per_col.append(f"(COALESCE({c}, '') REGEXP %s)")
                pp.append(value)
            else:
                per_col.append(f"(LOWER(COALESCE({c}, '')) LIKE %s)")
                pp.append(f"%{value.lower()}%")
        return "(" + " OR ".join(per_col) + ")", pp

    for cl in clauses:
        kind = cl["kind"]
        if kind == "has":
            parts.append(_fanout_has_not_null(cl["field"]))         # type: ignore[arg-type]
        elif kind == "none":
            parts.append(_fanout_has_not_null(cl["field"], negate=True))  # type: ignore[arg-type]
        elif kind == "field":
            sql, pp = _fanout_match(cl["field"], cl["value"], cl["is_regex"])  # type: ignore[arg-type]
            parts.append(sql)
            params.extend(pp)
        elif kind == "word":
            parts.append("(word REGEXP %s)")
            params.append(cl["value"])
        elif kind == "text":
            # Back-compat behaviour: substring match across word + translation.
            parts.append(
                "(LOWER(word) LIKE %s OR LOWER(COALESCE(translation,'')) LIKE %s)"
            )
            like = f"%{str(cl['value']).lower()}%"
            params.extend([like, like])
        else:  # pragma: no cover — defensive
            raise QueryError(f"Internal: unhandled clause kind {kind!r}")

    return " AND ".join(parts), params
