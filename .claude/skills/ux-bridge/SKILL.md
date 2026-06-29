---
name: ux-bridge
description: Use when you (Claude Code) need the rendered browser checked or driven but cannot see it yourself — to test UX, verify a UI fix renders correctly, confirm layout on the running app, or run a click/type flow you can't observe. Sets up a two-way UX-test exchange with the browser-capable VS Code Chat agent, transported over Beads. Trigger on "test the UI", "check how X looks", "verify the rendering", "ux-bridge", or whenever a UI change needs eyes on the actual page.
---

# UX Bridge

You (Claude Code) cannot see the rendered browser. The VS Code Chat-tab agent
(with the page shared via "Sharing with Agent") can read and control it. This
skill opens a durable two-way exchange between you, transported over Beads.

Full contract: `docs/dev-docs/UX_BRIDGE_PROTOCOL.md` — read it if unsure.

## Steps

1. **Make sure the app is running** and note the URL (usually
   `http://localhost:8601`). If it isn't up, start it
   (`scripts/dev_server.sh 8601`) before requesting a check.

2. **Create the bridge issue** with a concrete, checkable request. Put the URL,
   the steps to perform in the page, and a checklist the browser agent answers:

   ```bash
   bd create --type task --labels ux-bridge \
     --title "UX-BRIDGE: <short topic>" \
     --design "URL: <url>
   STEPS:
     1. <action, e.g. record a French word / open a tab / type X>
     2. ...
   CHECK (answer each):
     - [ ] <specific question about layout / text / rendering>
     - [ ] ...
   Report with: bd update <THIS-ID> --append-notes \"REPORT: ...\""
   ```

   Ask **specific, verifiable** things ("is the dual-channel line on ONE row or
   stacked?", "what exact IPA text shows under Your Pronunciation?") — not vague
   ones. You can't see it, so the questions must extract what you need.

3. **Emit ONE nudge line for the human to paste to the browser agent**, e.g.:
   > Browser agent: check the ux-bridge — `bd list --label ux-bridge --status open`, do what the open issue asks on the app, append your findings with `bd update <id> --append-notes "REPORT: ..."`.

4. **Wait for the report.** Neither agent is notified of the other's writes, so
   the human will say "report's in" (or you can poll). Then:
   ```bash
   bd show <id>          # read the appended REPORT
   ```
   If the report references a screenshot path under `scratchpad/ux-bridge/`,
   Read that image.

5. **Act on it**: make code fixes, then either append a follow-up
   `--append-notes "REQUEST: re-check ..."` for another round, or
   `bd close <id>` when the topic is resolved.

## Notes

- Keep each exchange to one topic; open a new issue per topic.
- This is dev-time UX testing, NOT the CCS spec test pathway.
- If `bd` is unavailable, fall back to files in `scratchpad/ux-bridge/`
  (request.md / report.md) per the protocol doc.
