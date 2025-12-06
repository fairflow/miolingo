"""
Miolingo Connection Pool - Reusable SSH tunnel and MySQL connection management
Extracted from connection_monitor.py for use in app.py and miolingo-admin.py

This module provides:
- Pool of SSH tunnels (configurable size)
- Multiple DB connections per tunnel
- Connection tracking and lifecycle management
- Session tracking
- Health monitoring and cleanup
- Context manager for ephemeral bootstrap connections

Author: Miolingo Team
Version: 2.0.0
"""

__version__ = "2.0.0"

import mysql.connector
from mysql.connector import Error
from sshtunnel import SSHTunnelForwarder
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any, Tuple
from contextlib import contextmanager
import warnings
import logging
import time
import os
import signal
import uuid
import random
from dataclasses import dataclass, asdict
import paramiko

# Suppress noise
warnings.filterwarnings('ignore', category=DeprecationWarning, module='paramiko')
logging.getLogger('paramiko').setLevel(logging.WARNING)

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
# CONFIGURATION
# ============================================================================

MAX_TUNNELS = 10  # Pool size (8 normal + 2 spare capacity)
MAX_CONNECTIONS_PER_TUNNEL = 10  # Connections per tunnel
MAX_TOTAL_CONNECTIONS = MAX_TUNNELS * MAX_CONNECTIONS_PER_TUNNEL  # 100 total
SOFT_LIMIT_CONNECTIONS = int(MAX_TOTAL_CONNECTIONS * 0.9)  # 90 - allow reconnects
HARD_LIMIT_CONNECTIONS = MAX_TOTAL_CONNECTIONS  # 100 - block all new logins

# Automatic cleanup configuration
AUTO_CLEANUP_INTERVAL_MINUTES = 10  # How often to run background cleanup
IDLE_CONNECTION_THRESHOLD_MINUTES = 10  # Close connections idle longer than this


# ============================================================================
# CONNECTION POOL STATE
# ============================================================================

class ConnectionPool:
    """
    Thread-safe connection pool manager.
    Manages SSH tunnels and MySQL connections across the pool.
    """
    
    def __init__(self, secrets_config: Dict[str, Any]):
        """
        Initialize connection pool.
        
        Args:
            secrets_config: Dictionary with ssh and mysql configuration
                Expected structure:
                {
                    'ssh': {'host', 'port', 'username', 'pkey_path'},
                    'mysql': {'host', 'port', 'database', 'user', 'password'}
                }
        """
        self.secrets = secrets_config
        self.tunnel_pool: Dict[str, TunnelInfo] = {}
        self.connection_registry: Dict[str, ConnectionInfo] = {}
        self.session_registry: Dict[str, SessionInfo] = {}
        self._next_tunnel_index = 0
        self._last_cleanup_time = None
    
    def create_ssh_tunnel(self) -> SSHTunnelForwarder:
        """
        Create a new SSH tunnel to the database server.
        Supports two modes for SSH key:
        1. Local development: key_path in secrets (file path)
        2. Streamlit Cloud: key_content in secrets (paste private key directly)
        """
        from io import StringIO
        
        ssh_config = self.secrets['ssh']
        mysql_config = self.secrets['mysql']
        
        # Handle SSH key - either from file path or direct content
        if "key_content" in ssh_config:
            # Streamlit Cloud: parse key content into paramiko key object
            key_content = ssh_config["key_content"]
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
            from pathlib import Path
            ssh_key_path = Path(ssh_config["key_path"]).expanduser().resolve()
            
            # Load the key file
            with open(ssh_key_path, 'r') as f:
                key_file = StringIO(f.read())
            
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
                raise ValueError(f"Could not parse SSH key from {ssh_key_path}")
        
        tunnel = SSHTunnelForwarder(
            (ssh_config['host'], int(ssh_config['port'])),
            ssh_username=ssh_config['username'],
            ssh_pkey=ssh_key,
            remote_bind_address=(mysql_config['host'], mysql_config['port']),
            set_keepalive=30
        )
        
        tunnel.start()
        return tunnel
    
    @contextmanager
    def get_bootstrap_connection(self):
        """
        Context manager for TRULY EPHEMERAL MySQL connection.
        Creates temporary tunnel → connection → automatically closes both.
        
        CRITICAL: Prevents tunnel proliferation (125 SSH tunnel limit).
        
        Usage:
            with pool.get_bootstrap_connection() as conn:
                cursor = conn.cursor()
                # use conn
                # tunnel and connection automatically closed on exit
        """
        tunnel = self.create_ssh_tunnel()
        conn = None
        
        try:
            conn = mysql.connector.connect(
                host='127.0.0.1',
                port=tunnel.local_bind_port,
                database=self.secrets['mysql']['database'],
                user=self.secrets['mysql']['user'],
                password=self.secrets['mysql']['password'],
                connect_timeout=10
            )
            yield conn
        finally:
            if conn:
                try:
                    conn.close()
                except:
                    pass
            try:
                tunnel.stop()
            except:
                pass
    
    def get_tunnel_pid(self, tunnel: SSHTunnelForwarder) -> Optional[int]:
        """
        Get the process ID of an SSH tunnel using multiple detection methods.
        """
        # Method 1: Try _transport attribute
        try:
            if hasattr(tunnel, '_transport') and tunnel._transport:
                sock = tunnel._transport.sock
                if sock and hasattr(sock, 'fileno'):
                    import subprocess
                    fd = sock.fileno()
                    result = subprocess.run(
                        ['lsof', '-F', 'p', '-a', f'-d{fd}'],
                        capture_output=True,
                        text=True
                    )
                    for line in result.stdout.split('\n'):
                        if line.startswith('p'):
                            return int(line[1:])
        except:
            pass
        
        # Method 2: Try _server_process attribute
        try:
            if hasattr(tunnel, '_server_process') and tunnel._server_process:
                return tunnel._server_process.pid
        except:
            pass
        
        # Method 3: Use lsof with local port
        try:
            if tunnel.local_bind_port:
                import subprocess
                result = subprocess.run(
                    ['lsof', '-ti', f':{tunnel.local_bind_port}'],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0 and result.stdout.strip():
                    return int(result.stdout.strip().split()[0])
        except:
            pass
        
        return None
    
    def get_or_create_tracked_tunnel(self) -> str:
        """
        Get an existing tunnel with capacity or create a new one.
        Uses database to track actual connection counts (persistent across restarts).
        Returns tunnel_id.
        """
        # Get actual connection counts from database
        tunnel_conn_counts = {}
        try:
            with self.get_bootstrap_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute("""
                    SELECT tunnel_id, COUNT(*) as conn_count
                    FROM connection_monitor
                    WHERE status = 'active'
                    GROUP BY tunnel_id
                """)
                results = cursor.fetchall()
                cursor.close()
                
                for row in results:
                    if row['tunnel_id']:
                        tunnel_conn_counts[row['tunnel_id']] = row['conn_count']
        except Exception as e:
            print(f"Warning: Could not query connection counts: {e}")
        
        # Try to find existing tunnel with capacity
        for tunnel_id, tunnel_info in self.tunnel_pool.items():
            actual_count = tunnel_conn_counts.get(tunnel_id, 0)
            
            if tunnel_info.status == 'active' and actual_count < MAX_CONNECTIONS_PER_TUNNEL:
                tunnel_info.last_used = datetime.now()
                tunnel_info.connection_count = actual_count
                return tunnel_id
        
        # No available tunnel - create new one if under limit
        if len(self.tunnel_pool) < MAX_TUNNELS:
            tunnel_id = f"tunnel_{self._next_tunnel_index}"
            self._next_tunnel_index += 1
            
            tunnel_obj = self.create_ssh_tunnel()
            pid = self.get_tunnel_pid(tunnel_obj)
            
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
            
            self.tunnel_pool[tunnel_id] = tunnel_info
            
            # Log to database immediately (prevents foreign key errors)
            try:
                with self.get_bootstrap_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT INTO tunnel_monitor 
                        (tunnel_id, pid, local_port, created_at, last_used, status, connection_count)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                        pid = VALUES(pid),
                        local_port = VALUES(local_port),
                        last_used = VALUES(last_used),
                        status = VALUES(status)
                    """, (tunnel_id, pid, tunnel_obj.local_bind_port,
                          tunnel_info.created_at, tunnel_info.last_used,
                          'active', 0))
                    conn.commit()
                    cursor.close()
            except Exception as e:
                print(f"Warning: Could not log tunnel creation: {e}")
            
            return tunnel_id
        
        # Pool exhausted - use round-robin
        if self.tunnel_pool:
            tunnel_ids = list(self.tunnel_pool.keys())
            selected = tunnel_ids[random.randint(0, len(tunnel_ids) - 1)]
            return selected
        
        raise RuntimeError("No tunnels available and cannot create new one")
    
    def get_tracked_connection(self, session_id: str, username: str) -> mysql.connector.MySQLConnection:
        """
        Create and track a database connection through the pool.
        Connection is logged to the database and added to the registry.
        
        Args:
            session_id: User session identifier
            username: Username for tracking
            
        Returns:
            MySQL connection object
        """
        tunnel_id = self.get_or_create_tracked_tunnel()
        tunnel_info = self.tunnel_pool[tunnel_id]
        
        # Create connection through the selected tunnel
        conn = mysql.connector.connect(
            host='127.0.0.1',
            port=tunnel_info.local_port,
            database=self.secrets['mysql']['database'],
            user=self.secrets['mysql']['user'],
            password=self.secrets['mysql']['password'],
            connect_timeout=10
        )
        
        # Get MySQL connection ID
        cursor = conn.cursor()
        cursor.execute("SELECT CONNECTION_ID()")
        mysql_conn_id = cursor.fetchone()[0]
        cursor.close()
        
        # Generate connection ID
        connection_id = f"{session_id}_{uuid.uuid4().hex[:8]}"
        
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
        
        # Add to registry
        self.connection_registry[connection_id] = conn_info
        
        # Update tunnel connection count
        tunnel_info.connection_count += 1
        
        # ========================================
        # RECOMMENDATION 4: Log First Connection Per Session
        # ========================================
        # Check if this is the first connection for this session
        is_first_connection = session_id not in self.session_registry
        
        # Log to database
        try:
            with self.get_bootstrap_connection() as admin_conn:
                cursor = admin_conn.cursor()
                cursor.execute("""
                    INSERT INTO connection_monitor 
                    (connection_id, mysql_connection_id, tunnel_id, session_id, username, 
                     created_at, last_activity, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (connection_id, mysql_conn_id, tunnel_id, session_id, username,
                      conn_info.created_at, conn_info.last_activity, 'active'))
                admin_conn.commit()
                
                # Log first connection event for debugging/analytics
                if is_first_connection:
                    print(f"[FIRST_CONNECTION] session_id={session_id}, username={username}, tunnel={tunnel_id}, mysql_conn={mysql_conn_id}")
                    # Track in session registry
                    now = datetime.now()
                    session_info = SessionInfo(
                        session_id=session_id,
                        username=username,
                        user_ip='unknown',  # Will be updated by session_monitor
                        user_agent='unknown',
                        device_type='unknown',
                        browser='unknown',
                        login_time=now,
                        expires_at=now,
                        last_activity=now,
                        connection_ids=[connection_id]
                    )
                    self.session_registry[session_id] = session_info
                else:
                    # Add to existing session's connection list
                    if session_id in self.session_registry:
                        self.session_registry[session_id].connection_ids.append(connection_id)
                
                cursor.close()
        except Exception as e:
            import logging
            logging.error(f"❌ FAILED to log connection to database '{self.secrets['mysql']['database']}': {e}")
            logging.error(f"   Connection details: session_id={session_id}, username={username}, tunnel={tunnel_id}")
            raise  # Don't hide the error - let it surface for debugging
        
        return conn
    
    def close_connection(self, connection_id: str) -> bool:
        """
        Close a specific database connection.
        Returns True if successful.
        """
        if connection_id not in self.connection_registry:
            return False
        
        conn_info = self.connection_registry[connection_id]
        
        # Close the connection
        try:
            if conn_info.conn_obj and conn_info.conn_obj.is_connected():
                conn_info.conn_obj.close()
        except:
            pass
        
        # Update tunnel connection count
        if conn_info.tunnel_id in self.tunnel_pool:
            self.tunnel_pool[conn_info.tunnel_id].connection_count -= 1
        
        # Update status
        conn_info.status = 'closed'
        
        # Update database
        try:
            with self.get_bootstrap_connection() as admin_conn:
                cursor = admin_conn.cursor()
                cursor.execute("""
                    UPDATE connection_monitor SET status = 'closed' WHERE connection_id = %s
                """, (connection_id,))
                admin_conn.commit()
                cursor.close()
        except:
            pass
        
        # Remove from registry
        del self.connection_registry[connection_id]
        
        return True
    
    def close_session_connection(self, session_id: str) -> int:
        """
        Close all connections for a specific session.
        Returns the number of connections closed.
        """
        closed_count = 0
        
        # Find all connections for this session
        connections_to_close = [
            conn_id for conn_id, conn_info in self.connection_registry.items()
            if conn_info.session_id == session_id
        ]
        
        # Close each connection
        for conn_id in connections_to_close:
            if self.close_connection(conn_id):
                closed_count += 1
        
        return closed_count
    
    def check_connection_capacity(self, is_existing_user: bool = False) -> Tuple[bool, str, int]:
        """
        Check if new connection can be created based on soft/hard limits.
        
        Args:
            is_existing_user: True if user is reconnecting (logged in before)
        
        Returns:
            (can_connect, message, current_count)
        """
        try:
            with self.get_bootstrap_connection() as bootstrap:
                cursor = bootstrap.cursor()
                cursor.execute("SELECT COUNT(*) FROM connection_monitor WHERE status = 'active'")
                active_count = cursor.fetchone()[0]
                cursor.close()
            
            # Hard limit - block everyone
            if active_count >= HARD_LIMIT_CONNECTIONS:
                return False, f"System at maximum capacity ({active_count}/{HARD_LIMIT_CONNECTIONS} connections). Please try again later.", active_count
            
            # Soft limit - only allow existing users to reconnect
            if active_count >= SOFT_LIMIT_CONNECTIONS:
                if not is_existing_user:
                    return False, f"System nearing capacity ({active_count}/{HARD_LIMIT_CONNECTIONS} connections). New logins temporarily restricted.", active_count
            
            return True, "OK", active_count
            
        except Exception as e:
            # If check fails, allow connection (fail open)
            return True, f"Capacity check failed: {e}", 0
    
    def cleanup_dead_connections(self) -> int:
        """
        Clean connections from DB that no longer exist in MySQL.
        Uses SHOW PROCESSLIST to verify connections are actually alive.
        Returns count of cleaned connections.
        """
        cleaned = 0
        
        try:
            # Get all MySQL connection IDs from SHOW PROCESSLIST
            with self.get_bootstrap_connection() as admin_conn:
                cursor = admin_conn.cursor()
                cursor.execute("SHOW PROCESSLIST")
                alive_ids = {row[0] for row in cursor.fetchall()}
                cursor.close()
                
                # Get all tracked connections
                cursor = admin_conn.cursor(dictionary=True)
                cursor.execute("""
                    SELECT connection_id, mysql_connection_id 
                    FROM connection_monitor 
                    WHERE status = 'active'
                """)
                tracked = cursor.fetchall()
                cursor.close()
                
                # Mark dead connections
                for row in tracked:
                    if row['mysql_connection_id'] and row['mysql_connection_id'] not in alive_ids:
                        cursor = admin_conn.cursor()
                        cursor.execute("""
                            UPDATE connection_monitor 
                            SET status = 'closed'
                            WHERE connection_id = %s
                        """, (row['connection_id'],))
                        cleaned += 1
                        cursor.close()
                
                if cleaned > 0:
                    admin_conn.commit()
        
        except Exception as e:
            print(f"Cleanup error: {e}")
        
        return cleaned
    
    def init_monitoring_tables(self) -> Tuple[bool, str]:
        """
        Create database tables for connection monitoring.
        Tables:
        - tunnel_monitor: SSH tunnel tracking
        - connection_monitor: DB connection tracking
        - session_monitor: User session tracking with IP, device, browser
        """
        try:
            with self.get_bootstrap_connection() as conn:
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
            
            return True, "Monitoring tables initialized successfully"
            
        except Error as e:
            return False, f"Failed to initialize tables: {e}"
