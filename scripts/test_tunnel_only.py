#!/usr/bin/env python3
"""Test just the SSH tunnel without any command execution"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import streamlit as st
from sshtunnel import SSHTunnelForwarder
import paramiko
from io import StringIO
import socket
import time

print("Testing SSH tunnel for MySQL...\n")

# Get credentials
ssh_host = st.secrets["ssh"]["host"]
ssh_port = int(st.secrets["ssh"]["port"])
ssh_user = st.secrets["ssh"]["username"]
key_content = st.secrets["ssh"]["key_content"]

print(f"SSH Target: {ssh_user}@{ssh_host}:{ssh_port}")

# Parse key
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
    print("❌ Could not parse SSH key")
    sys.exit(1)

print(f"Key type: {ssh_key.__class__.__name__}")

# Create tunnel with verbose logging
print("\nCreating SSH tunnel...")
print("Remote target: 127.0.0.1:3306 (MySQL on remote server)")

try:
    tunnel = SSHTunnelForwarder(
        (ssh_host, ssh_port),
        ssh_username=ssh_user,
        ssh_pkey=ssh_key,
        remote_bind_address=('127.0.0.1', 3306),
        set_keepalive=10.0,
        logger=None  # Suppress verbose logging
    )
    
    print("Starting tunnel...")
    tunnel.start()
    
    print(f"✅ Tunnel started successfully!")
    print(f"   Local endpoint: 127.0.0.1:{tunnel.local_bind_port}")
    print(f"   Remote endpoint: 127.0.0.1:3306 (via SSH)")
    
    # Test if we can connect to the local tunnel port
    print("\nTesting TCP connection to tunnel...")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)
    
    try:
        sock.connect(('127.0.0.1', tunnel.local_bind_port))
        print("✅ TCP connection to tunnel successful")
        
        # Try to receive MySQL greeting
        print("Waiting for MySQL greeting packet...")
        data = sock.recv(1024)
        
        if len(data) > 0:
            print(f"✅ Received {len(data)} bytes from MySQL")
            if len(data) >= 5:
                protocol_version = data[4]
                print(f"   MySQL protocol version: {protocol_version}")
                
                # Extract server version string
                if len(data) > 5:
                    # Version string starts at byte 5, null-terminated
                    version_end = data.find(b'\x00', 5)
                    if version_end > 0:
                        version = data[5:version_end].decode('ascii', errors='ignore')
                        print(f"   MySQL server version: {version}")
        else:
            print("❌ No data received - connection closed by MySQL")
            
    except socket.timeout:
        print("❌ Timeout - MySQL didn't respond")
    except ConnectionRefusedError:
        print("❌ Connection refused - tunnel port not listening")
    except ConnectionResetError:
        print("❌ Connection reset - MySQL closed the connection")
    finally:
        sock.close()
    
    # Keep tunnel open briefly
    print("\nTunnel is active. Keeping open for 2 seconds...")
    time.sleep(2)
    
    tunnel.stop()
    print("✅ Tunnel stopped cleanly")
    
except Exception as e:
    print(f"❌ Tunnel failed: {e}")
    import traceback
    traceback.print_exc()
