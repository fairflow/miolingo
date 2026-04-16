# Miolingo Session, Tunnel & Connection Architecture

_Last updated: 2026-03-10 · This is a descriptive map of what actually happens,
not what early comments hoped would happen._

This document captures how Miolingo currently handles:

- Streamlit sessions (browser tabs)
- User sessions (login/logout lifecycle)
- SSH tunnels to MySQL
- Database connections and pooling

It is based on:
- `src/app_mysql.py`
- `src/connection_pool.py`
- `src/connection_monitor.py`
- `src/unified_admin.py`
- empirical behaviour from `src/test_globals.py`

Where code comments claim something that is not borne out in practice, this
document sides with **observed behaviour**.

---

## 1. Key Concepts & Terminology

### 1.1 Streamlit Session (Tab Session)

- One browser tab connected to a Streamlit app.
- Backed by its own `st.session_state` dict on the server side.
- Lifetime:
  - Starts when the user opens the app URL in a tab.
  - Ends when the tab is closed, the app crashes, or the service restarts.
- A single tab can span **multiple user sessions** (log out, log back in) as
  long as the tab and backend stay alive.

### 1.2 User Session (Application Session)

- The period between a successful login and the end of that authenticated run.
- Lifetime:
  - Starts when a user successfully logs in.
  - Ends when **any** of the following happens:
    - The user explicitly logs out.
    - The underlying Streamlit session ends (tab closed, crash, restart).
    - The session expires server-side (idle timeout / forced logout).
- Represented in the **database** (unified `sessions` table) by a row keyed by
  `session_id` with `user_id`, `app_name`, timestamps, etc.
- Mirrored into `st.session_state` for the active Streamlit session
  (e.g. `st.session_state.session_id`, `st.session_state.authenticated`).

A single **Streamlit session** (tab) can host multiple **user sessions**
(sequentially), but at most one active user session at a time.

### 1.3 SSH Tunnel

- An `SSHTunnelForwarder` instance from `sshtunnel`.
- Forwards a local port (on the Streamlit side) to `127.0.0.1:3306` on the
  remote MySQL server (from the SSH server's perspective).
- All MySQL connections go through a tunnel – there is no direct MySQL
  connection without SSH.

### 1.4 Database Connection

- A `mysql.connector` connection object.
- In the main app, the intended pattern is:
  - One long-lived connection per **Streamlit session**, stored in
    `st.session_state.db_connection`.
  - Additional short-lived "bootstrap" connections for admin/monitoring tasks
    that are created via context managers and closed immediately.

---

## 2. What the Code *Claims* vs What Actually Happens

Several comments in `app_mysql.py` and related files talk about a **single
"global" SSH tunnel shared across all sessions**, implemented via a module-
level global:

```python
_global_ssh_tunnel = None

def get_ssh_tunnel() -> SSHTunnelForwarder:
    """Get or create SSH tunnel to MySQL server.

    - Uses st.secrets["ssh"] for configuration.
    - Attempts to reuse an existing tunnel if one is present and healthy.
    - Otherwise creates a new SSHTunnelForwarder and starts it.
    """
```

Comments describe this as:

> "Global SSH tunnel shared across ALL Streamlit sessions. This prevents
>  creating multiple tunnels and hitting server connection limits."

However, **empirical testing** with `src/test_globals.py` in this deployment
shows that:

- Module-level globals are effectively **per Streamlit session/tab**, not
  reliably shared across all tabs.
- On each rerun, the top-level code is executed against a fresh module
  namespace for that session.
- As a result, each Streamlit session behaves as if it has **its own copy** of
  module-level "globals", including `_global_ssh_tunnel`.

Therefore, in practice:

- The code does **not** guarantee a single shared tunnel across all
  Streamlit sessions.
- Each session/tab can and often does establish its **own SSH tunnel**.
- Connection pooling and tunnel sharing across sessions must be treated as
  **aspirational**, not guaranteed by the current implementation.

This matches the lived experience where it was easy to accidentally create
many tunnels (dozens or more) and hit SSH limits on the hosting provider.

---

## 3. Current Behaviour: End-to-End Flow

This section describes what actually happens in the main app and admin tools,
ignoring comments that assume cross-session globals.

### 3.1 Browser → Streamlit → DB (Main App)

For a typical user tab hitting the main app (`src/app.py` / `src/streamlit_app.py`):

1. **Streamlit creates a session**
   - A new `st.session_state` dict is created for that tab.
   - Top-level code in the app and imported modules (including `app_mysql`) is
     executed for this session.

2. **User logs in**
   - The app calls into `app_mysql.authenticate_user(...)` using a **bootstrap
     connection** (short-lived), obtained via a helper that opens and then
     closes a DB connection.
   - On success, `app_mysql.create_session(...)` inserts a row into the
     `sessions` table with:
     - `session_id`
     - `user_id`
     - `username`
     - `app_name='miolingo'`
     - timestamps, etc.
   - The returned `session_id` is stored in `st.session_state.session_id`.

3. **Persistent DB connection for this tab**
   - When the app first needs a long-lived DB connection, it calls something
     like `get_connection()` in `app_mysql`.
   - That function:
     - ensures there is an SSH tunnel for this session (via `get_ssh_tunnel()`),
     - opens a MySQL connection through that tunnel,
     - stores it in `st.session_state.db_connection` for this tab,
     - returns it.
   - Subsequent DB operations in this tab reuse `st.session_state.db_connection`.

4. **User session maintenance**
   - As the user interacts with the app, the code:
     - uses the persistent DB connection for queries,
     - periodically calls `touch_session(session_id)` to update last-activity /
       expiry in the `sessions` table.

5. **Logout or failure**
   - On explicit logout, the app:
     - marks the session as ended in the DB (`delete_session(session_id)`),
     - clears relevant keys from `st.session_state`.
   - If the DB connection or tunnel dies, current behaviour tends to be:
     - error on DB access,
     - force the user to log back in (because identity depends on DB access),
       rather than attempting a transparent reconnection.

### 3.2 Admin & Monitor Tools

Admin entrypoint (`src/unified_admin.py`) and monitor (`src/connection_monitor.py`):

- Use the same basic primitives in `app_mysql` (auth, sessions, tunnels,
  connections), but with extra logic for:
  - admin-only access,
  - capacity checks (how many active connections),
  - viewing per-connection/tunnel/session metadata.
- They often use **bootstrap connections** for quick queries so they don't
  consume pooled session connections for simple checks.

The important point for architecture is that these tools do not alter the fact
that tunnels and pooled connections are **session-local** in practice.

---

## 4. Persistence & State: What Actually Persists

### 4.1 `st.session_state` (Per-Tab)

- Durable for the lifetime of a **Streamlit session/tab** as long as:
  - the tab remains open, and
  - the backend process doesn't fully restart that session.
- Stores things like:
  - `authenticated`
  - `username`
  - `session_id` (DB session id)
  - `db_connection` (long-lived connection for this tab)
  - various UI + workflow flags.

### 4.2 Module-Level "Globals"

Examples: `_global_ssh_tunnel`, `_global_connection_pool`, `counter` in
`test_globals.py`.

- Are **defined at top level** in modules like `app_mysql.py`.
- In a plain long-lived Python process, these would be shared across imports
  and reruns.
- In this Streamlit deployment, testing shows that:
  - each Streamlit session/tab sees its **own module namespace**,
  - top-level code is re-executed on each rerun with a fresh `globals()` for
    that session,
  - changes to module-level variables are **not** shared between tabs.

Conclusion: module-level globals are **not a safe coordination mechanism** for
resource sharing across sessions. They behave more like "script-level" state
for that particular session, not process-wide singletons.

### 4.3 Database

- The database is the **only durable, cross-session store** of:
  - user accounts and hashes (argon2id)
  - user sessions (`sessions` table)
  - connection/tunnel usage history (monitor tables)
  - user progress and app data.
- When DB access is lost (tunnel down, MySQL down), the app currently has no
  independent way to know who the user is or what session they were in.

This is why the current design tends to **log users out on DB/tunnel failure**:
without DB, there is no reliable identity anchor.

---

## 5. Consequences for Design and Refactoring

Given the above, any future refactor should assume:

1. **No reliance on module globals for invariants**
   - Do not assume `_global_ssh_tunnel` or a single `ConnectionPool` instance
     is shared across all sessions.
   - Treat tunnels and pools as **session-scoped**, unless and until we
     explicitly introduce a mechanism (e.g. DB-based leader election or a
     separate service) to share them.

2. **DB + `st.session_state` are the only reliable state**
   - `st.session_state` for per-tab, short- to medium-lived state.
   - DB for any state that must survive tab crashes, service restarts, or
     multi-device use.

3. **User identity must be re-attachable without trusting globals**
   - Right now, the DB is *trying* to act like a cookie store for `session_id`,
     but we need a DB connection (and thus a tunnel) to read that.
   - To handle reconnections and mobile sleep better, we will likely need:
     - a browser cookie or equivalent that contains an opaque `session_id`,
     - a `SessionManager` layer that can:
       - re-establish a tunnel + DB connection when needed,
       - look up the DB session by `session_id`,
       - restore the user session without forcing a full login.

4. **Any "one tunnel per N users" policy must be explicit**
   - If we ever want to enforce something like "at most one tunnel per server
     process" or "at most K tunnels across all sessions", that must be
     implemented via:
     - DB coordination (e.g. a `tunnels` table with locking), or
     - an external coordinator.
   - It cannot safely rely on Python module globals in this Streamlit runtime.

---

## 6. Summary

- **Streamlit sessions (tabs)** and **user sessions (logins)** are distinct
  concepts; a single tab can host multiple user sessions over time.
- In this deployment, module-level "globals" behave as **per-session, per-rerun
  script state**, not as true process-wide singletons.
- SSH tunnels and DB connection pools are therefore effectively **session-
  scoped**, despite earlier comments suggesting a single shared tunnel.
- The **database** is the only durable, cross-session source of truth for
  identity, sessions, and resource tracking.
- `st.session_state` is the only reliable per-tab state that survives reruns.

All future architectural changes (cookies, SessionManager, simplified tunnel
handling, schema changes) should be designed with this reality in mind.
