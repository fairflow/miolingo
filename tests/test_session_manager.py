"""
Tests for SessionManager.logout() batched-save behaviour.

Exercises the fix for StreamlitDuplicateElementKey that occurred when
on_logout() called set_logged_out_flag() + clear_cookie_session_id()
separately, causing cookies.save() to be rendered twice in the same run
with the fixed key 'CookieManager.sync_cookies.save'.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestSessionManagerLogout:
    """SessionManager.logout() must call cookies.save() exactly once."""

    def _make_manager_with_cookies(self, cookie_name="miolingo_session", has_session_cookie=True):
        """Return a SessionManager whose _cookies attribute is a mock."""
        from session_manager import SessionManager, COOKIE_NAME, LOGOUT_COOKIE_NAME

        manager = SessionManager(cookie_password="test-password")

        mock_cookies = MagicMock()
        # Simulate the COOKIE_NAME being present (or absent)
        mock_cookies.__contains__ = MagicMock(return_value=has_session_cookie)

        manager._cookies = mock_cookies
        return manager, mock_cookies

    def test_logout_calls_save_exactly_once(self):
        from session_manager import SessionManager
        manager, mock_cookies = self._make_manager_with_cookies(has_session_cookie=True)
        manager.logout()
        mock_cookies.save.assert_called_once()

    def test_logout_sets_logout_flag(self):
        from session_manager import LOGOUT_COOKIE_NAME
        manager, mock_cookies = self._make_manager_with_cookies(has_session_cookie=True)
        manager.logout()
        mock_cookies.__setitem__.assert_any_call(LOGOUT_COOKIE_NAME, "1")

    def test_logout_clears_session_cookie_when_present(self):
        from session_manager import COOKIE_NAME
        manager, mock_cookies = self._make_manager_with_cookies(has_session_cookie=True)
        manager.logout()
        mock_cookies.__delitem__.assert_called_once_with(COOKIE_NAME)

    def test_logout_skips_delete_when_no_session_cookie(self):
        """If the session cookie is absent, no delete should be attempted."""
        manager, mock_cookies = self._make_manager_with_cookies(has_session_cookie=False)
        manager.logout()
        mock_cookies.__delitem__.assert_not_called()
        # save still called once
        mock_cookies.save.assert_called_once()

    def test_logout_no_crash_when_no_cookie_manager(self):
        """If cookie manager is unavailable, logout must return silently."""
        from session_manager import SessionManager
        manager = SessionManager(cookie_password=None)
        manager._cookies = None  # simulate missing cookie manager
        # Should not raise
        with patch.object(manager, "_get_cookie_manager", return_value=None):
            manager.logout()


class TestSessionManagerImports:
    """Smoke tests: session_manager module is importable with expected symbols."""

    def test_import_session_manager(self):
        import session_manager
        assert hasattr(session_manager, "SessionManager")

    def test_logout_method_exists(self):
        from session_manager import SessionManager
        assert callable(SessionManager.logout)

    def test_set_logged_out_flag_still_exists(self):
        """Legacy method retained for standalone use."""
        from session_manager import SessionManager
        assert callable(SessionManager.set_logged_out_flag)

    def test_clear_cookie_session_id_still_exists(self):
        """Legacy method retained for standalone use."""
        from session_manager import SessionManager
        assert callable(SessionManager.clear_cookie_session_id)
