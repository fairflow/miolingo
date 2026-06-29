# UX Bridge Protocol — Claude Code ⇄ browser-agent, via Beads

A lightweight, durable channel for **two-way UX testing** between two agents that
each see only half the picture:

- **Claude Code** (this agent): sees code, runs the app, edits files, reads bd —
  but **cannot see the rendered browser**.
- **Browser agent** (the VS Code Chat-tab agent, e.g. Copilot, with the page
  shared via "Sharing with Agent"): can **read and control the rendered page**
  (click, type, snapshot) — but does not see Claude Code's runtime.
- **Human**: gives a one-line nudge per cycle (no copy-paste of content).

The transport is **Beads** (`bd`) — already shared workspace infrastructure,
durable across sessions, so each exchange is a persistent record.

## The channel

- One **bd issue per UX-test cycle**, `type=task`, **label `ux-bridge`**, title
  prefixed `UX-BRIDGE: <short topic>`.
- The **request** is the issue description / design (what to inspect, the URL,
  steps to perform, an observation checklist).
- The **report** is appended by the browser agent via `--append-notes`,
  prefixed `REPORT:`. Follow-ups append again (`REQUEST:` / `REPORT:`), so the
  issue's notes become the threaded conversation.
- Close the issue (`bd close <id>`) when the topic is resolved.

## Discovery (how each side finds the active exchange)

```bash
bd list --label ux-bridge --status open     # the open bridge exchanges
bd show <id>                                 # read request + appended reports
```

## Roles

### Claude Code writes a request
```bash
bd create --type task --labels ux-bridge \
  --title "UX-BRIDGE: <topic>" \
  --design "URL: http://localhost:8601
STEPS:
  1. <action to perform in the page>
  2. ...
CHECK (answer each):
  - [ ] <question about layout/rendering>
  - [ ] <question ...>
Report findings with: bd update <this-id> --append-notes \"REPORT: ...\""
```

### Browser agent performs + reports
1. `bd list --label ux-bridge --status open` → find the issue.
2. `bd show <id>` → read URL, steps, checklist.
3. Perform the steps in the shared browser; observe the rendered result.
4. Append findings:
```bash
bd update <id> --append-notes "REPORT: <answers to each CHECK item, verbatim
text read from the page, layout observations, anything unexpected>"
```
5. Optionally save a screenshot to `scratchpad/ux-bridge/report-<id>-NNN.png`
   (Claude Code can Read images) and note the path in the report.

### Claude Code consumes + iterates
- `bd show <id>` → read the REPORT, make code fixes.
- Append a follow-up `REQUEST:` for re-test, or `bd close <id>` when done.

## The irreducible human step

Neither agent is notified when the other writes. So **one nudge per cycle**:
- to the browser agent: *"check the ux-bridge"* (it runs `bd list --label ux-bridge`)
- to Claude Code: *"report's in"* (it runs `bd show <id>`)

That nudge is the only relay — no content is copy-pasted between agents.

## Scope

Dev-time UX testing only. NOT the CCS spec-based testing pathway (deliberately
avoided as overhead while the core is still being built). If this proves useful,
it could later be grafted onto the real CCS spec flow.
