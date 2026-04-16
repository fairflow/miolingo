# Miolingo Roadmap 2026

_Last updated: 2026-03-10_

This document sketches the major themes for Miolingo development in 2026 and
links them to concrete GitHub issues. It is intentionally high-level; detailed
contracts and implementation plans should live in dedicated design docs or
issue threads.

## Themes

### 1. Session, Tunnel, and Connection Architecture

Miolingo currently relies on SSH tunnels and MySQL connections to support
multi-user sessions, but the behaviour under failure (mobile, Streamlit Cloud,
network blips) is fragile.

Key goals for 2026:

- Clarify and simplify the model for:
  - Streamlit sessions (tabs)
  - User sessions (login periods)
  - SSH tunnels
  - DB connections (bootstrap vs long-lived)
- Introduce a **SessionManager** layer and a browser-side identifier (cookie or
  equivalent) so we can re-attach a tab to an existing DB-backed session after
  transient failures.
- Stop depending on Python module globals for cross-session coordination.

Relevant issue:

- [#19 – Architecture: Refactor session/tunnel/DB connection model with cookies](https://github.com/fairflow/miolingo/issues/19)

Supporting doc:

- `docs/dev-docs/SESSION_ARCHITECTURE.md` – current behaviour and constraints.

---

### 2. Developer Experience & Refactoring Safety

New features have become harder to add, and refactors that touch the DB schema
are risky.

Key goals:

- Establish a consistent workflow for schema migrations (e.g. `migrations/`
  directory, clear tooling to apply and verify migrations).
- Encourage small, focused design docs for non-trivial changes.
- Standardise a branch/PR workflow (like the `fairclaw` branch) with clear
  scopes for work.
- Improve local/dev tooling so adding a DB column or feature feels safe and
  reversible.

Relevant issue:

- [#20 – Developer UX: Reduce feature-churn and refactor friction](https://github.com/fairflow/miolingo/issues/20)

---

### 3. Performance & Deployment Behaviour (Especially Mobile)

The current Streamlit Cloud deployment is too slow and unreliable, especially
on mobile (iPhone). Users experience long latencies and frequent logouts after
short periods of inactivity.

Key goals:

- Measure and document actual latency and resource usage on Streamlit Cloud.
- Understand Streamlit Cloud's behaviour around connection timeouts, session
  lifetimes, and mobile sleep/resume.
- Identify practical mitigations (more efficient loading, caching, avoiding
  heavy operations on the critical path, better reconnect logic).

Relevant issue:

- [#21 – Performance: Streamlit Cloud latency and mobile inactivity behaviour](https://github.com/fairflow/miolingo/issues/21)

This theme is closely tied to Theme 1 (session/tunnel/connection architecture).

---

### 4. Practice File Management & UX

Miolingo has an initial facility for users to upload practice files, but the
UX is clunky and not backed by a proper file management concept.

Key goals:

- Design and implement a **Practice File Manager** that allows users to:
  - upload files,
  - view and organise their practice materials (e.g. by language, level, tags),
  - select files efficiently when launching practice sessions.
- Decide on a clear storage model for practice files and how they are
  associated with users and languages.

Relevant issue:

- [#22 – Feature: User practice file manager and upload UX](https://github.com/fairflow/miolingo/issues/22)

---

### 5. Two-Way Translation and IPA Everywhere

Translations are currently under-utilised. A richer, two-way model that
connects source and target languages would make Miolingo significantly more
useful.

Key goals:

- Support a **two-way linguistic system** where users choose both a source
  language (native/comfortable) and a target language (being learned).
- Ensure practice files and phrases are aware of both source and target.
- Provide a consistent way to:
  - translate a source phrase to the target language, and
  - generate an IPA transliteration for the target phrase.

Relevant issue:

- [#23 – Feature: Two-way source/target translation support with IPA integration](https://github.com/fairflow/miolingo/issues/23)

---

### 6. Pronunciation Scoring and User Models

Pronunciation scoring is central to Miolingo's value proposition but is
currently too fragile for general release.

Key goals:

- Stabilise the existing scoring pipeline (Whisper → phonemes → scoring) and
  define a clear contract for what a score means.
- Create a small benchmark suite of phrases and expected scoring outcomes.
- Explore longer-term ideas for a per-user pronunciation profile that learns
  typical error patterns over time.

Relevant issue:

- [#24 – Feature: Robust pronunciation scoring algorithm and trainable user model](https://github.com/fairflow/miolingo/issues/24)

---

## How to Use This Roadmap

- Treat these themes as **buckets** for work in 2026.
- For any non-trivial change, link the PR to the relevant issue(s) and, when
  needed, add a short design doc under `docs/dev-docs/`.
- Use the `fairclaw` branch (or similarly named branches) for exploratory
  changes tied to these roadmap items.

This file is intentionally short; it should evolve as issues are refined,
completed, or replaced.
