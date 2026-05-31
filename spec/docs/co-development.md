# co-development.md
## How this spec is being built — human + LLM agent, in the open

This is a running log of the *process* by which miolingo's CCS specification is
being developed, as distinct from `METHODOLOGY.md` (which describes the
Specification-Governed Software Engineering *method* itself). The method is the
*what*; this is the *how we work*. It exists because the way the work is being
done — a person and an LLM coding agent in a tight, verifiable loop — is itself
worth describing, and because each step leaves a dated, reviewed checkpoint that
together tell a story about accelerating real software development with tools
that exist today.

The intended reader is not a miolingo end-user (they need none of this) and not
only a formal-methods specialist. It is anyone curious about whether — and how —
human+LLM collaboration can do careful, non-trivial engineering rather than just
generate plausible-looking code.

---

## The loop

Every change, large or small, goes through the same cycle:

1. **Discuss** — the human frames intent; the agent proposes a design and names
   the trade-offs. Genuine architectural choices (e.g. how to model external
   services, whether to model time) are *surfaced and deferred to the human*,
   not decided silently.
2. **Implement** — the agent writes the code on an isolated branch.
3. **Test** — the agent runs the spec headlessly on the Wolfram/RCA executor
   (`wolframscript`) and checks concrete assertions.
4. **Spiral** — failures are read, diagnosed, fixed, re-run, until green. (Real
   bugs caught this way are logged below — they are the evidence the loop
   works, not noise to hide.)
5. **Branch → PR** — the change lands as a pull request: a small, single-purpose,
   reviewable unit with a written rationale.
6. **Human review / merge** — the person reviews and merges (or asks the agent
   to merge). The human owns the spec and every decision; the agent realises
   them.

The single thing that makes this fast *and* trustworthy is step 3: **the
specification is executable**. Because the CCS spec runs on a real engine, the
agent can independently verify its own work — dedup really bumps a counter,
ordering really is faithful, a service value really flows through a
synchronisation — before asking for a human's time. Verification is not bolted
on; it is intrinsic. That is what turns "an LLM wrote some code" into "a change
that has been checked."

## Division of labour

This mirrors the method's governance split (`METHODOLOGY.md`, "Development
Workflow"):

- **Human-governed:** the specification, the architectural decisions, the
  merges. The spec — never old implementation code — is the source of truth.
- **Agent-executed, human-bounded:** bounded implementation tasks referenced to
  the spec, each producing a *verifiable artefact* (a passing headless test, a
  byte-identical regression). Anything touching multiple layers at once is
  rejected.
- **The human stays the open environment.** A nice consequence showed up in the
  interactive simulator (`walk`): rather than model the user as an agent inside
  the system, the person drives the model's input ports *from outside* — feeding
  the values that flow in, watching the values that flow out. They remain the
  unmodelled environment of an open system. "User and system are symmetric
  processes" is not a slogan here; it is literally how the tool is used.

## Decisions, as a legible trail

Because each non-trivial decision lands as its own PR with a written rationale,
the design history is self-documenting. Examples:

- *Should external services (translation, speech, DB) be oracles, agents, or
  real calls?* — a three-way cost/benefit/risk analysis, resolved **per service**
  rather than globally, since a service's port signature is invariant under the
  choice (so a service can be promoted from stub → canned-agent → live later
  without disturbing its consumers).
- *Should time be a clock agent?* — no: time in this app is passive data that
  never gates control, so a wall clock was *eliminated* in favour of a pure
  logical clock (a monotonic capture-counter), which turned out **more faithful
  and cheaper** than the real thing. (PR #137.)
- *Recover the stubbed functions from the Python* — pure data-transformations
  recovered as total functions; genuine side effects (clock, enrichment, speech
  recognition) quarantined behind named oracles, never invented. (PR #136.)

## PR trail (checkpoints)

Minimal commentary by design — each PR carries its own rationale.

- **#135** (merged 2026-05-31) — text-trace import parser + trace I/O round-trip test.
- **#136** (merged 2026-05-31) — function-recovery pass: VS + PS value-functions recovered from the Python.
- **#137** (open) — logical clock for VocabStore (replaces wall-clock).
- *(spike, pending)* — espeak grapheme-to-phoneme as a CCS service agent via the WolframScript bridge: the first external service made to run for real inside the spec.

*(Engine-side work on the Wolfram/RCA executor lives in the separate RCA
repository: native guard/choice, the substitution touch-gate, transition-time
relabelling, the `walk` simulator + trace replay.)*

---

## Honest about the technology

Communicating this work means meeting real and reasonable scepticism — about
energy and water use, about hype, about what these tools do to craft and to
jobs. A few things this project can say plainly:

- The claim here is **not** "the AI builds the app." It is "a person and a tool,
  in a loop where every step is *checked against an executable specification*,
  can do careful engineering faster." The human remains the author and the
  judge; the trail above is the evidence.
- The interesting acceleration is in the *verifiable* parts — recovering pure
  logic, running conformance checks, catching a bug at 3am that would otherwise
  surface in a user's hands. Not in producing more unreviewed code.
- The costs are real and worth naming rather than waving away. The honest frame
  is a trade — fewer human-hours and fewer downstream defects against compute
  spent — and whether that trade is worth it is a legitimate question, not a
  settled one.

The wider, communicable story is therefore not about miolingo's internals at
all. It is: *here is a concrete, inspectable example of human+LLM development
that is neither magic nor fraud — you can read every decision and every test.*

---

*This document is updated as the work proceeds; it is a log, not a finished
account.*
