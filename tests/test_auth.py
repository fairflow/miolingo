"""
Tests for auth.py: import smoke tests and pure-function unit tests.

Functions that require Streamlit runtime, a live database connection, or a
session cookie are not tested here — only importability and any logic that can
be exercised without those dependencies.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


# ---------------------------------------------------------------------------
# Import smoke tests
# ---------------------------------------------------------------------------

class TestAuthImports:
    """Verify auth.py is importable and exports expected names."""

    def test_import_check_authentication(self):
        from auth import check_authentication
        assert callable(check_authentication)

    def test_import_show_login_page(self):
        from auth import show_login_page
        assert callable(show_login_page)

    def test_import_show_announcements(self):
        from auth import show_announcements
        assert callable(show_announcements)

    def test_import_get_announcements(self):
        from auth import get_announcements
        assert callable(get_announcements)

    def test_import_init_session_manager(self):
        from auth import init_session_manager
        assert callable(init_session_manager)

    def test_import_on_logout(self):
        from auth import on_logout
        assert callable(on_logout)

    def test_enable_session_manager_flag(self):
        from auth import ENABLE_SESSION_MANAGER
        # Should be a bool
        assert isinstance(ENABLE_SESSION_MANAGER, bool)

    def test_module_has_session_manager_attribute(self):
        import auth
        # _session_manager exists at module level (may be None before init)
        assert hasattr(auth, '_session_manager')


class TestOnLogout:
    """on_logout() should be safe to call even when session manager is None."""

    def test_on_logout_no_session_manager(self, monkeypatch):
        import auth
        monkeypatch.setattr(auth, '_session_manager', None)
        # Should not raise
        auth.on_logout()

    def test_on_logout_disabled(self, monkeypatch):
        import auth
        monkeypatch.setattr(auth, 'ENABLE_SESSION_MANAGER', False)
        monkeypatch.setattr(auth, '_session_manager', None)
        # Should not raise
        auth.on_logout()
