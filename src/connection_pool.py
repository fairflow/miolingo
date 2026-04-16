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
    app_name: Optional[str]  # Which app created this connection
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
IDLE_CONNECTION_THRESHOLD_MINUTES = 60 * 24 * 7  # Close connections idle longer than this


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

    def _is_tunnel_healthy(self, tunnel_info: TunnelInfo) -> bool:
        """Best-effort health check for an in-memory SSHTunnelForwarder."""
        tunnel = tunnel_info.tunnel_obj
        if tunnel is None:
            return False
        try:
            if not getattr(tunnel, "is_active", False):
                return False
        except Exception:
            return False

        # If sshtunnel exposes per-bind status, use it.
        try:
            tunnel_is_up = getattr(tunnel, "tunnel_is_up", None)
            if isinstance(tunnel_is_up, dict) and tunnel_is_up:
                if not any(bool(v) for v in tunnel_is_up.values()):
                    return False
        except Exception:
            # Don't fail hard on introspection issues.
            pass

        return bool(tunnel_info.local_port)

    def _looks_like_dead_tunnel_error(self, err: Exception) -> bool:
        msg = str(err)
        needles = (
            "SSH session not active",
            "open new channel",
            "Socket is closed",
            "Broken pipe",
            "Connection reset by peer",
            "Error reading SSH protocol banner",
            "EOFError",
            "Unable to connect",
            "Can't connect to MySQL server",
            "Connection refused",
        )
        return any(n in msg for n in needles)

    def _stop_tunnel_safely(self, tunnel: Optional[SSHTunnelForwarder]) -> None:
        if tunnel is None:
            return
        try:
            tunnel.stop()
        except Exception:
            pass

    def _recreate_tracked_tunnel(self, tunnel_id: str) -> None:
        """Stop and recreate an existing tracked tunnel in-memory and in DB.

        Also marks any DB connections for that tunnel as closed, since a tunnel
        restart invalidates those forwarded connections.
        """
        old_info = self.tunnel_pool.get(tunnel_id)
        if old_info and old_info.tunnel_obj:
            self._stop_tunnel_safely(old_info.tunnel_obj)

        tunnel_obj = self.create_ssh_tunnel()
        pid = self.get_tunnel_pid(tunnel_obj)
        now = datetime.now()

        if old_info:
            old_info.tunnel_obj = tunnel_obj
            old_info.pid = pid
            old_info.local_port = tunnel_obj.local_bind_port
            old_info.created_at = now
            old_info.last_used = now
            old_info.status = 'active'
            old_info.connection_count = 0
        else:
            self.tunnel_pool[tunnel_id] = TunnelInfo(
                tunnel_id=tunnel_id,
                tunnel_obj=tunnel_obj,
                pid=pid,
                local_port=tunnel_obj.local_bind_port,
                created_at=now,
                last_used=now,
                status='active',
                connection_count=0,
            )

        # Give tunnel time to stabilize
        time.sleep(0.3)

        # Persist updates and clear stale connection rows.
        try:
            with self.get_bootstrap_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("START TRANSACTION")

                cursor.execute(
                    """
                    UPDATE connection_monitor
                    SET status = 'closed'
                    WHERE tunnel_id = %s AND status = 'active'
                    """,
                    (tunnel_id,),
                )

                cursor.execute(
                    """
                    INSERT INTO tunnel_monitor
                    (tunnel_id, pid, local_port, created_at, last_used, status, connection_count)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        pid = VALUES(pid),
                        local_port = VALUES(local_port),
                        last_used = VALUES(last_used),
                        status = VALUES(status),
                        connection_count = VALUES(connection_count)
                    """,
                    (tunnel_id, pid, tunnel_obj.local_bind_port, now, now, 'active', 0),
                )

                conn.commit()
                cursor.close()
        except Exception as e:
            logging.warning(f"Warning: could not persist recreated tunnel {tunnel_id}: {e}")

    def _ensure_tracked_tunnel_alive(self, tunnel_id: str) -> None:
        tunnel_info = self.tunnel_pool.get(tunnel_id)
        if tunnel_info is None:
            return
        if self._is_tunnel_healthy(tunnel_info):
            return
        logging.warning(f"Tracked tunnel {tunnel_id} unhealthy; recreating")
        self._recreate_tracked_tunnel(tunnel_id)
    
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
    
    def get_direct_connection(self):
        """
        Return a real MySQL connection object (not a context manager) using
        an available tracked tunnel from the pool, or creating one if needed.
        For pre-auth ephemeral use where storing in session state is required.
        Caller is responsible for closing when done.
        """
        # Reuse first available healthy tunnel
        for tunnel_info in self.tunnel_pool.values():
            if tunnel_info.status == 'active' and self._is_tunnel_healthy(tunnel_info):
                conn = mysql.connector.connect(
                    host='127.0.0.1',
                    port=tunnel_info.local_port,
                    database=self.secrets['mysql']['database'],
                    user=self.secrets['mysql']['user'],
                    password=self.secrets['mysql']['password'],
                    connect_timeout=10,
                    use_pure=True,
                )
                return conn

        # No existing tunnel — create one and register it in pool + DB
        tunnel = self.create_ssh_tunnel()
        pid = self.get_tunnel_pid(tunnel)
        now = datetime.now()

        # Store tunnel in pool so it can be reused (avoid proliferation)
        tunnel_id = f"bootstrap_{self._next_tunnel_index}"
        self._next_tunnel_index += 1
        self.tunnel_pool[tunnel_id] = TunnelInfo(
            tunnel_id=tunnel_id,
            tunnel_obj=tunnel,
            pid=pid,
            local_port=tunnel.local_bind_port,
            created_at=now,
            last_used=now,
            status='active',
            connection_count=0,
        )

        # Give tunnel time to stabilize
        time.sleep(0.3)

        conn = mysql.connector.connect(
            host='127.0.0.1',
            port=tunnel.local_bind_port,
            database=self.secrets['mysql']['database'],
            user=self.secrets['mysql']['user'],
            password=self.secrets['mysql']['password'],
            connect_timeout=10,
            use_pure=True,
        )

        # Register in tunnel_monitor DB table so FK constraints work when
        # this tunnel is later picked up by get_tracked_connection()
        try:
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
            """, (tunnel_id, pid, tunnel.local_bind_port, now, now, 'active', 0))
            conn.commit()
            cursor.close()
        except Exception as e:
            logging.warning(f"Could not register bootstrap tunnel {tunnel_id} in DB: {e}")

        return conn

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
        CRITICAL: This is called ONCE at tunnel creation and stored in database.
        Always read from database thereafter - single source of truth.
        """
        import subprocess
        
        pid = None
        
        # Method 1: Try _transport.get_pid() (if available)
        try:
            if hasattr(tunnel, '_transport') and tunnel._transport:
                if hasattr(tunnel._transport, 'get_pid'):
                    pid = tunnel._transport.get_pid()
                if pid:
                    print(f"✓ PID {pid} detected via _transport.get_pid()")
                    return pid
        except Exception as e:
            print(f"Method 1 (_transport.get_pid) failed: {e}")
        
        # Method 2: Try _server_process.pid
        try:
            if hasattr(tunnel, '_server_process') and tunnel._server_process:
                pid = tunnel._server_process.pid
                if pid:
                    print(f"✓ PID {pid} detected via _server_process.pid")
                    return pid
        except Exception as e:
            print(f"Method 2 (_server_process.pid) failed: {e}")
        
        # Method 3: Use lsof with local port (most reliable for macOS/Linux)
        try:
            if tunnel.local_bind_port:
                result = subprocess.run(
                    ['lsof', '-ti', f':{tunnel.local_bind_port}'],
                    capture_output=True,
                    text=True,
                    timeout=2
                )
                if result.returncode == 0 and result.stdout.strip():
                    # Get first PID from output (may have multiple lines)
                    pid = int(result.stdout.strip().split('\n')[0])
                    if pid:
                        print(f"✓ PID {pid} detected via lsof on port {tunnel.local_bind_port}")
                        return pid
        except Exception as e:
            print(f"Method 3 (lsof) failed: {e}")
        
        print(f"⚠️  Could not determine PID for tunnel on port {getattr(tunnel, 'local_bind_port', 'unknown')}")
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
                # Avoid reusing stale tunnels after long idle periods.
                try:
                    self._ensure_tracked_tunnel_alive(tunnel_id)
                except Exception as e:
                    logging.warning(f"Tunnel {tunnel_id} failed health/recreate check: {e}")
                    tunnel_info.status = 'dead'
                    continue
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
            
            # Give tunnel time to stabilize before first connection
            time.sleep(0.3)
            
            # Log to database immediately (prevents foreign key errors)
            # Use transaction to ensure atomicity
            try:
                with self.get_bootstrap_connection() as conn:
                    cursor = conn.cursor()
                    # Start transaction (implicitly started, make it explicit)
                    cursor.execute("START TRANSACTION")
                    
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
    
    def get_tracked_connection(self, session_id: str, username: str, app_name: str = 'unknown') -> mysql.connector.MySQLConnection:
        """
        Create and track a database connection through the pool.
        Connection is logged to the database and added to the registry.
        
        Args:
            session_id: User session identifier
            username: Username for tracking
            app_name: Name of the app creating the connection (e.g., 'app', 'connection_monitor', 'miolingo-admin')
            
        Returns:
            MySQL connection object
        """
        tunnel_id = self.get_or_create_tracked_tunnel()
        # Ensure tunnel is alive before using it.
        self._ensure_tracked_tunnel_alive(tunnel_id)
        tunnel_info = self.tunnel_pool[tunnel_id]
        
        # Create connection through the selected tunnel with retry + tunnel recreate.
        max_retries = 3
        retry_delay = 0.25
        conn = None
        last_error = None
        
        for attempt in range(max_retries):
            try:
                conn = mysql.connector.connect(
                    host='127.0.0.1',
                    port=tunnel_info.local_port,
                    database=self.secrets['mysql']['database'],
                    user=self.secrets['mysql']['user'],
                    password=self.secrets['mysql']['password'],
                    connect_timeout=10
                )
                break  # Success
            except Exception as e:
                last_error = e

                if attempt >= max_retries - 1:
                    raise last_error

                # If the tunnel died (common overnight), recreate and retry.
                if self._looks_like_dead_tunnel_error(e):
                    try:
                        self._recreate_tracked_tunnel(tunnel_id)
                        tunnel_info = self.tunnel_pool[tunnel_id]
                    except Exception as recreate_err:
                        raise last_error from recreate_err
                    time.sleep(retry_delay)
                    continue

                # Transient MySQL handshake hiccup.
                if "reading initial communication packet" in str(e):
                    time.sleep(retry_delay)
                    continue

                raise  # Don't retry other errors
        
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
            app_name=app_name,
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
        
        # Log to database with pessimistic locking
        try:
            with self.get_bootstrap_connection() as admin_conn:
                cursor = admin_conn.cursor()
                
                # Start transaction
                cursor.execute("START TRANSACTION")
                
                # Lock the tunnel row for update
                cursor.execute("""
                    SELECT connection_count FROM tunnel_monitor
                    WHERE tunnel_id = %s
                    FOR UPDATE
                """, (tunnel_id,))
                cursor.fetchall()  # Consume the SELECT result
                
                # Insert connection record
                cursor.execute("""
                    INSERT INTO connection_monitor 
                    (connection_id, mysql_connection_id, tunnel_id, session_id, username, app_name,
                     created_at, last_activity, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (connection_id, mysql_conn_id, tunnel_id, session_id, username, app_name,
                      conn_info.created_at, conn_info.last_activity, 'active'))
                
                # Atomically increment connection count
                cursor.execute("""
                    UPDATE tunnel_monitor 
                    SET connection_count = connection_count + 1,
                        last_used = %s
                    WHERE tunnel_id = %s
                """, (datetime.now(), tunnel_id))
                
                admin_conn.commit()
                
                # Log first connection event for debugging/analytics
                if is_first_connection:
                    print(f"[FIRST_CONNECTION] session_id={session_id}, username={username}, tunnel={tunnel_id}, mysql_conn={mysql_conn_id}")
                    # Track in session registry
                    now = datetime.now()
                    session_info = SessionInfo(
                        session_id=session_id,
                        username=username,
                        user_ip='unknown',  # Updated via unified `sessions` table
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
        
        # Update database with pessimistic locking
        try:
            with self.get_bootstrap_connection() as admin_conn:
                cursor = admin_conn.cursor()
                
                # Start transaction
                cursor.execute("START TRANSACTION")
                
                # Lock the tunnel row for update
                cursor.execute("""
                    SELECT connection_count FROM tunnel_monitor
                    WHERE tunnel_id = %s
                    FOR UPDATE
                """, (conn_info.tunnel_id,))
                cursor.fetchall()  # Consume the SELECT result
                
                # Update connection status
                cursor.execute("""
                    UPDATE connection_monitor SET status = 'closed' WHERE connection_id = %s
                """, (connection_id,))
                
                # Atomically decrement connection count
                cursor.execute("""
                    UPDATE tunnel_monitor 
                    SET connection_count = GREATEST(0, connection_count - 1)
                    WHERE tunnel_id = %s
                """, (conn_info.tunnel_id,))
                
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
    
    def cleanup_stale_connections(self, stale_hours: int = 12) -> int:
        """
        Delete rows from connection_monitor that are no longer useful:
          - Any row with status = 'closed'
          - Any row with status = 'active' but last_activity older than stale_hours

        Returns count of rows deleted.
        """
        deleted = 0
        try:
            with self.get_bootstrap_connection() as admin_conn:
                cursor = admin_conn.cursor()
                cursor.execute(
                    """
                    DELETE FROM connection_monitor
                    WHERE status = 'closed'
                       OR (status = 'active' AND last_activity < NOW() - INTERVAL %s HOUR)
                    """,
                    (stale_hours,),
                )
                deleted = cursor.rowcount
                admin_conn.commit()
                cursor.close()
        except Exception as e:
            print(f"Stale connection cleanup error: {e}")
        return deleted

    def init_monitoring_tables(self) -> Tuple[bool, str]:
        """
        Create database tables for connection monitoring.
        Tables:
        - tunnel_monitor: SSH tunnel tracking
        - connection_monitor: DB connection tracking
        - sessions: User session tracking is handled by the unified `sessions` table
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
                
                # Add app_name column if it doesn't exist (migration for existing tables)
                try:
                    cursor.execute("""
                        ALTER TABLE connection_monitor 
                        ADD COLUMN app_name VARCHAR(100) AFTER username,
                        ADD INDEX idx_app_name (app_name)
                    """)
                except mysql.connector.Error as e:
                    # Column already exists or other error - that's okay
                    if e.errno != 1060:  # 1060 = Duplicate column name
                        pass  # Ignore duplicate column errors, raise others if needed

                conn.commit()
                cursor.close()
            
            return True, "Monitoring tables initialized successfully"
            
        except Error as e:
            return False, f"Failed to initialize tables: {e}"
    
    def get_tunnel_info_from_db(self, tunnel_id: str) -> Optional[dict]:
        """
        Get tunnel information from database (single source of truth).
        Always use this instead of in-memory tunnel_pool for display/monitoring.
        
        Returns:
            Dict with tunnel info from database, or None if not found
        """
        try:
            with self.get_bootstrap_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute("""
                    SELECT tunnel_id, pid, local_port, created_at, last_used, 
                           status, connection_count
                    FROM tunnel_monitor
                    WHERE tunnel_id = %s
                """, (tunnel_id,))
                result = cursor.fetchone()
                cursor.close()
                return result
        except Exception as e:
            print(f"Could not read tunnel info from database: {e}")
            return None
