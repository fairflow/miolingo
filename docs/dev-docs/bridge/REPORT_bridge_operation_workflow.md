# Bridge Operation Report: Interaction Modes, Runbook Log, and Freshness Check

*Prepared in the same bridge directory as the foreign-agent cooperation report, for publication and reuse.*

## Purpose

This note records how the UX bridge was actually exercised in this phase, with particular attention to the different interaction modes used by the browser-side agent and the code-side agent. It is written alongside the bridge protocol and the new runbook so the workflow is readable as a single operating pattern rather than a one-off test log.

## Interaction Modes Observed

### 1. Direct screen interaction

This is the highest-level mode: a human or browser-capable agent works with the rendered page as a user would, by clicking visible controls and reading the UI state back from the screen. In this phase, the practical equivalent was the shared browser session in VS Code, where the page was the source of truth and the agent could observe the rendered controls, labels, and result text.

Use case:

- verify what is visibly rendered
- check whether a control is present or absent
- confirm the page state after rerender or navigation

Limits:

- it cannot see the underlying source code
- it is sensitive to rerender timing and stale page handles
- hidden Streamlit widgets are not always reachable by a simple visible click

### 2. `read_page` snapshots

This mode is best thought of as structured screen reading. It does not click anything; it returns the rendered accessibility tree and visible text in a way that is easier to inspect than a raw screenshot.

Use case:

- confirm the app shell, headings, and widget presence
- inspect the current rendered state without mutating it
- verify whether a previous click or rerun actually changed the DOM

Observed value in this phase:

- it showed when the app had reloaded into the login/guest shell
- it confirmed whether the build stamp was currently visible in the rendered page
- it exposed the presence of the debug injector once the app had rerendered into the practice view

### 3. `run_playwright_code`

This is the most surgical interaction mode. It is still browser-side, but it is script-driven and deterministic. It is useful when the visible control is not directly clickable, when a Streamlit widget is represented by a hidden input, or when a state change needs an exact sequence of DOM operations.

Use case:

- clicking hidden or off-viewport inputs with `evaluate((el) => el.click())`
- filling text inputs precisely
- pressing Enter to commit Streamlit field state
- reading the body text to detect whether a rerender exposed the expected section

Observed value in this phase:

- it made the debug injector usable when the plain click path was unreliable
- it committed the folder path and WAV selection so the saved-recording selector and `✅ Check Pronunciation` button would appear
- it triggered the mismatch result and then opened the detailed phoneme analysis and technical debug expander

### 4. `click_element`

This is the direct UI action layer over a known accessibility reference. It is ideal when the element is visible and already identified in the snapshot.

Use case:

- switching tabs such as Guest Mode
- toggling visible controls with known refs
- interacting with stable UI elements that do not need scripting

Observed value in this phase:

- it was useful for switching into Guest Mode in the restored app shell
- it worked well for visible controls, but not for the hidden Streamlit internals of the injector workflow

### 5. Shell and Beads tooling

The bridge operation also depended on non-browser tools:

- `bd show` and `bd update --append-notes` carried the durable request/report thread
- `git rev-parse --short HEAD` supplied the code hash for the freshness handshake
- `read_file` captured the runbook and protocol text for the report itself

These are not page-interaction tools, but they are part of the bridge because they define the contract, freshness, and durable handoff.

## Runbook Log

The new `RUNBOOK_agents.md` clarifies the bridge in two distinct modes.

### Claude Code runbook summary

Mnemonic: `Write, Ship, Serve, Ask, Wait, Read`.

Key points:

- code changes must be published before browser-side testing
- the serving checkout must be restarted after pull so the live app matches the merged source
- bridge requests must include the expected build hash, rendered-only instructions, concrete steps, and a verbatim checklist
- reports should answer from the rendered page, not from source code assumptions

### Copilot Chat runbook summary

Mnemonic: `Find, Freshness, Do, Report`.

Key points:

- locate the open `ux-bridge` issue and read it fully
- verify the served build stamp before trusting the page
- perform the actions on the rendered app, using the debug audio injector when the microphone is blocked
- append a report that quotes the visible text verbatim

### Human protocol summary

The human relay is intentionally minimal:

- tell Copilot: `check the ux-bridge`
- tell Claude Code: `report's in`

That is the entire manual handoff surface; the content moves through Beads.

## Freshness Check

The code-side freshness handshake for this report was:

- source hash: `6ee7946`

The served app was reattached in a fresh browser session and restored into the practice view. In the earlier authenticated render, the live page displayed the matching build stamp `build 6ee7946`, which matched the current source hash.

Important nuance:

- a later fresh attach landed on the login/guest shell before the practice view rehydrated, so the build caption was not immediately visible there
- the served app view used for the actual UX bridge test did expose the matching build stamp, so the browser-side report was aligned with the source revision

This is exactly the freshness pattern the runbook is meant to enforce: do not trust a browser-side report until the rendered build stamp and the source hash agree.

## Bridge Operation Notes

The most useful operational lesson is that the bridge is not just about the page being visible. It is about choosing the right interaction layer for the right problem:

- visible UI state is best checked with `read_page`
- hidden or timing-sensitive Streamlit widgets are best driven with browser scripting
- the durable conversation belongs in Beads, not in chat scrollback
- the build stamp matters because it prevents stale browser state from masquerading as current truth

In practice, the bridge works because it separates concerns:

- the code agent owns source truth and publication
- the browser agent owns rendered truth
- Beads owns the handoff
- the build stamp proves the two truths match

## Foreign-Agent Cooperation Findings

This phase was not just a UI test. It was a proof of coordination between two agents that have complementary strengths and no direct chat channel.

What worked:

- Claude Code could write, publish, and refresh the served code path.
- The browser-side agent could see and drive the rendered app without relying on the code view.
- Beads provided a durable, append-only mailbox for the request/report cycle.
- The build stamp made the freshness handshake explicit instead of implicit.

What the exercise showed:

- the bridge only became trustworthy once the running app and the source hash were pinned to the same revision
- mic-blocked pronunciation checks were still testable because the debug injector replayed saved audio
- the mismatch path was necessary to exercise the detailed comparison block; a perfect match skipped the very UI that needed verification
- the rendered-page contract mattered more than assumptions about source code, because the browser agent had to report only what was visible

The deeper operational lesson is that cooperation fails when two agents are reasoning from different representations of the same thing. In this project that showed up as:

- score vs display
- source vs render
- intended working directory vs actual shell state
- matching audio vs the mismatch path under test

The bridge succeeded because it forced all of those disagreements to surface in a place where they could be checked and recorded.

## Assessment

The overall outcome is that the bridge is practical, but only when the freshness rules are treated as mandatory rather than advisory.

Its strongest properties are:

- it avoids inventing a new transport layer
- it keeps the human relay tiny
- it makes the browser-side report durable and inspectable
- it gives publication-grade evidence about what the rendered app actually did

Its main limitation is that it still depends on the browser agent acting in response to a human nudge. That is acceptable for now, but it means the bridge is semi-automatic rather than fully autonomous.

For publication, the clean takeaway is this: a durable mailbox plus a freshness handshake is enough to make two blind-but-complementary agents cooperate on a rendered UI task without manufacturing false certainty.

## Publication Comments

If this is being published as a cooperation report, I would keep three claims explicit:

1. The bridge did not require a new transport service; Beads was sufficient as the mailbox.
2. The browser-side workflow became reliable only after freshness was treated as a first-class requirement.
3. The interaction-layer distinctions matter: visible clicking, snapshot reading, and DOM scripting each solved a different class of problem.

That framing makes the report more useful than a simple incident log because it explains why the workflow is robust and where it is still bounded.