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
# GLOBAL STATE
# ============================================================================

# Bootstrap tunnel - single untracked tunnel for logging/setup (avoids recursion)
_bootstrap_tunnel: Optional[SSHTunnelForwarder] = None

# Pool of 10 tracked tunnels for user connections
TUNNEL_POOL: Dict[str, TunnelInfo] = {}
MAX_TUNNELS = 10

# Registry of all tracked connections
CONNECTION_REGISTRY: Dict[str, ConnectionInfo] = {}
MAX_CONNECTIONS_PER_TUNNEL = 25
MAX_TOTAL_CONNECTIONS = MAX_TUNNELS * MAX_CONNECTIONS_PER_TUNNEL

# Session tracking
SESSION_REGISTRY: Dict[str, SessionInfo] = {}

# Round-robin tunnel assignment
_next_tunnel_index = 0


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
    global _bootstrap_tunnel
    
    # Ensure we have bootstrap tunnel
    if _bootstrap_tunnel is None or not _bootstrap_tunnel.is_active:
        _bootstrap_tunnel = create_ssh_tunnel()
    
    # Create connection through the tunnel
    conn = mysql.connector.connect(
        host='127.0.0.1',
        port=_bootstrap_tunnel.local_bind_port,
        database=st.secrets["mysql"]["database"],
        user=st.secrets["mysql"]["user"],
        password=st.secrets["mysql"]["password"],
        connect_timeout=10
    )
    
    return conn


def get_tracked_connection(session_id: Optional[str] = None, username: Optional[str] = None):
    """
    Get a tracked MySQL connection from the pool.
    Creates/assigns tunnel, tracks connection, logs to database.
    """
    global _next_tunnel_index
    
    # Get or create a tunnel with capacity
    tunnel_id, tunnel_info = get_or_create_tracked_tunnel()
    
    # Create connection through the tunnel
    conn = mysql.connector.connect(
        host='127.0.0.1',
        port=tunnel_info.tunnel_obj.local_bind_port,
        database=st.secrets["mysql"]["database"],
        user=st.secrets["mysql"]["user"],
        password=st.secrets["mysql"]["password"],
        connect_timeout=10
    )
    
    # Track this connection
    connection_id = f"conn_{uuid.uuid4().hex[:8]}"
    mysql_conn_id = conn.connection_id if hasattr(conn, 'connection_id') else None
    
    conn_info = ConnectionInfo(
        connection_id=connection_id,
        conn_obj=conn,
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
    
    # Log to database using bootstrap connection
    try:
        log_connection_to_db(conn_info)
        log_tunnel_to_db(tunnel_info)
    except Exception as e:
        print(f"Failed to log connection: {e}")
    
    return conn


def get_or_create_tracked_tunnel() -> Tuple[str, TunnelInfo]:
    """
    Get an existing tunnel with capacity or create a new one.
    Uses round-robin assignment.
    """
    global _next_tunnel_index
    
    # Check if we have any tunnels with capacity
    for tunnel_id, tunnel_info in TUNNEL_POOL.items():
        if (tunnel_info.status == 'active' and
            tunnel_info.connection_count < MAX_CONNECTIONS_PER_TUNNEL and
            tunnel_info.tunnel_obj and
            tunnel_info.tunnel_obj.is_active):
            return tunnel_id, tunnel_info
    
    # Create new tunnel if under limit
    if len(TUNNEL_POOL) < MAX_TUNNELS:
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
        return tunnel_id, tunnel_info
    
    # Pool full - use round robin
    tunnel_ids = list(TUNNEL_POOL.keys())
    tunnel_id = tunnel_ids[_next_tunnel_index % len(tunnel_ids)]
    _next_tunnel_index += 1
    
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


def create_ssh_tunnel() -> SSHTunnelForwarder:
    """
    Create a single SSH tunnel.
    Returns the tunnel object with PID tracking.
    """
    import paramiko
    from io import StringIO
    
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


def cleanup_idle_connections(idle_threshold_minutes: int = 10):
    """
    Close connections that have been idle for longer than threshold.
    """
    threshold = datetime.now() - timedelta(minutes=idle_threshold_minutes)
    
    closed_count = 0
    for conn_id, conn_info in list(CONNECTION_REGISTRY.items()):
        if conn_info.last_activity < threshold:
            if close_connection(conn_id):
                closed_count += 1
    
    return closed_count


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
    
    with col1:
        active_tunnels = sum(1 for t in TUNNEL_POOL.values() if t.status == 'active')
        st.metric("Active Tunnels", f"{active_tunnels}/{MAX_TUNNELS}")
    
    with col2:
        active_conns = sum(1 for c in CONNECTION_REGISTRY.values() if c.status == 'active')
        st.metric("Active Connections", f"{active_conns}/{MAX_TOTAL_CONNECTIONS}")
    
    with col3:
        session_stats = get_session_stats()
        st.metric("Active Sessions", session_stats.get('active_sessions', 0))
    
    with col4:
        capacity = (active_conns / MAX_TOTAL_CONNECTIONS) * 100 if MAX_TOTAL_CONNECTIONS > 0 else 0
        st.metric("Pool Capacity", f"{capacity:.1f}%")
    
    # Resource usage chart
    st.subheader("Resource Usage")
    st.info("Pool architecture: 10 tunnels × 25 connections = 250 total capacity")
    
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
        if st.button("🧹 Clean Stale"):
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
                    col1, col2 = st.columns(2)
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
        else:
            st.info("No active connection monitor sessions")
            
    except Exception as e:
        st.error(f"Error loading monitor sessions: {e}")


def show_tunnels():
    """Tunnel management page"""
    st.header("SSH Tunnel Pool")
    
    # Test controls
    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("🧪 Create Test Connection"):
            try:
                conn = get_tracked_connection(
                    session_id=st.session_state.get('monitor_session_id'),
                    username=st.session_state.get('monitor_username')
                )
                conn.close()
                st.success("Created and logged test connection!")
                st.rerun()
            except Exception as e:
                st.error(f"Failed to create test connection: {e}")
    
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
        st.error(f"Error loading database tunnels: {e}")


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
        st.error(f"Error loading database connections: {e}")
    
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
