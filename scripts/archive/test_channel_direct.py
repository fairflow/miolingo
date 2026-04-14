#!/usr/bin/env python3
"""Test SSH tunnel with maximum debugging to see exact SSH protocol messages"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import streamlit as st
from sshtunnel import SSHTunnelForwarder
import paramiko
from io import StringIO
import logging

# Enable maximum SSH debugging
logging.basicConfig(level=logging.DEBUG)
paramiko.util.log_to_file('/tmp/paramiko_detailed.log', level=paramiko.common.DEBUG)

print("Testing with maximum SSH debugging enabled...\n")

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

print(f"Connecting to: {ssh_user}@{ssh_host}:{ssh_port}")
print(f"Forwarding to: 127.0.0.1:3306 on remote")
print(f"\nStarting tunnel with verbose logging...\n")

try:
    # Create transport directly to see what's happening
    transport = paramiko.Transport((ssh_host, ssh_port))
    transport.connect(username=ssh_user, pkey=ssh_key)
    
    print("✅ SSH transport connected and authenticated")
    print(f"   Server version: {transport.remote_version}")
    print(f"   Cipher: {transport.get_security_options().ciphers}")
    
    # Try to open a direct-tcpip channel (this is what port forwarding uses)
    print("\nAttempting to open direct-tcpip channel to 127.0.0.1:3306...")
    
    channel = transport.open_channel(
        kind='direct-tcpip',
        dest_addr=('127.0.0.1', 3306),
        src_addr=('127.0.0.1', 0)
    )
    
    if channel:
        print("✅ Channel opened successfully!")
        print(f"   Channel ID: {channel.get_id()}")
        print(f"   Channel active: {channel.active}")
        
        # Try to receive MySQL greeting
        channel.settimeout(5.0)
        data = channel.recv(1024)
        
        if len(data) > 0:
            print(f"✅ Received {len(data)} bytes from MySQL")
            if len(data) > 5:
                version_end = data.find(b'\x00', 5)
                if version_end > 0:
                    version = data[5:version_end].decode('ascii', errors='ignore')
                    print(f"   MySQL version: {version}")
                    print("\n🎉 SUCCESS - Port forwarding is working!")
        else:
            print("❌ Channel opened but no data received from MySQL")
        
        channel.close()
    else:
        print("❌ Channel is None - request was rejected")
    
    transport.close()
    
except paramiko.ChannelException as e:
    print(f"❌ Channel exception: {e}")
    print(f"   Code: {e.code if hasattr(e, 'code') else 'N/A'}")
    print(f"   Text: {e.text if hasattr(e, 'text') else 'N/A'}")
    print("\nThis means the SSH server rejected the channel open request.")
    print("Possible reasons:")
    print("  - AllowTcpForwarding is disabled in sshd_config")
    print("  - PermitOpen restrictions in sshd_config")
    print("  - cPanel jailshell restrictions")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("\nCheck /tmp/paramiko_detailed.log for full SSH protocol trace")
