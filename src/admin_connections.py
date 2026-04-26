"""Admin connection diagnostics — surface what the SSH-tunnel pool is
doing right now so admins can spot leaks, runaway sessions, or stale
tunnels.

Reads exclusively from ``connection_monitor`` / ``tunnel_monitor`` /
``sessions`` on the **remote** DB — those tables only get populated when
the app talks through an SSH tunnel, so they're meaningless when local
mode is on (in which case the UI shows a "no diagnostics" message).
"""
from __future__ import annotations

from typing import Any, Dict, List

import admin_db_health
import app_mysql


# ----------------------------------------------------------------------------
# Tunnels
# ----------------------------------------------------------------------------

def list_tunnels() -> List[Dict[str, Any]]:
    """Return all rows from ``tunnel_monitor`` sorted newest-first, plus a
    derived ``conn_count`` taken live from ``connection_monitor``."""
    rows: List[Dict[str, Any]] = []
    with admin_db_health._remote_connect() as conn:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            """
            SELECT t.tunnel_id, t.pid, t.local_port, t.created_at,
                   t.last_used, t.status,
                   (SELECT COUNT(*) FROM connection_monitor cm
                      WHERE cm.tunnel_id = t.tunnel_id
                        AND cm.status = 'active') AS active_conns
            FROM tunnel_monitor t
            ORDER BY t.created_at DESC
            """
        )
        rows = cur.fetchall()
        cur.close()
    return rows


# ----------------------------------------------------------------------------
# Connections
# ----------------------------------------------------------------------------

def list_active_connections() -> List[Dict[str, Any]]:
    """Active rows in ``connection_monitor`` joined with usernames."""
    rows: List[Dict[str, Any]] = []
    with admin_db_health._remote_connect() as conn:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            """
            SELECT cm.connection_id, cm.tunnel_id, cm.session_id,
                   cm.username, cm.app_name, cm.created_at, cm.last_activity,
                   cm.status
            FROM connection_monitor cm
            WHERE cm.status = 'active'
            ORDER BY cm.last_activity DESC
            """
        )
        rows = cur.fetchall()
        cur.close()
    return rows


# ----------------------------------------------------------------------------
# Sessions per user / app
# ----------------------------------------------------------------------------

def sessions_per_user() -> List[Dict[str, Any]]:
    """``{username, app_name, active, expires_soon}`` per (user, app)."""
    rows: List[Dict[str, Any]] = []
    with admin_db_health._remote_connect() as conn:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            """
            SELECT s.username, s.app_name,
                   COUNT(*) AS active,
                   SUM(CASE WHEN s.expires_at < DATE_ADD(NOW(), INTERVAL 1 DAY)
                           THEN 1 ELSE 0 END) AS expires_within_24h
            FROM sessions s
            WHERE s.status = 'active' AND s.expires_at > NOW()
            GROUP BY s.username, s.app_name
            ORDER BY active DESC
            """
        )
        rows = cur.fetchall()
        cur.close()
    return rows


# ----------------------------------------------------------------------------
# Pool capacity snapshot
# ----------------------------------------------------------------------------

def pool_capacity() -> Dict[str, Any]:
    """One-shot summary: active connections / tunnels / soft-limit headroom."""
    with admin_db_health._remote_connect() as conn:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            """
            SELECT
                COUNT(*) AS active_connections,
                COUNT(DISTINCT tunnel_id) AS active_tunnels,
                COUNT(DISTINCT session_id) AS sessions_with_connections
            FROM connection_monitor
            WHERE status = 'active'
            """
        )
        stats = cur.fetchone() or {}
        cur.close()
    MAX_TOTAL = 100
    SOFT_LIMIT = 90
    active = int(stats.get("active_connections") or 0)
    return {
        "active_connections":        active,
        "active_tunnels":            int(stats.get("active_tunnels") or 0),
        "sessions_with_connections": int(stats.get("sessions_with_connections") or 0),
        "max_total":                 MAX_TOTAL,
        "soft_limit":                SOFT_LIMIT,
        "headroom":                  MAX_TOTAL - active,
        "capacity_pct":              (active / MAX_TOTAL) * 100,
        "over_soft_limit":           active >= SOFT_LIMIT,
    }


# ----------------------------------------------------------------------------
# Cleanup
# ----------------------------------------------------------------------------

def cleanup_stale_connections(stale_hours: int = 12) -> int:
    """Delete rows from ``connection_monitor`` that are closed or idle
    for ``stale_hours`` hours. Surfaces the existing pool helper.
    Returns the row count deleted."""
    pool = app_mysql.get_connection_pool_instance()
    return pool.cleanup_stale_connections(stale_hours=stale_hours)


def kill_dead_tunnels() -> Dict[str, int]:
    """Mark ``tunnel_monitor`` rows as ``dead`` for tunnels whose PID no
    longer exists. Returns ``{checked, marked_dead}``. Best-effort —
    skips rows where the PID is null. Does NOT touch live tunnels."""
    import os

    checked = 0
    marked = 0
    with admin_db_health._remote_connect() as conn:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            "SELECT tunnel_id, pid FROM tunnel_monitor "
            "WHERE status IN ('active','idle') AND pid IS NOT NULL"
        )
        rows = cur.fetchall()

        update_cur = conn.cursor()
        for row in rows:
            checked += 1
            pid = int(row["pid"])
            try:
                os.kill(pid, 0)  # signal 0 = existence check
            except OSError:
                update_cur.execute(
                    "UPDATE tunnel_monitor SET status='dead' "
                    "WHERE tunnel_id=%s",
                    (row["tunnel_id"],),
                )
                marked += 1
        conn.commit()
        update_cur.close()
        cur.close()
    return {"checked": checked, "marked_dead": marked}
