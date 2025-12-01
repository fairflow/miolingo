#!/usr/bin/env python3
"""
Deep diagnostic for MySQL connection issue

Tests each layer of the connection stack to isolate the problem.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

print("=" * 70)
print("MySQL Connection Deep Diagnostic")
print("=" * 70)

# Test 1: Can we read secrets?
print("\n1️⃣ Testing secrets access...")
try:
    import streamlit as st
    
    # Mock streamlit for testing
    if not hasattr(st, 'session_state'):
        class SessionState:
            def __init__(self):
                self._state = {}
            def __contains__(self, key):
                return key in self._state
            def __getitem__(self, key):
                return self._state[key]
            def __setitem__(self, key, value):
                self._state[key] = value
        st.session_state = SessionState()
    
    ssh_host = st.secrets["ssh"]["host"]
    ssh_port = st.secrets["ssh"]["port"]
    mysql_user = st.secrets["mysql"]["user"]
    mysql_db = st.secrets["mysql"]["database"]
    
    print(f"✅ Secrets OK")
    print(f"   SSH: {ssh_host}:{ssh_port}")
    print(f"   MySQL: {mysql_user}@{mysql_db}")
except Exception as e:
    print(f"❌ Secrets failed: {e}")
    sys.exit(1)

# Test 2: Can we establish SSH tunnel?
print("\n2️⃣ Testing SSH tunnel...")
try:
    from sshtunnel import SSHTunnelForwarder
    import paramiko
    from io import StringIO
    
    ssh_port_int = int(st.secrets["ssh"]["port"])
    
    # Parse SSH key
    key_content = st.secrets["ssh"]["key_content"]
    key_file = StringIO(key_content)
    ssh_key = None
    for key_class in (paramiko.Ed25519Key, paramiko.RSAKey, paramiko.ECDSAKey):
        try:
            key_file.seek(0)
            ssh_key = key_class.from_private_key(key_file)
            print(f"   Key type: {key_class.__name__}")
            break
        except Exception:
            continue
    
    if ssh_key is None:
        raise ValueError("Could not parse SSH key")
    
    # Create tunnel
    tunnel = SSHTunnelForwarder(
        (st.secrets["ssh"]["host"], ssh_port_int),
        ssh_username=st.secrets["ssh"]["username"],
        ssh_pkey=ssh_key,
        remote_bind_address=('127.0.0.1', 3306)
    )
    tunnel.start()
    
    print(f"✅ SSH tunnel established")
    print(f"   Local port: {tunnel.local_bind_port}")
    print(f"   Remote: {tunnel.ssh_host}:{tunnel.ssh_port}")
    print(f"   Target: 127.0.0.1:3306 (on remote)")
    
except Exception as e:
    print(f"❌ SSH tunnel failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 3: Can we make raw TCP connection to MySQL through tunnel?
print("\n3️⃣ Testing raw TCP connection to MySQL...")
try:
    import socket
    import time
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(10)
    
    print(f"   Connecting to 127.0.0.1:{tunnel.local_bind_port}...")
    sock.connect(('127.0.0.1', tunnel.local_bind_port))
    
    print(f"✅ TCP connection established")
    
    # Try to receive MySQL greeting packet
    print(f"   Waiting for MySQL greeting packet...")
    sock.settimeout(5)
    data = sock.recv(1024)
    
    if len(data) > 0:
        print(f"✅ Received {len(data)} bytes from MySQL")
        print(f"   First bytes (hex): {data[:20].hex()}")
        
        # Parse MySQL protocol version (first byte after packet length)
        if len(data) >= 5:
            protocol_version = data[4]
            print(f"   MySQL protocol version: {protocol_version}")
    else:
        print(f"❌ No data received (connection closed)")
    
    sock.close()
    
except socket.timeout:
    print(f"❌ Timeout - MySQL didn't send greeting packet")
except ConnectionResetError as e:
    print(f"❌ Connection reset by peer: {e}")
except Exception as e:
    print(f"❌ TCP test failed: {e}")
    import traceback
    traceback.print_exc()

# Test 4: Can we connect with mysql-connector-python?
print("\n4️⃣ Testing mysql-connector-python...")
try:
    import mysql.connector
    
    print(f"   Connecting to 127.0.0.1:{tunnel.local_bind_port}...")
    
    conn = mysql.connector.connect(
        host='127.0.0.1',
        port=tunnel.local_bind_port,
        user=st.secrets["mysql"]["user"],
        password=st.secrets["mysql"]["password"],
        database=st.secrets["mysql"]["database"],
        connection_timeout=10
    )
    
    print(f"✅ MySQL connection successful")
    
    cursor = conn.cursor()
    cursor.execute("SELECT VERSION(), CONNECTION_ID()")
    version, conn_id = cursor.fetchone()
    print(f"   MySQL version: {version}")
    print(f"   Connection ID: {conn_id}")
    
    cursor.execute("SHOW VARIABLES LIKE 'max_connections'")
    max_conn = cursor.fetchone()
    print(f"   Max connections: {max_conn[1]}")
    
    cursor.execute("SHOW STATUS LIKE 'Threads_connected'")
    current_conn = cursor.fetchone()
    print(f"   Current connections: {current_conn[1]}")
    
    cursor.close()
    conn.close()
    
except mysql.connector.Error as e:
    print(f"❌ MySQL connection failed: {e}")
    print(f"   Error code: {e.errno}")
    print(f"   SQL state: {e.sqlstate}")
    import traceback
    traceback.print_exc()

# Cleanup
print("\n5️⃣ Cleanup...")
try:
    tunnel.stop()
    print("✅ Tunnel closed")
except:
    pass

print("\n" + "=" * 70)
print("Diagnostic complete")
print("=" * 70)
