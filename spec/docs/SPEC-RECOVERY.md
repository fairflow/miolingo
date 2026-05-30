# SPEC-RECOVERY.md
## UI-first CCS spec recovery — protocol and motivation

This document governs the reverse-engineering of an L1 CCS specification from the existing Streamlit implementation of miolingo. Read it alongside ARCHITECTURE.md (the layer model and component inventory) and CLAUDE.md (agent governance). Where this document and ARCHITECTURE.md disagree on the methodology, ARCHITECTURE.md is authoritative; this document records *why* the recovery proceeds as it does.

---

## 1. Motivation — the failed migration, and why the formal detour is the shortcut

The work began as a direct task: delegate the migration of miolingo from Streamlit to PyQt to an autonomous agent. The agent completed the task as literally requested and the result was unimpressive — not because the code was wrong function-by-function, but because the migration was **syntactic, not semantic**.

The agent read the Python, moved the functions, and rebuilt a UI. What it did not do was model the app's *runtime interaction behaviour*. In Streamlit, a large part of how the app actually works lives in `session_state` and the full-script rerun model: which widget change triggers which recomputation, which state variable silently couples one component to another. None of that is visible in a function signature. The agent treated anything that did not explicitly mention Streamlit as the "real" design, and quietly discarded the interaction layer — the connections between variables and components that were the whole point. The output looked plausible and lost exactly the dependencies that mattered.

The obvious next move would be to patch the broken Qt port, or to re-run the migration with a better prompt. Both are traps: a direct re-attempt hits the same failure mode, because the source still contains no framework-independent record of what the app *does*. The Streamlit code conflates behaviour with framework, and that conflation is the disease, not the symptom.

The counterintuitive resolution — and the thesis of this project — is that **the long detour through a formal specification is the fastest way to recover.** Rather than salvage the port, we start over with a formal framework:

- The thing that was lost (interaction topology) is precisely what CCS makes **explicit and primary** — ports and synchronisations *are* the wiring, not an afterthought to it.
- Once the behaviour is captured in CCS, a corrected Qt skin is a derivation, not a re-analysis — and so is any future skin (web, mobile, the multi-user game variant).
- The formal model is the framework-independent record whose absence caused the failure. Producing it once pays off across every subsequent target.

In short: the migration failed because there was no specification. The shortcut to a working Qt app is therefore to write the specification first — which is also the research contribution.

---

## 2. What this protocol produces

An L1 CCS specification recovered **UI-first** and **stubbed**:

- **UI-first** — the interaction structure (ports, control flow, choice points, sequencing) is specified before the functional internals. The interaction topology is what was lost, is framework-entangled, and is hard to recover, so it gets careful first attention.
- **Stubbed** — value-transformation functions are left as named placeholders with declared signatures and no bodies. The pure logic survived in the Python and is framework-independent, so it is recovered mechanically in a later pass and must not be invented now.

Work one component at a time, beginning with **Practice Session** (highest interaction complexity).

You are NOT migrating and NOT writing any Qt code in this protocol.

---

## 3. Pre-draft analysis (submit for sign-off before any CCS is written)

### (1) State inventory with read/write dependencies
List every `session_state` variable the component touches. For each: what writes it, what reads it, its type. Then classify each as:
- **Domain state** — semantically meaningful to the trainer (current item, score, queue position, history)
- **Framework bookkeeping** — exists only to satisfy Streamlit's rerun model (widget keys, init guards, rerun-trigger flags, values cached solely to survive reruns)

Only domain state becomes CCS process-local state. Framework bookkeeping is discarded, not modelled — encoding it would re-import the contamination we are removing. The ratio and character of what is discarded is research data (evidence for H2); record it, do not silently drop it.

### (2) Interaction triggers as candidate input ports
List every point where the user causes a state change. Filter by the **port boundary criterion**: a port exists only where crossing it produces a state change that is *semantically observable* by the user or another component. Keystrokes and field edits are not ports; `attempt_made`, `evaluation_complete`, `next_item_requested` are. For each retained trigger, record the system-side transition it causes on synchronisation.

### (3) Displays as candidate output ports
List every place the component shows state. Each becomes an *output-only* port carrying a projection — `view!(f state)` — never direct state exposure. Record the projection `f` each display implies. Distinguish runtime-state projections from any reflective/source views.

### (4) Afforded-port (ready-set) table per mode
For each distinct state or mode, list which ports are actually on offer. In the Streamlit source this is encoded as conditional rendering — the `if` guards around widgets. Recovering those conditionals *is* recovering the CCS guards. Control enablement is L1-derived, not a skin decision; this table must not be skipped.

### (5) Wiring diagram (plain text)
Show how retained state, input ports, output ports, and stubbed logic functions connect. This is the draft link graph — precursor to the parallel composition and restriction structure of the CCS term.

---

## 4. What "stubbed" means precisely

Write the process terms with their real prefixes, choices, and port actions. Where a transition computes an emitted value or tests a guard, **name the function but do not define it**: `evaluate(attempt, target)`, `nextItem(queue)`, `isComplete(session)` are placeholders with declared signatures and no bodies. The port structure is committed and reviewable now; the function bodies are recovered from the Python in a later pass and must not be invented at this stage.

---

## 5. Sign-off criteria (the review gate before any CCS is drafted)

- Domain state cleanly separated from framework bookkeeping, with the discard list shown
- Every retained trigger justified by the port boundary criterion
- Every display expressed as a projection, not raw state access
- Ready sets identified for each mode
- All logic functions appear only as named stubs, with nothing invented

---

## 6. Why the deferral is safe

Steps 1–5 are pure observation and classification — recoverable without executing anything. The stubbed CCS that follows is L1 structure. Only the later function-recovery pass needs the Python read in earnest, and because those functions are framework-independent pure logic, that pass is the safe, mechanical part. The risky part — the interaction topology — is handled first and under review.
