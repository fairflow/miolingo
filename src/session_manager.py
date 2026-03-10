"""
SessionManager (scaffold)

Phase 0: Documentation + minimal structure. No behavior changes.

This module will become the single entry point for:
- Cookie-backed session discovery
- DB session validation
- Re-attach logic after transient failures

See docs/dev-docs/SESSION_MANAGER_DESIGN.md for target behavior.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class SessionContext:
    """Lightweight container for resolved session state.

    This is intentionally small for now; it will expand once the
    re-attach logic is implemented.
    """

    session_id: Optional[str] = None
    username: Optional[str] = None
    authenticated: bool = False


class SessionManager:
    """Scaffold for future session/cookie orchestration.

    NOTE: This class is not yet wired into the runtime.
    """

    def __init__(self):
        # Placeholder for future dependencies (cookie manager, DB helpers, etc.)
        pass

    # -- Cookie handling (future) -------------------------------------------------
    def read_cookie_session_id(self) -> Optional[str]:
        """Read the browser cookie and return the session_id if present.

        Phase 0: not implemented.
        """

        return None

    def write_cookie_session_id(self, session_id: str) -> None:
        """Persist session_id to browser cookie.

        Phase 0: not implemented.
        """

        return None

    def clear_cookie_session_id(self) -> None:
        """Clear the session cookie on logout / invalid session.

        Phase 0: not implemented.
        """

        return None

    # -- Session re-attach (future) -----------------------------------------------
    def resolve_session(self) -> SessionContext:
        """Attempt to resolve session from cookie + DB.

        Phase 0: returns unauthenticated context.
        """

        return SessionContext()
