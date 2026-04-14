#!/usr/bin/env python3
"""
Test SSH tunnel and MySQL connection for Miolingo

Run this to diagnose connection issues.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

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

try:
    print("🔍 Testing SSH tunnel and MySQL connection...")
    print()
    
    # Test SSH tunnel
    print("1️⃣ Testing SSH tunnel...")
    from app_mysql import get_ssh_tunnel
    
    tunnel = get_ssh_tunnel()
    print(f"✅ SSH tunnel established")
    print(f"   Local port: {tunnel.local_bind_port}")
    print(f"   Remote: {tunnel.ssh_host}:{tunnel.ssh_port}")
    print()
    
    # Test MySQL connection
    print("2️⃣ Testing MySQL connection...")
    from app_mysql import get_connection
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT VERSION()")
    version = cursor.fetchone()
    print(f"✅ MySQL connected")
    print(f"   Version: {version[0]}")
    cursor.close()
    conn.close()
    print()
    
    # Test database access
    print("3️⃣ Testing database access...")
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SHOW TABLES")
    tables = cursor.fetchall()
    print(f"✅ Database accessible")
    print(f"   Tables: {len(tables)}")
    for table in tables[:5]:  # Show first 5
        print(f"   - {table[0]}")
    cursor.close()
    conn.close()
    print()
    
    print("✅ All tests passed!")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
