# Miolingo — Claude Code Instructions

> **Project architecture, DB rules, module map, known issues, debug mode, and
> app layout are in [`AGENTS.md`](AGENTS.md) — read that first.**
> `AGENTS.md` is the canonical project reference; if `CLAUDE.md` and `AGENTS.md`
> ever conflict, `AGENTS.md` wins.

> **Before doing anything that touches scripts, versioning, or PRs:**
> read **[docs/dev-docs/SCRIPTS_WORKFLOW.md](docs/dev-docs/SCRIPTS_WORKFLOW.md)**.
> It is the single source of truth for the end-to-end workflow and a reference
> for every script in `scripts/`. If a script seems to misbehave, check that
> document first — the scripts used to have bugs that forced workarounds, and
> new agents have repeatedly relearned the workflow from scratch. Don't be the
> next one: read the doc, and if you fix a script, update the doc.

---

## Git Workflow — PR Branches (read before any `git push`)

All work lands via PRs targeting `claude/dev-swept`. **Never push directly to
`claude/dev-swept` or `claude/dev`.**

When `git checkout -b` or `git switch -c` derives a branch from
`origin/claude/dev-swept`, the new local branch silently inherits
`claude/dev-swept` as its upstream. A subsequent `git push -u` will then push
*onto the parent branch*, bypassing PR review. Use the explicit refspec form
on the first push.

**Recipe — start a PR branch:**

```bash
git fetch origin claude/dev-swept
git switch -c claude/<descriptive-name> origin/claude/dev-swept

# ... make commits ...

# First push — explicit refspec forces a NEW remote branch matching the
# local name, regardless of inherited upstream:
git push -u origin HEAD:refs/heads/claude/<descriptive-name>
```

**Before every first push on a new branch, verify the upstream:**

```bash
git rev-parse --abbrev-ref @{u}   # should match local branch name after push
git symbolic-ref --short HEAD      # local branch name
```

If they don't match, use the `HEAD:refs/heads/<name>` refspec form. Never use
bare `git push -u origin <branch>` as the first push on a branch that was
created from another tracking branch — the inherited upstream will win.

A `PreToolUse` hook in `.claude/settings.json` now blocks `git push` when the
local branch name does not match its upstream, but the hook is a safety net,
not a substitute for following this recipe.

---

## Python Environment

**Always activate the project virtual environment before running any Python, pip, or related command.**

The venv holds all installed packages — running outside it means those packages are invisible to Python, regardless of which binary you invoke.

- Look for `venv/` or `.venv/` at the project root (check both)
- Activate with `source venv/bin/activate` or `source .venv/bin/activate` before running anything
- If neither exists, **stop and ask the user for help** — do not attempt to recreate it

---

## Current Debug Mode

The app is running in active debug mode. The following are **intentional** — do not report as new bugs:
- `Missing cookie_password in st.secrets` warning banner
- State-change banners (e.g. "State changed: story_mode: None → Scene by Scene")
- Connection Info panel showing tunnel details, SQL connection string, MySQL ID — this is for developer/tester use

---

## Testing Protocol

When asked to test the app, follow this standard approach.

Use `docs/TESTING_CHECKLIST.md` as a structured guide.

### Classification
Every issue must have **both**:

| Field | Options |
|-------|---------|
| **Type** | `Warning` · `Bug` · `Missing Feature` |
| **Severity** | `Critical` · `High` · `Medium` · `Low` |

- *Warning* — something shown to users that shouldn't be (config leakage, internal messages)
- *Bug* — incorrect behaviour: wrong output, broken interaction, data error, encoding failure
- *Missing Feature* — expected functionality absent (no charts, no filter, no export)

**Severity calibration in debug mode:** Lower severity by one level for debug-message leakage compared to production — the app banner explicitly warns users about this.

### Report Format
Use this template for each issue:

```
### ISSUE-N [Type] [Severity] — Short descriptive title

**Steps to reproduce:**
1. ...
2. ...

**Expected:** ...
**Actual:** ...
**Notes:** (optional context, workaround, related issues)
```

Include at the top of the report:
- App version (from sidebar)
- Environment (browser, OS, TTS engine, logged-in user)

### Depth
Cover **all** of the following before writing up:
- Every tab: Quick Practice, Story Reader, Statistics, History
- Sidebar: language settings, TTS engine, slow speech, Scoring Algorithm, Audio Processing, CCS Testing, Connection Info
- Within each tab: every expander, every sub-mode, at least one complete primary action

**Widget State Rule:** For every interactive widget encountered (toggle, checkbox, radio button, dropdown, selector), test **all** states — not just the default. Binary widgets: test both on and off. Multi-value selectors: test at least one non-default value. An untested state is an untested feature.

### Interleaving
Claude may (and should) pause to ask the user to log in, record audio, or perform any action requiring human input. This is expected and collaborative — not an error.
