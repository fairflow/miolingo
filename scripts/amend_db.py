#!/usr/bin/env python3
"""
Database Amendment Script - Execute SQL queries safely
Version: 0.1

This script provides a safe way to execute SQL queries against the database
through SSH tunnel. It supports both direct queries and SQL file execution
with proper error handling and rollback on failure.

Usage:
    python scripts/amend_db.py --query "SELECT * FROM users LIMIT 5"
    python scripts/amend_db.py --file path/to/query.sql
    python scripts/amend_db.py --file query.sql --commit  # Auto-commit changes
    
Features:
    - Secure SSH tunnel connection
    - Transaction support with manual commit/rollback
    - Detailed error reporting
    - Dry-run mode (default for modifications)
    - Query result display
    - Multi-statement SQL file support

Author: Miolingo Team
"""

__version__ = "0.2"

import sys
import os
from pathlib import Path
import toml
import argparse
from typing import Optional, List, Tuple

# Add src directory to path
src_path = Path(__file__).parent.parent / 'src'
sys.path.insert(0, str(src_path))

from sshtunnel import SSHTunnelForwarder
import mysql.connector
from mysql.connector import Error


def load_secrets() -> dict:
    """Load secrets from .streamlit/secrets.toml"""
    secrets_path = Path(__file__).parent.parent / '.streamlit' / 'secrets.toml'
    if not secrets_path.exists():
        raise FileNotFoundError(f"Secrets file not found: {secrets_path}")
    
    return toml.load(secrets_path)


def create_connection() -> Tuple[SSHTunnelForwarder, mysql.connector.connection.MySQLConnection]:
    """Create SSH tunnel and MySQL connection"""
    secrets = load_secrets()
    
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
        local_bind_address=('127.0.0.1', 0)
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
        connect_timeout=10,
        autocommit=False  # Disable autocommit for transaction control
    )
    print("✅ Connected to MySQL")
    
    return tunnel, conn


def read_sql_file(filepath: str) -> List[str]:
    """Read SQL file and split into individual statements"""
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"SQL file not found: {filepath}")
    
    print(f"📖 Reading SQL file: {filepath}")
    
    with open(path, 'r') as f:
        content = f.read()
    
    # Split by semicolons, filter out empty statements and comments
    statements = []
    for stmt in content.split(';'):
        # Remove comment lines but preserve SQL
        lines = []
        for line in stmt.split('\n'):
            line = line.strip()
            # Skip comment-only lines
            if line and not line.startswith('--') and not line.startswith('#'):
                lines.append(line)
        
        # Join remaining lines and check if there's actual SQL
        cleaned_stmt = ' '.join(lines).strip()
        if cleaned_stmt:
            statements.append(cleaned_stmt)
    
    print(f"📝 Found {len(statements)} SQL statement(s)")
    return statements


def is_read_only_query(query: str) -> bool:
    """Check if query is read-only (SELECT, SHOW, DESCRIBE, etc.)"""
    query_upper = query.strip().upper()
    read_only_keywords = ['SELECT', 'SHOW', 'DESCRIBE', 'DESC', 'EXPLAIN']
    return any(query_upper.startswith(keyword) for keyword in read_only_keywords)


def is_ddl_query(query: str) -> bool:
    """Check if query is DDL (Data Definition Language) - cannot be rolled back!"""
    query_upper = query.strip().upper()
    ddl_keywords = ['CREATE', 'ALTER', 'DROP', 'TRUNCATE', 'RENAME']
    return any(query_upper.startswith(keyword) for keyword in ddl_keywords)


def confirm_execution(queries: List[str], auto_commit: bool, skip_confirm: bool = False) -> bool:
    """
    Check for dangerous queries and ask for confirmation
    
    Args:
        skip_confirm: If True, skip all confirmations (for non-interactive use)
    
    Returns:
        True if user confirms, False to abort
    """
    has_ddl = any(is_ddl_query(q) for q in queries)
    has_modifications = any(not is_read_only_query(q) for q in queries)
    
    # Skip confirmations if requested
    if skip_confirm:
        if has_ddl:
            print("⚠️  DDL statements will execute immediately (--yes flag)")
        elif has_modifications and not auto_commit:
            print("ℹ️  Dry-run mode: modifications will be rolled back (--yes flag)")
        return True
    
    if has_ddl:
        print("\n" + "="*60)
        print("⚠️  WARNING: DDL STATEMENT DETECTED!")
        print("="*60)
        print("This query will modify database structure:")
        print("  • ALTER, CREATE, DROP, TRUNCATE, or RENAME")
        print()
        print("⚠️  DDL statements CANNOT be rolled back in MySQL!")
        print("   They will be applied IMMEDIATELY, even without --commit flag")
        print()
        
        for i, query in enumerate(queries, 1):
            if is_ddl_query(query):
                print(f"Statement {i}:")
                print(f"  {query[:100]}{'...' if len(query) > 100 else ''}")
                print()
        
        response = input("Type 'yes' to proceed, or anything else to abort: ")
        if response.lower() != 'yes':
            print("\n❌ Aborted by user")
            return False
        print()
    
    elif has_modifications and not auto_commit:
        print("\n" + "="*60)
        print("ℹ️  DRY-RUN MODE: Data modifications will be rolled back")
        print("="*60)
        print("The following queries will execute but NOT be saved:")
        print()
        
        for i, query in enumerate(queries, 1):
            if not is_read_only_query(query):
                print(f"Statement {i}:")
                print(f"  {query[:100]}{'...' if len(query) > 100 else ''}")
                print()
        
        print("💡 Add --commit flag to actually save these changes")
        response = input("\nContinue with dry-run? (yes/no): ")
        if response.lower() != 'yes':
            print("\n❌ Aborted by user")
            return False
        print()
    
    return True


def execute_query(cursor, query: str, show_results: bool = True) -> Tuple[bool, Optional[str]]:
    """
    Execute a single SQL query
    
    Returns:
        (success: bool, error_message: Optional[str])
    """
    try:
        print(f"\n🔧 Executing query...")
        print(f"   {query[:100]}{'...' if len(query) > 100 else ''}")
        
        cursor.execute(query)
        
        # Check if it's a SELECT query
        if cursor.description:
            results = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            
            if results:
                print(f"\n📊 Results ({len(results)} row(s)):")
                print("   " + " | ".join(columns))
                print("   " + "-" * (len(" | ".join(columns))))
                
                # Show first 20 rows
                for i, row in enumerate(results[:20]):
                    print(f"   {' | '.join(str(val) for val in row)}")
                
                if len(results) > 20:
                    print(f"   ... and {len(results) - 20} more row(s)")
            else:
                print("   (No results)")
        else:
            # For INSERT, UPDATE, DELETE, etc.
            affected_rows = cursor.rowcount
            print(f"✅ Query executed successfully ({affected_rows} row(s) affected)")
        
        return True, None
        
    except Error as e:
        error_msg = f"MySQL Error: {e}"
        print(f"❌ {error_msg}")
        return False, error_msg


def execute_queries(queries: List[str], auto_commit: bool = False, show_results: bool = True) -> bool:
    """
    Execute list of queries with transaction support
    
    Returns:
        True if all queries succeeded, False otherwise
    """
    tunnel = None
    conn = None
    
    try:
        tunnel, conn = create_connection()
        cursor = conn.cursor()
        
        all_success = True
        has_modifications = False
        
        for i, query in enumerate(queries, 1):
            print(f"\n{'='*60}")
            print(f"Statement {i}/{len(queries)}")
            print(f"{'='*60}")
            
            success, error = execute_query(cursor, query, show_results)
            
            if not success:
                all_success = False
                break
            
            if not is_read_only_query(query):
                has_modifications = True
        
        # Handle transaction
        if has_modifications:
            if all_success:
                if auto_commit:
                    conn.commit()
                    print("\n✅ Changes committed to database")
                else:
                    print("\n⚠️  Changes NOT committed (dry-run mode)")
                    print("   Run with --commit flag to apply changes")
                    conn.rollback()
                    print("   Transaction rolled back")
            else:
                print("\n❌ Rolling back transaction due to error")
                conn.rollback()
                print("   Transaction rolled back")
        
        cursor.close()
        conn.close()
        tunnel.stop()
        
        return all_success
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        
        if conn:
            conn.rollback()
            print("   Transaction rolled back")
        
        return False
        
    finally:
        if conn and conn.is_connected():
            conn.close()
            print("\n🔌 MySQL connection closed")
        if tunnel and tunnel.is_active:
            tunnel.stop()
            print("📡 SSH tunnel closed")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Execute SQL queries against the database safely',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Execute a SELECT query
  python amend_db.py --query "SELECT * FROM users LIMIT 5"
  
  # Execute SQL from file (dry-run, no commit)
  python amend_db.py --file migration.sql
  
  # Execute and commit changes
  python amend_db.py --file migration.sql --commit
  
  # Execute inline UPDATE (dry-run by default)
  python amend_db.py --query "UPDATE users SET active=1 WHERE user_id=5"
        """
    )
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--query', '-q', 
                      help='SQL query to execute')
    group.add_argument('--file', '-f', 
                      help='SQL file to execute')
    
    parser.add_argument('--commit', '-c', 
                       action='store_true',
                       help='Commit changes (default is dry-run for modifications)')
    
    parser.add_argument('--no-results', 
                       action='store_true',
                       help='Do not display query results')
    
    parser.add_argument('--yes', '-y',
                       action='store_true',
                       help='Skip confirmation prompts (non-interactive mode)')
    
    parser.add_argument('--version', '-v',
                       action='version',
                       version=f'amend_db.py v{__version__}')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print(f"  Database Amendment Tool v{__version__}")
    print("=" * 60)
    print()
    
    # Get queries
    if args.query:
        queries = [args.query]
        print(f"📝 Executing inline query")
    else:
        queries = read_sql_file(args.file)
    
    print()
    
    # Confirm execution (especially for DDL statements)
    if not confirm_execution(queries, args.commit, skip_confirm=args.yes):
        sys.exit(1)
    
    # Execute
    success = execute_queries(queries, auto_commit=args.commit, show_results=not args.no_results)
    
    print()
    print("=" * 60)
    if success:
        print("✅ EXECUTION SUCCESSFUL")
    else:
        print("❌ EXECUTION FAILED")
    print("=" * 60)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
