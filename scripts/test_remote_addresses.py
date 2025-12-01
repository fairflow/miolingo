#!/usr/bin/env python3
"""Test SSH tunnel with different remote bind addresses"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import streamlit as st
from sshtunnel import SSHTunnelForwarder
import paramiko
from io import StringIO
import socket

print("Testing different remote MySQL bind addresses...\n")

# Get credentials
ssh_host = st.secrets["ssh"]["host"]
ssh_port = int(st.secrets["ssh"]["port"])
ssh_user = st.secrets["ssh"]["username"]
key_content = st.secrets["ssh"]["key_content"]

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

# Test different remote addresses
test_addresses = [
    ('127.0.0.1', 3306, "Loopback IPv4"),
    ('localhost', 3306, "localhost hostname"),
    ('::1', 3306, "Loopback IPv6"),
]

for remote_host, remote_port, description in test_addresses:
    print(f"\n{'='*60}")
    print(f"Testing: {description} ({remote_host}:{remote_port})")
    print(f"{'='*60}")
    
    try:
        tunnel = SSHTunnelForwarder(
            (ssh_host, ssh_port),
            ssh_username=ssh_user,
            ssh_pkey=ssh_key,
            remote_bind_address=(remote_host, remote_port),
            set_keepalive=10.0
        )
        
        tunnel.start()
        print(f"✅ Tunnel started: 127.0.0.1:{tunnel.local_bind_port} -> {remote_host}:{remote_port}")
        
        # Try to connect
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        
        try:
            sock.connect(('127.0.0.1', tunnel.local_bind_port))
            print("✅ TCP connection successful")
            
            # Try to receive data
            data = sock.recv(1024)
            if len(data) > 0:
                print(f"✅ SUCCESS! Received {len(data)} bytes from MySQL")
                print(f"   First 20 bytes: {data[:20].hex()}")
                if len(data) > 5:
                    version_end = data.find(b'\x00', 5)
                    if version_end > 0:
                        version = data[5:version_end].decode('ascii', errors='ignore')
                        print(f"   MySQL version: {version}")
                print(f"\n🎉 Working configuration: remote_bind_address=('{remote_host}', {remote_port})")
                sock.close()
                tunnel.stop()
                sys.exit(0)
            else:
                print("❌ No data received")
        except socket.timeout:
            print("❌ Timeout waiting for MySQL response")
        except ConnectionRefusedError:
            print("❌ Connection refused")
        except ConnectionResetError:
            print("❌ Connection reset by peer")
        except Exception as e:
            print(f"❌ Connection error: {e}")
        finally:
            sock.close()
        
        tunnel.stop()
        
    except Exception as e:
        print(f"❌ Tunnel failed: {e}")

print(f"\n{'='*60}")
print("❌ None of the configurations worked")
print("This indicates MySQL is either:")
print("  1. Not running on the remote server")
print("  2. Not listening on any TCP port (Unix socket only)")
print("  3. Firewalled even from localhost")
print("{'='*60}")
