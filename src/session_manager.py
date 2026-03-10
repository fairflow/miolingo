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

import streamlit as st


COOKIE_NAME = "miolingo_session"
COOKIE_PREFIX = "miolingo/"


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

    def __init__(self, cookie_password: Optional[str] = None):
        self._cookie_password = cookie_password
        self._cookies = None

    def _get_cookie_manager(self):
        """Lazy-init cookie manager.

        Returns None if the dependency or password is missing.
        """

        if self._cookies is not None:
            return self._cookies

        try:
            from streamlit_cookies_manager import EncryptedCookieManager
        except ImportError:
            st.warning("Cookie manager not installed (streamlit-cookies-manager)")
            return None

        password = self._cookie_password or st.secrets.get("cookie_password")
        if not password:
            st.warning("Missing cookie_password in st.secrets")
            return None

        cookies = EncryptedCookieManager(prefix=COOKIE_PREFIX, password=password)
        if not cookies.ready():
            st.stop()

        self._cookies = cookies
        return self._cookies

    # -- Cookie handling ----------------------------------------------------------
    def read_cookie_session_id(self) -> Optional[str]:
        """Read the browser cookie and return the session_id if present."""

        cookies = self._get_cookie_manager()
        if not cookies:
            return None
        return cookies.get(COOKIE_NAME)

    def write_cookie_session_id(self, session_id: str) -> None:
        """Persist session_id to browser cookie."""

        cookies = self._get_cookie_manager()
        if not cookies:
            return None
        cookies[COOKIE_NAME] = session_id
        cookies.save()
        return None

    def clear_cookie_session_id(self) -> None:
        """Clear the session cookie on logout / invalid session."""

        cookies = self._get_cookie_manager()
        if not cookies:
            return None
        if COOKIE_NAME in cookies:
            del cookies[COOKIE_NAME]
            cookies.save()
        return None

    # -- Session re-attach (future) -----------------------------------------------
    def resolve_session(self) -> SessionContext:
        """Attempt to resolve session from cookie + DB.

        Phase 1 (future) will:
        - read cookie
        - validate session in DB
        - restore st.session_state
        """

        return SessionContext()
