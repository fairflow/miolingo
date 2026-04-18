"""
Integration tests: end-to-end auth flow against a real MySQL database.

These hit real tables (`users`, `sessions`, `activity_log`), exercising the
actual argon2 hashing, SQL, and transaction behaviour — NOT mocks.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


def test_create_and_authenticate_user(db_conn, make_user):
    import app_mysql

    u = make_user(username="alice")

    # Correct password authenticates
    user = app_mysql.authenticate_user(u["username"], u["password"])
    assert user is not None
    assert user["user_id"] == u["user_id"]
    assert user["username"] == "alice"

    # Wrong password is rejected
    assert app_mysql.authenticate_user(u["username"], "wrongpass") is None

    # Nonexistent user is rejected
    assert app_mysql.authenticate_user("nobody", "anything") is None


def test_duplicate_username_is_rejected(db_conn, make_user):
    import app_mysql

    make_user(username="bob")
    duplicate = app_mysql.create_user("bob", "other@example.com", "x")
    assert duplicate is None


def test_duplicate_email_is_rejected(db_conn, make_user):
    import app_mysql

    u = make_user(username="carol")
    duplicate = app_mysql.create_user("different", u["email"], "x")
    assert duplicate is None


def test_session_lifecycle(db_conn, make_user):
    import app_mysql

    u = make_user(username="dave")
    session_id = app_mysql.create_session(
        user_id=u["user_id"],
        username=u["username"],
        ip_address="127.0.0.1",
        user_agent="pytest",
    )
    assert session_id, "create_session should return a session_id string"

    # validate_session resolves back to the user
    resolved = app_mysql.validate_session(session_id, ip_address="127.0.0.1")
    assert resolved is not None
    assert resolved["user_id"] == u["user_id"]
    assert resolved["username"] == "dave"

    # delete_session invalidates it
    assert app_mysql.delete_session(session_id) is True
    assert app_mysql.validate_session(session_id, ip_address="127.0.0.1") is None


def test_validate_session_rejects_unknown_id(db_conn):
    import app_mysql

    assert app_mysql.validate_session("does-not-exist", ip_address="127.0.0.1") is None


def test_get_user_by_id_roundtrip(db_conn, make_user):
    import app_mysql

    u = make_user(username="eve")
    got = app_mysql.get_user_by_id(u["user_id"])
    assert got is not None
    assert got["username"] == "eve"
    assert got["email"] == u["email"]
