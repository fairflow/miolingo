#!/usr/bin/env python3
"""
Add app_name column to session_monitor table.
This script adds the new column and sets default values for existing rows.

Run with: python scripts/add_app_name_column.py
"""

import sys
import os
from pathlib import Path
import toml

# Add src directory to path
src_path = Path(__file__).parent.parent / 'src'
sys.path.insert(0, str(src_path))

from sshtunnel import SSHTunnelForwarder
import mysql.connector
from mysql.connector import Error

def add_app_name_column():
    """Add app_name column to session_monitor table and populate existing rows."""
    
    print("🔧 Adding app_name column to session_monitor table...")
    
    # Create SSH tunnel
    tunnel = None
    conn = None
    
    try:
        # Load secrets from .streamlit/secrets.toml
        secrets_path = Path(__file__).parent.parent / '.streamlit' / 'secrets.toml'
        if not secrets_path.exists():
            raise FileNotFoundError(f"Secrets file not found: {secrets_path}")
        
        print(f"📖 Loading secrets from {secrets_path}")
        secrets = toml.load(secrets_path)
        
        # SSH tunnel configuration
        ssh_host = secrets["ssh"]["host"]
        ssh_port = int(secrets["ssh"]["port"])
        ssh_user = secrets["ssh"]["username"]
        ssh_password = secrets["ssh"].get("password")
        
        mysql_host = secrets["mysql"]["host"]
        mysql_port = int(secrets["mysql"]["port"])
        mysql_db = secrets["mysql"]["database"]
        mysql_user = secrets["mysql"]["user"]
        mysql_pass = secrets["mysql"]["password"]
        
        print(f"📡 Creating SSH tunnel to {ssh_host}...")
        tunnel = SSHTunnelForwarder(
            (ssh_host, ssh_port),
            ssh_username=ssh_user,
            ssh_password=ssh_password,
            remote_bind_address=(mysql_host, mysql_port),
            local_bind_address=('127.0.0.1', 0)  # Use any available port
        )
        tunnel.start()
        print(f"✅ SSH tunnel established on port {tunnel.local_bind_port}")
        
        # Connect to MySQL
        print(f"🔌 Connecting to MySQL database '{mysql_db}'...")
        conn = mysql.connector.connect(
            host='127.0.0.1',
            port=tunnel.local_bind_port,
            database=mysql_db,
            user=mysql_user,
            password=mysql_pass,
            connect_timeout=10
        )
        cursor = conn.cursor(dictionary=True)
        print("✅ Connected to MySQL")
        
        # Check if column already exists
        print("🔍 Checking if app_name column already exists...")
        cursor.execute("""
            SELECT COUNT(*) as count 
            FROM information_schema.COLUMNS 
            WHERE TABLE_SCHEMA = %s 
            AND TABLE_NAME = 'session_monitor' 
            AND COLUMN_NAME = 'app_name'
        """, (mysql_db,))
        result = cursor.fetchone()
        
        if result['count'] > 0:
            print("ℹ️  Column 'app_name' already exists in session_monitor table")
            
            # Check if there are rows with NULL app_name
            cursor.execute("SELECT COUNT(*) as count FROM session_monitor WHERE app_name IS NULL")
            null_count = cursor.fetchone()['count']
            
            if null_count > 0:
                print(f"⚠️  Found {null_count} rows with NULL app_name, updating...")
                cursor.execute("""
                    UPDATE session_monitor 
                    SET app_name = 'app' 
                    WHERE app_name IS NULL
                """)
                conn.commit()
                print(f"✅ Updated {cursor.rowcount} rows with default app_name='app'")
            else:
                print("✅ All rows have app_name values")
        else:
            # Add the column
            print("➕ Adding app_name column...")
            cursor.execute("""
                ALTER TABLE session_monitor 
                ADD COLUMN app_name VARCHAR(50) DEFAULT 'app' AFTER browser
            """)
            print("✅ Column added successfully")
            
            # Add index
            print("🔧 Adding index on app_name...")
            cursor.execute("""
                ALTER TABLE session_monitor 
                ADD INDEX idx_app_name (app_name)
            """)
            print("✅ Index added successfully")
            
            # Update existing rows (set to 'app' as default)
            cursor.execute("SELECT COUNT(*) as count FROM session_monitor")
            row_count = cursor.fetchone()['count']
            
            if row_count > 0:
                print(f"📝 Updating {row_count} existing rows with default app_name='app'...")
                cursor.execute("""
                    UPDATE session_monitor 
                    SET app_name = 'app' 
                    WHERE app_name IS NULL OR app_name = ''
                """)
                conn.commit()
                print(f"✅ Updated {cursor.rowcount} rows")
            else:
                print("ℹ️  No existing rows to update")
            
            conn.commit()
        
        # Show final statistics
        cursor.execute("""
            SELECT 
                app_name,
                COUNT(*) as count
            FROM session_monitor
            GROUP BY app_name
            ORDER BY count DESC
        """)
        stats = cursor.fetchall()
        
        print("\n📊 Session Monitor Statistics by App:")
        if stats:
            for stat in stats:
                app = stat['app_name'] or '(NULL)'
                count = stat['count']
                print(f"   {app}: {count} sessions")
        else:
            print("   No sessions in table")
        
        cursor.close()
        conn.close()
        tunnel.stop()
        
        print("\n✅ Migration completed successfully!")
        return True
        
    except Error as e:
        print(f"\n❌ MySQL Error: {e}")
        return False
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if conn and conn.is_connected():
            conn.close()
            print("🔌 MySQL connection closed")
        if tunnel and tunnel.is_active:
            tunnel.stop()
            print("📡 SSH tunnel closed")


if __name__ == "__main__":
    print("=" * 60)
    print("  Session Monitor Table Migration")
    print("  Adding app_name column")
    print("=" * 60)
    print()
    
    success = add_app_name_column()
    
    print()
    print("=" * 60)
    if success:
        print("✅ MIGRATION SUCCESSFUL")
    else:
        print("❌ MIGRATION FAILED")
    print("=" * 60)
    
    sys.exit(0 if success else 1)
