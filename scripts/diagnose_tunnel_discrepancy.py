#!/usr/bin/env python3
"""
Diagnose tunnel/connection discrepancy between connection_pool and connection_monitor.
Shows exactly what SQL queries return vs what's in memory.
"""

import mysql.connector
from sshtunnel import SSHTunnelForwarder
import streamlit as st
from pathlib import Path
import sys
from io import StringIO
import paramiko

# Load secrets
sys.path.insert(0, str(Path(__file__).parent.parent))

def main():
    # Create SSH tunnel
    ssh_config = st.secrets['ssh']
    if 'key_path' in ssh_config:
        key_path = ssh_config['key_path']
        for key_class in [paramiko.Ed25519Key, paramiko.RSAKey, paramiko.ECDSAKey]:
            try:
                pkey = key_class.from_private_key_file(key_path)
                break
            except:
                pkey = None
    elif 'key_content' in ssh_config:
        key_content = ssh_config['key_content']
        for key_class in [paramiko.Ed25519Key, paramiko.RSAKey, paramiko.ECDSAKey]:
            try:
                pkey = key_class.from_private_key(StringIO(key_content))
                break
            except:
                pkey = None
    
    tunnel = SSHTunnelForwarder(
        (ssh_config['host'], int(ssh_config['port'])),
        ssh_username=ssh_config['username'],
        ssh_pkey=pkey,
        remote_bind_address=(st.secrets['mysql']['host'], int(st.secrets['mysql']['port']))
    )
    tunnel.start()
    
    try:
        conn = mysql.connector.connect(
            host='127.0.0.1',
            port=tunnel.local_bind_port,
            database=st.secrets['mysql']['database'],
            user=st.secrets['mysql']['user'],
            password=st.secrets['mysql']['password']
        )
        
        cursor = conn.cursor(dictionary=True)
        
        print("=" * 100)
        print("TUNNEL_MONITOR TABLE (what connection_monitor.py shows)")
        print("=" * 100)
        cursor.execute("""
            SELECT tunnel_id, pid, local_port, created_at, last_used, status, connection_count
            FROM tunnel_monitor
            ORDER BY tunnel_id
        """)
        tunnels = cursor.fetchall()
        for t in tunnels:
            print(f"\nTunnel: {t['tunnel_id']}")
            print(f"  PID: {t['pid']}")
            print(f"  Port: {t['local_port']}")
            print(f"  Connections: {t['connection_count']}")
            print(f"  Created: {t['created_at']}")
            print(f"  Last Used: {t['last_used']}")
            print(f"  Status: {t['status']}")
        
        print("\n" + "=" * 100)
        print("CONNECTION_MONITOR TABLE (active connections)")
        print("=" * 100)
        cursor.execute("""
            SELECT connection_id, mysql_connection_id, tunnel_id, session_id, username,
                   created_at, last_activity, status
            FROM connection_monitor
            WHERE status = 'active'
            ORDER BY tunnel_id, created_at DESC
        """)
        connections = cursor.fetchall()
        
        # Group by tunnel
        tunnel_conns = {}
        for c in connections:
            tid = c['tunnel_id']
            if tid not in tunnel_conns:
                tunnel_conns[tid] = []
            tunnel_conns[tid].append(c)
        
        for tid in sorted(tunnel_conns.keys()):
            print(f"\n{tid}: {len(tunnel_conns[tid])} active connections")
            for c in tunnel_conns[tid][:3]:  # Show first 3
                print(f"  - {c['connection_id'][:40]}...")
                print(f"    MySQL ID: {c['mysql_connection_id']}")
                print(f"    Session: {c['session_id'][:40]}...")
                print(f"    Username: {c['username']}")
                print(f"    Created: {c['created_at']}")
                print(f"    Status: {c['status']}")
        
        print("\n" + "=" * 100)
        print("DISCREPANCY ANALYSIS")
        print("=" * 100)
        
        # Compare tunnel_monitor.connection_count vs actual count in connection_monitor
        cursor.execute("""
            SELECT tm.tunnel_id, tm.connection_count as reported_count,
                   COUNT(cm.id) as actual_count
            FROM tunnel_monitor tm
            LEFT JOIN connection_monitor cm ON tm.tunnel_id = cm.tunnel_id 
                AND cm.status = 'active'
            GROUP BY tm.tunnel_id, tm.connection_count
            ORDER BY tm.tunnel_id
        """)
        discrepancies = cursor.fetchall()
        
        for d in discrepancies:
            reported = d['reported_count']
            actual = d['actual_count']
            match = "✓" if reported == actual else "✗ MISMATCH"
            print(f"\n{d['tunnel_id']}: Reported={reported}, Actual={actual} {match}")
        
        print("\n" + "=" * 100)
        print("PID UNIQUENESS CHECK")
        print("=" * 100)
        cursor.execute("""
            SELECT pid, COUNT(*) as count, GROUP_CONCAT(tunnel_id) as tunnels
            FROM tunnel_monitor
            GROUP BY pid
            HAVING count > 1
        """)
        dup_pids = cursor.fetchall()
        
        if dup_pids:
            print("⚠️  DUPLICATE PIDs FOUND:")
            for d in dup_pids:
                print(f"  PID {d['pid']} used by: {d['tunnels']}")
        else:
            print("✓ All PIDs are unique")
        
        print("\n" + "=" * 100)
        print("SPECIFIC TUNNEL LOOKUP: tunnel_4 vs tunnel_5")
        print("=" * 100)
        
        for tid in ['tunnel_4', 'tunnel_5']:
            cursor.execute("""
                SELECT * FROM tunnel_monitor WHERE tunnel_id = %s
            """, (tid,))
            tunnel = cursor.fetchone()
            if tunnel:
                print(f"\n{tid} in tunnel_monitor:")
                print(f"  PID: {tunnel['pid']}")
                print(f"  Port: {tunnel['local_port']}")
                print(f"  Connections (field): {tunnel['connection_count']}")
                
                cursor.execute("""
                    SELECT COUNT(*) as count FROM connection_monitor
                    WHERE tunnel_id = %s AND status = 'active'
                """, (tid,))
                actual = cursor.fetchone()['count']
                print(f"  Connections (actual): {actual}")
            else:
                print(f"\n{tid}: NOT FOUND in tunnel_monitor")
        
        cursor.close()
        conn.close()
        
    finally:
        tunnel.stop()

if __name__ == '__main__':
    main()
