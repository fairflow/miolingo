#!/usr/bin/env python3
"""
Emergency cleanup script for connection monitor.
Use this if you're locked out and can't access the UI.

This script uses a bootstrap connection (doesn't count toward pool limits)
to clean up stale connections and tunnels.
"""

import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import mysql.connector
from sshtunnel import SSHTunnelForwarder
import streamlit as st

def create_emergency_tunnel():
    """Create SSH tunnel for emergency access"""
    tunnel = SSHTunnelForwarder(
        (st.secrets["ssh"]["host"], st.secrets["ssh"]["port"]),
        ssh_username=st.secrets["ssh"]["username"],
        ssh_pkey=st.secrets["ssh"]["key_path"],
        remote_bind_address=(st.secrets["mysql"]["host"], st.secrets["mysql"]["port"]),
        local_bind_address=('127.0.0.1', 0)
    )
    tunnel.start()
    return tunnel

def cleanup_all():
    """Clean up all stale connections and tunnels"""
    print("🚨 Emergency Cleanup Starting...")
    
    tunnel = None
    try:
        # Create tunnel
        print("1. Creating SSH tunnel...")
        tunnel = create_emergency_tunnel()
        
        # Connect to MySQL
        print("2. Connecting to MySQL...")
        conn = mysql.connector.connect(
            host='127.0.0.1',
            port=tunnel.local_bind_port,
            database=st.secrets["mysql"]["database"],
            user=st.secrets["mysql"]["user"],
            password=st.secrets["mysql"]["password"]
        )
        cursor = conn.cursor()
        
        # Get current counts
        cursor.execute("SELECT COUNT(*) FROM connection_monitor WHERE status = 'active'")
        active_conns = cursor.fetchone()[0]
        print(f"   Found {active_conns} active connections")
        
        cursor.execute("SELECT COUNT(*) FROM tunnel_monitor WHERE status = 'active'")
        active_tunnels = cursor.fetchone()[0]
        print(f"   Found {active_tunnels} active tunnels")
        
        # Clean connections
        print("\n3. Cleaning stale connections...")
        cursor.execute("""
            UPDATE connection_monitor 
            SET status = 'closed', last_activity = NOW()
            WHERE status = 'active'
        """)
        cleaned_conns = cursor.rowcount
        print(f"   ✅ Cleaned {cleaned_conns} connections")
        
        # Clean tunnels
        print("4. Cleaning stale tunnels...")
        cursor.execute("""
            UPDATE tunnel_monitor 
            SET status = 'closed', last_used = NOW()
            WHERE status = 'active'
        """)
        cleaned_tunnels = cursor.rowcount
        print(f"   ✅ Cleaned {cleaned_tunnels} tunnels")
        
        # Commit
        conn.commit()
        cursor.close()
        conn.close()
        
        print("\n✅ Emergency cleanup complete!")
        print(f"   Cleaned {cleaned_conns} connections and {cleaned_tunnels} tunnels")
        print("   You should now be able to login to the connection monitor.")
        
    except Exception as e:
        print(f"\n❌ Error during cleanup: {e}")
        sys.exit(1)
    finally:
        if tunnel:
            tunnel.stop()
            print("   Tunnel closed")

if __name__ == "__main__":
    print("=" * 60)
    print("EMERGENCY CONNECTION CLEANUP")
    print("=" * 60)
    print("\nThis will mark ALL active connections and tunnels as closed.")
    response = input("\nContinue? (yes/no): ")
    
    if response.lower() in ['yes', 'y']:
        cleanup_all()
    else:
        print("Cancelled.")
