#!/usr/bin/env python3
"""
Miolingo Admin Dashboard

Local admin interface for monitoring resource usage, users, and logs.
Run with: streamlit run miolingo-admin.py --server.port 8505 --server.headless=true
Then open: http://localhost:8505

Version: 2.1.0
"""

__version__ = "2.2.1-claude-dev"

# Auto-refresh interval in minutes
REFRESH_INTERVAL_MINUTES = 5

import streamlit as st
import json
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
from collections import defaultdict
import time
import app_mysql
from contextlib import contextmanager


HOSTED_BY_UNIFIED_ADMIN = st.session_state.get('_unified_admin_host', False)

# Page config (only if not hosted by unified entrypoint)
if not HOSTED_BY_UNIFIED_ADMIN:
    st.set_page_config(
        page_title="Miolingo Admin",
        page_icon="🔧",
        layout="wide"
    )

# Set app name for connection tracking
if 'app_name' not in st.session_state:
    st.session_state.app_name = 'miolingo'

# Auto-refresh feature - queries database every N seconds
if 'auto_refresh_enabled' not in st.session_state:
    st.session_state.auto_refresh_enabled = True  # Default on

# NOTE: Auto-refresh sleep happens at END of page, not here


# ============================================================================
# AUTHENTICATION
# ============================================================================

def check_authentication():
    """Simple authentication for admin dashboard (reuses miolingo auth)"""
    # When hosted, `unified_admin.py` owns authentication + session creation.
    if HOSTED_BY_UNIFIED_ADMIN:
        if not st.session_state.get('authenticated', False):
            st.error("This page is hosted by Unified Admin. Please authenticate there.")
            st.stop()
        return

    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    
    if not st.session_state.authenticated:
        st.title("🔧 Miolingo Admin Dashboard")
        st.subheader("Authentication Required")
        
        with st.form("login_form"):
            username = st.text_input("Username", key="admin_username_input", autocomplete="username")
            password = st.text_input("Password", type="password", key="admin_password_input", autocomplete="current-password")
            submitted = st.form_submit_button("Login")
            
            if submitted:
                # Authenticate using bootstrap connection (doesn't count toward pool)
                try:
                    user = app_mysql.authenticate_user(username, password)
                    
                    if not user:
                        st.error("Invalid credentials")
                        st.stop()
                    
                    # Check if user has admin role
                    is_admin = user.get('role') == 'admin'
                    
                    if not is_admin:
                        st.error("Access denied. Admin privileges required.")
                        st.info(f"Your role: {user.get('role', 'unknown')}")
                        st.stop()
                    
                    # Admin authentication successful
                    st.session_state.authenticated = True
                    st.session_state.admin_username = username
                    st.session_state.admin_user_id = user['user_id']
                    st.session_state.uses_bootstrap = True  # Flag to use bootstrap connections
                    
                    # Get user agent for logging
                    try:
                        headers = st.context.headers
                        user_agent = headers.get('User-Agent', 'unknown') if headers else 'unknown'
                    except:
                        user_agent = 'unknown'
                    
                    # Log this admin login
                    try:
                        session_id = app_mysql.create_session(
                            user['user_id'],
                            "127.0.0.1",
                            username=username,
                            user_agent=user_agent,
                            app_name='miolingo',
                        )
                        if session_id:
                            st.session_state.admin_session_id = session_id
                    except Exception as log_err:
                        st.warning(f"Login successful but session logging failed: {log_err}")
                    
                    st.success("✅ Admin access granted")
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"Authentication error: {e}")
        
        st.stop()

# Check authentication before showing dashboard
check_authentication()

st.title("🔧 Miolingo Admin Dashboard")
st.caption("Local monitoring and management interface • v2.0.5")

if not HOSTED_BY_UNIFIED_ADMIN:
    # Quick reconnect button in sidebar (standalone mode)
    with st.sidebar:
        st.caption("Miolingo Admin Dashboard v2.0.5")
        st.caption("Local monitoring interface")
        st.divider()
        
        st.subheader("🔧 Quick Actions")

        # Show logged in user
        if 'admin_username' in st.session_state:
            st.info(f"👤 Logged in as: **{st.session_state.admin_username}**")

        # Auto-refresh toggle
        auto_refresh = st.checkbox(
            f"🔄 Auto-refresh ({REFRESH_INTERVAL_MINUTES}m)",
            value=st.session_state.auto_refresh_enabled,
            help=f"Automatically refresh data from database every {REFRESH_INTERVAL_MINUTES} minutes",
        )
        if auto_refresh != st.session_state.auto_refresh_enabled:
            st.session_state.auto_refresh_enabled = auto_refresh
            st.rerun()

        if st.button("🔄 Clear Cache & Reconnect", use_container_width=True):
            # Clear all caches
            st.cache_resource.clear()
            st.cache_data.clear()

            # Clear connection pool from session state (forces fresh connections)
            if 'mysql_pool' in st.session_state:
                del st.session_state.mysql_pool

            st.success("✅ Cache cleared! Database connections will be recreated on next use.")
            st.info("💡 If you still see errors, refresh your browser (Cmd+R or Ctrl+R)")
            time.sleep(1)
            st.rerun()
        st.caption("💡 Use this if you see connection errors")

        # Logout button (standalone mode)
        st.divider()
        if st.button("🚪 Logout", use_container_width=True, type="primary"):
            # Delete admin session from database
            if 'admin_session_id' in st.session_state:
                try:
                    app_mysql.delete_session(st.session_state['admin_session_id'])
                except Exception as e:
                    st.warning(f"Session cleanup warning: {e}")

            # Clear session state
            st.session_state.clear()
            st.session_state['voluntary_logout'] = True
            st.rerun()

# Navigation (tabs deprecated)
_admin_pages = ["📊 Resource Usage", "👥 Users", "📝 Logs", "📧 Email", "📢 Announcements", "⚙️ Settings"]
if HOSTED_BY_UNIFIED_ADMIN:
    selected_page = st.session_state.get('ua_admin_page', _admin_pages[0])
    if selected_page not in _admin_pages:
        selected_page = _admin_pages[0]
else:
    selected_page = st.sidebar.radio("Admin Pages", _admin_pages, index=0)

# TAB 1: Resource Usage
if selected_page == "📊 Resource Usage":
    st.header("📊 Resource Usage")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.subheader("🗣️ TTS Usage")
        
        # Check for Google Cloud TTS quota
        try:
            # Check for API key at root level or in section
            has_gcloud = ("google_cloud_tts_api_key" in st.secrets) or ("google_cloud_tts" in st.secrets)
            
            if has_gcloud:
                st.success("✓ Google Cloud TTS configured")
                
                # Calculate actual usage from database
                conn = app_mysql.get_connection()
                if conn:
                    try:
                        cursor = conn.cursor(dictionary=True)
                        
                        # Get count of practice sessions this month (each generates TTS)
                        cursor.execute("""
                            SELECT COUNT(*) as count,
                                   SUM(LENGTH(target_phrase)) as total_chars
                            FROM user_progress
                            WHERE practice_date >= DATE_FORMAT(NOW(), '%Y-%m-01')
                        """)
                        usage = cursor.fetchone()
                        
                        # Convert Decimal to int/float for Streamlit
                        session_count = int(usage['count'] or 0)
                        char_count = int(usage['total_chars'] or 0)
                        
                        # Show actual usage
                        col_a, col_b = st.columns(2)
                        with col_a:
                            st.metric("TTS Requests (This Month)", f"{session_count:,}")
                        with col_b:
                            st.metric("Characters Used", f"{char_count:,}")
                        
                        # Calculate percentage of free tier
                        free_tier_limit = 1_000_000
                        usage_pct = float(char_count) / float(free_tier_limit) * 100
                        
                        st.progress(min(usage_pct / 100.0, 1.0))
                        st.caption(f"**{usage_pct:.1f}%** of free tier used ({char_count:,} / {free_tier_limit:,} characters)")
                        
                        # Show quota information
                        st.info("""
                        **Google Cloud TTS Quotas:**
                        - Free tier: 1M characters/month
                        - Standard: ~4M characters/month
                        - Neural: ~1M characters/month
                        """)
                        
                        cursor.close()
                    except Exception as e:
                        st.warning(f"Could not fetch usage: {e}")
                        st.info("**Estimated capacity:** ~20,000 phrases/month (free tier)")
                else:
                    st.info("**Average phrase:** ~50 characters\n**Estimated capacity:** ~20,000 phrases/month (free tier)")
            else:
                st.warning("Google Cloud TTS not configured in secrets")
        except Exception as e:
            st.warning(f"Error checking TTS config: {e}")
        
        # Show gTTS status
        st.write("**gTTS (Free, unlimited):**")
        try:
            import gtts
            st.success("✓ gTTS available")
        except:
            st.error("✗ gTTS not installed")
    
    with col2:
        st.subheader("💾 Storage Usage")
        
        # Check language materials size
        materials_dir = Path("language_materials")
        if materials_dir.exists():
            total_size = sum(f.stat().st_size for f in materials_dir.rglob('*') if f.is_file())
            st.metric("Language Materials", f"{total_size / 1024 / 1024:.2f} MB")
            
            # Count files by language
            lang_counts = defaultdict(int)
            for lang_dir in materials_dir.iterdir():
                if lang_dir.is_dir():
                    count = sum(1 for f in lang_dir.rglob('*.txt'))
                    lang_counts[lang_dir.name] = count
            
            st.write("**Files by language:**")
            for lang, count in sorted(lang_counts.items()):
                st.text(f"  {lang}: {count} files")
        else:
            st.warning("Language materials directory not found")
    
    with col3:
        st.subheader("🔌 API Status")
        
        # Check Whisper model
        st.write("**Speech Recognition:**")
        try:
            import whisper
            st.success("✓ Whisper available")
            
            # Check for downloaded models
            model_dir = Path.home() / ".cache" / "whisper"
            if model_dir.exists():
                models = list(model_dir.glob("*.pt"))
                st.text(f"  Downloaded models: {len(models)}")
        except:
            st.warning("✗ Whisper not installed")
        
        # Check database
        st.write("**Database:**")
        try:
            conn = app_mysql.get_connection()
            if conn:
                st.success("✓ Database connected")
            else:
                st.warning("✗ Database not connected")
        except Exception as e:
            st.warning(f"✗ Database not connected: {str(e)}")

# TAB 2: Users
if selected_page == "👥 Users":
    st.header("👥 Current Users")
    
    try:
        conn = app_mysql.get_connection()
    except:
        conn = None
    
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            
            # Get user count
            cursor.execute("SELECT COUNT(*) as count FROM users")
            user_count = cursor.fetchone()['count']
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Users", user_count)
            
            # Get currently logged-in users (active sessions with device/browser info)
            cursor.execute("""
                  SELECT u.username, u.email, s.created_at as login_time, s.expires_at, s.ip_address,
                       TIMESTAMPDIFF(HOUR, NOW(), s.expires_at) as hours_until_expire,
                      s.device_type as device_type,
                      s.browser as browser,
                      s.app_name as app_name
                FROM sessions s
                JOIN users u ON s.user_id = u.user_id
                WHERE s.status = 'active' AND s.expires_at > NOW()
                ORDER BY s.created_at DESC
            """)
            active_sessions = cursor.fetchall()
            
            with col2:
                active_usernames = {row.get('username') for row in active_sessions if row.get('username')}
                st.metric("Currently Logged In", len(active_usernames))
            
            # Show expired sessions count
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM sessions
                WHERE status != 'active' OR expires_at <= NOW()
            """)
            expired_count = int(cursor.fetchone()['count'] or 0)
            
            with col3:
                st.metric("Expired Sessions", expired_count, delta="⚠️" if expired_count > 0 else None)
            
            # ========================================
            # RECOMMENDATION 2: Connection Pool Metrics
            # ========================================
            st.markdown("---")
            st.subheader("🔌 Connection Pool Status")
            
            # Query connection pool utilization
            cursor.execute("""
                SELECT 
                    COUNT(*) as active_connections,
                    COUNT(DISTINCT tunnel_id) as active_tunnels,
                    COUNT(DISTINCT session_id) as sessions_with_connections
                FROM connection_monitor
                WHERE status = 'active'
            """)
            pool_stats = cursor.fetchone()
            active_connections = int(pool_stats['active_connections'] or 0)
            active_tunnels = int(pool_stats['active_tunnels'] or 0)
            sessions_with_connections = int(pool_stats['sessions_with_connections'] or 0)
            
            # Calculate utilization
            MAX_TOTAL_CONNECTIONS = 100  # 10 tunnels × 10 connections
            SOFT_LIMIT = 90
            capacity_pct = (active_connections / MAX_TOTAL_CONNECTIONS) * 100
            soft_limit_warning = active_connections >= SOFT_LIMIT
            
            # Display metrics
            pool_col1, pool_col2, pool_col3, pool_col4 = st.columns(4)
            
            with pool_col1:
                st.metric(
                    "Active Connections", 
                    f"{active_connections}/{MAX_TOTAL_CONNECTIONS}",
                    delta=f"{capacity_pct:.0f}% capacity",
                    delta_color="off" if capacity_pct < 75 else "normal"
                )
            
            with pool_col2:
                st.metric(
                    "Active Tunnels",
                    f"{active_tunnels}/10",
                    help="SSH tunnels in use"
                )
            
            with pool_col3:
                st.metric(
                    "Sessions with Connections",
                    sessions_with_connections,
                    help="Unique sessions holding connections"
                )
            
            with pool_col4:
                if soft_limit_warning:
                    st.metric(
                        "Status",
                        "⚠️ HIGH",
                        delta=f"{MAX_TOTAL_CONNECTIONS - active_connections} available",
                        delta_color="inverse"
                    )
                elif capacity_pct > 75:
                    st.metric(
                        "Status",
                        "⚡ BUSY",
                        delta=f"{MAX_TOTAL_CONNECTIONS - active_connections} available",
                        delta_color="normal"
                    )
                else:
                    st.metric(
                        "Status",
                        "✅ OK",
                        delta=f"{MAX_TOTAL_CONNECTIONS - active_connections} available",
                        delta_color="off"
                    )
            
            # Capacity warning banner
            if capacity_pct >= 85:
                st.warning(f"⚠️ **High Capacity**: System at {capacity_pct:.0f}% capacity ({active_connections}/{MAX_TOTAL_CONNECTIONS} connections). New users may experience slower service or be temporarily blocked above 90%.")
            elif soft_limit_warning:
                st.info(f"ℹ️ **Approaching Soft Limit**: {active_connections}/{MAX_TOTAL_CONNECTIONS} connections active. New user logins will be restricted above 90 connections.")
            
            # Per-tunnel breakdown
            with st.expander("📊 Per-Tunnel Connection Distribution"):
                cursor.execute("""
                    SELECT 
                        tunnel_id,
                        COUNT(*) as conn_count,
                        COUNT(DISTINCT session_id) as session_count,
                        COUNT(DISTINCT username) as user_count
                    FROM connection_monitor
                    WHERE status = 'active'
                    GROUP BY tunnel_id
                    ORDER BY conn_count DESC
                """)
                tunnel_breakdown = cursor.fetchall()
                
                if tunnel_breakdown:
                    df_tunnels = pd.DataFrame(tunnel_breakdown)
                    st.dataframe(df_tunnels, hide_index=True, use_container_width=True)
                    
                    # Show warning if any tunnel over capacity
                    max_per_tunnel = 10
                    overloaded = [t for t in tunnel_breakdown if t['conn_count'] > max_per_tunnel]
                    if overloaded:
                        st.warning(f"⚠️ {len(overloaded)} tunnel(s) over capacity limit of {max_per_tunnel} connections")
                else:
                    st.info("No active connections")
            
            st.markdown("---")
            
            # Cleanup buttons
            col_btn1, col_btn2, col_btn3 = st.columns(3)

            with col_btn1:
                if expired_count > 0:
                    if st.button("🧹 Clean Up Expired Sessions", type="secondary"):
                        try:
                            from app_mysql import cleanup_expired_sessions
                            expired = cleanup_expired_sessions()
                            st.success(f"✅ Marked {expired} session(s) expired")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Cleanup failed: {e}")

            with col_btn3:
                if st.button("🗑️ Purge Stale Connections", type="secondary",
                             help="Delete closed and 12 h+ idle rows from connection_monitor"):
                    try:
                        pool = app_mysql.get_connection_pool_instance()
                        purged = pool.cleanup_stale_connections(stale_hours=12)
                        st.success(f"✅ Purged {purged} stale connection row(s)")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Purge failed: {e}")

            with col_btn2:
                if len(active_sessions) > 0:
                    with st.popover("⚠️ Force Logout All Users"):
                        st.warning("This will immediately log out ALL users (including you on production)!")
                        if st.button("⚠️ Confirm Force Logout All", type="primary"):
                            try:
                                conn_del = app_mysql.get_connection()
                                cursor_del = conn_del.cursor()
                                cursor_del.execute("""
                                    UPDATE sessions
                                    SET status = 'forced_logout', expires_at = NOW(), last_activity = NOW()
                                    WHERE status = 'active'
                                """)
                                updated = cursor_del.rowcount
                                conn_del.commit()
                                cursor_del.close()
                                st.success(f"✅ Forced logout for all users ({updated} session(s) invalidated)")
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ Force logout failed: {e}")
            
            if active_sessions:
                st.subheader("🟢 Currently Logged In Users")
                df_active = pd.DataFrame(active_sessions)
                df_active['login_time'] = pd.to_datetime(df_active['login_time'])
                df_active['expires_at'] = pd.to_datetime(df_active['expires_at'])
                # Convert hours to int
                df_active['hours_until_expire'] = df_active['hours_until_expire'].astype(int)
                # Reorder columns for better display
                column_order = ['username', 'email', 'app_name', 'device_type', 'browser', 
                               'login_time', 'hours_until_expire', 'ip_address']
                # Only include columns that exist
                display_cols = [col for col in column_order if col in df_active.columns]
                st.dataframe(df_active[display_cols], width='stretch', hide_index=True)
                st.caption("💡 Active sessions expire after 7 days of inactivity (sliding). Sessions are invalidated on logout/force-logout/expiry.")
                
                # Force logout specific users
                st.subheader("🚪 Force Logout Selected Users")
                
                # Create list of usernames for selection
                usernames = sorted({session.get('username') for session in active_sessions if session.get('username')})
                
                selected_users = st.multiselect(
                    "Select users to force logout:",
                    options=usernames,
                    help="Selected users will be immediately logged out from all their sessions"
                )
                
                if selected_users:
                    col_warn, col_btn = st.columns([3, 1])
                    with col_warn:
                        st.warning(f"⚠️ This will log out {len(selected_users)} user(s): {', '.join(selected_users)}")
                    with col_btn:
                        if st.button("🚪 Force Logout Selected", type="primary"):
                            try:
                                conn_logout = app_mysql.get_connection()
                                cursor_logout = conn_logout.cursor()
                                
                                # Invalidate sessions for selected users (preserve history)
                                placeholders = ', '.join(['%s'] * len(selected_users))
                                query = f"""
                                    UPDATE sessions s
                                    JOIN users u ON s.user_id = u.user_id
                                    SET s.status = 'forced_logout', s.expires_at = NOW(), s.last_activity = NOW()
                                    WHERE s.status = 'active' AND u.username IN ({placeholders})
                                """
                                cursor_logout.execute(query, tuple(selected_users))
                                updated = cursor_logout.rowcount
                                conn_logout.commit()
                                cursor_logout.close()
                                
                                st.success(f"✅ Forced logout {len(selected_users)} user(s), invalidated {updated} session(s)")
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ Force logout failed: {e}")
            else:
                st.info("No users currently logged in")
            
            # Show expired sessions if any
            if expired_count > 0:
                with st.expander(f"⚠️ View {expired_count} Expired Sessions (not yet cleaned up)"):
                    cursor.execute("""
                        SELECT u.username, u.email, s.created_at as login_time, s.expires_at
                        FROM sessions s
                        JOIN users u ON s.user_id = u.user_id
                        WHERE s.status != 'active' OR s.expires_at <= NOW()
                        ORDER BY s.expires_at DESC
                    """)
                    expired_sessions = cursor.fetchall()
                    if expired_sessions:
                        df_expired = pd.DataFrame(expired_sessions)
                        df_expired['login_time'] = pd.to_datetime(df_expired['login_time'])
                        df_expired['expires_at'] = pd.to_datetime(df_expired['expires_at'])
                        st.dataframe(df_expired, width='stretch', hide_index=True)
            
            st.divider()
            
            # Get recent users
            cursor.execute("""
                SELECT username, email, created_at 
                FROM users 
                ORDER BY created_at DESC 
                LIMIT 20
            """)
            users = cursor.fetchall()
            
            if users:
                st.subheader("Recent Users")
                df = pd.DataFrame(users)
                df['created_at'] = pd.to_datetime(df['created_at'])
                st.dataframe(df, width='stretch', hide_index=True)
            else:
                st.info("No users found")
            
            # Get user activity stats
            try:
                cursor.execute("""
                    SELECT 
                        DATE(created_at) as date,
                        COUNT(*) as signups
                    FROM users
                    WHERE created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
                    GROUP BY DATE(created_at)
                    ORDER BY date DESC
                """)
                activity = cursor.fetchall()
                
                if activity:
                    st.subheader("Signups (Last 30 Days)")
                    df_activity = pd.DataFrame(activity)
                    st.line_chart(df_activity.set_index('date'))
            except Exception as e:
                st.warning(f"Could not load activity stats: {e}")
            
            cursor.close()
                
        except Exception as e:
            st.error(f"Database error: {e}")
            st.info("💡 The SSH tunnel may have timed out. Try:")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🔄 Retry Connection"):
                    st.cache_resource.clear()
                    st.rerun()
            with col2:
                if st.button("📊 Reload Page"):
                    st.rerun()
        finally:
            pass  # Don't close - session-persistent connection
    else:
        st.warning("Database connection not available. User data not accessible.")
        if st.button("🔄 Retry Connection", key="retry_no_conn"):
            st.cache_resource.clear()
            st.rerun()

# TAB 3: Logs
if selected_page == "📝 Logs":
    st.header("📝 Recent Logs")
    
    # Debug Logs from Database
    st.subheader("🔧 Debug Logs (Database)")
    st.caption("Session validation, forced logouts, and errors")
    
    col1, col2 = st.columns(2)
    with col1:
        log_limit = st.number_input("Limit", min_value=10, max_value=1000, value=100, step=10, key="log_limit")
        event_filter = st.selectbox(
            "Event Type",
            ['All', 'forced_logout', 'session_validation_failed', 'session_validation_error', 'audio_error', 'database_error'],
            index=0,
            key="event_filter"
        )
    with col2:
        env_filter = st.selectbox("Environment", ['All', 'local', 'deployed'], index=0, key="env_filter")
        username_filter = st.text_input("Username (optional)", key="username_filter")
    
    if st.button("🔄 Refresh Logs", key="refresh_debug_logs"):
        st.rerun()
    
    # Fetch logs from database
    try:
        logs = app_mysql.get_debug_logs(
            limit=int(log_limit),
            event_type=None if event_filter == 'All' else event_filter,
            username=username_filter if username_filter else None,
            environment=None if env_filter == 'All' else env_filter
        )
        
        if logs:
            st.markdown(f"**Showing {len(logs)} logs (newest first)**")
            
            for log in logs:
                timestamp = log['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
                event_type = log['event_type']
                username = log['username'] or 'anonymous'
                env = log['environment']
                message = log['message']
                user_agent = log['user_agent'] or 'N/A'
                session_partial = log['session_id_partial'] or 'N/A'
                
                # Color code by event type
                if 'error' in event_type:
                    emoji = "❌"
                elif 'logout' in event_type:
                    emoji = "🚪"
                elif 'failed' in event_type:
                    emoji = "⚠️"
                else:
                    emoji = "ℹ️"
                
                with st.expander(f"{emoji} {timestamp} | {env} | {event_type} | {username}", expanded=False):
                    st.markdown(f"**Message:** {message}")
                    if 'iPhone' in user_agent or 'iOS' in user_agent:
                        st.markdown(f"📱 **iPhone/iOS detected**: `{user_agent[:100]}...`")
                    elif user_agent != 'N/A':
                        st.markdown(f"**User Agent:** `{user_agent[:100]}...`")
                    st.markdown(f"**Session ID:** `{session_partial}`")
        else:
            st.info("No logs found matching filters")
    
    except Exception as e:
        st.error(f"Failed to load debug logs: {e}")
    
    st.markdown("---")
    
    # Check for Streamlit Cloud logs
    st.info("For production deployment logs, check Streamlit Cloud dashboard: https://share.streamlit.io/")
    
    # Local log viewer
    st.subheader("Local Application Events")
    
    # Look for practice history files (user activity indicator)
    history_file = Path("practice_history.json")
    if history_file.exists():
        try:
            with open(history_file, 'r') as f:
                history = json.load(f)
            
            if isinstance(history, list) and len(history) > 0:
                st.metric("Local Practice Sessions", len(history))
                
                # Show recent sessions
                st.write("**Recent Sessions:**")
                recent = history[-10:][::-1]  # Last 10, reversed
                
                for i, session in enumerate(recent, 1):
                    with st.expander(f"Session {i} - {session.get('timestamp', 'Unknown time')}"):
                        st.json(session)
            else:
                st.info("No practice history recorded")
        except Exception as e:
            st.warning(f"Could not read practice history: {e}")
    else:
        st.info("No local practice history file found")
    
    # Database activity logs
    conn_logs = app_mysql.get_connection()
    if conn_logs:
        try:
            cursor = conn_logs.cursor(dictionary=True)
            
            # Try to get recent sessions if table exists
            try:
                cursor.execute("""
                    SELECT * FROM practice_sessions 
                    ORDER BY created_at DESC 
                    LIMIT 20
                """)
                sessions = cursor.fetchall()
                
                if sessions:
                    st.subheader("Recent Practice Sessions (Database)")
                    df = pd.DataFrame(sessions)
                    st.dataframe(df, width='stretch', hide_index=True)
            except Exception as e:
                st.info("Practice sessions table not available")
            
            cursor.close()
        except Exception as e:
            st.warning(f"Could not fetch logs: {e}")
        finally:
            try:
                conn_logs.close()
            except:
                pass

# TAB 4: Email Monitor
if selected_page == "📧 Email":
    st.header("📧 Email Monitor")
    st.caption("Read-only monitoring of io@miolingo.io")
    
    try:
        import sys
        from pathlib import Path
        
        # Add admin-sources to path
        admin_sources = Path(__file__).parent.parent / "docs" / "admin-docs" / "sources"
        if str(admin_sources) not in sys.path:
            sys.path.insert(0, str(admin_sources))
        
        from email_monitor import EmailMonitor
        
        # Initialize monitor
        try:
            monitor = EmailMonitor()
            
            # Show connection status
            col1, col2, col3 = st.columns([2, 1, 1])
            
            with col1:
                if st.button("🔄 Refresh Emails"):
                    st.rerun()
            
            with col2:
                if st.button("🔌 Test Connection"):
                    with st.spinner("Testing connection..."):
                        success, message = monitor.test_connection()
                        if success:
                            st.success(message)
                        else:
                            st.error(message)
            
            with col3:
                try:
                    unread = monitor.get_unread_count()
                    st.metric("Unread", unread)
                except Exception as e:
                    st.warning(f"Could not get unread count: {e}")
            
            st.divider()
            
            # Fetch and display emails
            with st.spinner("Fetching emails..."):
                try:
                    emails = monitor.fetch_recent_emails(limit=30)
                    
                    if emails:
                        st.info(f"📬 Showing {len(emails)} most recent emails (read-only mode)")
                        
                        # Display each email
                        for email_data in emails:
                            with st.expander(
                                f"**{email_data['subject']}** - {email_data['from']} - {email_data['date'].strftime('%Y-%m-%d %H:%M')}",
                                expanded=False
                            ):
                                col1, col2 = st.columns([1, 3])
                                
                                with col1:
                                    st.write("**From:**")
                                    st.write("**Date:**")
                                    st.write("**ID:**")
                                
                                with col2:
                                    st.write(email_data['from'])
                                    st.write(email_data['date'].strftime('%Y-%m-%d %H:%M:%S'))
                                    st.code(email_data['id'], language=None)
                                
                                st.write("**Preview:**")
                                st.info(email_data['preview'])
                                
                                st.caption("ℹ️ Read-only mode - emails cannot be modified or deleted from this interface")
                    else:
                        st.info("📭 No emails found")
                
                except Exception as e:
                    st.error(f"❌ Error fetching emails: {e}")
                    st.caption("Check that email credentials are configured in .streamlit/secrets.toml")
        
        except ValueError as e:
            st.warning("⚠️ Email monitoring not configured")
            st.info("""
            To enable email monitoring, add the following to `.streamlit/secrets.toml`:
            
            ```toml
            [email]
            imap_server = "mail.yourdomain.com"
            imap_port = 993
            email_address = "io@miolingo.io"
            email_password = "your_password"
            ```
            """)
            st.caption(f"Configuration error: {e}")
    
    except ImportError:
        st.error("❌ Email monitor module not found")
        st.caption("Make sure email_monitor.py is in the admin-sources directory")

# TAB 5: Announcements
if selected_page == "📢 Announcements":
    st.header("📢 Announcements")
    st.caption("Manage system and feature announcements for users")
    
    # System Announcements Section
    st.subheader("⚠️ System Announcements")
    st.caption("Urgent messages (maintenance, downtime, etc.) - displayed in orange")
    
    system_templates = [
        "Custom message...",
        "⚠️ System maintenance in progress - some features may be unavailable",
        "⚠️ App will restart in 10 minutes - please save your work!",
        "⚠️ App will restart in 1 hour - please save your work!",
        "⚠️ Scheduled maintenance tonight at 11 PM GMT - expect brief downtime",
        "⚠️ Database maintenance in progress - progress tracking temporarily unavailable",
    ]
    
    system_template = st.selectbox("System Announcement Template", system_templates, key="system_template")
    
    if system_template == "Custom message...":
        system_message = st.text_area("Custom system message", key="system_message_custom", height=100)
    else:
        system_message = st.text_area("System message", value=system_template, key="system_message", height=100)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        system_show_login = st.checkbox("Show on login page", value=True, key="system_login")
    with col2:
        system_show_app = st.checkbox("Show in main app", value=True, key="system_app")
    
    # Determine display_on for system
    if system_show_login and system_show_app:
        system_display_on = 'both'
    elif system_show_login:
        system_display_on = 'login'
    elif system_show_app:
        system_display_on = 'app'
    else:
        system_display_on = 'both'  # Default if neither checked
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📢 Publish System Announcement", type="primary", key="publish_system"):
            if system_message.strip():
                if app_mysql.create_announcement('system', system_message.strip(), system_display_on):
                    st.success("✅ System announcement published!")
                    st.cache_data.clear()  # Clear cache to show immediately
                    time.sleep(1)
                    st.rerun()
            else:
                st.error("❌ Message cannot be empty")
    
    with col2:
        if st.button("🗑️ Clear System Announcement", key="clear_system"):
            if app_mysql.clear_announcement('system'):
                st.success("✅ System announcement cleared")
                st.cache_data.clear()  # Clear cache to update immediately
                time.sleep(1)
                st.rerun()
    
    st.markdown("---")
    
    # Feature Announcements Section
    st.subheader("✨ Feature Announcements")
    st.caption("New features, updates, improvements - displayed in green")
    
    feature_templates = [
        "Custom message...",
        "✨ New feature: Multi-language support now available!",
        "✨ New: Language materials browser with curated content",
        "✨ Improved: Better pronunciation scoring algorithm",
        "✨ New: Progress tracking dashboard for all languages",
        "✨ Updated: Enhanced audio quality with Google Cloud TTS",
        "✨ New: Export your practice history and statistics",
    ]
    
    feature_template = st.selectbox("Feature Announcement Template", feature_templates, key="feature_template")
    
    if feature_template == "Custom message...":
        feature_message = st.text_area("Custom feature message", key="feature_message_custom", height=100)
    else:
        feature_message = st.text_area("Feature message", value=feature_template, key="feature_message", height=100)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        feature_show_login = st.checkbox("Show on login page", value=False, key="feature_login")
    with col2:
        feature_show_app = st.checkbox("Show in main app", value=True, key="feature_app")
    
    # Determine display_on for feature
    if feature_show_login and feature_show_app:
        feature_display_on = 'both'
    elif feature_show_login:
        feature_display_on = 'login'
    elif feature_show_app:
        feature_display_on = 'app'
    else:
        feature_display_on = 'both'  # Default if neither checked
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📢 Publish Feature Announcement", type="primary", key="publish_feature"):
            if feature_message.strip():
                if app_mysql.create_announcement('feature', feature_message.strip(), feature_display_on):
                    st.success("✅ Feature announcement published!")
                    st.cache_data.clear()  # Clear cache to show immediately
                    time.sleep(1)
                    st.rerun()
            else:
                st.error("❌ Message cannot be empty")
    
    with col2:
        if st.button("🗑️ Clear Feature Announcement", key="clear_feature"):
            if app_mysql.clear_announcement('feature'):
                st.success("✅ Feature announcement cleared")
                st.cache_data.clear()  # Clear cache to update immediately
                time.sleep(1)
                st.rerun()
    
    st.markdown("---")
    st.info("💡 Announcements are cached for 60 seconds. Users will see updates within 1 minute.")

# TAB 6: Settings
if selected_page == "⚙️ Settings":
    st.header("⚙️ Settings & Configuration")
    
    st.subheader("🔑 Secrets Status")
    
    # Check for secrets
    try:
        has_gcloud = ("google_cloud_tts_api_key" in st.secrets) or ("google_cloud_tts" in st.secrets)
        
        secrets_available = {
            "Google Cloud TTS": has_gcloud,
            "MySQL Database": "mysql" in st.secrets,
            "SSH Tunnel": "ssh" in st.secrets,
        }
        
        for service, available in secrets_available.items():
            if available:
                st.success(f"✓ {service} configured")
            else:
                st.warning(f"✗ {service} not configured")
    except:
        st.error("No secrets file found. Create `.streamlit/secrets.toml`")
    
    st.subheader("📦 Installed Packages")
    
    # Check key dependencies
    packages = {
        "streamlit": "Web framework",
        "whisper": "Speech recognition",
        "gtts": "Text-to-speech (free)",
        "mysql.connector": "Database",
        "sshtunnel": "SSH tunneling",
        "soundfile": "Audio processing",
        "numpy": "Numerical processing",
    }
    
    for package, description in packages.items():
        try:
            __import__(package.replace("-", "_"))
            st.success(f"✓ {package} - {description}")
        except ImportError:
            st.error(f"✗ {package} - {description} (not installed)")
    
    st.subheader("🔄 Quick Actions")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🗑️ Clear Cache"):
            st.cache_data.clear()
            st.cache_resource.clear()
            st.success("Cache cleared!")
            st.rerun()
    
    with col2:
        if st.button("📊 Reload Data"):
            st.rerun()

# Auto-refresh sleep AFTER page renders
if st.session_state.get('auto_refresh_enabled', False):
    import time
    time.sleep(REFRESH_INTERVAL_MINUTES * 60)  # Convert minutes to seconds
    st.rerun()