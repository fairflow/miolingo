#!/usr/bin/env python3
"""
Create announcements table in the database.
Run with: python scripts/create_announcements_table.py
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import streamlit as st
import app_mysql

def main():
    # Read the schema
    schema_path = Path(__file__).parent.parent / 'config' / 'announcements_schema.sql'
    with open(schema_path, 'r') as f:
        schema_sql = f.read()
    
    # Strip comments and empty lines, extract just the CREATE TABLE statement
    lines = []
    for line in schema_sql.split('\n'):
        stripped = line.strip()
        if stripped and not stripped.startswith('--'):
            lines.append(line)
    schema_sql = '\n'.join(lines)
    
    # Execute it
    conn = None
    cursor = None
    try:
        print("Connecting to database...")
        conn = app_mysql.get_connection()
        cursor = conn.cursor()
        
        print("Creating announcements table...")
        cursor.execute(schema_sql)
        conn.commit()
        
        print("✅ Announcements table created successfully")
        
        # Close cursor before creating new one
        cursor.close()
        
        # Verify it exists with a fresh cursor
        cursor = conn.cursor()
        cursor.execute("SHOW TABLES LIKE 'announcements'")
        result = cursor.fetchone()
        if result:
            print(f"✅ Verified: Table exists - {result[0]}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if cursor:
            try:
                cursor.close()
            except:
                pass
        if conn:
            try:
                conn.close()
            except:
                pass

if __name__ == '__main__':
    main()
