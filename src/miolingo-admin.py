#!/usr/bin/env python3
"""
Miolingo Admin Dashboard

Local admin interface for monitoring resource usage, users, and logs.
Run with: streamlit run miolingo-admin.py --server.port 8505 --server.headless=true
Then open: http://localhost:8505

Version: 1.4.1
"""

import streamlit as st
import json
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
from collections import defaultdict
import time
import app_mysql
from contextlib import contextmanager

# Page config
st.set_page_config(
    page_title="Miolingo Admin",
    page_icon="🔧",
    layout="wide"
)

st.title("🔧 Miolingo Admin Dashboard")
st.caption("Local monitoring and management interface • v1.4.2")

# Quick reconnect button in sidebar
with st.sidebar:
    st.subheader("🔧 Quick Actions")
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

# Database connection helper with automatic cleanup
@contextmanager
def get_db_connection_context():
    """
    Context manager for database connections with automatic cleanup.
    
    Usage:
        with get_db_connection_context() as conn:
            if conn:
                cursor = conn.cursor()
                # ... use connection ...
                cursor.close()
    
    Ensures connection is always returned to pool, even if error occurs.
    """
    conn = None
    try:
        from app_mysql import get_connection
        conn = get_connection()
        yield conn
    except Exception as e:
        error_msg = str(e)
        
        # Provide user-friendly error message with fix suggestion
        if "2013" in error_msg or "Lost connection" in error_msg:
            st.error(f"⚠️ **Database Connection Lost**\n\n{error_msg}\n\n💡 **Fix:** Click '🔄 Clear Cache & Reconnect' in the sidebar, then refresh your browser.")
        elif "Can not reconnect" in error_msg:
            st.error(f"⚠️ **Cannot Reconnect to Database**\n\n{error_msg}\n\n💡 **Fix:** Click '🔄 Clear Cache & Reconnect' in the sidebar, then refresh your browser. If the problem persists, check if the database server is running.")
        else:
            st.error(f"⚠️ **Database Connection Error**\n\n{error_msg}\n\n💡 **Try:** Refresh your browser. If the error persists, click '🔄 Clear Cache & Reconnect' in the sidebar.")
        
        yield None
    finally:
        # Always return connection to pool
        if conn is not None:
            try:
                conn.close()
            except:
                pass


# Legacy function for backward compatibility (DEPRECATED - use context manager instead)
def get_db_connection():
    """
    DEPRECATED: Get database connection without automatic cleanup.
    Use get_db_connection_context() instead for proper resource management.
    
    Returns connection and None (for backward compatibility with old tunnel return).
    """
    try:
        from app_mysql import get_connection
        conn = get_connection()
        return conn, None
    except Exception as e:
        error_msg = str(e)
        if "2013" in error_msg or "Lost connection" in error_msg:
            st.error(f"⚠️ **Database Connection Lost**\n\n{error_msg}\n\n💡 **Fix:** Click '🔄 Clear Cache & Reconnect' in the sidebar, then refresh your browser.")
        elif "Can not reconnect" in error_msg:
            st.error(f"⚠️ **Cannot Reconnect to Database**\n\n{error_msg}\n\n💡 **Fix:** Click '🔄 Clear Cache & Reconnect' in the sidebar, then refresh your browser. If the problem persists, check if the database server is running.")
        else:
            st.error(f"⚠️ **Database Connection Error**\n\n{error_msg}\n\n💡 **Try:** Refresh your browser. If the error persists, click '🔄 Clear Cache & Reconnect' in the sidebar.")
        return None, None

# Tab layout
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["📊 Resource Usage", "👥 Users", "📝 Logs", "📧 Email", "📢 Announcements", "⚙️ Settings"])

# TAB 1: Resource Usage
with tab1:
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
                conn, tunnel = get_db_connection()
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
                    finally:
                        conn.close()
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
        conn, tunnel = get_db_connection()
        if conn:
            try:
                st.success("✓ Database connected")
            finally:
                conn.close()
        else:
            st.warning("✗ Database not connected")

# TAB 2: Users
with tab2:
    st.header("👥 Current Users")
    
    conn, tunnel = get_db_connection()
    
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            
            # Get user count
            cursor.execute("SELECT COUNT(*) as count FROM users")
            user_count = cursor.fetchone()['count']
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Users", user_count)
            
            # Get guest user counts
            cursor.execute("""
                SELECT COUNT(*) as count FROM users 
                WHERE username LIKE 'guest_%' 
                AND created_at > DATE_SUB(NOW(), INTERVAL 24 HOUR)
            """)
            active_guests = cursor.fetchone()['count']
            
            cursor.execute("""
                SELECT COUNT(*) as count FROM users 
                WHERE username LIKE 'guest_%'
            """)
            total_guests = cursor.fetchone()['count']
            
            with col2:
                st.metric("Active Guests (24h)", active_guests, 
                         delta="⚠️ At limit" if active_guests >= 3 else None)
            
            with col3:
                st.metric("Total Guest Accounts", total_guests,
                         delta="⚠️ Cleanup needed" if total_guests > 10 else None)
            
            # Get currently logged-in users (active sessions)
            cursor.execute("""
                SELECT u.username, u.email, s.created_at as login_time, s.expires_at, s.ip_address,
                       TIMESTAMPDIFF(HOUR, NOW(), s.expires_at) as hours_until_expire
                FROM sessions s
                JOIN users u ON s.user_id = u.user_id
                WHERE s.expires_at > NOW()
                ORDER BY s.created_at DESC
            """)
            active_sessions = cursor.fetchall()
            
            with col4:
                st.metric("Currently Logged In", len(active_sessions))
            
            # Show expired sessions count
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM sessions
                WHERE expires_at <= NOW()
            """)
            expired_count = int(cursor.fetchone()['count'] or 0)
            
            # Display in a new row if needed
            if expired_count > 0:
                st.warning(f"⚠️ {expired_count} expired sessions need cleanup")
            
            # Cleanup buttons
            col_btn1, col_btn2 = st.columns(2)
            
            with col_btn1:
                if expired_count > 0:
                    if st.button("🧹 Clean Up Expired Sessions", type="secondary"):
                        try:
                            from app_mysql import cleanup_expired_sessions
                            deleted = cleanup_expired_sessions()
                            st.success(f"✅ Removed {deleted} expired sessions")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Cleanup failed: {e}")
            
            with col_btn2:
                if len(active_sessions) > 0:
                    with st.popover("⚠️ Force Logout All Users"):
                        st.warning("This will immediately log out ALL users (including you on production)!")
                        if st.button("⚠️ Confirm Force Logout All", type="primary"):
                            conn_del = None
                            try:
                                conn_del = get_db_connection()[0]
                                cursor_del = conn_del.cursor()
                                cursor_del.execute("DELETE FROM sessions")
                                deleted = cursor_del.rowcount
                                conn_del.commit()
                                cursor_del.close()
                                st.success(f"✅ Logged out all users ({deleted} sessions removed)")
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ Force logout failed: {e}")
                            finally:
                                if conn_del:
                                    try:
                                        conn_del.close()
                                    except:
                                        pass
            
            if active_sessions:
                st.subheader("🟢 Currently Logged In Users")
                df_active = pd.DataFrame(active_sessions)
                df_active['login_time'] = pd.to_datetime(df_active['login_time'])
                df_active['expires_at'] = pd.to_datetime(df_active['expires_at'])
                # Convert hours to int
                df_active['hours_until_expire'] = df_active['hours_until_expire'].astype(int)
                st.dataframe(df_active, width='stretch', hide_index=True)
                st.caption("💡 Active sessions expire 24 hours after login. Sessions are removed on logout or cleanup.")
                
                # Force logout specific users
                st.subheader("🚪 Force Logout Selected Users")
                
                # Create list of usernames for selection
                usernames = [session['username'] for session in active_sessions]
                
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
                            conn_logout = None
                            try:
                                conn_logout = get_db_connection()[0]
                                cursor_logout = conn_logout.cursor()
                                
                                # Delete sessions for selected users
                                placeholders = ', '.join(['%s'] * len(selected_users))
                                query = f"""
                                    DELETE s FROM sessions s
                                    JOIN users u ON s.user_id = u.user_id
                                    WHERE u.username IN ({placeholders})
                                """
                                cursor_logout.execute(query, tuple(selected_users))
                                deleted = cursor_logout.rowcount
                                conn_logout.commit()
                                cursor_logout.close()
                                
                                st.success(f"✅ Logged out {len(selected_users)} user(s), removed {deleted} session(s)")
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ Force logout failed: {e}")
                            finally:
                                if conn_logout:
                                    try:
                                        conn_logout.close()
                                    except:
                                        pass
            else:
                st.info("No users currently logged in")
            
            # Show expired sessions if any
            if expired_count > 0:
                with st.expander(f"⚠️ View {expired_count} Expired Sessions (not yet cleaned up)"):
                    cursor.execute("""
                        SELECT u.username, u.email, s.created_at as login_time, s.expires_at
                        FROM sessions s
                        JOIN users u ON s.user_id = u.user_id
                        WHERE s.expires_at <= NOW()
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
            try:
                conn.close()
            except:
                pass
    else:
        st.warning("Database connection not available. User data not accessible.")
        if st.button("🔄 Retry Connection", key="retry_no_conn"):
            st.cache_resource.clear()
            st.rerun()

# TAB 3: Logs
with tab3:
    st.header("📝 Recent Logs")
    
    # Check for Streamlit Cloud logs
    st.info("For production logs, check Streamlit Cloud dashboard: https://share.streamlit.io/")
    
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
    conn_logs, tunnel_logs = get_db_connection()
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
with tab4:
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
with tab5:
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
with tab6:
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
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🗑️ Clear Cache"):
            st.cache_data.clear()
            st.cache_resource.clear()
            st.success("Cache cleared!")
            st.rerun()
    
    with col2:
        if st.button("📊 Reload Data"):
            st.rerun()
    
    with col3:
        if st.button("🧹 Clean Old Guests"):
            try:
                from app_mysql import cleanup_old_guest_users
                deleted = cleanup_old_guest_users(days_old=7)
                st.success(f"✅ Removed {deleted} old guest accounts (>7 days)")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Guest cleanup failed: {e}")

# Footer
st.divider()
st.caption("Miolingo Admin Dashboard v1.4.2 | Local monitoring interface")
