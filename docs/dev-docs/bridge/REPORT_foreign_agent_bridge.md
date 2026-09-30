# Developing foreign-agent cooperation in VS Code: the Miolingo UX bridge

*A report on building and operating a two-agent testing channel — Claude Code
and GitHub Copilot Chat — coordinating through Beads, June 2026.*

## The problem

Two AI agents run side by side in one VS Code window, each able to do what the
other cannot:

- **Claude Code** edits code, runs the app, reads the filesystem and Beads — but
  **cannot see the rendered browser**. It has no screen/pixel input.
- **GitHub Copilot Chat** (with a page shared via "Sharing with Agent") can
  **read and control the rendered app** — click, type, snapshot — but cannot see
  Claude Code's runtime, and cannot self-schedule.

Neither can message the other directly. For UX work — "does this fix render
correctly?" — Claude Code is blind exactly where it matters. The goal was a loop
where Claude Code fixes, Copilot tests the rendered result, Claude Code reads the
findings and iterates — with **minimal human relay** (no copy-pasting screenshots
or instructions between two chat panes).

## What was built

A **mailbox over Beads**. There is no new service or extension: the bridge is a
*convention* for using infrastructure both agents already have (`bd`, the
Dolt-backed issue tracker).

- One **bd issue per test cycle**, labelled `ux-bridge`, title prefixed
  `UX-BRIDGE:`.
- Claude Code writes the **request** (URL, steps, checklist) into the issue.
- Copilot **appends its report** with `bd update <id> --append-notes "REPORT: …"`.
- Follow-ups append again, so the issue's notes become the threaded conversation.
- Discovery is by label: `bd list --label ux-bridge --status open`.

Beads was the right mailbox because it is (a) **shared** — both agents run `bd`
in the same workspace; (b) **durable** — backed by a Dolt DB, persistent across
sessions and syncable; (c) **append-only-friendly** — `--append-notes` threads a
conversation onto one record; (d) **discoverable** — labels let each side find
the active exchange without being told an ID. A plain shared file (`request.md`/
`report.md`) was the fallback design, but Beads adds persistence and structure
for free.

## How it operates

**Claude Code's full loop (the long flow):**

```
write → commit → push → PR → merge → pull → restart → bd request → (human nudge)
       → wait for Copilot report → analyse → repeat
```

**Copilot's loop (the short flow):** on hearing `check the ux-bridge` —

```
bd list --label ux-bridge --status open → bd show <id> → act on rendered app
       → bd update <id> --append-notes "REPORT: …"
```

The human types one fixed phrase per direction (`check the ux-bridge` to Copilot,
`report's in` to Claude Code) — never crafted, never content.

## Glitches encountered, and why each step exists

Each step of the long flow earned its place by fixing a real failure:

1. **Mic blocked in the shared browser.** Copilot could drive the app but the OS
   denied microphone access, so the Results panel — the UX we needed — never
   rendered. → **Audio-injection debug hook**: a saved `.wav` substitutes for the
   mic, replaying real prior audio. The whole Results flow became agent-drivable.

2. **The score/display normalisation mismatch.** The detailed phone comparison
   was computed on a different normalisation than the score, so it showed stray
   artefacts (stress marks, an espeak clitic `-`, filler `·` middots that looked
   like phones) the scorer had already ignored. → Diff rewritten to use the
   scorer's own `segment()`, with a clear `∅` gap marker. *(This is the bug class
   the bridge exists to catch: a thing that looks fine in code but renders wrong.)*

3. **eSpeak `-x` ASCII codes shown as if IPA** (`mErs'i`). → Hidden outside debug
   mode, relabelled as codes-not-IPA.

4. **Perfect-match path bypassed the diff block.** A test whose audio matched the
   target scored 100% and skipped the very UI we wanted to verify. → Tests must
   use a deliberate **mismatch** to render the diff. *(Lesson: design the test
   input to exercise the path under test.)*

5. **The injector "not rendering."** The decisive, maddening glitch. Copilot
   reported the injector absent; the code was clearly present. Root cause: Copilot
   **conflates two views** — the rendered app and the on-disk source — and they
   had **drifted**, because the running server was a snapshot from an earlier
   checkout while files kept changing under it. Claude Code had also been asking
   Copilot to verify *uncommitted/unmerged* edits. → Two fixes:
   - **The commit→push→PR→merge→pull→restart discipline**, so the served code is
     provably the current merged source before any request.
   - **A `build <git-hash>` UI stamp** (debug mode): Copilot reads it off the
     *rendered* page and confirms it matches the expected hash before reporting.
     Render and source can no longer silently disagree.

6. **`cd` not persisting across calls.** Claude Code ran `git add/commit` from the
   wrong directory (cwd reverted between shell calls), silently staging nothing.
   → Always `git -C <worktree>` for worktree ops; never assume an earlier `cd`
   holds.

The recurring theme: **every glitch was a hidden disagreement between two
representations** — score vs display, code vs render, intended cwd vs actual,
matching-audio vs the path under test. The bridge's value is that it *surfaces*
these, because a second agent looking at the real rendered artefact contradicts
the first agent's confident assumption.

## Minimising human intervention: goal vs outcome

**Goal:** a no-human loop. **Outcome:** semi-automatic — one fixed nudge per
round each direction.

A capability probe (run *through the bridge itself* — pleasingly recursive)
established the ceiling honestly: **Copilot cannot self-schedule, poll on a
timer, or be auto-triggered into a chat turn by a file change.** It only acts on
an incoming message. It *can* write completion markers to Beads, which an
*external* watcher could detect. Claude Code can self-pace (via `/loop`), but
Copilot's half cannot.

So full autonomy is **not achievable from the agents alone** — it requires an
external orchestrator/watcher (a small VS Code extension or daemon watching Beads
for new `ux-bridge` notes and injecting a chat turn). We judged that
disproportionate to the problem mid-development and did not build it.

**How well the goal was met:** the human relay was reduced from *crafting and
pasting full instructions + screenshots both ways* to **two fixed three-word
phrases** — a large reduction, and the substantive content (requests, reports,
analysis) flows agent-to-agent through Beads with no human handling. The
irreducible residue is one nudge per direction per round, which only a custom
watcher could remove.

## Assessment

The exercise worked: two foreign agents, with no native channel between them,
cooperated productively on a task neither could complete alone, coordinating
through a shared durable store. The design is **portable** — the skill, the
protocol, the permissions baseline, and the build-stamp pattern drop into any
repo; only the app URL differs. The main cost was discovering, the hard way, that
**both agents must be pinned to the same source of truth** before their reports
can be trusted — which the commit-cycle discipline and the build stamp now
guarantee.

The deeper lesson is general to multi-agent work: cooperation fails not on the
*channel* but on **shared ground truth**. Give two agents a durable mailbox and a
freshness handshake, and they coordinate; omit either and they generate
confident, contradictory nonsense.
