"""Admin-only helpers for user CRUD.

All writes go through ``app_mysql.get_connection()`` so they honour the
local-mode flag. User-table writes also dual-write to remote via
``app_mysql._mirror_to_remote`` (when local mode is on) so admin actions
stay consistent with the regular registration path. Hard delete cascades
through related tables in a single transaction on the primary DB; the
mirror replays the same statements on remote, best-effort.

Every admin write logs an entry to ``activity_log`` so the action is
auditable.
"""
from __future__ import annotations

import secrets
from typing import Any, Dict, List, Optional

import app_mysql
from app_mysql import (
    _LOCAL_MODE,
    _mirror_to_remote,
    log_activity,
    pwd_hasher,
)


# ----------------------------------------------------------------------------
# Read
# ----------------------------------------------------------------------------

def list_users(search: str = "", limit: int = 500) -> List[Dict[str, Any]]:
    """Return all users (or filtered by ``search`` against username/email)."""
    conn = app_mysql.get_connection()
    cursor = conn.cursor(dictionary=True)
    if search:
        like = f"%{search}%"
        cursor.execute(
            """
            SELECT user_id, username, email, role, is_active, email_verified,
                   created_at, last_login
            FROM users
            WHERE username LIKE %s OR email LIKE %s
            ORDER BY user_id
            LIMIT %s
            """,
            (like, like, limit),
        )
    else:
        cursor.execute(
            """
            SELECT user_id, username, email, role, is_active, email_verified,
                   created_at, last_login
            FROM users
            ORDER BY user_id
            LIMIT %s
            """,
            (limit,),
        )
    rows = cursor.fetchall()
    cursor.close()
    return rows


def get_user(user_id: int) -> Optional[Dict[str, Any]]:
    conn = app_mysql.get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT user_id, username, email, role, is_active, email_verified, "
        "created_at, last_login FROM users WHERE user_id = %s",
        (user_id,),
    )
    row = cursor.fetchone()
    cursor.close()
    return row


# ----------------------------------------------------------------------------
# Update
# ----------------------------------------------------------------------------

# Whitelist of columns admins can edit inline.
_EDITABLE_COLUMNS = {"username", "email", "role", "is_active", "email_verified"}


def update_user_field(
    user_id: int,
    column: str,
    new_value: Any,
    *,
    admin_user_id: int,
    admin_username: str,
) -> None:
    """Update one column on the users row. Validates ``column`` against an
    allow-list to prevent SQL injection via dynamic column names.
    """
    if column not in _EDITABLE_COLUMNS:
        raise ValueError(f"Refusing to update non-editable column {column!r}")

    conn = app_mysql.get_connection()
    cursor = conn.cursor()
    sql = f"UPDATE users SET `{column}` = %s WHERE user_id = %s"
    cursor.execute(sql, (new_value, user_id))
    conn.commit()
    cursor.close()

    _mirror_to_remote(sql, (new_value, user_id))

    log_activity(
        admin_user_id,
        "ADMIN_USER_EDIT",
        f"by={admin_username}; user_id={user_id}; field={column}; value={new_value!r}",
        "admin",
    )


def set_role(user_id: int, role: str, *, admin_user_id: int, admin_username: str) -> None:
    if role not in ("user", "admin"):
        raise ValueError(f"Invalid role {role!r}")
    update_user_field(user_id, "role", role,
                      admin_user_id=admin_user_id, admin_username=admin_username)


def set_active(user_id: int, active: bool, *, admin_user_id: int, admin_username: str) -> None:
    update_user_field(user_id, "is_active", 1 if active else 0,
                      admin_user_id=admin_user_id, admin_username=admin_username)


# ----------------------------------------------------------------------------
# Reset password
# ----------------------------------------------------------------------------

def reset_password(
    user_id: int,
    *,
    admin_user_id: int,
    admin_username: str,
    new_plaintext: Optional[str] = None,
) -> str:
    """Reset the user's password. If ``new_plaintext`` is None, generate
    a 16-char URL-safe token. Returns the plaintext so the admin UI can
    show it once; never stored. The hash uses the same argon2id params
    as registration via ``app_mysql.pwd_hasher``.
    """
    if new_plaintext is None:
        new_plaintext = secrets.token_urlsafe(12)  # ~16 chars
    password_hash = pwd_hasher.hash(new_plaintext)

    conn = app_mysql.get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE users SET password_hash = %s WHERE user_id = %s",
        (password_hash, user_id),
    )
    conn.commit()
    cursor.close()

    _mirror_to_remote(
        "UPDATE users SET password_hash = %s WHERE user_id = %s",
        (password_hash, user_id),
    )

    log_activity(
        admin_user_id,
        "ADMIN_PASSWORD_RESET",
        f"by={admin_username}; user_id={user_id}",
        "admin",
    )
    return new_plaintext


# ----------------------------------------------------------------------------
# Force logout — invalidate all of a user's active sessions
# ----------------------------------------------------------------------------

def force_logout_user(user_id: int, *, admin_user_id: int, admin_username: str) -> int:
    conn = app_mysql.get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE sessions
        SET status = 'forced_logout', expires_at = NOW(), last_activity = NOW()
        WHERE user_id = %s AND status = 'active'
        """,
        (user_id,),
    )
    n = cursor.rowcount
    conn.commit()
    cursor.close()

    log_activity(
        admin_user_id,
        "ADMIN_FORCE_LOGOUT",
        f"by={admin_username}; user_id={user_id}; sessions={n}",
        "admin",
    )
    return n


# ----------------------------------------------------------------------------
# Delete
# ----------------------------------------------------------------------------

def soft_delete(user_id: int, *, admin_user_id: int, admin_username: str) -> None:
    """Mark the account inactive. Reversible via ``set_active(True)``."""
    set_active(user_id, False, admin_user_id=admin_user_id,
               admin_username=admin_username)
    log_activity(
        admin_user_id,
        "ADMIN_USER_SOFT_DELETE",
        f"by={admin_username}; user_id={user_id}",
        "admin",
    )


# Tables that hold per-user data and should be cleaned up on hard delete.
# Order matters: children before parent (the users row).
_HARD_DELETE_CASCADE = (
    ("user_settings", "user_id"),
    ("user_progress", "user_id"),
    ("vocab_entries", "user_id"),
    ("sessions",      "user_id"),
    ("activity_log",  "user_id"),
)


def hard_delete(user_id: int, *, admin_user_id: int, admin_username: str) -> Dict[str, int]:
    """Delete the user and all their per-user rows in a single transaction
    on the primary DB. The same statements are mirrored to remote in local
    mode (best-effort).

    Returns a dict ``{table: rows_deleted}`` so the UI can report what was
    purged. ``users`` itself is the last entry.
    """
    counts: Dict[str, int] = {}

    conn = app_mysql.get_connection()
    cursor = conn.cursor()
    try:
        for table, col in _HARD_DELETE_CASCADE:
            sql = f"DELETE FROM `{table}` WHERE `{col}` = %s"
            cursor.execute(sql, (user_id,))
            counts[table] = cursor.rowcount
        cursor.execute("DELETE FROM users WHERE user_id = %s", (user_id,))
        counts["users"] = cursor.rowcount
        conn.commit()
    except Exception:
        conn.rollback()
        cursor.close()
        raise
    cursor.close()

    # Mirror — best-effort, separate statements (same order).
    if _LOCAL_MODE:
        for table, col in _HARD_DELETE_CASCADE:
            _mirror_to_remote(f"DELETE FROM `{table}` WHERE `{col}` = %s", (user_id,))
        _mirror_to_remote("DELETE FROM users WHERE user_id = %s", (user_id,))

    log_activity(
        admin_user_id,
        "ADMIN_USER_HARD_DELETE",
        f"by={admin_username}; user_id={user_id}; counts={counts}",
        "admin",
    )
    return counts
