#!/usr/bin/env python3
"""
Quick diagnostic to check connection_monitor table contents.
Verifies that app.py connections are being logged to the database.
"""

import mysql.connector
from sshtunnel import SSHTunnelForwarder
import streamlit as st
from pathlib import Path
import sys

# Add parent directory to path to import from src
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

# Load secrets
sys.path.insert(0, str(Path(__file__).parent.parent))
from streamlit import secrets as st_secrets

def main():
    # Create SSH tunnel
    from io import StringIO
    import paramiko
    
    # Handle SSH key (file path vs content string)
    ssh_config = st.secrets['ssh']
    if 'key_path' in ssh_config:
        # Local mode: key is a file path
        key_path = ssh_config['key_path']
        # Try different key types
        for key_class in [paramiko.Ed25519Key, paramiko.RSAKey, paramiko.ECDSAKey]:
            try:
                pkey = key_class.from_private_key_file(key_path)
                break
            except:
                pkey = None
    elif 'key_content' in ssh_config:
        # Cloud mode: key is pasted content
        key_content = ssh_config['key_content']
        for key_class in [paramiko.Ed25519Key, paramiko.RSAKey, paramiko.ECDSAKey]:
            try:
                pkey = key_class.from_private_key(StringIO(key_content))
                break
            except:
                pkey = None
    else:
        raise ValueError("No SSH key found in secrets (need 'key_path' or 'key_content')")
    
    tunnel = SSHTunnelForwarder(
        (ssh_config['host'], int(ssh_config['port'])),
        ssh_username=ssh_config['username'],
        ssh_pkey=pkey,
        remote_bind_address=(st.secrets['mysql']['host'], int(st.secrets['mysql']['port']))
    )
    tunnel.start()
    
    try:
        # Connect to database
        conn = mysql.connector.connect(
            host='127.0.0.1',
            port=tunnel.local_bind_port,
            database=st.secrets['mysql']['database'],
            user=st.secrets['mysql']['user'],
            password=st.secrets['mysql']['password']
        )
        
        cursor = conn.cursor(dictionary=True)
        
        print("=" * 80)
        print(f"DATABASE: {st.secrets['mysql']['database']}")
        print("=" * 80)
        
        # Check tunnel_monitor
        cursor.execute("SELECT COUNT(*) as count FROM tunnel_monitor WHERE status='active'")
        tunnel_count = cursor.fetchone()['count']
        print(f"\n✓ ACTIVE TUNNELS: {tunnel_count}")
        
        # Check connection_monitor
        cursor.execute("SELECT COUNT(*) as count FROM connection_monitor WHERE status='active'")
        conn_count = cursor.fetchone()['count']
        print(f"✓ ACTIVE CONNECTIONS: {conn_count}")
        
        # Check session_monitor
        cursor.execute("SELECT COUNT(*) as count FROM session_monitor WHERE status='active'")
        session_count = cursor.fetchone()['count']
        print(f"✓ ACTIVE SESSIONS: {session_count}")
        
        # Show recent connections with details
        print("\n" + "=" * 80)
        print("RECENT CONNECTIONS (last 10):")
        print("=" * 80)
        cursor.execute("""
            SELECT connection_id, username, tunnel_id, session_id, 
                   created_at, status
            FROM connection_monitor 
            ORDER BY created_at DESC 
            LIMIT 10
        """)
        
        for row in cursor.fetchall():
            print(f"\n  Connection: {row['connection_id'][:30]}...")
            print(f"  Username:   {row['username']}")
            print(f"  Tunnel:     {row['tunnel_id']}")
            print(f"  Session:    {row['session_id'][:40]}...")
            print(f"  Created:    {row['created_at']}")
            print(f"  Status:     {row['status']}")
        
        # Show connections by username
        print("\n" + "=" * 80)
        print("CONNECTIONS BY USERNAME:")
        print("=" * 80)
        cursor.execute("""
            SELECT username, COUNT(*) as count, 
                   COUNT(DISTINCT tunnel_id) as tunnels,
                   MIN(created_at) as first_connection,
                   MAX(created_at) as last_connection
            FROM connection_monitor 
            WHERE status='active'
            GROUP BY username
            ORDER BY count DESC
        """)
        
        for row in cursor.fetchall():
            print(f"\n  {row['username']}: {row['count']} connections across {row['tunnels']} tunnel(s)")
            print(f"    First: {row['first_connection']}")
            print(f"    Last:  {row['last_connection']}")
        
        cursor.close()
        conn.close()
        
    finally:
        tunnel.stop()

if __name__ == '__main__':
    main()
