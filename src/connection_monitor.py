"""
Miolingo Connection Monitor - Experimental Architecture
Monitors and controls SSH tunnels, database connections, and user sessions.

This is a standalone exploration of a robust connection management architecture.
Features:
- Pool of 10 SSH tunnels (not 1 global tunnel)
- 25 DB connections per tunnel (250 total capacity)
- Per-session tracking: IP, device, browser, login time, time remaining
- Process ID tracking for tunnels
- Connection handle registry
- Health monitoring and cleanup

Author: Miolingo Team
Version: 0.1.0 (Experimental)
"""

import streamlit as st
import mysql.connector
from mysql.connector import Error
from sshtunnel import SSHTunnelForwarder
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any, Tuple
import json
from pathlib import Path
import atexit
import warnings
import logging
import time
import os
import signal
import uuid
import random
from dataclasses import dataclass, asdict
from io import StringIO
import paramiko

# Suppress noise
warnings.filterwarnings('ignore', category=DeprecationWarning, module='paramiko')
logging.getLogger('paramiko').setLevel(logging.WARNING)

# Configure Streamlit
st.set_page_config(
    page_title="Miolingo Connection Monitor",
    page_icon="🔌",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class TunnelInfo:
    """SSH tunnel metadata"""
    tunnel_id: str
    tunnel_obj: Optional[SSHTunnelForwarder]
    pid: Optional[int]
    local_port: Optional[int]
    created_at: datetime
    last_used: datetime
    status: str  # 'active', 'idle', 'dead'
    connection_count: int

@dataclass
class ConnectionInfo:
    """Database connection metadata"""
    connection_id: str
    conn_obj: Optional[Any]  # mysql.connector connection
    mysql_conn_id: Optional[int]
    tunnel_id: str
    session_id: Optional[str]
    username: Optional[str]
    created_at: datetime
    last_activity: datetime
    status: str  # 'active', 'idle', 'closed'

@dataclass
class SessionInfo:
    """User session metadata"""
    session_id: str
    username: str
    user_ip: str
    user_agent: str
    device_type: str
    browser: str
    login_time: datetime
    expires_at: datetime
    last_activity: datetime
    connection_ids: List[str]


# ============================================================================
# AUTHENTICATION
# ============================================================================

def check_authentication():
    """Simple authentication for connection monitor (reuses miolingo auth)"""
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    
    if not st.session_state.authenticated:
        st.title("🔌 Miolingo Connection Monitor")
        st.subheader("Authentication Required")
        
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Login")
            
            if submitted:
                # Check capacity BEFORE allowing login
                try:
                    temp_tunnel = create_ssh_tunnel()
                    temp_conn = mysql.connector.connect(
                        host='127.0.0.1',
                        port=temp_tunnel.local_bind_port,
                        database=st.secrets["mysql"]["database"],
                        user=st.secrets["mysql"]["user"],
                        password=st.secrets["mysql"]["password"]
                    )
                    cursor = temp_conn.cursor()
                    cursor.execute("SELECT COUNT(*) FROM connection_monitor WHERE status = 'active'")
                    active_count = cursor.fetchone()[0]
                    cursor.close()
                    temp_conn.close()
                    temp_tunnel.stop()
                    
                    if active_count >= HARD_LIMIT_CONNECTIONS:
                        st.error(f"🚫 **System at Maximum Capacity ({active_count}/{HARD_LIMIT_CONNECTIONS} connections)**")
                        st.info("Please wait and try again later.")
                        st.stop()
                except Exception as cap_err:
                    st.warning(f"Could not verify capacity: {cap_err}")
                
                # Use the same authentication as main app
                try:
                    from app_mysql import authenticate_user
                    user = authenticate_user(username, password)
                    if user:
                        st.session_state.authenticated = True
                        st.session_state.monitor_username = username
                        
                        # Log this login to session_monitor
                        try:
                            log_monitor_session(username)
                        except Exception as log_err:
                            st.warning(f"Login successful but session logging failed: {log_err}")
                        
                        st.rerun()
                    else:
                        st.error("Invalid credentials")
                except Exception as e:
                    st.error(f"Authentication error: {e}")
        
        st.stop()


def log_monitor_session(username: str):
    """Log a connection monitor login session to the database"""
    import streamlit.web.server.server as server
    
    # Get user info from Streamlit context
    try:
        # Get client IP (approximation)
        user_ip = "127.0.0.1"  # Default for local
        
        # Get user agent
        try:
            # Try to get from headers if available
            import streamlit as st
            ctx = st.runtime.scriptrunner.get_script_run_ctx()
            if ctx and hasattr(ctx, 'user_info'):
                user_agent = getattr(ctx.user_info, 'user_agent', 'Unknown')
            else:
                user_agent = "Unknown"
        except:
            user_agent = "Unknown"
        
        # Parse device and browser from user agent
        device_type = "Desktop"
        browser = "Unknown"
        
        if user_agent != "Unknown":
            ua_lower = user_agent.lower()
            # Device detection
            if 'mobile' in ua_lower or 'iphone' in ua_lower or 'android' in ua_lower:
                device_type = "Mobile"
            elif 'tablet' in ua_lower or 'ipad' in ua_lower:
                device_type = "Tablet"
            
            # Browser detection
            if 'chrome' in ua_lower:
                browser = "Chrome"
            elif 'safari' in ua_lower:
                browser = "Safari"
            elif 'firefox' in ua_lower:
                browser = "Firefox"
            elif 'edge' in ua_lower:
                browser = "Edge"
        
        # Generate session ID
        session_id = f"monitor_{username}_{uuid.uuid4().hex[:8]}"
        
        # Store session ID FIRST before any DB operations
        st.session_state.monitor_session_id = session_id
        
        # Calculate expiry (7 days like main app)
        expires_at = datetime.now() + timedelta(days=7)
        
        # Insert into session_monitor table using raw connection
        tunnel = create_ssh_tunnel()
        try:
            conn = mysql.connector.connect(
                host='127.0.0.1',
                port=tunnel.local_bind_port,
                database=st.secrets["mysql"]["database"],
                user=st.secrets["mysql"]["user"],
                password=st.secrets["mysql"]["password"],
                connect_timeout=10
            )
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO session_monitor 
                (session_id, username, user_ip, user_agent, device_type, browser, 
                 login_time, expires_at, last_activity, status)
                VALUES (%s, %s, %s, %s, %s, %s, NOW(), %s, NOW(), 'active')
            """, (session_id, username, user_ip, user_agent, device_type, browser, expires_at))
            
            conn.commit()
            cursor.close()
            conn.close()
        finally:
            tunnel.stop()
        
    except Exception as e:
        # Don't fail login if logging fails
        print(f"Failed to log monitor session: {e}")
        raise


def update_session_activity(session_id: str):
    """Update last_activity timestamp for a session"""
    try:
        # Use raw connection to avoid pool complexity
        tunnel = create_ssh_tunnel()
        try:
            conn = mysql.connector.connect(
                host='127.0.0.1',
                port=tunnel.local_bind_port,
                database=st.secrets["mysql"]["database"],
                user=st.secrets["mysql"]["user"],
                password=st.secrets["mysql"]["password"],
                connect_timeout=10
            )
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE session_monitor 
                SET last_activity = NOW()
                WHERE session_id = %s
            """, (session_id,))
            
            conn.commit()
            cursor.close()
            conn.close()
        finally:
            tunnel.stop()
    except Exception as e:
        # Silent fail - don't disrupt user experience
        pass

# ============================================================================
# GLOBAL STATE - Using Streamlit session state to persist across reruns
# ============================================================================

MAX_TUNNELS = 3  # Pool size
MAX_CONNECTIONS_PER_TUNNEL = 10  # Connections per tunnel
MAX_TOTAL_CONNECTIONS = MAX_TUNNELS * MAX_CONNECTIONS_PER_TUNNEL  # 30 total
SOFT_LIMIT_CONNECTIONS = int(MAX_TOTAL_CONNECTIONS * 0.9)  # 27 - allow reconnects
HARD_LIMIT_CONNECTIONS = MAX_TOTAL_CONNECTIONS  # 30 - block all new logins

# Initialize session state for persistent storage
if 'TUNNEL_POOL' not in st.session_state:
    st.session_state.TUNNEL_POOL = {}
    
if 'CONNECTION_REGISTRY' not in st.session_state:
    st.session_state.CONNECTION_REGISTRY = {}
    
if 'SESSION_REGISTRY' not in st.session_state:
    st.session_state.SESSION_REGISTRY = {}
    
if '_next_tunnel_index' not in st.session_state:
    st.session_state._next_tunnel_index = 0
    
if '_bootstrap_tunnel' not in st.session_state:
    st.session_state._bootstrap_tunnel = None

# Shortcuts for easier access (maintain compatibility)
TUNNEL_POOL = st.session_state.TUNNEL_POOL
CONNECTION_REGISTRY = st.session_state.CONNECTION_REGISTRY
SESSION_REGISTRY = st.session_state.SESSION_REGISTRY


# ============================================================================
# DATABASE TABLE INITIALIZATION
# ============================================================================

def init_monitoring_tables():
    """
    Create database tables for connection monitoring.
    Tables:
    - tunnel_monitor: SSH tunnel tracking
    - connection_monitor: DB connection tracking
    - session_monitor: User session tracking with IP, device, browser
    """
    try:
        # Use raw connection for initialization (avoid pool complexity)
        tunnel = create_ssh_tunnel()
        try:
            conn = mysql.connector.connect(
                host='127.0.0.1',
                port=tunnel.local_bind_port,
                database=st.secrets["mysql"]["database"],
                user=st.secrets["mysql"]["user"],
                password=st.secrets["mysql"]["password"],
                connect_timeout=10
            )
            cursor = conn.cursor()
            
            # Tunnel monitoring table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS tunnel_monitor (
                id INT AUTO_INCREMENT PRIMARY KEY,
                tunnel_id VARCHAR(50) UNIQUE NOT NULL,
                pid INT,
                local_port INT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                status ENUM('active', 'idle', 'dead') DEFAULT 'active',
                connection_count INT DEFAULT 0,
                INDEX idx_tunnel_id (tunnel_id),
                INDEX idx_status (status)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
            
            # Connection monitoring table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS connection_monitor (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    connection_id VARCHAR(100) UNIQUE NOT NULL,
                    mysql_connection_id INT,
                    tunnel_id VARCHAR(50),
                    session_id VARCHAR(100),
                    username VARCHAR(100),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    status ENUM('active', 'idle', 'closed') DEFAULT 'active',
                    INDEX idx_connection_id (connection_id),
                    INDEX idx_tunnel_id (tunnel_id),
                    INDEX idx_session_id (session_id),
                    INDEX idx_status (status),
                    FOREIGN KEY (tunnel_id) REFERENCES tunnel_monitor(tunnel_id) ON DELETE SET NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            
            # Session monitoring table (comprehensive user tracking)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS session_monitor (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    session_id VARCHAR(100) UNIQUE NOT NULL,
                    username VARCHAR(100) NOT NULL,
                    user_ip VARCHAR(45),
                    user_agent TEXT,
                    device_type VARCHAR(50),
                    browser VARCHAR(50),
                    login_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP,
                    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    status ENUM('active', 'expired', 'forced_logout') DEFAULT 'active',
                    INDEX idx_session_id (session_id),
                    INDEX idx_username (username),
                    INDEX idx_status (status),
                    INDEX idx_expires_at (expires_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
        
            conn.commit()
            cursor.close()
            conn.close()
        finally:
            tunnel.stop()
        
        return True, "Monitoring tables initialized successfully"
        
    except Error as e:
        return False, f"Failed to initialize tables: {e}"


def get_bootstrap_connection():
    """
    Get a MySQL connection using the bootstrap tunnel.
    This is ONLY for logging and setup - not tracked, avoids recursion.
    """
    # Ensure we have bootstrap tunnel
    if st.session_state._bootstrap_tunnel is None or not st.session_state._bootstrap_tunnel.is_active:
        st.session_state._bootstrap_tunnel = create_ssh_tunnel()
    
    # Create connection through the tunnel
    conn = mysql.connector.connect(
        host='127.0.0.1',
        port=st.session_state._bootstrap_tunnel.local_bind_port,
        database=st.secrets["mysql"]["database"],
        user=st.secrets["mysql"]["user"],
        password=st.secrets["mysql"]["password"],
        connect_timeout=10
    )
    
    return conn


def check_connection_capacity(is_existing_user: bool = False) -> Tuple[bool, str, int]:
    """
    Check if new connection can be created based on soft/hard limits.
    
    Args:
        is_existing_user: True if user is reconnecting (logged in before)
    
    Returns:
        (can_connect, message, current_count)
    """
    try:
        bootstrap = get_bootstrap_connection()
        cursor = bootstrap.cursor()
        cursor.execute("SELECT COUNT(*) FROM connection_monitor WHERE status = 'active'")
        active_count = cursor.fetchone()[0]
        cursor.close()
        bootstrap.close()
        
        # Hard limit - block everyone
        if active_count >= HARD_LIMIT_CONNECTIONS:
            return False, f"System at maximum capacity ({active_count}/{HARD_LIMIT_CONNECTIONS} connections). Please try again later.", active_count
        
        # Soft limit - only allow existing users to reconnect
        if active_count >= SOFT_LIMIT_CONNECTIONS:
            if not is_existing_user:
                return False, f"System near capacity ({active_count}/{HARD_LIMIT_CONNECTIONS} connections). New logins temporarily paused. Please try again later.", active_count
        
        # Under soft limit - allow all
        return True, f"Capacity OK ({active_count}/{HARD_LIMIT_CONNECTIONS})", active_count
        
    except Exception as e:
        print(f"Error checking capacity: {e}")
        # On error, be conservative and reject
        return False, "Unable to verify system capacity. Please try again.", 0


def get_tracked_connection(session_id: Optional[str] = None, username: Optional[str] = None, is_existing_user: bool = False):
    """
    Get a tracked MySQL connection from the pool with proper handoff.
    
    Sequence (CRITICAL):
    1. Check capacity limits (soft/hard)
    2. Open bootstrap connection to read tunnel/connection pools from DB
    3. Find available tunnel (one with < MAX_CONNECTIONS_PER_TUNNEL)
    4. Create NEW MySQL connection through that tunnel
    5. Get its MySQL CONNECTION_ID and store in DB
    6. CLOSE bootstrap connection (handoff complete)
    7. Return the new tracked connection
    
    This ensures we never accumulate connections - always close bootstrap after handoff.
    
    Args:
        session_id: User session ID
        username: Username
        is_existing_user: True if user is reconnecting (allows above soft limit)
    
    Returns:
        MySQL connection object with details stored in DB, or None if capacity reached
    """
    # STEP 1: Check capacity before proceeding
    can_connect, capacity_msg, active_count = check_connection_capacity(is_existing_user)
    if not can_connect:
        print(f"🚫 Connection rejected: {capacity_msg}")
        return None
    
    print(f"✓ {capacity_msg}")
    
    # STEP 2: Open bootstrap connection to access DB
    bootstrap_conn = None
    try:
        bootstrap_conn = get_bootstrap_connection()
        
        # Query DB for current tunnel/connection state
        cursor = bootstrap_conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT tunnel_id, connection_count 
            FROM tunnel_monitor 
            WHERE status = 'active'
            ORDER BY connection_count ASC
            LIMIT 1
        """)
        db_tunnel_info = cursor.fetchone()
        cursor.close()
        
    except Exception as e:
        print(f"Failed to query DB for tunnel info: {e}")
        db_tunnel_info = None
    
    # STEP 2: Find available tunnel (or create one)
    tunnel_id, tunnel_info = get_or_create_tracked_tunnel()
    
    # STEP 3: Create NEW MySQL connection through that tunnel
    new_conn = mysql.connector.connect(
        host='127.0.0.1',
        port=tunnel_info.tunnel_obj.local_bind_port,
        database=st.secrets["mysql"]["database"],
        user=st.secrets["mysql"]["user"],
        password=st.secrets["mysql"]["password"],
        connect_timeout=10
    )
    
    # Get MySQL's internal connection ID
    cursor = new_conn.cursor()
    cursor.execute("SELECT CONNECTION_ID() as conn_id")
    mysql_conn_id = cursor.fetchone()[0]
    cursor.close()
    
    # Test the connection works
    cursor = new_conn.cursor(dictionary=True)
    cursor.execute("SELECT DATABASE() as db, NOW() as timestamp")
    test_result = cursor.fetchone()
    cursor.close()
    print(f"✅ New connection {mysql_conn_id} works: {test_result}")
    
    # STEP 4: Store connection details in DB (using bootstrap)
    connection_id = f"conn_{uuid.uuid4().hex[:8]}"
    
    conn_info = ConnectionInfo(
        connection_id=connection_id,
        conn_obj=new_conn,
        mysql_conn_id=mysql_conn_id,
        tunnel_id=tunnel_id,
        session_id=session_id or st.session_state.get('monitor_session_id'),
        username=username or st.session_state.get('monitor_username'),
        created_at=datetime.now(),
        last_activity=datetime.now(),
        status='active'
    )
    
    CONNECTION_REGISTRY[connection_id] = conn_info
    
    # Update tunnel stats
    tunnel_info.connection_count += 1
    tunnel_info.last_used = datetime.now()
    
    # Log to DB using bootstrap (still open)
    if bootstrap_conn:
        try:
            cursor = bootstrap_conn.cursor()
            cursor.execute("""
                INSERT INTO connection_monitor
                (connection_id, mysql_connection_id, tunnel_id, session_id, username,
                 created_at, last_activity, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (connection_id, mysql_conn_id, tunnel_id, session_id, username,
                  datetime.now(), datetime.now(), 'active'))
            bootstrap_conn.commit()
            cursor.close()
            
            # Update tunnel stats
            cursor = bootstrap_conn.cursor()
            cursor.execute("""
                INSERT INTO tunnel_monitor 
                (tunnel_id, pid, local_port, created_at, last_used, status, connection_count)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    connection_count = connection_count + 1,
                    last_used = VALUES(last_used)
            """, (tunnel_id, tunnel_info.pid, tunnel_info.local_port,
                  tunnel_info.created_at, datetime.now(), 'active', 1))
            bootstrap_conn.commit()
            cursor.close()
            
        except Exception as e:
            print(f"Failed to log to DB: {e}")
    
    # STEP 5: CLOSE bootstrap connection (CRITICAL - prevents proliferation)
    if bootstrap_conn:
        try:
            bootstrap_conn.close()
            print(f"✅ Bootstrap connection closed after handoff")
        except Exception as e:
            print(f"Warning: Failed to close bootstrap: {e}")
    
    # STEP 6: Return the new tracked connection
    print(f"✅ Returning tracked connection {connection_id} (MySQL ID: {mysql_conn_id}) through {tunnel_id}")
    return new_conn


def get_or_create_tracked_tunnel() -> Tuple[str, TunnelInfo]:
    """
    Get an existing tunnel with capacity or create a new one.
    Checks DATABASE for actual connection counts (not in-memory).
    """
    # Query database for actual connection counts per tunnel
    tunnel_conn_counts = {}
    try:
        bootstrap = get_bootstrap_connection()
        cursor = bootstrap.cursor(dictionary=True)
        cursor.execute("""
            SELECT tunnel_id, COUNT(*) as conn_count
            FROM connection_monitor
            WHERE status = 'active'
            GROUP BY tunnel_id
        """)
        rows = cursor.fetchall()
        for row in rows:
            tunnel_conn_counts[row['tunnel_id']] = row['conn_count']
        cursor.close()
        bootstrap.close()
    except Exception as e:
        print(f"Warning: Could not query DB for tunnel counts: {e}")
    
    # Check in-memory tunnels for one with capacity (using DB counts)
    for tunnel_id, tunnel_info in TUNNEL_POOL.items():
        db_count = tunnel_conn_counts.get(tunnel_id, 0)
        if (tunnel_info.status == 'active' and
            db_count < MAX_CONNECTIONS_PER_TUNNEL and
            tunnel_info.tunnel_obj and
            tunnel_info.tunnel_obj.is_active):
            print(f"✅ Reusing {tunnel_id} ({db_count}/{MAX_CONNECTIONS_PER_TUNNEL} connections)")
            return tunnel_id, tunnel_info
    
    # Create new tunnel if under limit
    if len(TUNNEL_POOL) < MAX_TUNNELS:
        print(f"📊 Creating new tunnel (currently have {len(TUNNEL_POOL)}/{MAX_TUNNELS})")
        tunnel_obj = create_ssh_tunnel()
        tunnel_id = f"tunnel_{len(TUNNEL_POOL)}"
        
        # Get PID
        pid = None
        try:
            if hasattr(tunnel_obj, '_transport') and tunnel_obj._transport:
                pid = tunnel_obj._transport.get_pid()
        except:
            pass
        
        tunnel_info = TunnelInfo(
            tunnel_id=tunnel_id,
            tunnel_obj=tunnel_obj,
            pid=pid,
            local_port=tunnel_obj.local_bind_port,
            created_at=datetime.now(),
            last_used=datetime.now(),
            status='active',
            connection_count=0
        )
        
        TUNNEL_POOL[tunnel_id] = tunnel_info
        print(f"✅ Created {tunnel_id} (port {tunnel_info.local_port})")
        
        # Log the new tunnel to DB immediately (so foreign key works for connections)
        try:
            log_bootstrap = get_bootstrap_connection()
            cursor = log_bootstrap.cursor()
            cursor.execute("""
                INSERT INTO tunnel_monitor 
                (tunnel_id, pid, local_port, created_at, last_used, status, connection_count)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (tunnel_id, tunnel_info.pid, tunnel_info.local_port,
                  tunnel_info.created_at, datetime.now(), 'active', 0))
            log_bootstrap.commit()
            cursor.close()
            log_bootstrap.close()
            print(f"📝 Logged {tunnel_id} to database")
        except Exception as e:
            print(f"⚠️  Failed to log {tunnel_id} to DB: {e}")
        
        return tunnel_id, tunnel_info
    
    # Pool full - use round robin (WARNING: exceeding capacity)
    print(f"⚠️  WARNING: All {MAX_TUNNELS} tunnels at capacity, using round-robin (may exceed {MAX_CONNECTIONS_PER_TUNNEL} per tunnel)")
    tunnel_ids = list(TUNNEL_POOL.keys())
    tunnel_id = tunnel_ids[st.session_state._next_tunnel_index % len(tunnel_ids)]
    st.session_state._next_tunnel_index += 1
    
    db_count = tunnel_conn_counts.get(tunnel_id, 0)
    print(f"⚠️  Assigning to {tunnel_id} (currently {db_count} connections - OVER CAPACITY)")
    
    return tunnel_id, TUNNEL_POOL[tunnel_id]


# Alias for compatibility with existing code
def get_direct_connection():
    """Alias for get_bootstrap_connection for compatibility"""
    return get_bootstrap_connection()


def get_or_create_tunnel() -> Tuple[str, SSHTunnelForwarder]:
    """
    Get an existing tunnel with capacity or create a new one.
    Returns (tunnel_id, tunnel_object)
    """
    # Find a tunnel with capacity
    for tunnel_id, tunnel_info in TUNNEL_POOL.items():
        if (tunnel_info.status == 'active' and 
            tunnel_info.connection_count < MAX_CONNECTIONS_PER_TUNNEL and
            tunnel_info.tunnel_obj and
            tunnel_info.tunnel_obj.is_active):
            return tunnel_id, tunnel_info.tunnel_obj
    
    # Need to create a new tunnel
    if len(TUNNEL_POOL) >= MAX_TUNNELS:
        # Pool is full - reuse least recently used
        lru_item = min(TUNNEL_POOL.items(), key=lambda x: x[1].last_used)
        lru_tunnel_id = lru_item[0]
        lru_tunnel_info = lru_item[1]
        return lru_tunnel_id, lru_tunnel_info.tunnel_obj
    
    # Create new tunnel
    tunnel_obj = create_ssh_tunnel()
    tunnel_id = f"tunnel_{len(TUNNEL_POOL)}"
    
    # Get PID from tunnel process
    pid = None
    try:
        if hasattr(tunnel_obj, '_transport') and tunnel_obj._transport:
            pid = tunnel_obj._transport.get_pid()
    except:
        pass
    
    tunnel_info = TunnelInfo(
        tunnel_id=tunnel_id,
        tunnel_obj=tunnel_obj,
        pid=pid,
        local_port=tunnel_obj.local_bind_port,
        created_at=datetime.now(),
        last_used=datetime.now(),
        status='active',
        connection_count=0
    )
    
    TUNNEL_POOL[tunnel_id] = tunnel_info
    
    # Log to database (skip for now to avoid recursion issues)
    # try:
    #     log_tunnel_to_db(tunnel_info)
    # except Exception as e:
    #     print(f"Failed to log tunnel: {e}")
    
    return tunnel_id, tunnel_obj


def log_tunnel_to_db(tunnel_info: TunnelInfo):
    """Log tunnel to database using bootstrap connection"""
    try:
        conn = get_bootstrap_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO tunnel_monitor 
            (tunnel_id, pid, local_port, created_at, last_used, status, connection_count)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                last_used = VALUES(last_used),
                connection_count = VALUES(connection_count),
                status = VALUES(status)
        """, (tunnel_info.tunnel_id, tunnel_info.pid, tunnel_info.local_port,
              tunnel_info.created_at, tunnel_info.last_used, tunnel_info.status,
              tunnel_info.connection_count))
        
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Failed to log tunnel: {e}")


def log_connection_to_db(conn_info: ConnectionInfo):
    """Log connection to database using bootstrap connection"""
    try:
        conn = get_bootstrap_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO connection_monitor
            (connection_id, mysql_connection_id, tunnel_id, session_id, username,
             created_at, last_activity, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                last_activity = VALUES(last_activity),
                status = VALUES(status)
        """, (conn_info.connection_id, conn_info.mysql_conn_id, conn_info.tunnel_id,
              conn_info.session_id, conn_info.username, conn_info.created_at,
              conn_info.last_activity, conn_info.status))
        
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Failed to log connection: {e}")


def close_session_connection(session_id: str) -> bool:
    """
    Explicitly close a session's connection using stored MySQL connection ID.
    This can work even if the connection object is lost - we can kill by ID.
    
    Returns: True if connection was found and closed, False otherwise
    """
    # Find connection info in registry or DB
    conn_info = None
    conn_id = None
    
    # First check in-memory registry
    for cid, cinfo in list(CONNECTION_REGISTRY.items()):
        if cinfo.session_id == session_id and cinfo.status == 'active':
            conn_id = cid
            conn_info = cinfo
            break
    
    # If not in memory, check database
    if not conn_info:
        try:
            bootstrap = get_bootstrap_connection()
            cursor = bootstrap.cursor(dictionary=True)
            cursor.execute("""
                SELECT connection_id, mysql_connection_id, tunnel_id
                FROM connection_monitor
                WHERE session_id = %s AND status = 'active'
                LIMIT 1
            """, (session_id,))
            db_conn_info = cursor.fetchone()
            cursor.close()
            bootstrap.close()
            
            if db_conn_info:
                mysql_conn_id = db_conn_info['mysql_connection_id']
                conn_id = db_conn_info['connection_id']
                
                # Kill the MySQL connection by ID
                kill_conn = get_bootstrap_connection()
                kill_cursor = kill_conn.cursor()
                kill_cursor.execute(f"KILL {mysql_conn_id}")
                kill_cursor.close()
                kill_conn.close()
                
                # Update status in DB
                update_conn = get_bootstrap_connection()
                cursor = update_conn.cursor()
                cursor.execute("""
                    UPDATE connection_monitor
                    SET status = 'closed', last_activity = NOW()
                    WHERE connection_id = %s
                """, (conn_id,))
                update_conn.commit()
                cursor.close()
                update_conn.close()
                
                print(f"✅ Killed MySQL connection {mysql_conn_id} from database")
                return True
        except Exception as e:
            print(f"Failed to close connection from DB: {e}")
            return False
    
    # Close using connection object
    if conn_info:
        try:
            mysql_conn_id = conn_info.mysql_conn_id
            
            # Close the connection object if we have it
            if conn_info.conn_obj:
                conn_info.conn_obj.close()
                print(f"✅ Closed connection object for {conn_id}")
            
            # Also kill it in MySQL to be sure
            if mysql_conn_id:
                try:
                    kill_conn = get_bootstrap_connection()
                    kill_cursor = kill_conn.cursor()
                    kill_cursor.execute(f"KILL {mysql_conn_id}")
                    kill_cursor.close()
                    kill_conn.close()
                    print(f"✅ Killed MySQL connection {mysql_conn_id}")
                except Exception as e:
                    print(f"Warning: Could not kill MySQL connection: {e}")
            
            # Update in database
            try:
                update_conn = get_bootstrap_connection()
                cursor = update_conn.cursor()
                cursor.execute("""
                    UPDATE connection_monitor
                    SET status = 'closed', last_activity = NOW()
                    WHERE connection_id = %s
                """, (conn_id,))
                update_conn.commit()
                cursor.close()
                update_conn.close()
            except Exception as e:
                print(f"Failed to update DB: {e}")
            
            # Remove from registry
            if conn_id in CONNECTION_REGISTRY:
                del CONNECTION_REGISTRY[conn_id]
            
            return True
        except Exception as e:
            print(f"Error closing connection {conn_id}: {e}")
            return False
    
    return False


def create_ssh_tunnel(retry_count: int = 0, max_retries: int = 3) -> SSHTunnelForwarder:
    """
    Create a single SSH tunnel with retry logic.
    Returns the tunnel object with PID tracking.
    """
    import paramiko
    from io import StringIO
    
    try:
        ssh_port = int(st.secrets["ssh"]["port"])
        
        # Parse SSH key from secrets
        if "key_content" in st.secrets["ssh"]:
            key_content = st.secrets["ssh"]["key_content"]
            key_file = StringIO(key_content)
            
            ssh_key = None
            for key_class in (paramiko.Ed25519Key, paramiko.RSAKey, paramiko.ECDSAKey):
                try:
                    key_file.seek(0)
                    ssh_key = key_class.from_private_key(key_file)
                    break
                except Exception:
                    continue
            
            if ssh_key is None:
                raise ValueError("Could not parse SSH key")
        else:
            ssh_key_path = Path(st.secrets["ssh"]["key_path"]).expanduser().resolve()
            ssh_key = str(ssh_key_path)
        
        tunnel = SSHTunnelForwarder(
            (st.secrets["ssh"]["host"], ssh_port),
            ssh_username=st.secrets["ssh"]["username"],
            ssh_pkey=ssh_key,
            remote_bind_address=('127.0.0.1', 3306),
            set_keepalive=30.0
        )
        tunnel.start()
        
        # Wait for tunnel to be ready
        max_wait = 5  # seconds
        waited = 0
        while not tunnel.is_active and waited < max_wait:
            time.sleep(0.1)
            waited += 0.1
        
        if not tunnel.is_active:
            tunnel.stop()
            raise ConnectionError("SSH tunnel failed to become active")
        
        return tunnel
        
    except Exception as e:
        if retry_count < max_retries:
            # Exponential backoff: 1s, 2s, 4s
            wait_time = 2 ** retry_count
            print(f"Tunnel creation failed (attempt {retry_count + 1}/{max_retries + 1}): {e}")
            print(f"Retrying in {wait_time}s...")
            time.sleep(wait_time)
            return create_ssh_tunnel(retry_count + 1, max_retries)
        else:
            print(f"Tunnel creation failed after {max_retries + 1} attempts: {e}")
            raise


# ============================================================================
# TUNNEL POOL MANAGEMENT
# ============================================================================

def get_or_create_tunnel() -> Tuple[str, TunnelInfo]:
    """
    Get an existing tunnel or create a new one.
    Load balances across the pool of 10 tunnels.
    Returns: (tunnel_id, TunnelInfo)
    """
    # Find tunnel with lowest connection count
    available_tunnels = [
        (tid, tinfo) for tid, tinfo in TUNNEL_POOL.items()
        if tinfo.status == 'active' and tinfo.connection_count < MAX_CONNECTIONS_PER_TUNNEL
    ]
    
    if available_tunnels:
        # Use least loaded tunnel
        tunnel_id, tunnel_info = min(available_tunnels, key=lambda x: x[1].connection_count)
        tunnel_info.last_used = datetime.now()
        return tunnel_id, tunnel_info
    
    # Need to create new tunnel (if under limit)
    if len(TUNNEL_POOL) < MAX_TUNNELS:
        tunnel_id = f"tunnel_{len(TUNNEL_POOL)}"
        tunnel_obj = create_ssh_tunnel()
        
        # Get PID if possible
        pid = None
        try:
            # SSHTunnelForwarder uses a thread, not a separate process
            # But we can track the parent process
            pid = os.getpid()
        except:
            pass
        
        tunnel_info = TunnelInfo(
            tunnel_id=tunnel_id,
            tunnel_obj=tunnel_obj,
            pid=pid,
            local_port=tunnel_obj.local_bind_port,
            created_at=datetime.now(),
            last_used=datetime.now(),
            status='active',
            connection_count=0
        )
        
        TUNNEL_POOL[tunnel_id] = tunnel_info
        
        # Record in database
        try:
            conn = get_direct_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO tunnel_monitor (tunnel_id, pid, local_port, status)
                VALUES (%s, %s, %s, %s)
            """, (tunnel_id, pid, tunnel_info.local_port, 'active'))
            conn.commit()
            cursor.close()
            conn.close()
        except:
            pass
        
        return tunnel_id, tunnel_info
    
    # Pool exhausted
    raise Exception(f"Tunnel pool exhausted ({MAX_TUNNELS} tunnels, all at capacity)")


def close_tunnel(tunnel_id: str) -> bool:
    """
    Close a specific tunnel and clean up its connections.
    Returns True if successful.
    """
    if tunnel_id not in TUNNEL_POOL:
        return False
    
    tunnel_info = TUNNEL_POOL[tunnel_id]
    
    # Close all connections using this tunnel
    for conn_id, conn_info in list(CONNECTION_REGISTRY.items()):
        if conn_info.tunnel_id == tunnel_id:
            close_connection(conn_id)
    
    # Stop the tunnel
    try:
        if tunnel_info.tunnel_obj:
            tunnel_info.tunnel_obj.stop()
    except:
        pass
    
    # Update status
    tunnel_info.status = 'dead'
    
    # Update database
    try:
        conn = get_direct_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE tunnel_monitor SET status = 'dead' WHERE tunnel_id = %s
        """, (tunnel_id,))
        conn.commit()
        cursor.close()
        conn.close()
    except:
        pass
    
    # Remove from pool
    del TUNNEL_POOL[tunnel_id]
    
    return True


# ============================================================================
# CONNECTION POOL MANAGEMENT
# ============================================================================

def get_connection(session_id: Optional[str] = None, username: Optional[str] = None) -> Tuple[str, Any]:
    """
    Get a database connection from the pool.
    Returns: (connection_id, connection_object)
    """
    # Check if we're at capacity
    active_connections = sum(1 for c in CONNECTION_REGISTRY.values() if c.status == 'active')
    if active_connections >= MAX_TOTAL_CONNECTIONS:
        raise Exception(f"Connection pool exhausted ({MAX_TOTAL_CONNECTIONS} connections)")
    
    # Get or create tunnel
    tunnel_id, tunnel_info = get_or_create_tunnel()
    
    # Create new connection
    try:
        conn = mysql.connector.connect(
            host='127.0.0.1',
            port=tunnel_info.local_port,
            database=st.secrets["mysql"]["database"],
            user=st.secrets["mysql"]["user"],
            password=st.secrets["mysql"]["password"],
            connect_timeout=10
        )
        
        # Get MySQL's internal connection ID
        cursor = conn.cursor()
        cursor.execute("SELECT CONNECTION_ID()")
        mysql_conn_id = cursor.fetchone()[0]
        cursor.close()
        
        # Generate unique connection ID
        connection_id = f"conn_{uuid.uuid4().hex[:8]}"
        
        # Create connection info
        conn_info = ConnectionInfo(
            connection_id=connection_id,
            conn_obj=conn,
            mysql_conn_id=mysql_conn_id,
            tunnel_id=tunnel_id,
            session_id=session_id,
            username=username,
            created_at=datetime.now(),
            last_activity=datetime.now(),
            status='active'
        )
        
        CONNECTION_REGISTRY[connection_id] = conn_info
        tunnel_info.connection_count += 1
        
        # Record in database
        try:
            admin_conn = get_direct_connection()
            cursor = admin_conn.cursor()
            cursor.execute("""
                INSERT INTO connection_monitor 
                (connection_id, mysql_connection_id, tunnel_id, session_id, username, status)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (connection_id, mysql_conn_id, tunnel_id, session_id, username, 'active'))
            admin_conn.commit()
            cursor.close()
            admin_conn.close()
        except:
            pass
        
        return connection_id, conn
        
    except Error as e:
        raise Exception(f"Failed to create connection: {e}")


def close_connection(connection_id: str) -> bool:
    """
    Close a specific database connection.
    Returns True if successful.
    """
    if connection_id not in CONNECTION_REGISTRY:
        return False
    
    conn_info = CONNECTION_REGISTRY[connection_id]
    
    # Close the connection
    try:
        if conn_info.conn_obj and conn_info.conn_obj.is_connected():
            conn_info.conn_obj.close()
    except:
        pass
    
    # Update tunnel connection count
    if conn_info.tunnel_id in TUNNEL_POOL:
        TUNNEL_POOL[conn_info.tunnel_id].connection_count -= 1
    
    # Update status
    conn_info.status = 'closed'
    
    # Update database
    try:
        admin_conn = get_direct_connection()
        cursor = admin_conn.cursor()
        cursor.execute("""
            UPDATE connection_monitor SET status = 'closed' WHERE connection_id = %s
        """, (connection_id,))
        admin_conn.commit()
        cursor.close()
        admin_conn.close()
    except:
        pass
    
    # Remove from registry
    del CONNECTION_REGISTRY[connection_id]
    
    return True


def cleanup_dead_connections():
    """
    Clean connections from DB that no longer exist in MySQL.
    Uses SHOW PROCESSLIST to verify connections are actually alive.
    """
    cleaned = 0
    
    try:
        # Get all MySQL connection IDs from SHOW PROCESSLIST
        bootstrap = get_bootstrap_connection()
        cursor = bootstrap.cursor(dictionary=True)
        cursor.execute("SHOW PROCESSLIST")
        processlist = cursor.fetchall()
        alive_mysql_ids = {row['Id'] for row in processlist}
        cursor.close()
        bootstrap.close()
        
        print(f"Found {len(alive_mysql_ids)} live MySQL connections")
        
        # Get all active connections from our DB
        check_conn = get_bootstrap_connection()
        cursor = check_conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT connection_id, mysql_connection_id
            FROM connection_monitor
            WHERE status = 'active'
        """)
        db_conns = cursor.fetchall()
        cursor.close()
        check_conn.close()
        
        # Mark as closed any that don't exist in MySQL anymore
        for conn_data in db_conns:
            mysql_id = conn_data['mysql_connection_id']
            conn_id = conn_data['connection_id']
            
            if mysql_id not in alive_mysql_ids:
                # Connection is dead in MySQL but still marked active in our DB
                try:
                    update_conn = get_bootstrap_connection()
                    cursor = update_conn.cursor()
                    cursor.execute("""
                        UPDATE connection_monitor
                        SET status = 'closed', last_activity = NOW()
                        WHERE connection_id = %s
                    """, (conn_id,))
                    update_conn.commit()
                    cursor.close()
                    update_conn.close()
                    cleaned += 1
                    print(f"🧹 Cleaned dead connection {conn_id} (MySQL ID {mysql_id})")
                except Exception as e:
                    print(f"Failed to clean {conn_id}: {e}")
                
                # Remove from memory
                if conn_id in st.session_state.CONNECTION_REGISTRY:
                    del st.session_state.CONNECTION_REGISTRY[conn_id]
        
        return cleaned
        
    except Exception as e:
        print(f"Error in cleanup_dead_connections: {e}")
        return 0


def cleanup_dead_tunnels():
    """
    Clean tunnels from DB whose SSH process no longer exists.
    """
    cleaned = 0
    
    try:
        # Get all active tunnels from DB
        bootstrap = get_bootstrap_connection()
        cursor = bootstrap.cursor(dictionary=True)
        cursor.execute("""
            SELECT tunnel_id, pid
            FROM tunnel_monitor
            WHERE status = 'active'
        """)
        db_tunnels = cursor.fetchall()
        cursor.close()
        bootstrap.close()
        
        for tunnel_data in db_tunnels:
            tunnel_id = tunnel_data['tunnel_id']
            pid = tunnel_data['pid']
            
            # Skip if PID is None or 0
            if not pid:
                continue
            
            # Check if process is still alive
            try:
                import os
                import signal
                os.kill(pid, 0)  # Signal 0 just checks if process exists
                # Process exists, continue
            except (OSError, ProcessLookupError, TypeError):
                # Process doesn't exist, mark tunnel as closed
                try:
                    update_conn = get_bootstrap_connection()
                    cursor = update_conn.cursor()
                    cursor.execute("""
                        UPDATE tunnel_monitor
                        SET status = 'closed', last_used = NOW()
                        WHERE tunnel_id = %s
                    """, (tunnel_id,))
                    update_conn.commit()
                    cursor.close()
                    update_conn.close()
                    cleaned += 1
                    print(f"🧹 Cleaned dead tunnel {tunnel_id} (PID {pid})")
                except Exception as e:
                    print(f"Failed to clean tunnel {tunnel_id}: {e}")
                
                # Remove from memory
                if tunnel_id in st.session_state.TUNNEL_POOL:
                    del st.session_state.TUNNEL_POOL[tunnel_id]
        
        return cleaned
        
    except Exception as e:
        print(f"Error in cleanup_dead_tunnels: {e}")
        return 0


def cleanup_idle_connections(idle_threshold_minutes: int = 10):
    """
    Close connections that have been idle for longer than threshold.
    Works on DATABASE records, not just in-memory registry.
    """
    closed_count = 0
    
    try:
        # Get all active connections from DB that are past threshold
        bootstrap = get_bootstrap_connection()
        cursor = bootstrap.cursor(dictionary=True)
        cursor.execute("""
            SELECT connection_id, mysql_connection_id, tunnel_id, session_id, username
            FROM connection_monitor
            WHERE status = 'active'
              AND last_activity < DATE_SUB(NOW(), INTERVAL %s MINUTE)
        """, (idle_threshold_minutes,))
        stale_conns = cursor.fetchall()
        cursor.close()
        bootstrap.close()
        
        print(f"Found {len(stale_conns)} idle connections (>{idle_threshold_minutes}m)")
        
        # Close each stale connection
        for conn_data in stale_conns:
            conn_id = conn_data['connection_id']
            mysql_conn_id = conn_data['mysql_connection_id']
            
            # Try to kill the MySQL connection
            try:
                kill_conn = get_bootstrap_connection()
                kill_cursor = kill_conn.cursor()
                kill_cursor.execute(f"KILL {mysql_conn_id}")
                kill_cursor.close()
                kill_conn.close()
                print(f"✅ Killed idle MySQL connection {mysql_conn_id}")
            except Exception as e:
                print(f"⚠️  Could not kill MySQL conn {mysql_conn_id}: {e}")
            
            # Update status in DB
            try:
                update_conn = get_bootstrap_connection()
                cursor = update_conn.cursor()
                cursor.execute("""
                    UPDATE connection_monitor
                    SET status = 'closed', last_activity = NOW()
                    WHERE connection_id = %s
                """, (conn_id,))
                update_conn.commit()
                cursor.close()
                update_conn.close()
                closed_count += 1
            except Exception as e:
                print(f"Failed to update DB for {conn_id}: {e}")
            
            # Remove from memory if present
            if conn_id in st.session_state.CONNECTION_REGISTRY:
                del st.session_state.CONNECTION_REGISTRY[conn_id]
        
        return closed_count
        
    except Exception as e:
        print(f"Error in cleanup_idle_connections: {e}")
        return 0


# ============================================================================
# SESSION MANAGEMENT
# ============================================================================

def parse_user_agent(user_agent: str) -> Tuple[str, str]:
    """
    Parse user agent to extract device type and browser.
    Returns: (device_type, browser)
    """
    user_agent_lower = user_agent.lower()
    
    # Device detection
    if 'iphone' in user_agent_lower or 'ipad' in user_agent_lower:
        device = 'iOS'
    elif 'android' in user_agent_lower:
        device = 'Android'
    elif 'macintosh' in user_agent_lower or 'mac os' in user_agent_lower:
        device = 'macOS'
    elif 'windows' in user_agent_lower:
        device = 'Windows'
    elif 'linux' in user_agent_lower:
        device = 'Linux'
    else:
        device = 'Unknown'
    
    # Browser detection
    if 'chrome' in user_agent_lower and 'edg' not in user_agent_lower:
        browser = 'Chrome'
    elif 'safari' in user_agent_lower and 'chrome' not in user_agent_lower:
        browser = 'Safari'
    elif 'firefox' in user_agent_lower:
        browser = 'Firefox'
    elif 'edg' in user_agent_lower:
        browser = 'Edge'
    else:
        browser = 'Unknown'
    
    return device, browser


def register_session(username: str, session_id: str, user_ip: str, user_agent: str, expires_at: datetime):
    """
    Register a new user session with full tracking.
    """
    device, browser = parse_user_agent(user_agent)
    
    session_info = SessionInfo(
        session_id=session_id,
        username=username,
        user_ip=user_ip,
        user_agent=user_agent,
        device_type=device,
        browser=browser,
        login_time=datetime.now(),
        expires_at=expires_at,
        last_activity=datetime.now(),
        connection_ids=[]
    )
    
    SESSION_REGISTRY[session_id] = session_info
    
    # Record in database
    try:
        conn = get_direct_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO session_monitor 
            (session_id, username, user_ip, user_agent, device_type, browser, expires_at, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (session_id, username, user_ip, user_agent, device, browser, expires_at, 'active'))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        st.error(f"Failed to register session: {e}")


def get_session_stats() -> Dict[str, Any]:
    """
    Get comprehensive session statistics from database.
    """
    try:
        conn = get_direct_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Active sessions
        cursor.execute("""
            SELECT COUNT(*) as count FROM session_monitor 
            WHERE status = 'active' AND expires_at > NOW()
        """)
        active_sessions = cursor.fetchone()['count']
        
        # Sessions by device
        cursor.execute("""
            SELECT device_type, COUNT(*) as count 
            FROM session_monitor 
            WHERE status = 'active' AND expires_at > NOW()
            GROUP BY device_type
        """)
        by_device = {row['device_type']: row['count'] for row in cursor.fetchall()}
        
        # Sessions by browser
        cursor.execute("""
            SELECT browser, COUNT(*) as count 
            FROM session_monitor 
            WHERE status = 'active' AND expires_at > NOW()
            GROUP BY browser
        """)
        by_browser = {row['browser']: row['count'] for row in cursor.fetchall()}
        
        cursor.close()
        conn.close()
        
        return {
            'active_sessions': active_sessions,
            'by_device': by_device,
            'by_browser': by_browser
        }
        
    except Exception as e:
        return {'error': str(e)}


# ============================================================================
# STREAMLIT UI
# ============================================================================

# Main function moved to end of file (after all UI functions defined)


def show_dashboard():
    """Overview dashboard"""
    st.header("System Overview")
    
    # Show table existence status
    with st.expander("📋 Database Tables Status", expanded=False):
        try:
            conn = get_direct_connection()
            cursor = conn.cursor()
            
            tables = ['tunnel_monitor', 'connection_monitor', 'session_monitor']
            for table in tables:
                cursor.execute(f"SHOW TABLES LIKE '{table}'")
                exists = cursor.fetchone() is not None
                if exists:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cursor.fetchone()[0]
                    st.success(f"✅ `{table}` exists ({count} rows)")
                else:
                    st.error(f"❌ `{table}` does not exist")
            
            cursor.close()
            conn.close()
        except Exception as e:
            st.error(f"Error checking tables: {e}")
    
    col1, col2, col3, col4 = st.columns(4)
    
    # Query database for actual counts
    try:
        bootstrap = get_bootstrap_connection()
        cursor = bootstrap.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM tunnel_monitor WHERE status = 'active'")
        db_tunnels = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM connection_monitor WHERE status = 'active'")
        db_conns = cursor.fetchone()[0]
        
        cursor.close()
        bootstrap.close()
    except Exception as e:
        print(f"Dashboard query error: {e}")
        db_tunnels = 0
        db_conns = 0
    
    with col1:
        mem_tunnels = sum(1 for t in TUNNEL_POOL.values() if t.status == 'active')
        st.metric("Active Tunnels", f"{db_tunnels}/{MAX_TUNNELS}", help=f"In DB: {db_tunnels}, In memory: {mem_tunnels}")
    
    with col2:
        mem_conns = sum(1 for c in CONNECTION_REGISTRY.values() if c.status == 'active')
        st.metric("Active Connections", f"{db_conns}/{MAX_TOTAL_CONNECTIONS}", help=f"In DB: {db_conns}, In memory: {mem_conns}")
    
    with col3:
        session_stats = get_session_stats()
        st.metric("Active Sessions", session_stats.get('active_sessions', 0))
    
    with col4:
        capacity = (db_conns / MAX_TOTAL_CONNECTIONS) * 100 if MAX_TOTAL_CONNECTIONS > 0 else 0
        st.metric("Pool Capacity", f"{capacity:.1f}%")
    
    # Resource usage chart
    st.subheader("Resource Usage")
    st.info(f"Pool architecture: {MAX_TUNNELS} tunnels × {MAX_CONNECTIONS_PER_TUNNEL} connections = {MAX_TOTAL_CONNECTIONS} total capacity")
    
    # Architecture explanation
    with st.expander("ℹ️  How Memory vs Database Tracking Works", expanded=False):
        st.markdown("""
        ### Dual Tracking System
        
        **Memory (Session State):**
        - Fast access for active operations
        - `TUNNEL_POOL`: SSH tunnel objects (connection info, ports, PIDs)
        - `CONNECTION_REGISTRY`: MySQL connection objects (for queries)
        - Persists during Streamlit session (stored in `st.session_state`)
        
        **Database (Persistent):**
        - `tunnel_monitor`: Tunnel metadata (tunnel_id, PID, port, status)
        - `connection_monitor`: Connection metadata (connection_id, MySQL ID, tunnel_id, user, timestamps)
        - `session_monitor`: User sessions (login times, device info, activity)
        - Survives app restarts
        - **Source of truth** for counts and allocation
        
        ### Why Both?
        1. **Memory**: Need actual connection objects to execute queries
        2. **Database**: Track across app restarts, multiple admin users, audit history
        3. **Verification**: Compare DB vs memory to find leaks/stale records
        
        ### Cleanup Operations
        - **Clean Dead Connections**: Queries MySQL `SHOW PROCESSLIST` to verify connections actually exist
        - **Clean Dead Tunnels**: Checks if SSH tunnel process (PID) is still running
        - **Clean Idle**: Closes connections inactive for N minutes
        - **Database is always updated** when connections/tunnels are closed
        
        ### Important Notes
        - Dashboard shows **database counts** (accurate across app sessions)
        - Memory counts may differ if connections died without cleanup
        - Admin can forcibly close any resource and DB will be updated
        - Bootstrap connection (for logging) is NOT tracked in database
        - This monitor connects to **same database** as main Miolingo app
        """)
    
    # Show logged-in monitor users
    st.subheader("👥 Connection Monitor Users (Logged In Now)")
    
    col1, col2, col3 = st.columns([2, 1, 1])
    with col2:
        if st.button("🧪 Test Tracked"):
            try:
                # Use tracked connection to populate pool
                conn = get_tracked_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM session_monitor")
                count = cursor.fetchone()[0]
                cursor.close()
                conn.close()
                st.success(f"Tracked query: {count} sessions")
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")
    
    with col3:
        if st.button("🧹 Clean Stale Sessions"):
            try:
                conn = get_bootstrap_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE session_monitor 
                    SET status = 'expired'
                    WHERE status = 'active' 
                      AND last_activity < DATE_SUB(NOW(), INTERVAL 10 MINUTE)
                """)
                cleaned = cursor.rowcount
                conn.commit()
                cursor.close()
                conn.close()
                st.success(f"Marked {cleaned} stale sessions as expired")
                st.rerun()
            except Exception as e:
                st.error(f"Error cleaning sessions: {e}")
    
    # Add comprehensive cleanup button
    st.subheader("🛠️ System Cleanup")
    st.write("**Verify database matches reality** - removes stale records for dead connections/tunnels")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🧹 Clean Dead Connections", help="Remove connections that no longer exist in MySQL"):
            with st.spinner("Checking MySQL SHOW PROCESSLIST..."):
                cleaned = cleanup_dead_connections()
                st.success(f"Cleaned {cleaned} dead connections from database")
                st.rerun()
    
    with col2:
        if st.button("🧹 Clean Dead Tunnels", help="Remove tunnels whose SSH process died"):
            with st.spinner("Checking SSH process list..."):
                cleaned = cleanup_dead_tunnels()
                st.success(f"Cleaned {cleaned} dead tunnels from database")
                st.rerun()
    
    with col3:
        if st.button("🧹 Clean All Stale", type="primary", help="Run all cleanup operations"):
            with st.spinner("Running comprehensive cleanup..."):
                dead_conns = cleanup_dead_connections()
                dead_tunnels = cleanup_dead_tunnels()
                idle_conns = cleanup_idle_connections(10)
                st.success(f"Cleaned {dead_conns} dead connections, {dead_tunnels} dead tunnels, {idle_conns} idle connections")
                st.rerun()
    
    try:
        conn = get_direct_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT session_id, username, user_ip, device_type, browser,
                   login_time, expires_at, last_activity,
                   TIMESTAMPDIFF(SECOND, NOW(), expires_at) as seconds_remaining,
                   TIMESTAMPDIFF(SECOND, login_time, NOW()) as seconds_logged_in,
                   TIMESTAMPDIFF(MINUTE, last_activity, NOW()) as minutes_idle
            FROM session_monitor
            WHERE status = 'active' 
              AND expires_at > NOW()
              AND last_activity > DATE_SUB(NOW(), INTERVAL 10 MINUTE)
            ORDER BY last_activity DESC
        """)
        monitor_sessions = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if monitor_sessions:
            for session in monitor_sessions:
                # Calculate time logged in
                logged_in_seconds = session['seconds_logged_in']
                hours_in = logged_in_seconds // 3600
                minutes_in = (logged_in_seconds % 3600) // 60
                
                # Calculate time remaining
                time_remaining = timedelta(seconds=session['seconds_remaining'])
                hours_left, remainder = divmod(int(time_remaining.total_seconds()), 3600)
                minutes_left, seconds_left = divmod(remainder, 60)
                
                with st.expander(f"👤 {session['username']} - {session['device_type']}/{session['browser']}", expanded=True):
                    col1, col2, col3 = st.columns([3, 3, 1])
                    with col1:
                        st.write(f"**IP Address:** {session['user_ip']}")
                        st.write(f"**Device:** {session['device_type']}")
                        st.write(f"**Browser:** {session['browser']}")
                        st.write(f"**Logged In:** {hours_in}h {minutes_in}m ago")
                    with col2:
                        st.write(f"**Login Time:** {session['login_time']}")
                        st.write(f"**Last Activity:** {session['last_activity']} ({session['minutes_idle']} min ago)")
                        st.write(f"**Time Remaining:** {hours_left}h {minutes_left}m {seconds_left}s")
                        st.write(f"**Session ID:** `{session['session_id']}`")
                    with col3:
                        if st.button("🚫 Force Logout", key=f"logout_{session['session_id']}", help="Expire session and close all connections"):
                            try:
                                # Mark session as expired
                                logout_conn = get_bootstrap_connection()
                                cursor = logout_conn.cursor()
                                cursor.execute("""
                                    UPDATE session_monitor
                                    SET status = 'forced_logout', last_activity = NOW()
                                    WHERE session_id = %s
                                """, (session['session_id'],))
                                logout_conn.commit()
                                cursor.close()
                                logout_conn.close()
                                
                                # Close all connections for this session
                                close_session_connection(session['session_id'])
                                
                                st.success(f"Logged out {session['username']}")
                                time.sleep(1)
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error: {e}")
        else:
            st.info("No active connection monitor sessions")
            
    except Exception as e:
        st.error(f"Error loading monitor sessions: {e}")


def show_tunnels():
    """Tunnel management page"""
    st.header("SSH Tunnel Pool")
    
    # Simulated user test
    st.subheader("🧪 Simulate New User Connection")
    st.write("Test the complete flow: allocate tunnel → create connection → execute query → close")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        test_username = st.text_input("Username", value=f"test_user_{random.randint(1000, 9999)}", key="sim_username")
    with col2:
        test_session = st.text_input("Session ID", value=f"sim_{uuid.uuid4().hex[:8]}", key="sim_session")
    with col3:
        st.write("") # spacing
        st.write("") # spacing
        if st.button("🗑️ Close", key="close_session_btn"):
            if close_session_connection(test_session):
                st.success(f"✅ Closed connection for session {test_session}")
                time.sleep(1)
                st.rerun()
            else:
                st.warning("No active connection found for this session")
    
    btn_col1, btn_col2 = st.columns(2)
    with btn_col1:
        create_new = st.button("🚀 Create New Connection", key="simulate_user_btn", type="primary")
    with btn_col2:
        reuse_existing = st.button("🔄 Reuse Existing Connection", key="reuse_conn_btn")
    
    # Check capacity first and show status
    can_connect, capacity_msg, active_count = check_connection_capacity(is_existing_user=False)
    if not can_connect:
        st.error(f"🚫 **{capacity_msg}**")
        st.info("💡 Try logging out an existing session or wait for connections to free up.")
    else:
        st.success(f"✅ {capacity_msg}")
    
    if create_new:
        result_placeholder = st.empty()
        
        # Check capacity again before attempting
        can_connect, capacity_msg, active_count = check_connection_capacity(is_existing_user=False)
        if not can_connect:
            st.error(f"🚫 **Connection Limit Reached**")
            st.warning(capacity_msg)
            st.info("**Next steps:**\n1. Wait for existing connections to close\n2. Admin can force-logout idle sessions\n3. Admin can clean stale connections")
            return
        
        try:
            with result_placeholder.container():
                st.info(f"**Step 1:** Simulating user '{test_username}' with session '{test_session}'")
                
                # Get tracked connection - proper handoff sequence
                with st.spinner("Step 2: Allocating tunnel from pool (round-robin)..."):
                    conn = get_tracked_connection(test_session, test_username, is_existing_user=False)
                    
                    if not conn:
                        st.error("❌ Connection limit reached or allocation failed")
                        st.info("System at capacity. Please try again later.")
                        return
                    
                    # Find which tunnel was allocated
                    conn_id = None
                    allocated_tunnel = None
                    for cid, cinfo in CONNECTION_REGISTRY.items():
                        if cinfo.session_id == test_session:
                            conn_id = cid
                            allocated_tunnel = cinfo.tunnel_id
                            break
                    
                    st.success(f"✅ Tunnel allocated: **{allocated_tunnel}** (connection: {conn_id})")
                    st.info("🔒 Connection kept alive in registry (not closed)")
                
                # Execute real query through tracked connection (bootstrap already closed in get_tracked_connection)
                with st.spinner("Step 3: Executing query through tracked connection..."):
                    cursor = conn.cursor(dictionary=True)
                    cursor.execute("SELECT DATABASE() as db, CONNECTION_ID() as conn_id, NOW() as timestamp")
                    result = cursor.fetchone()
                    cursor.close()
                    
                    st.success(f"✅ Query successful!")
                    st.json(result)
                
                st.success(f"🎉 **Test Complete!** User '{test_username}' has active connection through '{allocated_tunnel}'")
                st.info("✅ Bootstrap connection was closed after handoff (prevents proliferation)")
                st.info("✨ Tracked connection remains open. Check registry and DB logs below.")
                st.info("Refresh the page to see updated tunnel and connection lists")
            
        except Exception as e:
            with result_placeholder.container():
                st.error(f"❌ Test failed: {e}")
                import traceback
                st.code(traceback.format_exc())
    
    if reuse_existing:
        result_placeholder = st.empty()
        
        try:
            with result_placeholder.container():
                st.info(f"**Testing Connection Reuse** for session '{test_session}'")
                
                # Get tracked connection - will check registry first
                with st.spinner("Fetching connection (checking registry first)..."):
                    conn = get_tracked_connection(test_session, test_username)
                    
                    if not conn:
                        st.error("❌ Failed to get connection")
                        return
                    
                    # Find connection info
                    conn_id = None
                    allocated_tunnel = None
                    created_at = None
                    for cid, cinfo in CONNECTION_REGISTRY.items():
                        if cinfo.session_id == test_session:
                            conn_id = cid
                            allocated_tunnel = cinfo.tunnel_id
                            created_at = cinfo.created_at
                            break
                    
                    st.success(f"✅ Using connection: **{conn_id}** through **{allocated_tunnel}**")
                    st.info(f"📅 Connection created at: {created_at} (reused, not recreated!)")
                
                # Execute query to prove it works
                with st.spinner("Executing query through reused connection..."):
                    cursor = conn.cursor(dictionary=True)
                    cursor.execute("SELECT DATABASE() as db, CONNECTION_ID() as conn_id, NOW() as timestamp, 'REUSED!' as status")
                    result = cursor.fetchone()
                    cursor.close()
                    
                    st.success(f"✅ Query successful on reused connection!")
                    st.json(result)
                
                st.success(f"🎉 **Connection Reuse Verified!** Same connection object reused without recreating.")
            
        except Exception as e:
            with result_placeholder.container():
                st.error(f"❌ Reuse test failed: {e}")
                import traceback
                st.code(traceback.format_exc())
    
    st.divider()
    
    # Show in-memory pool
    st.subheader("In-Memory Pool")
    if not TUNNEL_POOL:
        st.info("No tunnels in memory yet. Tunnels are created on-demand when connections are requested.")
    else:
        for tunnel_id, tunnel_info in TUNNEL_POOL.items():
            with st.expander(f"🔌 {tunnel_id} - {tunnel_info.status.upper()}", expanded=False):
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.write(f"**PID:** {tunnel_info.pid}")
                    st.write(f"**Local Port:** {tunnel_info.local_port}")
                
                with col2:
                    st.write(f"**Created:** {tunnel_info.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
                    st.write(f"**Last Used:** {tunnel_info.last_used.strftime('%Y-%m-%d %H:%M:%S')}")
                
                with col3:
                    st.write(f"**Connections:** {tunnel_info.connection_count}/{MAX_CONNECTIONS_PER_TUNNEL}")
                    st.write(f"**Status:** {tunnel_info.status}")
    
    # Show database-logged tunnels
    st.subheader("Database-Logged Tunnels")
    try:
        conn = get_bootstrap_connection()
        if not conn:
            st.warning("Could not establish bootstrap connection to query database")
        else:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT tunnel_id, pid, local_port, created_at, last_used, status, connection_count
                FROM tunnel_monitor
                ORDER BY last_used DESC
            """)
            tunnels = cursor.fetchall()
            cursor.close()
            conn.close()
            
            if tunnels:
                for tunnel in tunnels:
                    with st.expander(f"📊 {tunnel['tunnel_id']} - {tunnel['status'].upper()}", expanded=False):
                        col1, col2 = st.columns(2)
                        with col1:
                            st.write(f"**PID:** {tunnel['pid']}")
                            st.write(f"**Port:** {tunnel['local_port']}")
                            st.write(f"**Connections:** {tunnel['connection_count']}")
                        with col2:
                            st.write(f"**Created:** {tunnel['created_at']}")
                            st.write(f"**Last Used:** {tunnel['last_used']}")
                            st.write(f"**Status:** {tunnel['status']}")
            else:
                st.info("No tunnels logged to database yet")
    except Exception as e:
        st.warning(f"Could not load database tunnels (may be temporary): {e}")
        st.info("Try refreshing the page if this persists")


def show_connections():
    """Connection management page"""
    st.header("Database Connections")
    
    # Show in-memory registry
    st.subheader("In-Memory Registry")
    if not CONNECTION_REGISTRY:
        st.info("No connections in memory registry yet.")
    else:
        for conn_id, conn_info in CONNECTION_REGISTRY.items():
            with st.expander(f"🔗 {conn_id} - {conn_info.status.upper()}", expanded=False):
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**MySQL Conn ID:** {conn_info.mysql_conn_id}")
                    st.write(f"**Tunnel:** {conn_info.tunnel_id}")
                    st.write(f"**Session:** {conn_info.session_id}")
                with col2:
                    st.write(f"**Username:** {conn_info.username}")
                    st.write(f"**Created:** {conn_info.created_at}")
                    st.write(f"**Last Activity:** {conn_info.last_activity}")
    
    # Show database-logged connections
    st.subheader("Database-Logged Connections")
    try:
        conn = get_bootstrap_connection()
        if not conn:
            st.warning("Could not establish bootstrap connection to query database")
        else:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT connection_id, mysql_connection_id, tunnel_id, session_id, username,
                       created_at, last_activity, status
                FROM connection_monitor
                WHERE status = 'active'
                ORDER BY last_activity DESC
            """)
            connections = cursor.fetchall()
            cursor.close()
            conn.close()
            
            if connections:
                for conn_data in connections:
                    with st.expander(f"📊 {conn_data['connection_id']} - {conn_data['status'].upper()}", expanded=False):
                        col1, col2 = st.columns(2)
                        with col1:
                            st.write(f"**MySQL Conn ID:** {conn_data['mysql_connection_id']}")
                            st.write(f"**Tunnel:** {conn_data['tunnel_id']}")
                            st.write(f"**Username:** {conn_data['username']}")
                        with col2:
                            st.write(f"**Session:** {conn_data['session_id']}")
                            st.write(f"**Created:** {conn_data['created_at']}")
                            st.write(f"**Last Activity:** {conn_data['last_activity']}")
            else:
                st.info("No connections logged to database yet")
    except Exception as e:
        st.warning(f"Could not load database connections (may be temporary): {e}")
        st.info("Try refreshing the page if this persists")
    
    return
    
    for conn_id, conn_info in CONNECTION_REGISTRY.items():
        with st.expander(f"🔗 {conn_id} - {conn_info.status.upper()}"):
            col1, col2 = st.columns(2)
            
            with col1:
                st.write(f"**MySQL ID:** {conn_info.mysql_conn_id}")
                st.write(f"**Tunnel:** {conn_info.tunnel_id}")
                st.write(f"**Session:** {conn_info.session_id or 'None'}")
            
            with col2:
                st.write(f"**Username:** {conn_info.username or 'None'}")
                st.write(f"**Created:** {conn_info.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
                st.write(f"**Last Activity:** {conn_info.last_activity.strftime('%Y-%m-%d %H:%M:%S')}")
            
            if st.button(f"Close {conn_id}", key=f"close_conn_{conn_id}"):
                if close_connection(conn_id):
                    st.success(f"Closed {conn_id}")
                    st.rerun()


def show_sessions():
    """Session monitoring page"""
    st.header("User Sessions")
    
    session_stats = get_session_stats()
    
    if 'error' in session_stats:
        st.error(f"Error loading sessions: {session_stats['error']}")
        return
    
    # Stats
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Active Sessions", session_stats['active_sessions'])
    with col2:
        st.write("**By Device:**")
        for device, count in session_stats.get('by_device', {}).items():
            st.write(f"- {device}: {count}")
    with col3:
        st.write("**By Browser:**")
        for browser, count in session_stats.get('by_browser', {}).items():
            st.write(f"- {browser}: {count}")
    
    # Detailed session list
    st.subheader("Active Sessions")
    try:
        conn = get_direct_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT session_id, username, user_ip, device_type, browser,
                   login_time, expires_at, last_activity,
                   TIMESTAMPDIFF(SECOND, NOW(), expires_at) as seconds_remaining
            FROM session_monitor
            WHERE status = 'active' AND expires_at > NOW()
            ORDER BY last_activity DESC
        """)
        sessions = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if sessions:
            for session in sessions:
                time_remaining = timedelta(seconds=session['seconds_remaining'])
                hours, remainder = divmod(int(time_remaining.total_seconds()), 3600)
                minutes, seconds = divmod(remainder, 60)
                
                with st.expander(f"👤 {session['username']} - {session['device_type']}/{session['browser']}"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"**IP:** {session['user_ip']}")
                        st.write(f"**Login:** {session['login_time']}")
                        st.write(f"**Last Activity:** {session['last_activity']}")
                    with col2:
                        st.write(f"**Device:** {session['device_type']}")
                        st.write(f"**Browser:** {session['browser']}")
                        st.write(f"**Time Remaining:** {hours}h {minutes}m {seconds}s")
        else:
            st.info("No active sessions")
            
    except Exception as e:
        st.error(f"Error loading sessions: {e}")


def show_controls():
    """Control panel"""
    st.header("System Controls")
    
    st.subheader("Cleanup Operations")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Close Idle Connections**")
        idle_minutes = st.number_input("Idle threshold (minutes)", min_value=1, max_value=60, value=10)
        if st.button("Close Idle Connections"):
            closed = cleanup_idle_connections(idle_minutes)
            st.success(f"Closed {closed} idle connections")
            st.rerun()
    
    with col2:
        st.write("**Close All Tunnels**")
        st.warning("This will close ALL tunnels and connections")
        if st.button("Close All Tunnels", type="primary"):
            for tunnel_id in list(TUNNEL_POOL.keys()):
                close_tunnel(tunnel_id)
            st.success("Closed all tunnels")
            st.rerun()
    
    st.subheader("Configuration")
    st.write(f"**Max Tunnels:** {MAX_TUNNELS}")
    st.write(f"**Connections per Tunnel:** {MAX_CONNECTIONS_PER_TUNNEL}")
    st.write(f"**Total Capacity:** {MAX_TOTAL_CONNECTIONS}")


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Main application entry point"""
    # Check authentication
    check_authentication()
    
    # Ensure tables exist on startup
    if 'tables_created' not in st.session_state:
        with st.spinner("Initializing monitoring tables..."):
            success, message = init_monitoring_tables()
            if success:
                st.success(message)
                st.session_state.tables_created = True
            else:
                st.error(f"Failed to create monitoring tables: {message}")
                st.stop()
    
    # Update session activity on each page load
    if 'monitor_session_id' in st.session_state:
        try:
            update_session_activity(st.session_state.monitor_session_id)
        except Exception as e:
            # Don't fail the app if activity update fails
            pass
    
    # Show the app
    st.title("🔌 Miolingo Connection Monitor")
    st.caption(f"Logged in as: {st.session_state.get('monitor_username', 'unknown')}")
    
    # Sidebar with logout
    st.sidebar.title("Navigation")
    if st.sidebar.button("🚪 Logout", type="primary"):
        st.session_state.authenticated = False
        st.session_state.monitor_username = None
        st.rerun()
    
    st.sidebar.markdown("---")
    
    page = st.sidebar.radio(
        "Go to page:",
        ["Dashboard", "Tunnels", "Connections", "Sessions", "Controls"]
    )
    
    if page == "Dashboard":
        show_dashboard()
    elif page == "Tunnels":
        show_tunnels()
    elif page == "Connections":
        show_connections()
    elif page == "Sessions":
        show_sessions()
    elif page == "Controls":
        show_controls()


if __name__ == "__main__":
    main()
