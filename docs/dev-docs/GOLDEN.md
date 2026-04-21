# GOLDEN.md — How Matthew and Claude Work Together

**Audience:** Matthew (after a pause) and any future Claude session picking up
the project. This is the human-readable contract; `SCRIPTS_WORKFLOW.md` is the
mechanical recipe.

Last revised: 2026-04-21 (end of v7.8.0 session).

---

## The division of labour

| Role | Matthew | Claude |
|---|---|---|
| Write code / tests | — | ✅ inside a **linked worktree** |
| Run bump + create PR | — | ✅ via `scripts/bump_version.py` + `scripts/create-pr.sh` |
| Review & merge PRs | ✅ | — |
| Decide product direction | ✅ | proposes, awaits yes/no |
| Run manual UI testing | ✅ | may suggest what to click |

**Claude never pushes directly to `claude/dev-swept` or `claude/dev`.**
Everything lands via a PR that Matthew merges.

---

## Terminology

- **Main clone** — `/Users/matthew/Software/working/miolingo/`. The working
  tree Matthew opens in VS Code. Holds the venv and the secrets file.
- **Linked worktree** — `.claude/worktrees/<name>/`. Created by Claude Code's
  isolation mode. Has its own branch; shares `.git/` with the main clone.
  Git calls both of these "worktrees" internally, but in conversation we use
  *main clone* vs *linked worktree* to avoid confusion.

---

## Branches

- **`claude/dev-swept`** — the PR target. All Claude work merges here first.
- **`claude/dev`** — periodic promotion target (Matthew merges swept → dev
  when ready). Never PR'd to directly from a worktree.
- **`claude/<descriptive-name>`** — one PR branch per piece of work, always
  branched explicitly from `origin/claude/dev-swept`:

  ```bash
  git switch -c claude/<name> origin/claude/dev-swept
  ```

  The explicit upstream is critical — see `feedback_git_push_upstream_trap.md`
  in memory and the hook in `.claude/settings.json`.

---

## The golden path — every change, start to finish

Canonical mechanics live in `SCRIPTS_WORKFLOW.md`. Summary:

1. **Branch** from `origin/claude/dev-swept` inside a fresh linked worktree.
2. **Code + tests**, using `venv/bin/python` directly (the main clone's venv;
   no activation needed from the worktree).
3. **Run tests**: `venv/bin/pytest tests/…`
4. **Bump**: `venv/bin/python scripts/bump_version.py <kind> <level> \
   --suffix claude-dev --tag --notes "one" --notes "two"`.
   The `--notes` flag is **required** (v7.7.1+).
5. **PR**: `bash scripts/create-pr.sh --title "…"`.
6. **Push the tag**: `git push origin v<X.Y.Z>-claude-dev`.
7. **Boot the preview on 8701** (see below) so Matthew can click through.
8. **Hand back to Matthew** with a one-line summary of what shipped, PR URL,
   and which ports are live.

After Matthew merges, **reset the worktree**:
```bash
git fetch origin
git reset --hard origin/claude/dev-swept
```

---

## Ports

| Range | Owner | Purpose |
|---|---|---|
| 8501–8599 | Matthew | personal/daily dev |
| 8601–8699 | Claude | ad-hoc testing (first pick: 8601) |
| 8701 | Claude | **worktree live-preview after each PR** (agreed workflow — see below) |
| 8702 | IDE Preview | miolingo-admin |
| 8703 | IDE Preview | unified-admin |

**Workflow (agreed in v7.8.0 session, refined in v7.8.1):** after each PR push,
Claude takes over port 8701 so the IDE Preview button always shows the
branch-under-review. The mechanics — free the port, then start via the
Preview MCP (**not** via `bash scripts/dev_server.sh 8701 &`; that binds
the port and prevents Preview from owning it):

```bash
bash scripts/dev_server.sh stop 8701 2>/dev/null || true
```
Then, via MCP: `mcp__Claude_Preview__preview_start name="miolingo (main app)"`
— the config comes from `.claude/launch.json`.

The previous plan (8601 worktree vs 8701 main) was dropped — it duplicated work
without adding signal, because Matthew opens VS Code on the main clone and
navigates into the worktree tree anyway.

**Caveat — stale servers lie.** A Streamlit process holds whatever source it
loaded at startup. If 8701 shows an unexpected version, check with
`lsof -p <PID> | awk '$4=="cwd"'` before assuming the code is wrong.

---

## Python environment

- **One venv, lives in the main clone only** (`<main>/venv/`).
- Linked worktrees inherit Python via the path `…/miolingo/venv/bin/python` —
  absolute invocation bypasses the need for `source activate` and avoids the
  approval prompt.
- `pytest`, `pip show`, etc. work the same way: `venv/bin/pytest`, etc.
- Never run `pip install` inside a worktree unless the new dep will also be
  committed to `requirements.txt` in the same PR.

---

## Changelog discipline

- `scripts/bump_version.py` **requires `--notes`** (v7.7.1+). One `--notes`
  flag per bullet; each bullet gets prepended to `APP_CHANGELOG.md` under
  the appropriate heading (`--kind` defaults based on bump level).
- One-off doc or infra-only changes can pass `--no-notes`, which writes a
  literal "Housekeeping" bullet — only use it when there genuinely is no
  user-visible change.
- The bump commit is *part of* the PR; don't cherry-pick it separately.

---

## Settings files — three layers

| File | Scope | Committed? | Use for |
|---|---|---|---|
| `~/.claude/settings.json` | Matthew, globally | no (personal) | auto-allows for commands Claude runs on every project |
| `.claude/settings.json` | project, team | **yes** | hooks, permission rules that every contributor needs |
| `.claude/settings.local.json` | per-worktree | no (gitignored) | one-off allow-lists for this branch |

Personal auto-allows (git commands, `gh` CLI, `Claude_Preview`) should live in
the user-global file, not in the project. Miolingo-specific ones (the
venv path pattern, `scripts/create-pr.sh`, etc.) stay in the project file.

A starter template for the user-global file was left at
`proposed-user-settings.json` in the v7.7.x worktree — copy over once, then
delete.

---

## When things go wrong

- **"Git push rejected by hook"** — the branch's upstream is still
  `claude/dev-swept`. Use `git push origin HEAD:refs/heads/<branch>` for the
  first push of a new branch. Never `git push -u` on an inherited upstream.
- **"Version not bumped" from `create-pr.sh`** — bump first, then PR. The
  script compares HEAD to `origin/claude/dev-swept`.
- **"Preview shows old version after my edit"** — Streamlit's `sys.modules`
  cache keeps module-level constants frozen for the process lifetime. Stop
  and restart the server, don't just reload the page.
- **"Tests passed locally, CI failed"** — check whether the failing test
  hits the DB; the `miolingo_test` schema is only available on Matthew's
  machine and the CI docker, not random clones.

---

## Out of scope for this document

- Product roadmap and feature priorities — those live in
  `docs/dev-docs/ROADMAP.md` and the various `project_*.md` memory entries.
- How to actually use the app as an end user — `docs/app-docs/USER_GUIDE.md`.
- Detailed script flag reference — `docs/dev-docs/SCRIPTS_WORKFLOW.md`.

---

**TL;DR** — Claude branches from dev-swept in a linked worktree, codes +
tests + bumps + PRs + boots 8701, then stops. Matthew merges, resets the
worktree, and the loop repeats.
