"""
Authentication: login page, session validation, announcements.

Extracted from app.py (Phase 3 of refactor).

Exports
-------
    init_session_manager()     — call once from app.py after st.set_page_config
    check_authentication()     — call at the top of every app run
    show_login_page()          — renders login / register / guest UI
    show_announcements(loc)    — render active announcements for a location
    get_announcements(loc)     — cached fetch from DB
    on_logout()                — call from the logout button handler in app.py
    ENABLE_SESSION_MANAGER     — flag (read from app.py if needed)
"""

import time
from typing import Dict, Optional

import streamlit as st

import app_mysql
from config import (
    __version__,
    LANGUAGE_CONFIG,
    load_settings as _config_load_settings,
)

# ---------------------------------------------------------------------------
# Session manager (auth infrastructure)
# ---------------------------------------------------------------------------

ENABLE_SESSION_MANAGER = True
_session_manager = None   # set by init_session_manager()


def init_session_manager():
    """
    Create and initialise the SessionManager. Call once from app.py immediately
    after st.set_page_config() and before any other Streamlit calls.
    Returns the session manager instance (or None if disabled).
    """
    global _session_manager
    if ENABLE_SESSION_MANAGER:
        from session_manager import SessionManager
        _session_manager = SessionManager()
        _session_manager.ensure_cookie_manager_ready()
    return _session_manager


def on_logout():
    """
    Handle the session-manager side of logout (clear cookie, set logged-out flag).
    Call from the logout button handler in app.py before clearing session state.
    """
    if ENABLE_SESSION_MANAGER and _session_manager:
        _session_manager.set_logged_out_flag()
        _session_manager.clear_cookie_session_id()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_settings():
    """Load user settings via the config module (mirrors app.py's load_settings wrapper)."""
    return _config_load_settings(session_state=st.session_state, db_module=app_mysql)


# ---------------------------------------------------------------------------
# Announcements
# ---------------------------------------------------------------------------

@st.cache_data(ttl=60)
def get_announcements(location: str) -> Dict[str, Optional[str]]:
    """Get active announcements for display. Cached for 60 seconds."""
    return app_mysql.get_active_announcements(location)


def show_announcements(location: str):
    """Display active announcements for the specified location."""
    loading = st.empty()
    loading.info("Loading updates…")
    try:
        announcements = get_announcements(location)
    except Exception:
        loading.warning("⚠️ Unable to load updates right now.")
        return
    loading.empty()

    # System announcement (orange, priority)
    if announcements.get('system'):
        st.warning(f"⚠️ {announcements['system']}")

    # Feature announcement (green, secondary)
    if announcements.get('feature'):
        st.success(f"✨ {announcements['feature']}")


# ---------------------------------------------------------------------------
# Login page
# ---------------------------------------------------------------------------

def show_login_page():
    """Display login/registration page."""
    st.markdown(f"# 🔐 Miolingo <small>{__version__}</small>", unsafe_allow_html=True)

    # Get language list from config
    languages = ", ".join(LANGUAGE_CONFIG.keys())
    st.markdown(f"Pronunciation trainer - practice {languages}")

    # Choose the initial practice language before login/guest
    # (keeps the main app language selection aligned on first load)
    language_names = list(LANGUAGE_CONFIG.keys())
    default_language_name = st.session_state.get('login_practice_language', 'Portuguese')
    if default_language_name not in language_names:
        default_language_name = language_names[0] if language_names else 'Portuguese'

    selected_language_name = st.selectbox(
        "Practice language",
        language_names,
        index=language_names.index(default_language_name) if default_language_name in language_names else 0,
        key='login_practice_language',
        help="Select the language you want to practice first. You can change this later in Settings."
    )

    # Persist as the canonical material language code (used by the main app selector)
    try:
        selected_code = LANGUAGE_CONFIG[selected_language_name]['code']
        if st.session_state.get('material_language') != selected_code:
            st.session_state.material_language = selected_code
    except Exception:
        pass

    # CRITICAL: Show forced logout reason if present (prominent display)
    # BUT: Don't show if this was a voluntary logout (user clicked logout button)
    if 'voluntary_logout' in st.session_state:
        # User clicked logout button - this is expected, don't show warning
        del st.session_state['voluntary_logout']
    elif 'forced_logout_reason' in st.session_state:
        # This was an unexpected/forced logout - show warning
        reason = st.session_state['forced_logout_reason']
        message = st.session_state.get('forced_logout_message', 'You have been logged out.')

        # Show as error (red banner) so it's highly visible
        st.error(f"🚨 **FORCED LOGOUT**\n\n{message}\n\n📋 *Reason code: `{reason}` - Please report if unexpected*")

        # Clear the forced logout markers after showing (so refresh doesn't show again)
        del st.session_state['forced_logout_reason']
        if 'forced_logout_message' in st.session_state:
            del st.session_state['forced_logout_message']

    # Show announcements for login page
    show_announcements('login')

    # About section with links
    st.markdown("📖 [About & Features](https://github.com/fairflow/miolingo/blob/feature/admin-fusion/README.md) • 📚 [Development Story](https://github.com/fairflow/miolingo/blob/feature/admin-fusion/articles/development_detailed.md)")
    st.markdown("---")

    tab1, tab2, tab3 = st.tabs(["Login", "Register", "Guest Mode"])

    with tab1:
        st.subheader("Login to Your Account")

        with st.form("login_form"):
            username = st.text_input("Username", key="login_username", autocomplete="username")
            password = st.text_input("Password", type="password", key="login_password", autocomplete="current-password")
            submit = st.form_submit_button("Login")

            if submit:
                if not username or not password:
                    st.error("❌ Please enter both username and password")
                else:
                    # Authenticate user
                    user = app_mysql.authenticate_user(username, password)

                    if user:
                        # Get user agent for session metadata
                        try:
                            headers = st.context.headers
                            user_agent = headers.get('User-Agent', 'unknown') if headers else 'unknown'
                        except Exception:
                            user_agent = 'unknown'

                        # Create session (stores metadata directly in `sessions`)
                        session_id = app_mysql.create_session(
                            user['user_id'],
                            "127.0.0.1",
                            username=username,
                            user_agent=user_agent,
                            app_name='miolingo',
                        )

                        if session_id:
                            # HANDOVER: Close any bootstrap connection, get tracked connection
                            old_bootstrap = st.session_state.get('db_connection')
                            if old_bootstrap:
                                try:
                                    old_bootstrap.close()
                                    print("✓ Closed bootstrap connection before login")
                                except Exception:
                                    pass
                                del st.session_state.db_connection

                            # Store in session state
                            st.session_state['authenticated'] = True
                            st.session_state['user'] = user
                            st.session_state['session_id'] = session_id

                            # Persist cookie for re-attach (feature-flagged)
                            if ENABLE_SESSION_MANAGER and _session_manager:
                                _session_manager.clear_logged_out_flag()
                                _session_manager.write_cookie_session_id(session_id)

                            # Get tracked connection from pool (replaces bootstrap)
                            tracked_conn = app_mysql.get_connection()  # noqa: F841
                            print(f"✓ Established tracked connection for {username}")

                            # Reload settings from database (using new tracked connection)
                            st.session_state.settings = _load_settings()
                            st.success(f"✅ Welcome back, {user['username']}!")
                            st.rerun()
                        else:
                            st.error("❌ Failed to create session. Please try again.")
                    else:
                        st.error("❌ Invalid username or password")

    with tab2:
        st.subheader("Create New Account")

        with st.form("register_form"):
            new_username = st.text_input("Choose Username", key="register_username", autocomplete="username", help="3-20 characters, letters/numbers only")
            new_email = st.text_input("Email Address", key="register_email", autocomplete="email")
            new_password = st.text_input("Choose Password", type="password", key="register_password", autocomplete="new-password", help="Min 8 characters")
            new_password_confirm = st.text_input("Confirm Password", type="password", key="register_password_confirm", autocomplete="new-password")
            submit_register = st.form_submit_button("Create Account")

            if submit_register:
                # Validation
                if not all([new_username, new_email, new_password, new_password_confirm]):
                    st.error("❌ Please fill in all fields")
                elif new_password != new_password_confirm:
                    st.error("❌ Passwords do not match")
                elif len(new_password) < 8:
                    st.error("❌ Password must be at least 8 characters")
                elif len(new_username) < 3 or len(new_username) > 20:
                    st.error("❌ Username must be 3-20 characters")
                else:
                    # Create user
                    user_id = app_mysql.create_user(new_username, new_email, new_password)

                    if user_id:
                        # Note: Registration doesn't auto-login, so no handover needed here
                        # User will do handover when they click Login tab
                        st.success(f"✅ Account created! Welcome, {new_username}!")
                        st.info("👆 Please login with your new account in the Login tab")
                    # Errors are handled in app_mysql.create_user()

    with tab3:
        st.subheader("Try Without Registration")

        st.info("🎭 **Guest Mode** - Try the app instantly without creating an account!")
        st.warning("⚠️ **Note:** Guest sessions are temporary. Your progress won't be saved.")

        st.markdown("""
        **What you get as a guest:**
        - ✅ Full access to all practice features
        - ✅ All supported languages
        - ✅ AI pronunciation feedback
        - ❌ Progress not saved after session ends
        """)

        if st.button("🚀 Start as Guest", type="primary", use_container_width=True):
            # Create guest user
            # Get user agent for session metadata
            try:
                headers = st.context.headers
                user_agent = headers.get('User-Agent', 'unknown') if headers else 'unknown'
            except Exception:
                user_agent = 'unknown'

            result = app_mysql.create_guest_user(
                ip_address="127.0.0.1",
                user_agent=user_agent,
                app_name='miolingo',
            )

            if result:
                user_id, username, session_id = result

                # HANDOVER: Close any bootstrap connection, get tracked connection
                old_bootstrap = st.session_state.get('db_connection')
                if old_bootstrap:
                    try:
                        old_bootstrap.close()
                        print("✓ Closed bootstrap connection before guest login")
                    except Exception:
                        pass
                    del st.session_state.db_connection

                # Create user dict (matching regular auth format)
                guest_user = {
                    'user_id': user_id,
                    'username': username,
                    'email': f'{username}@temp.miolingo.io',
                    'is_guest': True  # Flag for UI indication
                }

                # Store in session state
                st.session_state['authenticated'] = True
                st.session_state['user'] = guest_user
                st.session_state['session_id'] = session_id

                # Persist cookie for re-attach (feature-flagged)
                if ENABLE_SESSION_MANAGER and _session_manager:
                    _session_manager.clear_logged_out_flag()
                    _session_manager.write_cookie_session_id(session_id)

                # Get tracked connection from pool (replaces bootstrap)
                tracked_conn = app_mysql.get_connection()  # noqa: F841
                print(f"✓ Established tracked connection for guest {username}")

                # Reload settings from database (will have defaults for new guest)
                st.session_state.settings = _load_settings()
                st.success(f"✅ Welcome, Guest! Enjoy exploring Miolingo!")
                st.rerun()
            else:
                st.error("❌ Failed to create guest session. Please try again.")


# ---------------------------------------------------------------------------
# Authentication gate
# ---------------------------------------------------------------------------

def check_authentication():
    """
    Check if user is authenticated. If not, show login page and stop.
    Call at the start of every app run (after init_session_manager).

    Session validation is done periodically (every 60 minutes) rather than on
    every rerun to prevent logout due to temporary database connection issues.
    """
    # Initialize session state
    if 'authenticated' not in st.session_state:
        st.session_state['authenticated'] = False

    # Attempt cookie-based reattach (feature-flagged)
    if ENABLE_SESSION_MANAGER and not st.session_state.get('authenticated', False):
        if _session_manager:
            context = _session_manager.resolve_session()
            if context.authenticated and context.user:
                st.session_state['authenticated'] = True
                st.session_state['user'] = context.user
                st.session_state['session_id'] = context.session_id
                st.session_state.settings = _load_settings()

    # Check if authenticated
    if not st.session_state['authenticated']:
        show_login_page()
        st.stop()

    # Validate session periodically (not on every rerun)
    if 'session_id' in st.session_state:
        # Only validate every 60 minutes to reduce DB load and avoid logout on
        # connection issues
        last_check = st.session_state.get('last_session_check', 0)
        now = time.time()

        if now - last_check > 3600:  # 60 minutes = 3600 seconds
            try:
                # Get user agent for logging
                try:
                    headers = st.context.headers
                    user_agent = headers.get('User-Agent', 'unknown') if headers else 'unknown'
                except Exception:
                    user_agent = 'unknown'

                user = app_mysql.validate_session(st.session_state['session_id'], "127.0.0.1")

                # validate_session returns None if session not valid
                # It raises exceptions for database errors (which we catch below)
                if not user:
                    # Session validation failed - could be expired or invalid
                    # Log the forced logout
                    app_mysql.write_debug_log(
                        event_type='forced_logout',
                        message='Session validation failed - forcing logout',
                        username=st.session_state.get('user', {}).get('username'),
                        user_id=st.session_state.get('user', {}).get('user_id'),
                        user_agent=user_agent,
                        session_id=st.session_state['session_id']
                    )
                    # FORCED LOGOUT: Set generic message (don't assume 7-day expiry)
                    st.session_state['forced_logout_reason'] = "session_invalid"
                    st.session_state['forced_logout_message'] = "⚠️ **Session Ended**: Your session is no longer valid. Please login again."
                    st.session_state['authenticated'] = False

                    # Clear cookie on invalid session (feature-flagged)
                    if ENABLE_SESSION_MANAGER and _session_manager:
                        _session_manager.clear_cookie_session_id()

                    st.rerun()
                else:
                    # Session valid - update check timestamp
                    st.session_state['last_session_check'] = now

            except Exception:
                # Database connection error or other exception - DON'T logout user
                # This is the key fix: exceptions mean errors, not expiry
                # Just show warning and keep user logged in
                st.warning(f"⚠️ Temporary connection issue during session validation. You remain logged in.")
                # Don't update last_session_check so we retry sooner (next rerun)
