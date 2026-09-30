# UX bridge — agent runbooks

How each agent actually runs the bridge. Two separate runbooks: one for **Claude
Code**, one for **GitHub Copilot Chat**. Keep them mentally separate — each agent
does only its own list.

The mailbox is Beads: one issue per cycle, label `ux-bridge`, title `UX-BRIDGE:`.
Request lives in the issue; reports are appended with `--append-notes`.

---

## Runbook A — Claude Code (the long flow)

Mnemonic: **"Write, Ship, Serve, Ask, Wait, Read."**

For any cycle that involves a **code change**, never skip the Ship/Serve steps —
that is what keeps Copilot testing the real merged code, not a stale snapshot.

1. **Write** — make the code change.
2. **Ship** — `commit → push → PR → merge`. (Worktree git: use
   `git -C <worktree> …`; cwd does not persist across shell calls.)
3. **Serve** — `pull` into the checkout the app serves from, then **restart** the
   server (e.g. `bash scripts/dev_server.sh stop 8601` then `… 8601`). Now the
   running app == merged source.
4. **Ask** — write a self-contained request into a `ux-bridge` issue:
   ```bash
   bd create --type task --labels ux-bridge --title "UX-BRIDGE: <topic>" \
     --design "URL: http://localhost:8601
   EXPECT build: <current git short-hash>   # freshness handshake
   Report only what the RENDERED page shows — do NOT reason from source files.
   STEPS: 1) … 2) …
   CHECK (quote verbatim): - [ ] … - [ ] …
   Append: bd update <id> --append-notes \"REPORT: …\""
   ```
   Always include: the **expected build hash**, the **rendered-only** instruction,
   concrete **steps**, and a **verbatim-quote checklist**. For anything needing a
   recording, tell Copilot to use the **🧪 inject test audio** debug expander
   (mic is blocked for it); to render the diff block, use a **mismatched** target
   vs injected wav.
5. **Wait** — the human will say `report's in`. Then `bd show <id>`, read the
   `REPORT:`. If it references a screenshot under `scratchpad/ux-bridge/`, Read it.
6. **Read & repeat** — analyse; either append a follow-up `REQUEST:` (and go to
   step 1 if more code changes) or `bd close <id>` when the topic is resolved.
   **Never leave an issue open with no pending REQUEST** — Copilot will idle.

Discipline checks:
- Phrase shell commands to MATCH the allowlist (relative paths, simple commands,
  no `VAR=` prefixes, no compound `;`/`&`/redirects) — see the shell-hygiene memory.
- A code-change request without a fresh build hash is invalid — fix the cycle first.

---

## Runbook B — GitHub Copilot Chat (the short flow)

Mnemonic: **"Find, Freshness, Do, Report."**

On hearing the human say **`check the ux-bridge`**:

1. **Find** the open exchange:
   ```bash
   bd list --label ux-bridge --status open
   bd show <id>          # read EVERYTHING: URL, expected build, steps, checklist
   ```
2. **Freshness** — open the app URL, hard-refresh, ensure Debug Mode is ON, and
   read the `build <hash>` caption under the title. If it does **not** match the
   request's `EXPECT build`, STOP and append a note saying the server is stale —
   do not test against stale code.
3. **Do** — perform the steps on the **rendered** app. Mic is blocked for you:
   use the **🧪 Debug: inject test audio (no mic)** expander to substitute a saved
   `.wav`. Report only what you SEE rendered; do **not** infer from source files.
4. **Report** — append findings, answering each checklist item verbatim:
   ```bash
   bd update <id> --append-notes "REPORT: <answers; quote exact page text>"
   ```
   Optionally save a screenshot to `scratchpad/ux-bridge/` and note the path.

You cannot self-loop or poll — you act only when the human nudges you. That is
expected; one nudge per round is the design.

---

## Shared rules (both agents)

- The bd issue is the single source of truth for a cycle — read it fully, don't
  assume.
- Reports describe the **rendered page**, never the source code.
- Confirm the **build hash** before trusting any code-change test.
- One topic per issue; close when done.
