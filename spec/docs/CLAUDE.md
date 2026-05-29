# Claude — Read This First

This project implements a research methodology called Specification-Governed Software Engineering (SGSE). Read `ARCHITECTURE.md` before doing anything else; the methodology is in `METHODOLOGY.md`.

## The One Idea You Must Hold Onto

Every component is an agent with hidden state, visible *only* through named, typed ports. The set of ports and their value types is the entire contract. You never see or touch state except through a port. If you ever find yourself reasoning about a component's internals by any route other than its ports, stop — you have left the model.

## Your Role

You implement and render declared contracts at L3 (skin). You may also *assist* in drafting L1 CCS specs, but only as a drafting aid: the human architect reviews, owns, and signs off every spec. You never treat old implementation code as the source of semantic truth, and you never silently infer a dependency that isn't a declared port.

## The Most Important Rule

If you find yourself reading existing (e.g. Streamlit) code to work out how components interact — stop. That analysis belongs at L1, expressed as ports. Ask for the relevant CCS spec. If it doesn't exist yet, say so and halt. Do not proceed by inferring dependencies from code.

## What a Valid Implementation Session Looks Like

You will be given:

1. A specific component from the Component Inventory in `ARCHITECTURE.md`.
2. Its CCS agent definition (L1): ports, value types, guard structure.
3. Its declared interaction form (L2).
4. A single deliverable: a widget binding, a WolframScript bridge stub, or a test harness.

You produce that and nothing else.

## How to Render the Contract

- **Ports → widgets.** Each input port becomes a control of the L2-declared form; each output port becomes a rendering of the value it carries.
- **Ready set → enablement.** A control is live iff its port is in the current ready set. The ready set is computed on the fly by the live component from its current state — it cannot be precomputed. Query the component's afforded-ports operation on each state change and render the result; never tabulate enablement yourself or invent your own enable/disable logic.
- **Read-only views → output ports.** A state display is an output-only port carrying a published projection `view!(f state)`. Render the projection; never reach for raw state. Keep runtime-state views and any reflective (code-showing) views as separate ports.
- **Non-ready ports.** L2 says whether a non-ready port is greyed or hidden. Follow it; don't choose for yourself.

## Red Flags — Stop and Ask Before Proceeding

- You are about to modify any file under `/spec/` without explicit human sign-off.
- Your output touches more than one architectural layer.
- You cannot find an L2 interaction form for a port in scope.
- You are resolving an ambiguity by consulting old Streamlit code.
- You are inventing control enablement rather than rendering a ready set.
- You are about to expose state other than through a declared projection port.
- Your session brief references both Wolfram and Qt simultaneously.

## Stack Reference

| Layer | Technology |
|---|---|
| Spec language | Value-passing CCS |
| Spec executor / validation | Wolfram/RCA (at `/spec/wolfram/`) |
| Wolfram bridge | WolframScript + `wolframclient` (at `/spec/wolfram/`) |
| UI framework | PyQt6 |
| Qt connection type | Direct signal/slot (single-threaded) |
| Test approach | CCS process traces and ready-set agreement, not GUI automation |

## Interaction Form Vocabulary (L2)

Your L2 brief specifies, per port, one of:

- finite-choice input — tabs / radio / dropdown
- sequential input — wizard / paged flow
- free-form input — text field / IPA input
- confirmation input — dialog / inline confirm
- scalar projection — bar / score
- collection projection — list / table
- non-ready rendering — greyed / hidden

Do not deviate from the declared form without architectural review.

## Current Priority

Practice Session — highest interaction complexity, most critical to get right at L1 first. Do not implement any Practice Session skin code until its CCS spec exists and has been reviewed.

## This Project Is Also a Research Artefact

Implementation decisions may be documented as findings. If the framework makes clean separation difficult — e.g. you cannot render the ready set without a blocking sync, or a port has no clean Qt analogue — flag it explicitly rather than working around it silently. These boundary cases are research data.
