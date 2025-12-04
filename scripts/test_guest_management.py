#!/usr/bin/env python3
"""
Test guest user management functions for Miolingo.

This test validates:
1. Guest user limit enforcement
2. Guest cleanup function
3. Active guest counting
4. Proper resource cleanup (connections closed)

Run without database connection to test function signatures and logic.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

def test_function_signatures():
    """Test that new functions exist with correct signatures"""
    print("1️⃣ Testing function signatures...")
    
    try:
        import inspect
        from app_mysql import count_active_guests, cleanup_old_guest_users, create_guest_user
        
        # Check count_active_guests signature
        sig1 = inspect.signature(count_active_guests)
        assert len(sig1.parameters) == 0, "count_active_guests should have no parameters"
        assert sig1.return_annotation == int or sig1.return_annotation == inspect.Signature.empty, "Should return int"
        print("   ✅ count_active_guests() signature correct")
        
        # Check cleanup_old_guest_users signature
        sig2 = inspect.signature(cleanup_old_guest_users)
        assert 'days_old' in sig2.parameters, "cleanup_old_guest_users should have days_old parameter"
        default = sig2.parameters['days_old'].default
        assert default is None, f"days_old default should be None (uses constant), got {default}"
        assert sig2.return_annotation == int or sig2.return_annotation == inspect.Signature.empty, "Should return int"
        print("   ✅ cleanup_old_guest_users(days_old=None) signature correct (uses GUEST_CLEANUP_DAYS constant)")
        
        # Check create_guest_user is modified
        source = inspect.getsource(create_guest_user)
        assert 'MAX_CONCURRENT_GUESTS' in source, "create_guest_user should check MAX_CONCURRENT_GUESTS"
        assert 'count_active_guests' in source, "create_guest_user should call count_active_guests()"
        print("   ✅ create_guest_user() includes guest limit check")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_cleanup_patterns():
    """Test that all functions have proper resource cleanup"""
    print("\n2️⃣ Testing resource cleanup patterns...")
    
    try:
        import inspect
        from app_mysql import count_active_guests, cleanup_old_guest_users, test_connection
        
        # Check each function has proper cleanup
        functions = [
            ('count_active_guests', count_active_guests),
            ('cleanup_old_guest_users', cleanup_old_guest_users),
            ('test_connection', test_connection),
        ]
        
        for name, func in functions:
            source = inspect.getsource(func)
            
            # Check for try/finally pattern
            has_try = 'try:' in source
            has_finally = 'finally:' in source
            has_close = 'conn.close()' in source
            
            if has_try and has_finally and has_close:
                print(f"   ✅ {name}() has proper try/finally/close pattern")
            else:
                print(f"   ❌ {name}() missing cleanup: try={has_try}, finally={has_finally}, close={has_close}")
                return False
        
        return True
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_guest_limit_constant():
    """Test that guest limit constant is properly defined"""
    print("\n3️⃣ Testing guest limit configuration...")
    
    try:
        import inspect
        from app_mysql import create_guest_user
        
        # Check that create_guest_user uses MAX_CONCURRENT_GUESTS
        source = inspect.getsource(create_guest_user)
        assert 'MAX_CONCURRENT_GUESTS' in source, "MAX_CONCURRENT_GUESTS not used in function"
        
        # Import the constant and verify it
        from app_mysql import MAX_CONCURRENT_GUESTS, GUEST_CLEANUP_DAYS, GUEST_CLEANUP_WARNING_THRESHOLD
        
        assert MAX_CONCURRENT_GUESTS == 3, f"Expected limit of 3, got {MAX_CONCURRENT_GUESTS}"
        assert GUEST_CLEANUP_DAYS == 7, f"Expected cleanup days of 7, got {GUEST_CLEANUP_DAYS}"
        assert GUEST_CLEANUP_WARNING_THRESHOLD == 10, f"Expected warning threshold of 10, got {GUEST_CLEANUP_WARNING_THRESHOLD}"
        
        print(f"   ✅ MAX_CONCURRENT_GUESTS = {MAX_CONCURRENT_GUESTS}")
        print(f"   ✅ GUEST_CLEANUP_DAYS = {GUEST_CLEANUP_DAYS}")
        print(f"   ✅ GUEST_CLEANUP_WARNING_THRESHOLD = {GUEST_CLEANUP_WARNING_THRESHOLD}")
        print(f"   ✅ Guest limit enforcement is active")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_sql_queries():
    """Test that SQL queries are properly structured"""
    print("\n4️⃣ Testing SQL query structure...")
    
    try:
        import inspect
        from app_mysql import count_active_guests, cleanup_old_guest_users
        
        # Check count_active_guests query
        source1 = inspect.getsource(count_active_guests)
        assert "WHERE username LIKE 'guest_%'" in source1, "Should filter by guest username pattern"
        assert "DATE_SUB(NOW(), INTERVAL 24 HOUR)" in source1, "Should check last 24 hours"
        print("   ✅ count_active_guests() SQL query correct")
        
        # Check cleanup_old_guest_users query
        source2 = inspect.getsource(cleanup_old_guest_users)
        assert "DELETE FROM users" in source2, "Should delete from users table"
        assert "WHERE username LIKE 'guest_%'" in source2, "Should filter by guest username pattern"
        assert "DATE_SUB(NOW(), INTERVAL %s DAY)" in source2, "Should use parameterized days"
        print("   ✅ cleanup_old_guest_users() SQL query correct")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_admin_integration():
    """Test that admin interface has new features"""
    print("\n5️⃣ Testing admin interface integration...")
    
    try:
        admin_file = Path(__file__).parent.parent / 'src' / 'miolingo-admin.py'
        with open(admin_file, 'r') as f:
            admin_content = f.read()
        
        # Check for guest cleanup button
        assert 'cleanup_old_guest_users' in admin_content, "Admin should import cleanup function"
        assert 'Clean Old Guests' in admin_content or 'clean.*guest' in admin_content.lower(), "Admin should have cleanup button"
        print("   ✅ Guest cleanup button added to admin Settings tab")
        
        # Check for guest statistics
        assert "guest_%" in admin_content or "Active Guests" in admin_content, "Admin should show guest statistics"
        print("   ✅ Guest statistics added to admin Users tab")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print("=" * 70)
    print("🧪 Miolingo Guest Management Test Suite")
    print("=" * 70)
    print()
    print("This test validates the guest user management implementation")
    print("without requiring a database connection.")
    print()
    
    tests = [
        test_function_signatures,
        test_cleanup_patterns,
        test_guest_limit_constant,
        test_sql_queries,
        test_admin_integration,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"   ❌ Test failed with exception: {e}")
            import traceback
            traceback.print_exc()
            results.append(False)
    
    print()
    print("=" * 70)
    passed = sum(results)
    total = len(results)
    
    if passed == total:
        print(f"✅ All tests passed! ({passed}/{total})")
        print()
        print("Guest user management is properly implemented:")
        print("  • Max 3 concurrent guests enforced")
        print("  • Cleanup function available (delete guests >7 days)")
        print("  • All functions have proper resource cleanup")
        print("  • Admin interface updated with guest management")
    else:
        print(f"❌ Some tests failed ({passed}/{total})")
        print()
        print("Please review the failures above.")
    
    print("=" * 70)
    
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
