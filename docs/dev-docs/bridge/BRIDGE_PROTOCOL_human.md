# The UX bridge — a guide for the human in the loop

You sit between two AI agents in VS Code that can't talk to each other directly:

- **Claude Code** — writes and runs the code, but **can't see the app's screen**.
- **GitHub Copilot Chat** — **can see and click the running app** (via "Sharing
  with Agent"), but can't see Claude Code or the code's behaviour.

The bridge lets them collaborate on "does this actually look/work right?" Your
job is small: **pass two fixed signals** and merge a PR when asked. You never
copy content between the two chat panes.

## What you actually do (per round)

1. Claude Code makes a change and (for code changes) **commits, pushes, opens a
   PR, merges, pulls, and restarts the app**. It may ask you to confirm a merge.
2. Claude Code says it has written a request. You turn to the **Copilot** pane and
   type exactly:

   > **check the ux-bridge**

3. Copilot reads the request, tests the running app, and writes its findings back.
   When it's done, you turn to the **Claude Code** pane and type exactly:

   > **report's in**

4. Claude Code reads the findings and either fixes more (back to step 1) or
   declares the cycle done.

That's it. Two three-word phrases. Everything substantive — the request, the
test findings, the analysis — travels between the agents automatically; you don't
relay any of it.

## How the agents pass messages: Beads, in one paragraph

The agents have no shared chat, so they use **Beads** (`bd`) as a mailbox. Beads
is this project's issue tracker (a small database, the same one used for task
tracking). For each test cycle the agents open one Beads issue tagged
`ux-bridge`: Claude Code writes the request into it, Copilot appends its report to
it, and they take turns adding notes — so the issue becomes their shared
conversation thread. Because Beads is durable and both agents can read/write it,
it's a reliable post-box that survives even if a chat is closed. You don't need to
touch Beads; it's just where their notes live.

## The discipline that makes it reliable (and why)

Two rules were learned the hard way; they're why the agents sometimes do extra
steps before asking you to nudge:

- **Always publish before testing.** A code change must be committed → pushed →
  merged → pulled → and the app **restarted** before Copilot tests it. Otherwise
  Copilot may test an old running version while Claude Code thinks it's testing
  the new one — they then report contradictory things. (This caused a long,
  confusing debugging detour once.)
- **Confirm the build stamp.** In debug mode the app shows a small `build <code>`
  tag under the title. Copilot checks this matches the version Claude Code expects
  *before* reporting, so the two agents are provably looking at the same code. If
  it doesn't match, Copilot stops and says so rather than reporting on stale code.

## A couple of practical notes

- **Microphone:** Copilot can't use the mic in the shared browser, so for
  pronunciation tests it uses a hidden debug control that plays a **saved
  recording** instead. Real audio, replayed — not faked.
- **Debug mode must be ON** for the build stamp and the audio-injector to appear.
- **If Copilot says "nothing to do" or "no request":** Claude Code hasn't written
  the next request yet — wait for it, then nudge.

## What this can and can't do automatically

The agents can carry the *content* themselves, but **neither can trigger the
other** — Copilot in particular can't be put on a timer or made to act on its own.
So your two nudges per round are, for now, irreducible. Removing them entirely
would need a small custom VS Code extension that watches Beads and pokes Copilot;
that's a future option, not built yet.
