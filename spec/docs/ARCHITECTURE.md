# miolingo — Architectural Record

## Governing Principle

miolingo's behaviour is specified in value-passing CCS as a network of agents, each visible only through named, typed ports. The port signature is the contract; everything else is subordinate. All UI implementations are derived from, or verified against, this spec. The spec is the authority.

## The Agent / Port Model

- Each component is an agent with hidden internal state.
- An agent exposes input and output ports, each carrying a typed value.
- Output: on synchronisation, a value computed from current state is delivered; state may change as the agent's own definition dictates.
- Input: on synchronisation, a value is received and incorporated, directly or via a derived state change.
- The partner across any port may be another agent or an external client (UI, test harness, user) — symmetric, unprivileged.
- The agent is visible only at its ports. No other channel exists.

**Sort vs ready set.** The *sort* is an agent's full port alphabet — every presentation L2/L3 must be able to produce. The *ready set* is the subset offered in the current state, fixed by guarding. Control enablement is therefore L1-derived: the skin renders the ready set, it does not decide it. Because guards are state-dependent, the ready set cannot be precomputed in general; the live agent encoding must compute its afforded ports on the fly from current state, and the skin queries and renders them.

**Read-only views.** A state display is an output-only port carrying a published projection, `view!(f state)` — never raw state. The projection `f` is an L1 decision; its rendering is L2/L3. Reflective views (showing the agent's own definition) are a distinct projection and a distinct port.

## The Three Levels

### L1 — Semantic Specification

- Language: value-passing CCS
- Location: `/spec/*.ccs` (i.e. sibling of this `docs/` directory)
- Executor: Wolfram/RCA (existing codebase), via WolframScript bridge at `/spec/wolfram/`
- Defines: agents, ports, value types, guard structure (hence ready sets), published projections
- Governed by: human architect (agent-assisted drafting permitted; human reviews and owns)

### L2 — Abstract Interaction Form

How each port is presented, in framework-independent vocabulary derived from L1:

| Port shape | Example realisations |
|---|---|
| Finite-choice input | tabs, radio buttons, dropdown |
| Sequential input | wizard, paged flow |
| Free-form input | text field, IPA input |
| Confirmation input | dialog, inline confirm |
| Scalar projection (output) | progress bar, score display |
| Collection projection (output) | scrollable list, table |
| Non-ready port rendering | greyed-and-inert, or hidden |

Location: `/spec/interaction-forms.md`. Governed by: human designer.

### L3 — Skin

- Framework-specific widget implementation and styling
- Swappable without modifying L1 or L2
- Location: `/spec/skins/{skin-name}/`
- Agent-executable under the L2 contract
- Multiple skins may coexist against the same spec

## Component Inventory (preliminary)

| Component | CCS agent family | Kind | Priority |
|---|---|---|---|
| Practice Session | `PracticeSession` | Stateful agent — tight interaction loop | High — **recovered** (PS) |
| Vocabulary Manager | `VocabStore` | Stateful agent — CRUD with IPA | High — **recovered** (VS) |
| Session / language | `Helm` | Stateful agent — finite-choice settings; **owns the (source, target) language pair** | **recovered** |
| Stats Display † | (projection of `PracticeSession`/`VocabStore`) | Read-only view port — **not** a standalone agent | Medium |
| History Browser † | (projection of a session/store agent) | Read-only view port — **not** a standalone agent | Medium |
| Mode Navigation | `ModeSelector` | Stateful agent — finite-choice | Low |

Correction from the previous draft: the read-only "displays" are most likely *view ports on* the stateful agents (a published `view!` projection rendered by a skin), not agents in their own right. Promote one to a standalone agent only if it genuinely owns state; otherwise it is a presentation of another agent's projection. Decide this deliberately per component.

**† Stats / History and the external store (a rigging issue).** Treating these as *view ports* is correct only under the current modelling assumption that each component stores its own domain data in-process. In any sensible implementation, stats and history are retrieved from an **external store**, not held by the component. Rigging that external store into the system — where the data lives, who reads/writes it, how a view port is backed by a *query* rather than in-process state — is a key **rig** concern, and the question of *how* it is done may itself need to enter the model (an external-store agent / port), not be left wholly to L3. Flagged for when stats/history (and persistence generally) are recovered.

## Execution Model

- Single-user, single-threaded (current version).
- Qt direct signal/slot connections throughout; direct connections preserve CCS synchronisation semantics.
- Validation path: execute the CCS spec on the RCA executor and/or run CCS-derived test processes.
- Product path: a PyQt skin realises the port contract. Whether core logic is reimplemented natively or bridged to Wolfram at runtime is an open decision; the spec governs either way.
- Multi-user game variant: future work — concurrency (and possibly bigraph place-structure) introduced at L1 only when locality/mobility becomes load-bearing, not before.

## Framework Selection Criterion (hypothesis)

Prefer frameworks whose execution model is compatible with the port/ready-set model. The sharp form: a view port emitting on state-change *is* a Qt signal, and a ready set *is* the set of currently connected/enabled slots; Streamlit's whole-script rerun only simulates both. Qt is therefore preferred not on taste but because it has native constructs for the view port and the ready set, whereas Streamlit fakes them. Under empirical investigation, not yet confirmed.

## Port Boundary Criterion

A port exists where the agent deliberately exposes a typed data exchange — an input it accepts, or a projection of state it publishes — that advances the protocol or is observable by a partner. Not every widget signal; only exchanges the agent chooses to make part of its contract.

Example for Practice Session: `attempt_made` (in), `evaluation` (out, a projection), `next_item_requested` (in) — not individual keystrokes or field updates.

## What Agents May and May Not Do

### Permitted

- Implement L3 skin code given L2 interaction-form declarations.
- Generate Qt bindings for declared ports, including ready-set rendering (enablement) and view-port projections.
- Write WolframScript bridge code for specified port types.
- Generate test-harness code from spec-derived traces and ready sets.
- Assist in *drafting* CCS under explicit human review (the human owns and signs off L1).

### Not Permitted

- Treat old Streamlit code as a source of semantic truth.
- Infer component dependencies from existing code rather than from ports.
- Refactor across architectural layers in a single session.
- Invent control enablement instead of rendering the ready set.
- Expose agent state other than through a declared port/projection.
- Proceed without a declared L2 interaction form for each port in scope.

## Open Problems

- Formal definition of the binding-layer protocol, including the mandatory afforded-ports operation each encoding must compute on the fly, and how to verify it matches `init(P)` at every reachable state.
- Precise vocabulary and grammar of L2 interaction forms, including non-ready-port rendering.
- Handling framework constructs with no clean CCS analogue.
- Automated verification of L3 against L1 via ready-set / testing equivalence.
- The point at which the multi-user variant forces locality into L1 (bigraph adoption threshold).
