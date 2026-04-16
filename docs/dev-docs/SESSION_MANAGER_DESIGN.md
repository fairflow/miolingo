# SessionManager Design (Roadmap Theme 1)

_Last updated: 2026-03-10_

## Objective
Introduce a **SessionManager** layer and **browser cookies** to allow Miolingo to reliably
re-attach a browser tab to an existing DB-backed user session after transient failures
(Streamlit reruns, mobile sleep, network blips), without relying on module-level globals
or Streamlit’s internal session model for persistence.

This doc is intentionally **high-level + actionable**. Implementation details should be
tracked in issue threads and code comments as the scaffolding lands.

---

## Current State (Summary)
See `docs/dev-docs/SESSION_ARCHITECTURE.md` for the authoritative map.

Key realities:
- Module-level globals are **per-tab** in this Streamlit runtime.
- SSH tunnels and pooled DB connections behave **session-local**.
- DB is the only **durable** identity store; when DB access drops, the user is forced to
  log back in.

---

## Goals
- **Cookie-backed session identity** independent of Streamlit session state.
- **Session re-attachment** after transient failures when DB is available.
- **Clear ownership boundaries** between:
  - Streamlit tab lifecycle
  - User login session lifecycle
  - SSH tunnel / DB connection lifecycle
- **Minimal initial blast radius**: introduce a SessionManager scaffold without changing
  production behavior.

## Non-goals (Phase 0–1)
- No DB schema migrations.
- No immediate change to login/auth flows.
- No cross-session tunnel sharing.
- No reliability promises until explicit reconnect logic is shipped.

---

## Proposed Model

### 1) Browser Cookie: `miolingo_session`
- **Opaque token** generated on login and stored in a browser cookie.
- Mapped to the existing `sessions.session_id` in the DB.
- Scope: **path=/**, `Secure`, `HttpOnly` where possible.
- Lifetime: expires with the DB session or a configurable TTL.

> Note: We explicitly avoid Streamlit’s session model for persistence. Cookies are the
> durable client-side identity anchor.

### 2) SessionManager Responsibilities
- **Read cookie** at app start to discover an existing session.
- **Bootstrap DB connection** (tunnel + connection) if needed.
- **Validate session** in DB and restore `st.session_state` for the tab.
- **Refresh cookie** on activity if TTL-based.
- **Clear cookie** on logout or invalid session.

### 3) Source of Truth
- DB remains the authoritative identity store.
- Cookie holds only an **opaque session identifier**.
- `st.session_state` is a cache for the current tab (derived state).

---

## Lifecycle Flows (Target)

### A) Fresh Visit (No Cookie)
1. Streamlit starts → SessionManager checks cookie → none.
2. User logs in → DB creates session row.
3. SessionManager sets cookie = `session_id`.
4. Tab proceeds with authenticated state.

### B) Returning Visit (Valid Cookie)
1. Streamlit starts → SessionManager reads cookie.
2. SessionManager bootstraps DB connection.
3. SessionManager validates session row.
4. Tab session restored (user is authenticated without re-login).

### C) Returning Visit (Invalid/Expired Cookie)
1. Cookie exists but DB session invalid.
2. SessionManager clears cookie.
3. User is prompted to log in.

### D) Tunnel/DB Failure Mid-Session
1. DB access fails.
2. SessionManager attempts reconnect (tunnel + DB).
3. If reconnect succeeds and session still valid → continue.
4. If reconnect fails → tab goes to safe unauth state, cookie retained for retry
   (until TTL). If session invalid, cookie cleared.

---

## Incremental Rollout Plan

### Phase 0 (Now): Documentation + Scaffold
- Add `SESSION_MANAGER_DESIGN.md` (this doc).
- Add `src/session_manager.py` scaffold with explicit TODOs.
- No runtime behavior changes.

### Phase 1: Cookie + Validation Path
- Implement cookie read/write using a small, stable library (or custom JS bridge).
- Add SessionManager hook in app startup to attempt re-attach.
- Add feature flag for gradual rollout.

### Phase 2: Reconnect Logic
- Add explicit tunnel+DB reconnect attempts before forcing logout.
- Make failure modes consistent across main app and admin tools.

### Phase 3: UX & Observability
- Add UI messaging for reconnect attempts / expired session.
- Extend admin/monitor tools to track reconnect events.

---

## Risks & Mitigations
- **Cookie handling in Streamlit**: choose a stable cookie manager and document
  limitations. If `HttpOnly` is not possible due to Streamlit constraints, use
  strict naming and rotation.
- **Security**: cookie should be opaque; no user data inside. Rotate on login.
- **DB availability**: re-attach still depends on DB; this change improves
  robustness but doesn’t eliminate DB dependency.

---

## Open Questions
- Exact cookie library / implementation approach.
- Session TTL policy (DB session expiration vs cookie expiration).
- Do we need a “Session re-attach grace window” after logout?

---

## Next Implementation Targets
- `src/session_manager.py` scaffold (Phase 0).
- Add a **feature-flagged hook** in the main app startup path.
- Add lightweight logging around session re-attach attempts.
