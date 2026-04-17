#!/usr/bin/env python3
"""Test SSH key authentication with verbose logging"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import streamlit as st
import paramiko
from io import StringIO

print("Testing SSH key authentication...\n")

# Get credentials
ssh_host = st.secrets["ssh"]["host"]
ssh_port = int(st.secrets["ssh"]["port"])
ssh_user = st.secrets["ssh"]["username"]
key_content = st.secrets["ssh"]["key_content"]

print(f"Host: {ssh_host}:{ssh_port}")
print(f"User: {ssh_user}")

# Parse key
key_file = StringIO(key_content)
ssh_key = None
key_type = None

for key_class in (paramiko.Ed25519Key, paramiko.RSAKey, paramiko.ECDSAKey):
    try:
        key_file.seek(0)
        ssh_key = key_class.from_private_key(key_file)
        key_type = key_class.__name__
        break
    except Exception:
        continue

if ssh_key is None:
    print("❌ Could not parse SSH key")
    sys.exit(1)

print(f"Key type: {key_type}")
print(f"Key fingerprint: {ssh_key.get_fingerprint().hex()}")

# Try to connect
print("\nAttempting SSH connection...")

try:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    # Enable verbose logging
    paramiko.util.log_to_file('/tmp/paramiko.log', level=paramiko.util.DEBUG)
    
    client.connect(
        hostname=ssh_host,
        port=ssh_port,
        username=ssh_user,
        pkey=ssh_key,
        timeout=10,
        allow_agent=False,
        look_for_keys=False
    )
    
    print("✅ SSH connection successful!")
    
    # Test command
    stdin, stdout, stderr = client.exec_command("echo 'Hello from Python'")
    output = stdout.read().decode().strip()
    print(f"Command output: {output}")
    
    # Check MySQL port
    stdin, stdout, stderr = client.exec_command("netstat -tuln | grep :3306 || ss -tuln | grep :3306")
    mysql_check = stdout.read().decode().strip()
    if mysql_check:
        print(f"\n✅ MySQL port 3306 is listening:")
        print(mysql_check)
    else:
        print(f"\n❌ MySQL port 3306 NOT listening")
    
    client.close()
    
except paramiko.AuthenticationException as e:
    print(f"❌ Authentication failed: {e}")
    print("\nThis means the SSH key is not authorized on the server.")
    print("Check that the public key is in ~/.ssh/authorized_keys on the server.")
    
except paramiko.SSHException as e:
    print(f"❌ SSH error: {e}")
    
except Exception as e:
    print(f"❌ Connection failed: {e}")

print("\nCheck /tmp/paramiko.log for detailed SSH debugging info")
