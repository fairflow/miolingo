# Two agents, one rendered app: building a cooperation bridge in VS Code

*Introduction to a pair of companion reports on coordinating two AI coding
agents — Claude Code and GitHub Copilot Chat — through a shared mailbox, to test
a web UI neither could verify alone.*

## The setup

Two AI agents ran side by side in one VS Code window on the Miolingo project
(a pronunciation-practice app). They had complementary blindnesses:

- **Claude Code** edits and runs the code, reads the filesystem and the issue
  tracker — but cannot see the rendered browser.
- **GitHub Copilot Chat** can see and drive the rendered app (click, type,
  snapshot) — but cannot see Claude Code's runtime or reason reliably about the
  code behind the page.

No native channel connects them. The work was to make them cooperate on a task
that needs both halves — "does this UI fix actually render correctly?" — with the
human reduced to a minimal relay. The transport they settled on was **Beads**
(the project's durable issue tracker) used as an append-only mailbox, plus a
**build-hash stamp** in the UI so each side could confirm they were looking at
the same revision.

## The two reports

This introduces two companion documents:

- **The code agent's account** (`REPORT_foreign_agent_bridge.md`, Claude Code) —
  how the bridge was generated and operated, why each step of the protocol
  exists, the glitches encountered, and the goal of minimising human
  intervention versus the outcome.
- **The browser agent's account** (`REPORT_bridge_operation_workflow.md`,
  Copilot) — the interaction *modes* used on the page (visible clicking, snapshot
  reading, DOM scripting), why hidden Streamlit widgets needed scripting rather
  than clicks, and the freshness handshake as observed from the rendered side.

They are complementary: each documents the half the other is blind to. Read
together they describe one operating pattern from both ends.

## A necessary note on provenance (so the convergence isn't oversold)

The two reports reach strikingly similar conclusions — most notably that
*cooperation fails when two agents reason from different representations of the
same thing* (score vs display, source vs render, intended working directory vs
actual shell state, matching audio vs the mismatch path under test).

**This agreement is not independent corroboration.** The reports were written in
sequence, each with knowledge of the other: the code agent's report was written
first and shown to the browser agent before it wrote its own; the code agent then
read the browser agent's report. So the convergence reflects **shared exposure
and a genuinely shared experience of the same debugging sessions**, not two
analysts arriving at the same place in isolation. We flag this explicitly because
it would be easy — and wrong — to present sequential influence as independent
discovery. What the agreement *does* show is that the lesson was salient enough to
both participants, from their different vantage points, to be stated in
compatible terms; it is corroboration of *salience and mutual legibility*, not of
independence.

A genuinely independent replication — two agents each writing up the same logged
sessions without seeing the other's report — would be a worthwhile follow-up, and
is the honest way to test whether the central finding survives without priming.

## A small concrete discrepancy, kept honest

The two reports cite different build hashes (`f878a66` in the code agent's
expectation at one point; `6ee7946` in the browser agent's verified test view).
This is not an error but the freshness mechanism working: the served code
advanced between observations, and the build stamp is precisely what made the
difference visible rather than silent. The reports observed different revisions
at different moments, and said so.

## What a reader should take away

A durable shared mailbox plus an explicit freshness handshake is enough to let
two blind-but-complementary agents cooperate on a rendered-UI task without
manufacturing false certainty — and the failure mode to guard against is not the
channel but **divergent representations of the same ground truth**. The residual
limitation is that the loop is semi-automatic: the browser agent cannot
self-trigger, so one human nudge per round remains, removable only with an
external watcher not built here.
