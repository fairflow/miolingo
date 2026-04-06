"""
Tests for connection pool and debug log fixes.

Bug 1: get_connection() pre-auth path must not store a generator (context manager).
Bug 2: write_debug_log() must return gracefully when 'ssh' not in secrets.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock
from contextlib import contextmanager

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestGetDirectConnection:
    """ConnectionPool.get_direct_connection() returns a real connection, not a generator."""

    def test_returns_real_connection_not_generator(self):
        """get_direct_connection() must return a mysql connection, not a _GeneratorContextManager."""
        from connection_pool import ConnectionPool

        pool = ConnectionPool({
            'ssh': {'host': 'h', 'port': 22, 'username': 'u', 'key_path': '/dev/null'},
            'mysql': {'host': '127.0.0.1', 'port': 3306, 'database': 'db', 'user': 'u', 'password': 'p'},
        })

        fake_conn = MagicMock()
        fake_tunnel = MagicMock()
        fake_tunnel.local_bind_port = 13306

        with patch.object(pool, 'create_ssh_tunnel', return_value=fake_tunnel), \
             patch.object(pool, 'get_tunnel_pid', return_value=123), \
             patch('connection_pool.mysql.connector.connect', return_value=fake_conn):
            conn = pool.get_direct_connection()

        # Must be the real connection object, not a generator/context manager
        assert conn is fake_conn
        assert not hasattr(conn, '__enter__') or not hasattr(conn, '__exit__') or isinstance(conn, MagicMock)

    def test_reuses_existing_healthy_tunnel(self):
        """get_direct_connection() should prefer an existing healthy tunnel."""
        from connection_pool import ConnectionPool, TunnelInfo
        from datetime import datetime

        pool = ConnectionPool({
            'ssh': {'host': 'h', 'port': 22, 'username': 'u', 'key_path': '/dev/null'},
            'mysql': {'host': '127.0.0.1', 'port': 3306, 'database': 'db', 'user': 'u', 'password': 'p'},
        })

        fake_tunnel = MagicMock()
        fake_tunnel.is_active = True
        fake_tunnel.local_bind_port = 13306

        pool.tunnel_pool['tunnel_0'] = TunnelInfo(
            tunnel_id='tunnel_0',
            tunnel_obj=fake_tunnel,
            pid=100,
            local_port=13306,
            created_at=datetime.now(),
            last_used=datetime.now(),
            status='active',
            connection_count=1,
        )

        fake_conn = MagicMock()
        with patch('connection_pool.mysql.connector.connect', return_value=fake_conn):
            conn = pool.get_direct_connection()

        assert conn is fake_conn


class TestBootstrapConnectionIsContextManager:
    """get_bootstrap_connection() must remain a context manager (not broken by our changes)."""

    def test_is_context_manager(self):
        from connection_pool import ConnectionPool

        pool = ConnectionPool({
            'ssh': {'host': 'h', 'port': 22, 'username': 'u', 'key_path': '/dev/null'},
            'mysql': {'host': '127.0.0.1', 'port': 3306, 'database': 'db', 'user': 'u', 'password': 'p'},
        })

        result = pool.get_bootstrap_connection()
        # Must be a context manager (generator-based)
        assert hasattr(result, '__enter__') and hasattr(result, '__exit__')


class TestWriteDebugLogSSHGuard:
    """write_debug_log() must return gracefully when 'ssh' not in st.secrets."""

    def test_returns_when_ssh_missing(self):
        """write_debug_log should no-op when SSH secrets are absent."""
        mock_secrets = MagicMock()
        mock_secrets.__contains__ = lambda self, key: key != 'ssh'

        with patch('app_mysql.st') as mock_st:
            mock_st.secrets = mock_secrets
            mock_st.session_state = {}

            # Import after patching
            import app_mysql
            # Should return without error (no connection attempt)
            app_mysql.write_debug_log(
                event_type='test',
                message='test message',
            )
            # If we get here without exception, the guard works

    def test_proceeds_when_ssh_present(self):
        """write_debug_log should attempt connection when SSH secrets exist."""
        mock_secrets = MagicMock()
        mock_secrets.__contains__ = lambda self, key: True

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch('app_mysql.st') as mock_st, \
             patch('app_mysql.get_connection', return_value=mock_conn):
            mock_st.secrets = mock_secrets
            mock_st.session_state = {'authenticated': True, 'user': {'user_id': 1}}

            import app_mysql
            app_mysql.write_debug_log(
                event_type='test',
                message='test message',
            )
            # Should have attempted to use connection
            mock_conn.cursor.assert_called()
