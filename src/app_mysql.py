"""
Miolingo MySQL Database Module
Handles all database operations for multi-user authentication and progress tracking.

Security features:
- Argon2id password hashing (hardened for Emerald plan)
- Parameterized queries (SQL injection prevention)
- Connection pooling (optimized for Emerald resources)
- Session management with expiration
- Rate limiting support
- Audit logging

Connection Management Pattern:
- Session connections: ONE persistent connection per Streamlit session, stored in 
  st.session_state.db_connection and reused for all queries. NEVER close these.
- Bootstrap connections: Ephemeral admin connections using context managers.
  These DO get closed automatically by the context manager.
  
IMPORTANT: Do NOT call conn.close() on session connections returned by get_connection().
The connection is stored in session_state and will be reused for the session lifetime.

Author: Miolingo Team
Version: 1.3.0
"""

import streamlit as st
import mysql.connector
from mysql.connector import pooling, Error
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any, Tuple
import json
from sshtunnel import SSHTunnelForwarder
from pathlib import Path
import atexit
import warnings
import logging
import time

# Import new connection pool module
from connection_pool import ConnectionPool

# Suppress cryptography deprecation warnings
warnings.filterwarnings('ignore', category=DeprecationWarning, module='paramiko')

# Suppress debug logging from SSH and other libraries
logging.getLogger('paramiko').setLevel(logging.WARNING)
logging.getLogger('gtts').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('fsevents').setLevel(logging.WARNING)


# ============================================================================
# PASSWORD HASHING (Hardened for Emerald Plan)
# ============================================================================

# Argon2id password hasher - memory-hard, GPU-resistant
# Parameters optimized for Emerald plan resources
pwd_hasher = PasswordHasher(
    time_cost=4,        # 4 iterations (hardened from default 3)
    memory_cost=102400, # 100 MB per hash (hardened from default 64 MB)
    parallelism=8,      # 8 threads (hardened from default 4)
    hash_len=32,        # 32-byte hash output
    salt_len=16         # 16-byte random salt per password
)


# ============================================================================
# SSH TUNNEL & CONNECTION POOLING (Secure, Optimized for Emerald Plan)
# ============================================================================

# Global SSH tunnel shared across ALL Streamlit sessions
# This prevents creating multiple tunnels and hitting server connection limits
_global_ssh_tunnel = None

# Global connection pool instance (NEW POOLING ARCHITECTURE)
# Manages 10 tunnels × 10 connections = 100 total capacity
_global_connection_pool: Optional[ConnectionPool] = None


def get_connection_pool_instance() -> ConnectionPool:
    """
    Get or create the global ConnectionPool instance.
    This replaces the old single-tunnel architecture with proper pooling.
    """
    global _global_connection_pool
    
    if _global_connection_pool is None:
        # Build secrets config for ConnectionPool
        secrets_config = {
            'ssh': dict(st.secrets["ssh"]),
            'mysql': dict(st.secrets["mysql"])
        }
        
        # Create pool instance
        _global_connection_pool = ConnectionPool(secrets_config)
        
        # Initialize monitoring tables
        success, message = _global_connection_pool.init_monitoring_tables()
        if not success:
            logging.warning(f"Could not initialize monitoring tables: {message}")
    
    return _global_connection_pool


def get_ssh_tunnel() -> SSHTunnelForwarder:
    """
    Get or create SSH tunnel to MySQL server.
    Encrypts all database traffic via SSH tunnel.
    Uses st.session_state to prevent duplicate tunnels across Streamlit reruns.
    
    CRITICAL: Uses global (not session_state) to share tunnel across ALL sessions.
    This prevents creating multiple tunnels and hitting server connection limits.
    
    Implements health checking and automatic reconnection:
    - Checks if existing tunnel is still alive
    - Recreates tunnel if it died
    - Shares ONE tunnel across all users (efficient resource usage)
    - Tracks tunnel creation for debugging
    
    Supports two modes for SSH key:
    1. Local development: key_path in secrets (file path)
    2. Streamlit Cloud: key_content in secrets (paste private key directly)
    """
    # Use a global variable to share tunnel across ALL Streamlit sessions
    # This is critical to prevent multiple tunnels from accumulating
    global _global_ssh_tunnel
    
    # Check if we have an existing tunnel and if it's still alive
    if '_global_ssh_tunnel' in globals() and _global_ssh_tunnel is not None:
        tunnel = _global_ssh_tunnel
        # Verify tunnel is active and transport is connected
        try:
            if tunnel.is_active and tunnel.tunnel_is_up.get(tunnel.remote_bind_address):
                # Tunnel is healthy, return it
                return tunnel
        except:
            pass
        
        # Tunnel died, clean it up
        try:
            tunnel.stop()
        except:
            pass
        _global_ssh_tunnel = None
    
    # Create new tunnel
    try:
        import paramiko
        from io import StringIO
        
        # Ensure port is integer
        ssh_port = int(st.secrets["ssh"]["port"])
        
        # Handle SSH key - either from file path or direct content
        if "key_content" in st.secrets["ssh"]:
            # Streamlit Cloud: parse key content into paramiko key object
            key_content = st.secrets["ssh"]["key_content"]
            key_file = StringIO(key_content)
            
            # Try different key types
            ssh_key = None
            for key_class in (paramiko.Ed25519Key, paramiko.RSAKey, paramiko.ECDSAKey):
                try:
                    key_file.seek(0)
                    ssh_key = key_class.from_private_key(key_file)
                    break
                except Exception:
                    continue
            
            if ssh_key is None:
                raise ValueError("Could not parse SSH key - unsupported key type")
        else:
            # Local development: use key file path
            ssh_key_path = Path(st.secrets["ssh"]["key_path"]).expanduser().resolve()
            ssh_key = str(ssh_key_path)
        
        # Remote MySQL is on the SSH server itself (localhost from SSH server's perspective)
        # Don't specify local_bind_address to let sshtunnel auto-select an available port
        # This avoids port conflicts and allows tunnel reuse across sessions
        tunnel = SSHTunnelForwarder(
            (st.secrets["ssh"]["host"], ssh_port),
            ssh_username=st.secrets["ssh"]["username"],
            ssh_pkey=ssh_key,
            remote_bind_address=('127.0.0.1', 3306),  # MySQL on SSH server
            set_keepalive=30.0  # Keep connection alive with 30s heartbeat
        )
        tunnel.start()
        
        # Store in global variable so it's shared across ALL Streamlit sessions
        _global_ssh_tunnel = tunnel
        
        # Log tunnel creation for debugging
        import logging
        logging.info(f"SSH tunnel created on local port {tunnel.local_bind_port}")
        
    except Exception as e:
        st.error(f"❌ SSH tunnel failed: {e}")
        raise
    
    return _global_ssh_tunnel


def get_connection_pool() -> pooling.MySQLConnectionPool:
    """
    DEPRECATED: Old connection pool function (single tunnel architecture).
    Kept for backward compatibility during transition.
    
    NEW CODE SHOULD USE: get_connection() which now uses ConnectionPool internally.
    """
    if "mysql_pool" not in st.session_state:
        try:
            # Establish SSH tunnel first
            tunnel = get_ssh_tunnel()
            
            st.session_state.mysql_pool = pooling.MySQLConnectionPool(
                pool_name="miolingo_pool",
                pool_size=10,  # Increased for Emerald plan resources
                pool_reset_session=True,  # Reset session variables on get
                host='127.0.0.1',  # Connect via SSH tunnel
                port=tunnel.local_bind_port,  # Tunnel's local port
                database=st.secrets["mysql"]["database"],
                user=st.secrets["mysql"]["user"],
                password=st.secrets["mysql"]["password"],
                autocommit=False,  # Explicit transaction control
                connection_timeout=10,
                # Connection health parameters
                use_pure=True,  # Use pure Python implementation (more stable)
                # MySQL session variables to prevent timeout
                init_command="SET SESSION wait_timeout=28800, interactive_timeout=28800"  # 8 hours
            )
        except Error as e:
            st.error(f"❌ Database connection pool failed: {e}")
            raise
    
    return st.session_state.mysql_pool


def get_connection() -> mysql.connector.MySQLConnection:
    """
    Get THE session-persistent database connection (creates once, reuses for entire session).
    
    REFACTORED ARCHITECTURE (v2.1):
    - ONE connection per session (stored in st.session_state)
    - Reused for ALL database operations (no create/close on every query)
    - Auto-reconnect if connection dies (health check)
    - Connection tracked in pool and database
    - Properly implements connection pooling concept
    
    Usage:
        conn = get_connection()  # Always returns same connection for this session
        cursor = conn.cursor()
        # use connection (DON'T close it - it's persistent)
    
    Returns:
        MySQL connection (persistent for session)
    """
    # Check if we already have a session connection
    if 'db_connection' in st.session_state:
        conn = st.session_state.db_connection
        session_id = st.session_state.get('session_id', 'unknown')
        
        # Quick health check - if it fails, use bootstrap to get fresh one
        try:
            cursor = conn.cursor(buffered=True)
            cursor.execute("SELECT 1")
            cursor.fetchall()  # Consume results
            cursor.close()
            print(f"✓ Reusing session connection for {session_id[:20]}...")
            return conn
        except Exception as e:
            print(f"⚠️ Session connection failed ({e}), getting fresh connection via bootstrap...")
            
            # Clear the dead connection from session state
            del st.session_state.db_connection
            
            # Use bootstrap connection to get a fresh tracked connection
            pool = get_connection_pool_instance()
            
            # Get session info for tracking - use existing session_id from state
            fresh_session_id = st.session_state.get('session_id', f'app_{secrets.token_hex(8)}')
            user = st.session_state.get('user', {})
            username = user.get('username', 'anonymous')
            app_name = st.session_state.get('app_name', 'miolingo-app')
            
            # Store session_id if not set
            if 'session_id' not in st.session_state:
                st.session_state.session_id = fresh_session_id
            
            # Get fresh connection from pool
            fresh_conn = pool.get_tracked_connection(fresh_session_id, username, app_name)
            
            # Store in session state
            st.session_state.db_connection = fresh_conn
            
            print(f"✓ Replaced dead connection with fresh one for {session_id[:20]}...")
            return fresh_conn
    
    # No existing connection or it died - create new one
    pool = get_connection_pool_instance()
    
    # CRITICAL: Untracked → Tracked handover architecture
    # Pre-auth: Use single bootstrap connection (untracked, temporary)
    # Post-auth: Switch to tracked connection from pool (permanent until logout)
    if not st.session_state.get('authenticated', False):
        # Not authenticated - use bootstrap connection (unlimited, not tracked)
        # Store it for reuse until login, then it will be closed during handover
        if 'db_connection' not in st.session_state:
            print("⚠️ Creating bootstrap connection for unauthenticated user (temporary, not tracked)")
            conn = pool.get_bootstrap_connection()
            st.session_state.db_connection = conn
        else:
            conn = st.session_state.db_connection
            # Health check
            try:
                cursor = conn.cursor(buffered=True)
                cursor.execute("SELECT 1")
                cursor.fetchall()
                cursor.close()
                print("✓ Reusing bootstrap connection")
            except Exception as e:
                print(f"⚠️ Bootstrap connection died, getting fresh one")
                try:
                    conn.close()
                except:
                    pass
                conn = pool.get_bootstrap_connection()
                st.session_state.db_connection = conn
        return conn
    
    # Authenticated user - create tracked connection
    # Get session info for tracking
    session_id = st.session_state.get('session_id', f'app_{secrets.token_hex(8)}')
    
    # CRITICAL: Extract username from nested user dict
    user = st.session_state.get('user', {})
    username = user.get('username', 'anonymous')
    
    # Store session_id if not already set
    if 'session_id' not in st.session_state:
        st.session_state.session_id = session_id
    
    # Get tracked connection from pool with app name
    app_name = st.session_state.get('app_name', 'miolingo-app')
    conn = pool.get_tracked_connection(session_id, username, app_name)
    
    # Store in session state for reuse
    st.session_state.db_connection = conn
    
    # Store connection info for display panel
    if hasattr(pool, 'connection_registry'):
        # Find this connection in registry
        session_conns = [c for c in pool.connection_registry.values() if c.session_id == session_id]
        if session_conns:
            last_conn = max(session_conns, key=lambda c: c.created_at)
            st.session_state['_last_connection_info'] = {
                'connection_id': last_conn.connection_id,
                'mysql_conn_id': last_conn.mysql_conn_id,
                'tunnel_id': last_conn.tunnel_id,
                'created_at': last_conn.created_at,
                'status': last_conn.status
            }
            # Get tunnel info from database (single source of truth)
            db_tunnel = pool.get_tunnel_info_from_db(last_conn.tunnel_id)
            if db_tunnel:
                st.session_state['_last_tunnel_info'] = db_tunnel
    
    print(f"✓ Created new session connection: {session_id[:20]}...")
    return conn


def get_current_connection_info() -> dict:
    """
    Get information about the current connection and tunnel for display.
    CRITICAL: Reads from DATABASE, not memory - single source of truth.
    Returns a dict with connection and tunnel details, or empty dict if not available.
    """
    conn_info = st.session_state.get('_last_connection_info', {})
    
    if not conn_info:
        return {}
    
    from datetime import datetime
    now = datetime.now()
    
    # Get tunnel info from DATABASE (not memory)
    tunnel_id = conn_info.get('tunnel_id')
    tunnel_info = {}
    
    if tunnel_id:
        pool = get_connection_pool_instance()
        db_tunnel = pool.get_tunnel_info_from_db(tunnel_id)
        if db_tunnel:
            tunnel_info = db_tunnel
    
    # Calculate connection age
    created_at = conn_info.get('created_at')
    if created_at:
        age = now - created_at
        age_str = f"{age.seconds // 60}m {age.seconds % 60}s"
    else:
        age_str = "unknown"
    
    # Get session expiry
    session_expires = st.session_state.get('session_expires')
    if session_expires:
        ttl = session_expires - now
        ttl_str = f"{ttl.seconds // 60}m"
    else:
        ttl_str = "unknown"
    
    return {
        'tunnel_id': tunnel_info.get('tunnel_id', 'unknown'),
        'tunnel_pid': tunnel_info.get('pid', 'unknown'),
        'tunnel_port': tunnel_info.get('local_port', 'unknown'),
        'tunnel_created': tunnel_info.get('created_at', 'unknown'),
        'tunnel_conn_count': tunnel_info.get('connection_count', 'unknown'),
        'connection_id': conn_info.get('connection_id', 'unknown'),
        'mysql_conn_id': conn_info.get('mysql_conn_id', 'unknown'),
        'connection_created': created_at,
        'connection_age': age_str,
        'connection_status': conn_info.get('status', 'unknown'),
        'session_ttl': ttl_str,
        'current_time': now
    }


def cleanup_ssh_tunnel():
    """
    Cleanup function to properly close SSH tunnel on app exit.
    Registered with atexit to ensure cleanup happens.
    
    NOTE: This only runs when the Python process exits, not on logout.
    For logout cleanup, use cleanup_session_resources() instead.
    """
    global _global_ssh_tunnel
    
    if _global_ssh_tunnel is not None:
        try:
            if _global_ssh_tunnel.is_active:
                _global_ssh_tunnel.stop()
                logging.info("SSH tunnel closed on process exit")
        except:
            pass
        _global_ssh_tunnel = None


def cleanup_session_resources():
    """
    Cleanup resources associated with current session.
    Call this on user logout to prevent resource leaks.
    
    Strategy:
    - Close MySQL connections from pool (they'll be recreated if needed)
    - Keep SSH tunnel alive (shared across all users for efficiency)
    - Tunnel has keepalive and will auto-reconnect if needed
    """
    # Close any active MySQL connections for this session
    if "mysql_pool" in st.session_state:
        # Connections are automatically returned to pool when garbage collected
        # No need to explicitly close the pool as it's shared
        pass
    
    # Note: We intentionally DON'T close the SSH tunnel here because:
    # 1. It's shared across all users (efficient)
    # 2. Creating/destroying tunnels for each session wastes resources
    # 3. Tunnel has keepalive to stay alive between sessions
    # 4. Tunnel will auto-reconnect if it dies (health check in get_ssh_tunnel)


# Register cleanup function for process exit
atexit.register(cleanup_ssh_tunnel)


# ============================================================================
# USER MANAGEMENT
# ============================================================================

def create_guest_user() -> Optional[tuple]:
    """
    Create a temporary guest user for this session.
    Guest users have unique usernames and don't persist across sessions.
    
    Returns:
        Tuple of (user_id, username, session_id) if successful, None if failed
    """
    import secrets
    import time
    
    conn = None
    cursor = None
    
    try:
        # Generate unique username and email
        timestamp = int(time.time())
        random_suffix = secrets.token_hex(4)
        username = f"guest_{timestamp}_{random_suffix}"
        email = f"guest_{timestamp}@temp.miolingo.io"
        
        # Create with random password (won't be used)
        password = secrets.token_urlsafe(32)
        password_hash = pwd_hasher.hash(password)
        
        conn = get_connection()
        cursor = conn.cursor()
        
        query = """
            INSERT INTO users (username, email, password_hash, created_at, is_active)
            VALUES (%s, %s, %s, NOW(), TRUE)
        """
        cursor.execute(query, (username, email, password_hash))
        conn.commit()
        
        user_id = cursor.lastrowid
        
        # Log guest account creation (non-critical, swallow errors)
        try:
            log_activity(user_id, "GUEST_CREATED", f"Guest username: {username}", "system")
        except:
            pass  # Don't fail guest creation if logging fails
        
        # Create session immediately
        session_id = create_session(user_id, "127.0.0.1")
        
        if session_id:
            return (user_id, username, session_id)
        else:
            return None
        
    except Exception as e:
        if conn:
            try:
                conn.rollback()
            except:
                pass
        # Return None without calling st.error (let caller handle UI)
        return None
    
    finally:
        if cursor:
            try:
                cursor.close()
            except:
                pass
        # Don't close conn - it's a persistent session connection


def create_user(username: str, email: str, password: str) -> Optional[int]:
    """
    Create a new user account.
    
    Args:
        username: Unique username (3-20 chars, alphanumeric)
        email: Unique email address
        password: Plain text password (will be hashed with Argon2id)
    
    Returns:
        user_id if successful, None if failed
    """
    conn = None
    try:
        # Hash password with Argon2id
        password_hash = pwd_hasher.hash(password)
        
        conn = get_connection()
        cursor = conn.cursor()
        
        query = """
            INSERT INTO users (username, email, password_hash, created_at, is_active)
            VALUES (%s, %s, %s, NOW(), TRUE)
        """
        cursor.execute(query, (username, email, password_hash))
        conn.commit()
        
        user_id = cursor.lastrowid
        cursor.close()
        
        # Log account creation
        log_activity(user_id, "USER_CREATED", f"Username: {username}, Email: {email}", "system")
        
        return user_id
        
    except Error as e:
        if conn:
            conn.rollback()
        
        # Check for duplicate username/email
        if "Duplicate entry" in str(e):
            if "username" in str(e):
                st.error("❌ Username already exists. Please choose another.")
            elif "email" in str(e):
                st.error("❌ Email already registered. Please use another or login.")
        else:
            st.error(f"❌ Failed to create user: {e}")
        
        return None
    
    finally:
        pass  # Don't close conn - it's a persistent session connection


def authenticate_user(username: str, password: str) -> Optional[Dict]:
    """
    Authenticate user with username and password.
    Uses bootstrap connection to prevent creating tracked connections for failed logins.
    
    Args:
        username: Username
        password: Plain text password
    
    Returns:
        User dict {user_id, username, email} if successful, None if failed
    """
    # CRITICAL: Use bootstrap connection for authentication
    # This prevents creating tracked connections for failed login attempts
    pool = get_connection_pool_instance()
    
    try:
        with pool.get_bootstrap_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            
            query = """
                SELECT user_id, username, email, password_hash, is_active
                FROM users
                WHERE username = %s
            """
            cursor.execute(query, (username,))
            user = cursor.fetchone()
            cursor.close()
            
            if not user:
                log_activity(None, "LOGIN_FAILED", f"Username not found: {username}", "system", use_bootstrap=True)
                return None
            
            if not user['is_active']:
                log_activity(user['user_id'], "LOGIN_FAILED", "Account inactive", "system", use_bootstrap=True)
                st.error("❌ Account is inactive. Please contact support.")
                return None
            
            # Verify password with Argon2id
            try:
                pwd_hasher.verify(user['password_hash'], password)
                
                # Update last login
                cursor = conn.cursor()
                cursor.execute("UPDATE users SET last_login = NOW() WHERE user_id = %s", (user['user_id'],))
                conn.commit()
                cursor.close()
                
                # Log successful login
                log_activity(user['user_id'], "LOGIN_SUCCESS", f"Username: {username}", "system", use_bootstrap=True)
                
                return {
                    'user_id': user['user_id'],
                    'username': user['username'],
                    'email': user['email']
                }
                
            except VerifyMismatchError:
                log_activity(user['user_id'], "LOGIN_FAILED", "Invalid password", "system", use_bootstrap=True)
                return None
    
    except Error as e:
        st.error(f"❌ Authentication error: {e}")
        return None


def get_user_by_id(user_id: int) -> Optional[Dict]:
    """Get user details by user_id."""
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        query = "SELECT user_id, username, email, created_at, last_login FROM users WHERE user_id = %s"
        cursor.execute(query, (user_id,))
        user = cursor.fetchone()
        cursor.close()
        
        return user
    
    except Error as e:
        st.error(f"❌ Error fetching user: {e}")
        return None
    
    finally:
        pass  # Don't close conn - it's a persistent session connection


# ============================================================================
# SESSION MANAGEMENT
# ============================================================================

def create_session(user_id: int, ip_address: str = "unknown") -> Optional[str]:
    """
    Create a new session for authenticated user.
    Uses bootstrap connection before user's tracked connection is established.
    
    Args:
        user_id: User ID
        ip_address: Client IP address for security tracking
    
    Returns:
        session_id (32-byte secure token) if successful, None if failed
    """
    # CRITICAL: Use bootstrap connection for session creation
    # User doesn't have a tracked connection yet at this point
    pool = get_connection_pool_instance()
    
    try:
        # Generate cryptographically secure session ID
        session_id = secrets.token_urlsafe(32)
        
        # Session expires in 7 days
        expires_at = datetime.now() + timedelta(days=7)
        
        with pool.get_bootstrap_connection() as conn:
            cursor = conn.cursor()
            
            query = """
                INSERT INTO sessions (session_id, user_id, created_at, expires_at, ip_address)
                VALUES (%s, %s, NOW(), %s, %s)
            """
            cursor.execute(query, (session_id, user_id, expires_at, ip_address))
            conn.commit()
            cursor.close()
        
        log_activity(user_id, "SESSION_CREATED", f"IP: {ip_address}", ip_address, use_bootstrap=True)
        
        return session_id
        
    except Error as e:
        st.error(f"❌ Failed to create session: {e}")
        return None


def validate_session(session_id: str, ip_address: str = "unknown") -> Optional[Dict]:
    """
    Validate session and return user info.
    Uses bootstrap connection to avoid creating tracked connection before validation.
    Also checks IP address for session hijacking detection.
    
    Args:
        session_id: Session token
        ip_address: Current client IP address
    
    Returns:
        User dict if session valid, None if invalid/expired
    """
    # CRITICAL: Use bootstrap connection for session validation
    # We don't want to create a tracked connection if session is invalid
    pool = get_connection_pool_instance()
    
    try:
        with pool.get_bootstrap_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            
            query = """
                SELECT s.session_id, s.user_id, s.ip_address, s.expires_at,
                       u.username, u.email, u.is_active
                FROM sessions s
                JOIN users u ON s.user_id = u.user_id
                WHERE s.session_id = %s AND s.expires_at > NOW()
            """
            cursor.execute(query, (session_id,))
            session = cursor.fetchone()
            cursor.close()
            
            if not session:
                # Log session validation failure
                write_debug_log(
                    event_type='session_validation_failed',
                    message=f'Session not found or expired in database',
                    session_id=session_id
                )
                return None
            
            # Check if user is active
            if not session['is_active']:
                write_debug_log(
                    event_type='session_validation_failed',
                    message=f'User account is inactive',
                    username=session.get('username'),
                    user_id=session.get('user_id'),
                    session_id=session_id
                )
                return None
            
            # IP address validation (detect session hijacking)
            if session['ip_address'] != ip_address and session['ip_address'] != "unknown":
                log_activity(
                    session['user_id'],
                    "SESSION_IP_MISMATCH",
                    f"Expected: {session['ip_address']}, Got: {ip_address}",
                    ip_address,
                    use_bootstrap=True
                )
                # Still allow (IPs can change legitimately), but log for security monitoring
            
            return {
                'user_id': session['user_id'],
                'username': session['username'],
                'email': session['email']
            }
        
    except Error as e:
        # Log the error
        write_debug_log(
            event_type='session_validation_error',
            message=f'Database error during validation: {str(e)}',
            session_id=session_id
        )
        # Re-raise the exception so caller knows this is an ERROR, not expiry
        raise


def delete_session(session_id: str) -> bool:
    """
    Delete a session (logout) and properly close the connection.
    This is the ONLY time we close a connection (user explicitly logs out).
    """
    try:
        # Use the session's existing connection for the delete operation
        conn = st.session_state.get('db_connection')
        if conn:
            cursor = conn.cursor()
            
            # Get user_id before deleting
            cursor.execute("SELECT user_id FROM sessions WHERE session_id = %s", (session_id,))
            result = cursor.fetchone()
            user_id = result[0] if result else None
            
            cursor.execute("DELETE FROM sessions WHERE session_id = %s", (session_id,))
            conn.commit()
            cursor.close()
            
            if user_id:
                log_activity(user_id, "SESSION_DELETED", "User logged out", "system")
            
            # CRITICAL: Now properly close the connection after cleanup
            # This is the ONLY place we close connections (explicit logout)
            try:
                pool = get_connection_pool_instance()
                pool.close_connection(conn, session_id)
            except Exception as close_err:
                print(f"Warning: Error closing connection on logout: {close_err}")
            
            # Clear from session state
            if 'db_connection' in st.session_state:
                del st.session_state.db_connection
        
        return True
        
    except Error as e:
        st.error(f"❌ Failed to delete session: {e}")
        return False


def log_session_to_monitor(session_id: str, username: str, user_ip: str, user_agent: str, app_name: str) -> bool:
    """
    Log session details to session_monitor table for comprehensive tracking.
    This is the single source of truth for session metadata (device, browser, app).
    
    Args:
        session_id: Session ID from sessions table
        username: Username
        user_ip: Client IP address
        user_agent: Browser user agent string
        app_name: Which app created the session ('app', 'connection_monitor', 'miolingo-admin')
    
    Returns:
        True if successful, False otherwise
    """
    try:
        # Parse device type and browser from user agent
        device_type = "Desktop"
        browser = "Unknown"
        
        if user_agent and user_agent != "unknown":
            ua_lower = user_agent.lower()
            
            # Device detection
            if 'mobile' in ua_lower or 'iphone' in ua_lower or 'android' in ua_lower:
                device_type = "Mobile"
            elif 'tablet' in ua_lower or 'ipad' in ua_lower:
                device_type = "Tablet"
            
            # Browser detection
            if 'edg/' in ua_lower or 'edge' in ua_lower:
                browser = "Edge"
            elif 'chrome' in ua_lower and 'edg' not in ua_lower:
                browser = "Chrome"
            elif 'safari' in ua_lower and 'chrome' not in ua_lower:
                browser = "Safari"
            elif 'firefox' in ua_lower:
                browser = "Firefox"
            elif 'opera' in ua_lower or 'opr/' in ua_lower:
                browser = "Opera"
        
        # Calculate expiry (7 days like main session)
        expires_at = datetime.now() + timedelta(days=7)
        
        # Use bootstrap connection for logging
        pool = get_connection_pool_instance()
        
        with pool.get_bootstrap_connection() as conn:
            cursor = conn.cursor()
            
            # Insert or update session_monitor
            query = """
                INSERT INTO session_monitor 
                (session_id, username, user_ip, user_agent, device_type, browser, app_name, 
                 login_time, expires_at, last_activity, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), %s, NOW(), 'active')
                ON DUPLICATE KEY UPDATE
                    user_ip = VALUES(user_ip),
                    user_agent = VALUES(user_agent),
                    device_type = VALUES(device_type),
                    browser = VALUES(browser),
                    app_name = VALUES(app_name),
                    last_activity = NOW(),
                    status = 'active'
            """
            cursor.execute(query, (session_id, username, user_ip, user_agent, device_type, browser, app_name, expires_at))
            conn.commit()
            cursor.close()
        
        return True
        
    except Error as e:
        print(f"Warning: Failed to log session to monitor: {e}")
        return False


def cleanup_expired_sessions() -> int:
    """
    Remove expired sessions from database.
    Should be run periodically (e.g., daily cron job).
    
    Returns:
        Number of sessions deleted
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM sessions WHERE expires_at < NOW()")
        deleted_count = cursor.rowcount
        conn.commit()
        cursor.close()
        
        return deleted_count
        
    except Error as e:
        if conn:
            conn.rollback()
        return 0
    
    finally:
        pass  # Don't close conn - it's a persistent session connection


# ============================================================================
# USER SETTINGS (Per-User Configuration)
# ============================================================================

def get_user_settings(user_id: int) -> Dict[str, Any]:
    """
    Get all settings for a user as a dictionary.
    
    Args:
        user_id: User ID
    
    Returns:
        Dict of {setting_key: setting_value}
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        query = "SELECT setting_key, setting_value FROM user_settings WHERE user_id = %s"
        cursor.execute(query, (user_id,))
        rows = cursor.fetchall()
        cursor.close()
        
        # Convert to dict and deserialize JSON values
        settings = {}
        for row in rows:
            try:
                settings[row['setting_key']] = json.loads(row['setting_value'])
            except json.JSONDecodeError:
                settings[row['setting_key']] = row['setting_value']
        
        return settings
        
    except Error as e:
        st.error(f"❌ Error fetching settings: {e}")
        return {}
    

def save_user_setting(user_id: int, key: str, value: Any) -> bool:
    """
    Save a single setting for a user.
    Uses INSERT ... ON DUPLICATE KEY UPDATE for upsert behavior.
    
    Args:
        user_id: User ID
        key: Setting key (e.g., "language", "voice_variant")
        value: Setting value (will be JSON serialized)
    
    Returns:
        True if successful, False otherwise
    """
    conn = None
    try:
        # Serialize value to JSON
        value_json = json.dumps(value)
        
        conn = get_connection()
        cursor = conn.cursor()
        
        query = """
            INSERT INTO user_settings (user_id, setting_key, setting_value, updated_at)
            VALUES (%s, %s, %s, NOW())
            ON DUPLICATE KEY UPDATE setting_value = %s, updated_at = NOW()
        """
        cursor.execute(query, (user_id, key, value_json, value_json))
        conn.commit()
        cursor.close()
        
        return True
        
    except Error as e:
        if conn:
            conn.rollback()
        st.error(f"❌ Failed to save setting: {e}")
        return False
    

def delete_user_setting(user_id: int, key: str) -> bool:
    """Delete a specific setting for a user."""
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = "DELETE FROM user_settings WHERE user_id = %s AND setting_key = %s"
        cursor.execute(query, (user_id, key))
        conn.commit()
        cursor.close()
        
        return True
        
    except Error as e:
        if conn:
            conn.rollback()
        st.error(f"❌ Failed to delete setting: {e}")
        return False
    

# ============================================================================
# DEBUG LOGGING (Admin troubleshooting)
# ============================================================================

def write_debug_log(
    event_type: str,
    message: str,
    username: str = None,
    user_id: int = None,
    user_agent: str = None,
    session_id: str = None
):
    """
    Write a debug log entry for admin troubleshooting.
    Automatically maintains last 20,000 entries.
    
    Args:
        event_type: Type of event (e.g., 'session_validation_failed', 'audio_error')
        message: Detailed message about the event
        username: Current username (if available)
        user_id: Current user ID (if available)
        user_agent: Browser/device user agent string
        session_id: Session ID (first 8 chars will be stored)
    """
    conn = None
    try:
        # Detect environment
        try:
            # Check if running on Streamlit Cloud
            import socket
            hostname = socket.gethostname()
            environment = 'deployed' if 'streamlit' in hostname.lower() else 'local'
        except:
            environment = 'unknown'
        
        # Extract partial session ID for correlation (privacy)
        session_id_partial = session_id[:8] if session_id else None
        
        conn = get_connection()
        cursor = conn.cursor()
        
        # Insert log entry
        query = """
            INSERT INTO debug_logs 
            (timestamp, environment, username, user_id, event_type, message, user_agent, session_id_partial)
            VALUES (NOW(), %s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(query, (
            environment,
            username,
            user_id,
            event_type,
            message,
            user_agent,
            session_id_partial
        ))
        conn.commit()
        
        # Cleanup: Keep only last 20,000 entries
        cursor.execute("SELECT COUNT(*) FROM debug_logs")
        count = cursor.fetchone()[0]
        
        if count > 20000:
            cursor.execute("""
                DELETE FROM debug_logs 
                WHERE id < (
                    SELECT id FROM (
                        SELECT id FROM debug_logs 
                        ORDER BY id DESC 
                        LIMIT 1 OFFSET 20000
                    ) AS t
                )
            """)
            conn.commit()
        
        cursor.close()
        
    except Exception as e:
        # Don't let logging errors break the app
        logging.error(f"Failed to write debug log: {e}")


def get_debug_logs(
    limit: int = 100,
    event_type: str = None,
    username: str = None,
    environment: str = None
) -> List[Dict]:
    """
    Retrieve debug logs with optional filtering.
    
    Args:
        limit: Maximum number of logs to return
        event_type: Filter by event type
        username: Filter by username
        environment: Filter by environment (local/deployed)
    
    Returns:
        List of log entries (newest first)
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Build query with filters
        query = "SELECT * FROM debug_logs WHERE 1=1"
        params = []
        
        if event_type:
            query += " AND event_type = %s"
            params.append(event_type)
        
        if username:
            query += " AND username = %s"
            params.append(username)
        
        if environment:
            query += " AND environment = %s"
            params.append(environment)
        
        query += " ORDER BY id DESC LIMIT %s"
        params.append(limit)
        
        cursor.execute(query, tuple(params))
        logs = cursor.fetchall()
        cursor.close()
        
        return logs
        
    except Exception as e:
        logging.error(f"Failed to retrieve debug logs: {e}")
        return []


# ============================================================================
# PRACTICE PROGRESS (Per-User, Per-Language Tracking)
# ============================================================================

def save_practice(
    user_id: int,
    language_code: str,
    target_phrase: str,
    recognized_phrase: str,
    similarity_score: float,
    perfect_match: bool,
    target_phonemes: str = "",
    user_phonemes: str = ""
) -> bool:
    """
    Save a practice session result.
    
    Args:
        user_id: User ID
        language_code: Language code (e.g., "pt-BR", "fr-FR")
        target_phrase: Original phrase to practice
        recognized_phrase: What the user said (from speech recognition)
        similarity_score: Similarity score (0-100)
        perfect_match: Whether it was a perfect match
        target_phonemes: Target phoneme representation
        user_phonemes: User's phoneme representation
    
    Returns:
        True if successful, False otherwise
    """
    conn = None
    max_retries = 2  # Try twice if connection fails
    
    for attempt in range(max_retries):
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            query = """
                INSERT INTO user_progress (
                    user_id, language_code, practice_date,
                    target_phrase, recognized_phrase, similarity_score, perfect_match,
                    target_phonemes, user_phonemes
                ) VALUES (%s, %s, NOW(), %s, %s, %s, %s, %s, %s)
            """
            cursor.execute(query, (
                user_id, language_code, target_phrase, recognized_phrase,
                similarity_score, perfect_match, target_phonemes, user_phonemes
            ))
            conn.commit()
            cursor.close()
            
            return True
            
        except Error as e:
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
                conn = None
            
            # If this is not the last attempt and looks like connection issue, retry
            if attempt < max_retries - 1:
                error_str = str(e)
                if "2003" in error_str or "Connection refused" in error_str or "Lost connection" in error_str:
                    logging.warning(f"Connection error on attempt {attempt + 1}, retrying: {e}")
                    time.sleep(0.5)  # Brief delay before retry
                    continue
            
            # Last attempt or non-connection error - show error to user
            st.error(f"⚠️ Could not save practice result to database (connection issue). Your progress for this session is stored locally.")
            logging.error(f"Failed to save practice after {attempt + 1} attempts: {e}")
            return False
    return False


def get_user_progress(user_id: int, language_code: str, limit: int = 50) -> List[Dict]:
    """
    Get recent practice history for a user and language.
    
    Args:
        user_id: User ID
        language_code: Language code (e.g., "pt-BR")
        limit: Maximum number of records to return
    
    Returns:
        List of practice session dicts
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        query = """
            SELECT progress_id, language_code, practice_date,
                   target_phrase, recognized_phrase, similarity_score, perfect_match,
                   target_phonemes, user_phonemes
            FROM user_progress
            WHERE user_id = %s AND language_code = %s
            ORDER BY practice_date DESC
            LIMIT %s
        """
        cursor.execute(query, (user_id, language_code, limit))
        progress = cursor.fetchall()
        cursor.close()
        
        return progress
        
    except Error as e:
        st.error(f"❌ Error fetching progress: {e}")
        return []
    

def get_user_stats(user_id: int, language_code: str) -> Dict:
    """
    Get statistics for a user's practice in a specific language.
    
    Args:
        user_id: User ID
        language_code: Language code
    
    Returns:
        Dict with statistics: {total, perfect_count, avg_score, recent_avg}
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        query = """
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN perfect_match = 1 THEN 1 ELSE 0 END) as perfect_count,
                AVG(similarity_score) as avg_score
            FROM user_progress
            WHERE user_id = %s AND language_code = %s
        """
        cursor.execute(query, (user_id, language_code))
        stats = cursor.fetchone()
        
        # Get average of last 10 practices
        query_recent = """
            SELECT AVG(similarity_score) as recent_avg
            FROM (
                SELECT similarity_score 
                FROM user_progress
                WHERE user_id = %s AND language_code = %s
                ORDER BY practice_date DESC
                LIMIT 10
            ) recent
        """
        cursor.execute(query_recent, (user_id, language_code))
        recent = cursor.fetchone()
        
        cursor.close()
        
        return {
            'total': stats['total'] or 0,
            'perfect_count': stats['perfect_count'] or 0,
            'avg_score': float(stats['avg_score'] or 0),
            'recent_avg': float(recent['recent_avg'] or 0)
        }
        
    except Error as e:
        st.error(f"❌ Error fetching stats: {e}")
        return {'total': 0, 'perfect_count': 0, 'avg_score': 0, 'recent_avg': 0}
    

# ============================================================================
# RATE LIMITING
# ============================================================================

def check_rate_limit(
    identifier: str,
    action: str,
    max_attempts: int,
    window_minutes: int
) -> bool:
    """
    Check if action is rate-limited.
    
    Args:
        identifier: User ID, IP address, or email
        action: Action type (e.g., "LOGIN_ATTEMPT", "PRACTICE_SUBMIT")
        max_attempts: Maximum attempts allowed
        window_minutes: Time window in minutes
    
    Returns:
        True if allowed, False if rate limit exceeded
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Count recent attempts
        query = """
            SELECT COUNT(*) as attempt_count
            FROM rate_limits
            WHERE identifier = %s 
              AND action = %s
              AND attempt_time > DATE_SUB(NOW(), INTERVAL %s MINUTE)
        """
        cursor.execute(query, (identifier, action, window_minutes))
        result = cursor.fetchone()
        
        if result['attempt_count'] >= max_attempts:
            cursor.close()
            return False
        
        # Log this attempt
        insert_query = """
            INSERT INTO rate_limits (identifier, action, attempt_time)
            VALUES (%s, %s, NOW())
        """
        cursor.execute(insert_query, (identifier, action))
        conn.commit()
        cursor.close()
        
        return True
        
    except Error as e:
        if conn:
            conn.rollback()
        # On error, allow the action (fail open)
        return True
    

# ============================================================================
# ACTIVITY LOGGING (Audit Trail)
# ============================================================================

def log_activity(
    user_id: Optional[int],
    action: str,
    details: str,
    ip_address: str = "system",
    use_bootstrap: bool = False
) -> bool:
    """
    Log user activity for audit trail.
    
    Args:
        user_id: User ID (None for system events)
        action: Action type (e.g., "LOGIN_SUCCESS", "SETTING_CHANGED")
        details: Additional details
        ip_address: Client IP address
        use_bootstrap: If True, use bootstrap connection (for pre-auth logging)
    
    Returns:
        True if logged successfully
    """
    try:
        if use_bootstrap:
            # Use bootstrap connection for authentication-related logging
            pool = get_connection_pool_instance()
            with pool.get_bootstrap_connection() as conn:
                cursor = conn.cursor()
                query = """
                    INSERT INTO activity_log (user_id, action, details, ip_address, timestamp)
                    VALUES (%s, %s, %s, %s, NOW())
                """
                cursor.execute(query, (user_id, action, details, ip_address))
                conn.commit()
                cursor.close()
        else:
            # Use normal session connection
            conn = get_connection()
            cursor = conn.cursor()
            query = """
                INSERT INTO activity_log (user_id, action, details, ip_address, timestamp)
                VALUES (%s, %s, %s, %s, NOW())
            """
            cursor.execute(query, (user_id, action, details, ip_address))
            conn.commit()
            cursor.close()
        
        return True
        
    except Error as e:
        # Don't show error to user for logging failures
        return False
    

def get_user_activity_log(user_id: int, limit: int = 100) -> List[Dict]:
    """Get recent activity log for a user."""
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        query = """
            SELECT log_id, action, details, ip_address, timestamp
            FROM activity_log
            WHERE user_id = %s
            ORDER BY timestamp DESC
            LIMIT %s
        """
        cursor.execute(query, (user_id, limit))
        logs = cursor.fetchall()
        cursor.close()
        
        return logs
        
    except Error as e:
        st.error(f"❌ Error fetching activity log: {e}")
        return []
    

# ============================================================================
# ANNOUNCEMENTS
# ============================================================================

def get_active_announcements(location: str = 'both') -> Dict[str, Optional[str]]:
    """
    Get active announcements for a specific location.
    Called from login page (pre-auth), so uses bootstrap connection.
    
    Args:
        location: 'login', 'app', or 'both'
        
    Returns:
        Dict with 'system' and 'feature' keys containing message strings or None
    """
    try:
        # Use bootstrap connection - this is called from login page before authentication
        pool = get_connection_pool_instance()
        with pool.get_bootstrap_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            
            # Query for system announcement
            system_query = """
                SELECT message FROM announcements
                WHERE type = 'system' 
                AND active = TRUE
                AND (display_on = %s OR display_on = 'both')
                AND (expires_at IS NULL OR expires_at > NOW())
                ORDER BY created_at DESC
                LIMIT 1
            """
            cursor.execute(system_query, (location,))
            system_result = cursor.fetchone()
            
            # Query for feature announcement
            feature_query = """
                SELECT message FROM announcements
                WHERE type = 'feature'
                AND active = TRUE
                AND (display_on = %s OR display_on = 'both')
                AND (expires_at IS NULL OR expires_at > NOW())
                ORDER BY created_at DESC
                LIMIT 1
            """
            cursor.execute(feature_query, (location,))
            feature_result = cursor.fetchone()
            
            cursor.close()
            
            return {
                'system': system_result['message'] if system_result else None,
                'feature': feature_result['message'] if feature_result else None
            }
        
    except Error as e:
        # Silently fail - don't disrupt app if announcements fail
        return {'system': None, 'feature': None}
    

def create_announcement(ann_type: str, message: str, display_on: str = 'both', 
                       expires_at: Optional[datetime] = None) -> bool:
    """
    Create a new announcement. Deactivates any existing active announcement of the same type.
    
    Args:
        ann_type: 'system' or 'feature'
        message: Announcement text
        display_on: 'login', 'app', or 'both'
        expires_at: Optional expiration datetime
        
    Returns:
        True if successful, False otherwise
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Deactivate existing active announcements of this type
        deactivate_query = """
            UPDATE announcements 
            SET active = FALSE 
            WHERE type = %s AND active = TRUE
        """
        cursor.execute(deactivate_query, (ann_type,))
        
        # Insert new announcement
        insert_query = """
            INSERT INTO announcements (type, message, active, display_on, expires_at)
            VALUES (%s, %s, TRUE, %s, %s)
        """
        cursor.execute(insert_query, (ann_type, message, display_on, expires_at))
        
        conn.commit()
        cursor.close()
        
        return True
        
    except Error as e:
        st.error(f"❌ Error creating announcement: {e}")
        if conn:
            conn.rollback()
        return False
    

def clear_announcement(ann_type: str) -> bool:
    """
    Deactivate active announcement of the specified type.
    
    Args:
        ann_type: 'system' or 'feature'
        
    Returns:
        True if successful, False otherwise
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = """
            UPDATE announcements 
            SET active = FALSE 
            WHERE type = %s AND active = TRUE
        """
        cursor.execute(query, (ann_type,))
        conn.commit()
        cursor.close()
        
        return True
        
    except Error as e:
        st.error(f"❌ Error clearing announcement: {e}")
        if conn:
            conn.rollback()
        return False
    

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def test_connection() -> bool:
    """Test database connection."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        cursor.close()
        return True
    except Error as e:
        st.error(f"❌ Database connection test failed: {e}")
        return False


if __name__ == "__main__":
    # Module test
    print("Miolingo Database Module v1.3.0")
    print("This module should be imported, not run directly.")
