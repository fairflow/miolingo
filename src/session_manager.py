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
    user: Optional[dict] = None
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

        password = (
            self._cookie_password
            or st.secrets.get("cookie_password")
            or st.secrets.get("auth", {}).get("cookie_password")
        )
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
        """Attempt to resolve session from cookie + DB."""

        session_id = self.read_cookie_session_id()
        if not session_id:
            return SessionContext()

        # Lazy import to avoid circulars
        import app_mysql

        def _log(event_type: str, message: str, **kwargs):
            try:
                app_mysql.write_debug_log(
                    event_type=event_type,
                    message=message,
                    session_id=session_id,
                    **kwargs,
                )
            except Exception:
                pass

        _log("session_reattach_attempt", "Attempting cookie-based session reattach")

        ip_address = "unknown"
        try:
            headers = st.context.headers
            if headers:
                xff = headers.get("X-Forwarded-For") or headers.get("x-forwarded-for")
                if xff:
                    ip_address = xff.split(",")[0].strip()
        except Exception:
            pass

        try:
            user = app_mysql.validate_session(session_id, ip_address=ip_address)
        except Exception:
            _log("session_reattach_error", "Validation raised exception")
            # Treat validation errors as non-attachable for now
            return SessionContext()

        if not user:
            _log("session_reattach_failed", "Session invalid or expired")
            return SessionContext()

        _log(
            "session_reattach_success",
            "Session reattached",
            username=user.get("username"),
            user_id=user.get("user_id"),
        )

        return SessionContext(
            session_id=session_id,
            username=user.get("username"),
            user=user,
            authenticated=True,
        )
