# Development

## Directory layout

```
miolingo/
├── src/                  # Python source for the Streamlit app (production)
│   ├── app.py            # Main Streamlit app — UI, routing, session state (~2800 lines)
│   ├── miolingo-admin.py # Admin dashboard (usage, users, cost)
│   ├── app_mysql.py      # Database layer: auth, progress, sessions
│   ├── config.py         # LANGUAGE_CONFIG and other constants
│   ├── scoring/          # comparison.py (edit_distance), phone_distance.py
│   │                     #   (weighted_phone), phonemes.py (espeak IPA), practice.py (pipeline)
│   ├── audio/            # tts.py (Google Cloud/gTTS/espeak fallback chain), asr.py (Whisper)
│   ├── ipa/               # fold_map.py (per-language accent-tolerance data), minimal_pairs.py
│   └── translation.py, translation_providers.py
├── web/                  # In-progress rewrite: local-first Svelte SPA + FastAPI sidecar
│   ├── app/              # Svelte 5 + TypeScript SPA (Vite, Dexie/IndexedDB persistence)
│   │   └── src/domain/   # Framework-free TS port of the CCS spec's five agents
│   ├── oracle/           # Stateless FastAPI sidecar wrapping src/ (espeak, Whisper, scoring)
│   └── docs/             # DESIGN.md, DECISIONS.md, PITFALLS.md for this subproject
├── spec/                 # Wolfram Language (.wl) formal spec the app's domain logic is
│                         #   ported from — "CCS" state-machine agents (PracticeSession, Helm,
│                         #   Vocab, VocabTable, StoryReader) with golden test tables
├── language_materials/   # Curated content per language/CEFR level; unified/ is the JSON
│                         #   form both the Streamlit app and web port read from
├── research/phonetics/   # Design notes and prototypes for the phone-distance scorer
│                         #   (research/phonetics/DESIGN_DIGEST.md is the rationale doc)
├── swift/                # A native macOS/iOS port (separate from the web port)
├── desktop/              # An Electron-style desktop port
├── scripts/               # bump_app.py/bump_admin.py (version bump + changelog),
│                         #   create-pr.sh, language-generation/ (content pipeline)
├── docs/app-docs/         # USER_GUIDE.md, DEVELOPER_GUIDE.md — detailed Streamlit-app docs
├── tests/                # pytest suite for src/
└── Makefile              # install / run / run-admin / test / clean
```

Three ports of the same domain logic exist in this repo (Streamlit/Python,
the web SPA, and a Swift native app) at different levels of completeness. The
Streamlit app is the one actually deployed and in day-to-day use; the web
port is the active development focus; the Swift and Electron ports are
further behind. `spec/` is the formal reference all of them are meant to
match.

## Build and test

**Streamlit app / Python core:**
```bash
source venv/bin/activate
make install-dev        # requirements.txt + requirements-wav2vec2.txt
make test                # pytest tests/ -v (integration tests needing a live
                          #   MySQL are skipped by default: pytest.ini's
                          #   addopts = -m "not integration")
make run                 # localhost:8501
```

**Web port:**
```bash
cd web/app && npm install
pip install -r web/oracle/requirements.txt
cd web && make test      # vitest (app/test/*.spec.ts) + tsc --noEmit + pytest web/oracle/tests
cd web && make dev       # vite :8330 + oracle :8331
```

The web port's `test/golden.spec.ts` and `test/sequences.spec.ts` check the
TypeScript domain port against the same test tables the `.wl` spec defines,
so a change to domain logic on either side should keep both green.

## Branch situation (check before basing new work)

This repo has an unusually large number of long-lived branches and — at time
of writing — several other Claude Code worktrees active in parallel on
different branches. Two things to know before picking a base branch:

- **GitHub's configured default branch is `main`**, but `main` is a stale,
  separate lineage (last commit June 2026) that predates the web port and
  much of the current `src/` — it is *not* where active development happens.
- **The project's own PR tooling** (`scripts/pr-config.env`,
  `CLAUDE_BRANCH_TARGET`) targets **`claude/spec`**, and there's an open PR
  (#178) merging `claude/weighted-phone-scorer` — the branch this repo is
  currently on, and the most complete/current one (master + the web port +
  the weighted phone-distance scorer) — into `claude/spec`.

In short: `main` on GitHub is not the real trunk right now. If you're
starting new work, check `scripts/pr-config.env` for the current
`CLAUDE_BRANCH_TARGET` and branch from there (or from whatever branch your
task was actually opened against), not blindly from `main`.

If you're working in a Claude Code worktree, run `scripts/setup-worktree.sh`
once to get the standard permissions allowlist and a copy of
`.streamlit/secrets.toml`.

## Contribution notes

- `AGENTS.md` at the repo root is the canonical instruction file AI
  assistants working on this repo are expected to read first (`CLAUDE.md`
  and `.github/copilot-instructions.md` extend it per-tool).
- Version bumps use `scripts/bump_app.py` / `scripts/bump_admin.py`
  (`patch`/`minor`/`major`, optionally `tag` and `push`) — see `BUMP_GUIDE.md`.
- `scripts/create-pr.sh` wraps `gh pr create` with checks: no duplicate open
  PR on the branch, version bumped since the last tag, branch pushed first.
- Never open new MySQL/SSH-tunnel connections directly — reuse
  `app_mysql.get_connection()` (documented in `AGENTS.md`; a past violation
  of this caused a production outage).
- Full developer walkthrough of the Streamlit app specifically:
  `docs/app-docs/DEVELOPER_GUIDE.md`.
