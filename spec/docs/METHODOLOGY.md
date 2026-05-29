# Specification-Governed Software Engineering with LLM Agents

## Methodology Summary v0.2

### The Core Idea

An agent in this methodology is a named process with hidden internal state, visible to the outside world *only* through a set of named, typed ports. Nothing else about it is observable. The set of ports, together with the types of value they carry, is the entire contract the system offers — to its users and to its other components alike. We call this the **port signature**.

This single commitment is the foundation:

- *What the system does* is the behaviour observable at its ports.
- *What a component depends on* is exactly the ports it synchronises with — nothing implicit, nothing inferred.
- *How a port appears* to a human — a dropdown, a radio group, a pane, a gauge — is a separate question, deferred to lower levels and freely variable.

Because the contract is stated entirely in framework-independent terms (port names and value types), the same specification can be realised against Qt, web, mobile, or any future target without alteration. The presentation is swappable; the contract is not.

### Why This Matters for LLM Agents

LLM coding agents are syntactically fluent but semantically shallow. Given an existing codebase they optimise locally, migrate superficially, and lose implicit behavioural dependencies — particularly those carried by framework-specific runtime mechanisms (Streamlit's `session_state`, React hooks, hidden reactivity) rather than by explicit code structure. The larger and more autonomous the task, the worse this gets.

A port-signature contract removes the thing agents are bad at. There is no implicit dependency to infer, because every dependency is a declared port. The agent's job shifts from *understanding the system* to *implementing a declared contract* — a tractable task. Catching the migration-failure class then falls out as a corollary of the design rather than being its primary aim.

### The Agent Model (L1)

- An agent has internal state, not directly visible from outside.
- It has input ports and output ports, each carrying a value of a declared type.
- On synchronisation at an **output** port, a value is delivered to the partner. That value is a function of the agent's current state. The act of output may itself change state, but only as the agent's own definition dictates.
- On synchronisation at an **input** port, a value is received from the partner and incorporated — stored directly, or via a derived state change.
- The partner across a port may be another core process or an external client (a UI, a test harness, the user). User and system are symmetric processes; neither is privileged.
- The agent is visible *only* at its ports. There is no other channel.

### Sort and Ready Set

Two distinct facts about an agent's interface, easily conflated:

- The **sort** is the agent's full port alphabet — every port it can ever use. This is the static interface. It tells L2/L3 the complete set of presentations that must exist, because any port may eventually appear.
- The **ready set** is the subset of ports the agent is actually offering *in its current state*, determined by guarding (prefixing and choice) in the operational semantics. It is a function of state, in exactly the way an output value is.

The consequence is significant: **control enablement is derived from L1, not invented at L2/L3.** Whether a control is live — Submit enabled, the next-item control present — is governed by whether its port lies in the current ready set. The skin *renders* the ready set; it does not decide it. This dissolves a notorious bug class: the scattered, ad-hoc enable/disable logic that drifts out of step with the model.

One honest wrinkle. CCS synchronisation is a blocking rendezvous: ordinarily one learns a port is unavailable only by the handshake failing to happen. A UI wants to render enablement *before* the user acts, which needs the ready set without attempting a sync — and the bare calculus offers no "is this port ready?" query. Crucially, the ready set cannot be precomputed in general: with data-dependent guards it depends entirely on current state, so there is no static table to consult. It must be evaluated on the fly. The rendering engine cannot do this from outside — it does not hold the state, and reaching in would breach encapsulation — so it must ask the component, and the component (in whatever target language it is encoded) must answer from its own state by evaluating its guards. This afforded-ports operation is therefore a *mandatory part of every faithful encoding's contract*, not an optional projection: the single point where pure CCS, which offers only the blocking rendezvous, is extended with a non-blocking introspection the encoding is obliged to provide. (Only in the degenerate finite-control, no-data-guard case could ready sets be tabulated in advance; do not lean on that case architecturally.)

### Read-Only Views Are Output Ports

A pane that shows "a view of the agent's state" must not breach encapsulation by exposing state directly — that would make the agent visible by something other than its ports. It does not have to. A read-only display is an output port whose carried value is a *projection* the agent chooses to publish: `view!(f state)`. The observer never sees state; it sees only what `f` emits. "Read-only" means simply an output-only port with no complementary input to write back. The display is therefore not an exception to *data crosses only at ports* — it is an instance of it.

Two corollaries:

- The projection `f` — what an agent publishes about itself — is an L1 decision. How `f`'s output is rendered (text, gauge, list, even a code listing) is L2/L3.
- A reflective view (e.g. an IDE-style pane showing the component's own CCS definition) is a legitimate but *different* projection, carrying the process term itself. Keep runtime-state projections and source/reflective projections as distinct ports, or one "display" quietly does two jobs.

### Why Not Bigraphs (Yet)

It is tempting to want the formalism to express that a pane and certain ports *belong together and are arranged so*. That instinct points at bigraphs, which add to CCS an orthogonal **place graph** (nesting and locality) alongside the **link graph** (connectivity) that plain CCS already provides.

Resist crossing that line for now. The *belonging-together* of a pane and an agent's ports is already expressed in CCS — they are ports of the same process. The *spatial arrangement* is presentation, and has no business at L1 at all. Plain value-passing CCS plus view ports covers the present need; L2/L3 own layout.

Adoption criterion: reach for bigraphs only when locality or nesting becomes *semantically load-bearing and changes at runtime* — agents migrating between contexts, sessions nested within rooms, name scoping under reconfiguration. That is the setting they were built for. The multi-user variant of miolingo is the plausible point of arrival; the single-user trainer is not.

### Why Value-Passing CCS

- Interaction is its primary abstraction — which is what UIs fundamentally are.
- Component dependencies are explicit typed port synchronisations, never implicit shared state.
- User and system are symmetric processes — no privileged role for either.
- Guarding gives state-dependent port availability for free, which is precisely control enablement.
- Parallel composition expresses concurrency naturally without requiring it prematurely.
- Specifications are executable — simulation and verification are intrinsic, not bolted on.
- The formalism is framework-independent — the same spec maps to Qt, web, mobile, or any future target.

### The Three Levels

**L1 — Semantic Specification.** Value-passing CCS. Agents, hidden state, typed in/out ports, guarding. Framework-independent and human-governed. The sole authority. The port signature is the contract; the ready set is enablement; published projections are read-only views.

**L2 — Abstract Interaction Form.** The designer's choice of how each port is presented, in framework-independent vocabulary. A finite-choice input port may be realised as a dropdown, radio buttons, or a tabbed display — all semantically equivalent. L2 also chooses how a *non-ready* port shows (greyed-and-inert versus hidden-entirely): both are faithful renderings of the same absent-from-ready-set fact, so the guard structure constrains L2 without fully fixing it.

**L3 — Skin.** Framework-specific implementation and styling. L2 and L3 together constitute a skin — a separately deployable presentation artefact. Multiple skins may run against the same L1. Swapping skins does not touch L1.

### The Development Workflow

1. **Specify** — author CCS agents for each component: explicit ports, value types, guard structure.
2. **Simulate** — execute the spec on the RCA executor, and/or run CCS-derived test processes, to validate behaviour.
3. **Govern** — produce the architectural record: agent inventory, port map, sorts, interaction traces.
4. **Bind** — derive framework bindings from the declared port interfaces, including the afforded-ports operation each encoding must compute on the fly.
5. **Implement** — generate framework (skin) code, bounded by the binding contracts.
6. **Verify** — check generated code against spec behaviour: ready-set agreement at each reachable state, not syntax alone.

Steps 1–3 are human-governed. An agent may *assist* in drafting CCS, but the human reviews and owns the spec, and the spec — never old implementation code — remains the source of semantic truth. Steps 4–5 are agent-executed under human-authored constraints. Step 6 is shared.

### Relationship to the Wolfram/RCA Executor

The RCA project provides a complete, executable implementation of value-passing CCS. Its role is to *execute the spec* — which is how behaviour is validated. Running miolingo's CCS on RCA is therefore not a separate "Wolfram implementation"; it is the specification itself running, a semantic check.

A shipped product is a separate matter: an L3 skin (e.g. PyQt) realising the same port contract. Whether the product's core logic is reimplemented natively or delegated to a Wolfram engine via the WolframScript bridge at runtime is an open implementation decision the methodology does not force — the spec governs either way. (This replaces the earlier, conflicting claims that the spec both "compiles away with no Wolfram dependency" and would have "a first cut in Wolfram.")

### Agent Governance Principles

- Every agent session has a single bounded deliverable referenced to the spec.
- The architectural record is read-only to implementing agents — they realise it, never silently modify it.
- Any agent output touching multiple layers simultaneously is rejected.
- Agents produce verifiable artefacts — outputs checkable against spec behaviour.
- The spec is the escalation path — ambiguity resolves upward to the spec, never downward to implementation convenience.
- Old implementation code is never treated as a source of semantic truth.

### Key Hypotheses Requiring Validation

- **H1**: A port-signature contract makes framework-level dependencies explicit, removing the implicit-inference step where unconstrained agents fail.
- **H2**: A view port that emits on state-change *is* a Qt signal; Streamlit's whole-script rerun is a degenerate simulation of that push. The claim "Qt maps more faithfully than Streamlit" thus becomes concrete and falsifiable: Qt has a native construct for the view port and the ready set; Streamlit fakes both.
- **H3**: Constraining agents to render declared contracts (ports, ready sets, projections) produces more reliable, verifiable output than unconstrained agentic migration.
- **H4**: The current ready set is exactly the ready/refusal set of testing-and-failures semantics, so verifying a skin against the spec means checking ready-set agreement at each reachable state — testing equivalence, not trace inclusion alone. CCS-derived test processes can then replace GUI-level integration tests.

### Current Status

| Artefact | Status |
|---|---|
| Conceptual architecture (port-signature model) | Established |
| Wolfram/RCA CCS executor | Existing; WolframScript bridge PoC |
| miolingo worked example | Identified, not yet formally specified |
| Binding layer design (incl. ready-set lookahead) | Open problem |
| Agent governance documentation | Draft |
| Empirical validation | Not yet begun |

### Open Questions

- Right granularity for an agent definition — widget, component, or subsystem? (Preliminary answer: component-level, with port boundaries at semantically observable exchanges.)
- How is the afforded-ports obligation specified and verified — i.e. how do we check that an encoding reports exactly `init(P)` at every reachable state?
- How is the binding layer formally defined — is it itself a specification artefact?
- Where does single-choice constraint live: value typing (the port's type), port availability (guarding), or both? (Working view: both — a finite-choice input whose legal options vary with state is a guarded choice whose available summands change.)
- How are framework constructs with no clean CCS analogue handled?
- How clean can the L1/L2 boundary be kept across frameworks with implicit reactivity?
