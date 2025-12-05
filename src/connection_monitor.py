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
# GLOBAL STATE
# ============================================================================

# Pool of 10 tunnels
TUNNEL_POOL: Dict[str, TunnelInfo] = {}
MAX_TUNNELS = 10

# Registry of all connections (up to 250)
CONNECTION_REGISTRY: Dict[str, ConnectionInfo] = {}
MAX_CONNECTIONS_PER_TUNNEL = 25
MAX_TOTAL_CONNECTIONS = MAX_TUNNELS * MAX_CONNECTIONS_PER_TUNNEL

# Session tracking
SESSION_REGISTRY: Dict[str, SessionInfo] = {}


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
        # Get a direct connection (bypass the pool for setup)
        conn = get_direct_connection()
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
        
        return True, "Monitoring tables initialized successfully"
        
    except Error as e:
        return False, f"Failed to initialize tables: {e}"


def get_direct_connection():
    """
    Get a direct MySQL connection for setup/admin tasks.
    Creates a temporary SSH tunnel if needed.
    """
    # Create temporary tunnel for this connection
    tunnel = create_ssh_tunnel()
    
    conn = mysql.connector.connect(
        host='127.0.0.1',
        port=tunnel.local_bind_port,
        database=st.secrets["mysql"]["database"],
        user=st.secrets["mysql"]["user"],
        password=st.secrets["mysql"]["password"],
        connect_timeout=10
    )
    
    return conn


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

def main():
    st.title("🔌 Miolingo Connection Monitor")
    st.caption("Experimental connection pool architecture - v0.1.0")
    
    # Initialize tables on first run
    if 'tables_initialized' not in st.session_state:
        with st.spinner("Initializing monitoring tables..."):
            success, message = init_monitoring_tables()
            if success:
                st.success(message)
                st.session_state.tables_initialized = True
            else:
                st.error(message)
                st.stop()
    
    # Sidebar navigation
    st.sidebar.title("Navigation")
    page = st.sidebar.radio("Go to", [
        "📊 Dashboard",
        "🔌 Tunnels",
        "🔗 Connections",
        "👥 Sessions",
        "⚙️ Controls"
    ])
    
    if page == "📊 Dashboard":
        show_dashboard()
    elif page == "🔌 Tunnels":
        show_tunnels()
    elif page == "🔗 Connections":
        show_connections()
    elif page == "👥 Sessions":
        show_sessions()
    elif page == "⚙️ Controls":
        show_controls()


def show_dashboard():
    """Overview dashboard"""
    st.header("System Overview")
    
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


def show_tunnels():
    """Tunnel management page"""
    st.header("SSH Tunnel Pool")
    
    if not TUNNEL_POOL:
        st.info("No tunnels created yet. Tunnels are created on-demand when connections are requested.")
        return
    
    for tunnel_id, tunnel_info in TUNNEL_POOL.items():
        with st.expander(f"🔌 {tunnel_id} - {tunnel_info.status.upper()}", expanded=True):
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
            
            if st.button(f"Close {tunnel_id}", key=f"close_{tunnel_id}"):
                if close_tunnel(tunnel_id):
                    st.success(f"Closed {tunnel_id}")
                    st.rerun()


def show_connections():
    """Connection management page"""
    st.header("Database Connections")
    
    if not CONNECTION_REGISTRY:
        st.info("No active connections.")
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


if __name__ == "__main__":
    main()
