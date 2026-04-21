# Scripts & Release Workflow

Single source of truth for the Miolingo dev scripts and the end-to-end workflow for landing changes. **Follow this exactly** — deviations have cost multiple sessions' worth of confusion. If you find the scripts don't match this document, the scripts are wrong: fix them and update this page.

Audience: AI assistants (Claude Code, other models) and humans continuing work between sessions.

Last verified: 2026-04-20 with `scripts/create-pr.sh` v2 (post-bug-fix commit).

---

## The golden path — every change, start to finish

These six steps turn a clean worktree into a landed PR. Do them in order.

```bash
# 0. You're in a worktree. Activate venv (lives in main repo root).
source /Users/matthew/Software/working/miolingo/venv/bin/activate

# 1. Start from a clean, up-to-date base branch.
git fetch origin
git switch -c claude/<descriptive-name> origin/claude/dev-swept

# 2. Do the work — edit code, run tests, run the app if UI changed.
pytest tests/unit/ -q             # fast feedback
scripts/test_app_starts.sh 8601   # smoke test the app boots

# 3. Commit the functional change(s).
git add <files>
git commit -m "fix(scope): concise subject"

# 4. Bump version + tag.  Do NOT pass --push here.
#    --notes is REQUIRED — it's what appears in APP_CHANGELOG.md.
python scripts/bump_version.py patch --suffix claude-dev --tag \
  --notes "One-line summary of what this PR actually changes."
#    --kind added|changed|fixed|removed|deprecated|security (default: changed)
#    Repeat --notes, or use '\n' in one value, for multiple bullets.
#    --no-notes is reserved for emergency bumps only.
# For admin changes: python scripts/bump_version.py admin patch --suffix claude-dev --tag --notes "..."

# 5. Create the PR.  Script handles branch push + PR creation.
bash scripts/create-pr.sh --title "fix(scope): concise subject (vX.Y.Z-claude-dev)"

# 6. Push the tag separately.  Safe to do AFTER create-pr.sh because
#    step 5 set the upstream cleanly; no hook trigger.
git push origin vX.Y.Z-claude-dev

# 7. Boot the worktree preview on 8701 via the Preview MCP so
#    Matthew's IDE Preview button points at the branch-under-review.
#    Stop any stale dev_server first, then call preview_start with
#    the "miolingo (main app)" entry from .claude/launch.json.
#    DO NOT use `bash scripts/dev_server.sh 8701 &` — it binds the
#    port and blocks preview_start from doing so.
bash scripts/dev_server.sh stop 8701 2>/dev/null || true
# then, via MCP:  mcp__Claude_Preview__preview_start name="miolingo (main app)"
```

Port 8701 is, by agreed workflow (see `GOLDEN.md`), taken over by Claude from the linked worktree after each PR push. The IDE Preview button then serves the branch-under-review automatically. 8601–8699 remain available for ad-hoc Claude testing; 8702/8703 stay as IDE Preview targets for the admin apps.

After the PR merges, before starting the next piece of work, **reset the worktree**:

```bash
git fetch origin
git reset --hard origin/claude/dev-swept
```

If the reset would lose uncommitted work, `git stash push -u` first.

---

## Why each step is the way it is

The reasoning behind each step — so if the script breaks or the model changes, the next agent can reconstruct the workflow.

### Step 1 — Fresh branch from `origin/claude/dev-swept`

The explicit `origin/claude/dev-swept` argument is critical. Without it, a new branch inherits its parent's tracking branch. Worktree branches often inherit `origin/claude/dev-swept` as upstream, which means a later `git push` (without a refspec) would push **directly to dev-swept**, bypassing PR review. The `PreToolUse` git-push hook blocks this, but the hook is a safety net, not a substitute for doing the git command correctly.

Never reuse a branch that has already had PRs merged from it — the old commits linger locally and make subsequent PRs re-show already-merged changes.

### Step 4 — Bump version **before** creating the PR, no `--push`

`bump_version.py --tag`:
- rewrites `__version__` in `src/config.py` (or `src/unified_admin.py` for admin)
- prepends a stub entry to `APP_CHANGELOG.md` (or `ADMIN_CHANGELOG.md`)
- commits both with message `vX.Y.Z-claude-dev: version bump`
- annotates the new commit with tag `vX.Y.Z-claude-dev`

**Do not pass `--push`.** The `--push` flag runs `git push origin HEAD` which respects the branch's upstream — and on a fresh worktree branch that upstream is still `origin/claude/dev-swept`. That would push the bump commit onto the base branch, not into a PR.

The `create-pr.sh` script's version check now compares HEAD against `origin/$BASE_BRANCH` (not against the last git tag), so bumping before calling `create-pr.sh` is the correct order. Earlier versions of the script used `git describe` and failed when the bump-commit-tag sat at HEAD; if you see a "version not bumped" warning despite having bumped, the script is out of date — pull `main` and try again.

### Step 5 — `create-pr.sh`

The script:
1. Reads `CLAUDE_BRANCH_TARGET` from `scripts/pr-config.env` (currently `claude/dev-swept`).
2. Checks there is no open PR already on this branch (preventing duplicate PRs).
3. Compares `src/config.py __version__` on HEAD vs `origin/$BASE_BRANCH`; fails if they match.
4. Pushes using the explicit `HEAD:refs/heads/<branch>` form — bypasses the `PreToolUse` hook AND is safe regardless of upstream inheritance.
5. Sets upstream to the new remote branch so subsequent pushes (tags, follow-up commits) don't re-trigger the hook.
6. Creates the PR with `gh pr create`.

Flags:
- `--title` (required) — PR title.
- `--body` (optional) — full PR body. Default is an auto-generated summary of commits on the branch.
- `--skip-version-check` — for tooling/docs-only PRs that legitimately don't bump the version.

### Step 6 — Push the tag

`bump_version.py --tag` only creates the tag **locally**. You must push it explicitly, or the app sidebar will still show the old version when a fresh clone runs. After step 5 the branch upstream matches its remote name, so a plain `git push origin <tag>` is safe.

---

## Script reference

All scripts live in `scripts/`. Paths shown are relative to the repo root.

### Release & PR

| Script | Purpose |
|---|---|
| `bump_version.py` | Bump version + changelog entry + local git tag. See flags below. |
| `create-pr.sh` | Push branch + raise PR targeting `CLAUDE_BRANCH_TARGET`. |
| `pr-config.env` | Config: `CLAUDE_BRANCH_TARGET=<branch>`. Update when the target branch rotates (e.g. dev-swept → dev). |

`bump_version.py` flags:
- positional: `app` (default) or `admin` — selects which version file to edit
- command: `show | major | minor | patch | set X.Y.Z`
- `--suffix LABEL` — appends `-LABEL` (use `claude-dev` for dev PRs)
- `--tag` — commits the bump and creates a local annotated tag
- `--notes "TEXT"` — **REQUIRED** for any real bump; one line per bullet. Repeatable. Accepts `\n` inside a single value. Lifted verbatim into `APP_CHANGELOG.md`; do not prefix with `-`.
- `--kind added|changed|fixed|removed|deprecated|security` — changelog heading (default: `changed`).
- `--no-notes` — opt out of the notes requirement. Reserved for emergency / tooling-only re-tags. **Do not use for feature or fix PRs** — the whole point of the requirement is that "Version bump" entries are useless.
- `--push` — **avoid in normal workflow**. Runs `git push origin HEAD` which follows upstream. Use only when you know the branch upstream matches its remote name.

### Dev server

| Script | Purpose |
|---|---|
| `dev_server.sh [port]` | Start Miolingo on a Claude-owned port (default 8601). Auto-finds venv in main repo root. Handles stale-process kills. |
| `dev_server.sh stop [port]` | Stop a Claude-started server. |
| `test_app_starts.sh [port]` | Boot the app, wait 15 s, exit 0 if healthy. Good CI smoke test. |
| `clean_restart.py` | Kill any Streamlit + ports + caches, then user restarts manually. |

Port convention (memorise):
- 8501–8599 — Matthew (hands off)
- 8601–8699 — Claude test/verification servers
- 8701–8799 — IDE Preview / launch.json
- 8702+ — Admin app and named launchers

### Database

| Script | Purpose |
|---|---|
| `sync_db.py` | Bidirectional sync between local and remote MySQL. See `SYNC_TABLES` for coverage. Run `--full` for first-time or when you suspect drift, `--dry-run` to preview. |
| `check_vocab_sync.py` | Read-only diagnostic: how many vocab rows on each side, what's missing, is vocab_entries registered for sync. |
| `test_vocab_sync.py` | Automated round-trip test harness for the vocab sync strategy. Exits 0 on pass. Runs without human auth. |
| `amend_db.py --file <sql> --commit` | Apply a SQL migration file against local or remote. Default is dry-run; use `--commit` to execute. Avoid semicolons in SQL comments — the parser splits on them. |
| `export_schema.sh` | Dump the current schema for reference / new-dev onboarding. |
| `add_vocab_entries.sql`, `add_vocab_url.sql`, etc. | One-shot migration files used with `amend_db.py`. |

### Worktree & setup

| Script | Purpose |
|---|---|
| `setup-worktree.sh [path]` | Bootstrap `.claude/settings.local.json` + link `secrets.toml` into a fresh worktree. Run once per new worktree. |
| `setup.sh` | First-time environment setup (venv, dependencies). Not usually needed if the venv already exists. |
| `worktree-settings.json` | Template for worktree-local Claude settings. |

### Language materials

| Script | Purpose |
|---|---|
| `merge_materials.py` | Merge per-language fragments into unified schemas. Re-run `add_english_ipa.py` afterwards. |
| `add_english_ipa.py` | Add English IPA to unified materials. |
| `language-generation/` | Subdirectory for offline language-material generation pipeline. |

### Archive

`scripts/archive/` holds scripts kept for reference but no longer in the golden path. Don't add new scripts there without asking.

---

## Things that look like bugs but aren't

- **The sidebar version doesn't update after a merge.** Streamlit caches aggressively. Stop+start the server (`scripts/dev_server.sh stop && scripts/dev_server.sh`), not just a page reload.
- **`git status` says "up to date" but I just merged a PR.** The local branch tracking was probably set to the PR branch, not to dev-swept. See step 6 and the reset recipe above.
- **`gh pr create` complains about "no commits between".** You forgot to commit or you're on the base branch itself. `git log origin/claude/dev-swept..HEAD --oneline` should show your commits.

## Things that ARE bugs — fix them, don't work around them

- `create-pr.sh` version check using `git describe` instead of comparing against base — **fixed in this commit**.
- `create-pr.sh` push without explicit refspec — **fixed in this commit**.
- `bump_version.py --push` using bare `git push origin HEAD` — still present; stop-gap is "don't use `--push`", proper fix is TODO.
- Any script that reads `.streamlit/secrets.toml` from the worktree directly — worktrees don't get gitignored files, so secrets must be symlinked from the main repo (see `project_worktree_secrets.md`).

---

## Pointers to related docs

- `CLAUDE.md` — project-root file, the entry point for any AI assistant. Contains the Git-Workflow rules that should match this document. If they diverge, update both.
- `AGENTS.md` — canonical module map and architecture notes.
- `docs/TESTING_CHECKLIST.md` — structured manual UI test.
- `~/.claude/projects/<project>/memory/MEMORY.md` — cross-session memory index. This document should be linked there (entry: `scripts_workflow.md`).
