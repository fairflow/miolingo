#!/usr/bin/env python3
"""Unified admin entrypoint for Miolingo.

Run with:
    streamlit run src/unified_admin.py --server.port 8507 --server.headless=true

This is the single admin entrypoint:
- Handles admin authentication
- Creates exactly one session in the unified `sessions` table (app_name='miolingo')
- Provides radio-button navigation (tabs deprecated)

The hosted legacy tools (`miolingo-admin.py`, `connection_monitor.py`) are executed
in-process and should skip `st.set_page_config` when `_unified_admin_host` is set.
"""

from __future__ import annotations

import runpy
from pathlib import Path

import streamlit as st

import app_mysql

__version__ = "1.0.0"


REFRESH_INTERVAL_MINUTES = 5


def _ensure_admin_auth() -> None:
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False

    if st.session_state.authenticated:
        return

    st.title("🔧 Miolingo Admin")
    st.subheader("Authentication Required")

    with st.form("unified_admin_login_form"):
        username = st.text_input("Username", key="ua_username", autocomplete="username")
        password = st.text_input("Password", type="password", key="ua_password", autocomplete="current-password")
        submitted = st.form_submit_button("Login")

        if not submitted:
            st.stop()

        user = app_mysql.authenticate_user(username, password)
        if not user:
            st.error("Invalid credentials")
            st.stop()

        if user.get('role') != 'admin':
            st.error("Access denied. Admin privileges required.")
            st.info(f"Your role: {user.get('role', 'unknown')}")
            st.stop()

        try:
            headers = st.context.headers
            user_agent = headers.get('User-Agent', 'unknown') if headers else 'unknown'
        except Exception:
            user_agent = 'unknown'

        session_id = app_mysql.create_session(
            user['user_id'],
            "127.0.0.1",
            username=username,
            user_agent=user_agent,
            app_name='miolingo',
        )
        if not session_id:
            st.error("Failed to create session")
            st.stop()

        st.session_state.authenticated = True
        st.session_state.is_admin = True
        st.session_state.uses_bootstrap = False
        st.session_state.admin_username = username
        st.session_state.admin_user_id = user['user_id']

        # Shared session id across hosted tools
        st.session_state.session_id = session_id
        st.session_state.admin_session_id = session_id
        st.session_state.monitor_session_id = session_id
        st.session_state.monitor_username = username

        # App identity
        st.session_state.app_name = 'miolingo'

        # Establish a tracked connection for this session (sparse connection creation)
        try:
            app_mysql.get_connection()
        except Exception as e:
            st.warning(f"Login succeeded, but connection creation failed: {e}")

        st.success("✅ Admin access granted")
        st.rerun()


st.session_state._unified_admin_host = True

st.set_page_config(page_title="Miolingo Admin", page_icon="🔧", layout="wide")

_ensure_admin_auth()

# Keep the unified admin session alive (sliding inactivity window)
if st.session_state.get('session_id'):
    try:
        app_mysql.touch_session(st.session_state['session_id'])
    except Exception:
        pass

with st.sidebar:
    st.caption(f"Miolingo Admin Dashboard v{__version__}")
    st.caption("Local monitoring interface")
    st.divider()
    
    st.subheader("Admin")
    if 'admin_username' in st.session_state:
        st.info(f"👤 {st.session_state.admin_username}")
    
    # Connection info dropdown
    conn_info = app_mysql.get_current_connection_info()
    with st.expander("🔌 Connection Info", expanded=False):
        if conn_info:
            st.caption(f"**Tunnel:** `{conn_info['tunnel_id']}` (PID: {conn_info['tunnel_pid']}, Port: {conn_info['tunnel_port']})")
            st.caption(f"**Created:** {conn_info['tunnel_created']}")
            st.caption(f"**Connections:** {conn_info['tunnel_conn_count']} on this tunnel")
            st.caption("---")
            st.caption(f"**SQL Conn:** `{conn_info['connection_id'][:30]}...`")
            st.caption(f"**MySQL ID:** {conn_info['mysql_conn_id']} ({conn_info['connection_status']})")
            st.caption(f"**Age:** {conn_info['connection_age']} | **TTL:** {conn_info['session_ttl']}")
            st.caption(f"**Now:** {conn_info['current_time'].strftime('%H:%M:%S')}")
        else:
            st.caption("⚠️ No connection info available")
    
    st.divider()

    # Global quick actions (used by hosted tools)
    auto_refresh = st.checkbox(
        f"🔄 Auto-refresh ({REFRESH_INTERVAL_MINUTES}m)",
        value=st.session_state.get('auto_refresh_enabled', False),
        help=f"Automatically refresh data every {REFRESH_INTERVAL_MINUTES} minutes",
        key="ua_auto_refresh",
    )
    if auto_refresh != st.session_state.get('auto_refresh_enabled', True):
        st.session_state.auto_refresh_enabled = auto_refresh
        st.rerun()

    if st.button("🔄 Clear Cache & Reconnect", use_container_width=True, key="ua_clear_cache"):
        st.cache_resource.clear()
        st.cache_data.clear()
        if 'mysql_pool' in st.session_state:
            del st.session_state.mysql_pool
        st.success("✅ Cache cleared")
        st.rerun()

    st.divider()

    tool = st.radio("Tools", ["Admin Dashboard", "Connection Monitor"], index=0, key="ua_tools")

    # Per-tool navigation lives here (hosted tools read from session state)
    if tool == "Admin Dashboard":
        admin_pages = ["📊 Resource Usage", "👥 Users", "📝 Logs", "📧 Email", "📢 Announcements", "⚙️ Settings"]
        st.session_state.ua_admin_page = st.radio(
            "Admin Pages",
            admin_pages,
            index=admin_pages.index(st.session_state.get('ua_admin_page', admin_pages[0]))
            if st.session_state.get('ua_admin_page', admin_pages[0]) in admin_pages
            else 0,
            key="ua_admin_pages",
        )
    else:
        monitor_pages = ["Dashboard", "Tunnels", "Connections", "Sessions", "Controls"]
        st.session_state.ua_monitor_page = st.radio(
            "Monitor Pages",
            monitor_pages,
            index=monitor_pages.index(st.session_state.get('ua_monitor_page', monitor_pages[0]))
            if st.session_state.get('ua_monitor_page', monitor_pages[0]) in monitor_pages
            else 0,
            key="ua_monitor_pages",
        )

    st.divider()

    if st.button("🚪 Logout", type="primary", use_container_width=True, key="ua_logout"):
        try:
            if 'session_id' in st.session_state:
                app_mysql.delete_session(st.session_state['session_id'])
        except Exception as e:
            st.warning(f"Session cleanup warning: {e}")

        try:
            app_mysql.cleanup_session_resources()
        except Exception:
            pass

        st.session_state.clear()
        st.session_state['voluntary_logout'] = True
        st.rerun()


base_dir = Path(__file__).resolve().parent

if tool == "Admin Dashboard":
    runpy.run_path(str(base_dir / "miolingo-admin.py"), run_name="__main__")
else:
    runpy.run_path(str(base_dir / "connection_monitor.py"), run_name="__main__")
