# Session Notes — SGSE / miolingo

**Purpose of this file.** This is a handoff record from a web-chat session, written so that Claude Code (or Cowork) can pick up the work with full context. Read this first, then `docs/METHODOLOGY.md`, `docs/ARCHITECTURE.md`, and `CLAUDE.md`. Where this file and those documents disagree, those documents are authoritative for the methodology; this file records *why* they say what they say and what is still open.

---

## 1. One-paragraph orientation

The project is a research methodology called **Specification-Governed Software Engineering (SGSE)** and a worked example, **miolingo** (a pronunciation-training app being migrated Streamlit → PyQt). The thesis: specify a system as a network of agents, each visible *only* through named, typed **ports**; the set of ports and their value types is the entire contract ("the port signature"). LLM agents are then constrained to *implement/render a declared contract* rather than infer hidden dependencies — which is the thing they do badly. The specification language is **value-passing CCS (VP-CCS)**, executed on an existing Wolfram/Mathematica engine (referred to as RCA). This is a solo research project; the realistic near-term output is a **well-argued LinkedIn/X post**, not a widely adopted methodology.

---

## 2. The refined conceptual model (the core of this session)

The uploaded docs (drafted earlier with Sonnet) were "a bit off beam." The corrected model:

**Agents and ports (L1).**
- An agent has hidden internal state, visible to the outside *only* through named, typed in/out ports. No other channel exists.
- Output port: on synchronisation, delivers a value that is a **function of current state**; the output may itself change state, as the agent's own definition dictates.
- Input port: on synchronisation, receives a value and incorporates it (directly or via a derived state change).
- The partner across a port may be another core agent **or** an external client (UI, test harness, user). User and system are **symmetric** processes; neither is privileged.
- The **port signature is the entire UX contract.** Framework-independence follows from this single commitment, not as a separate assertion. This should be the *lead* principle; the "migration-failure" story is a corollary, not the thesis.

**The three levels.**
- **L1** — VP-CCS. Agents, hidden state, typed ports, guarding. Human-governed, sole authority.
- **L2** — Abstract interaction form: how each port is *presented*, in framework-independent vocabulary (a finite-choice input port → dropdown / radio / tabs; a state projection → pane / gauge / list). L2 also chooses how a *non-ready* port shows (greyed-inert vs hidden).
- **L3** — Skin: framework-specific implementation + styling (PyQt). L2+L3 = a swappable skin. Multiple skins can run against one L1.

**Sort vs ready set (important).**
- The **sort** = the agent's full port alphabet (every port it can ever use) = the static interface L2/L3 must be able to render.
- The **ready set** = the subset of ports actually on offer *in the current state*, fixed by **guarding** (prefix/choice) in the operational semantics.
- Consequence: **control enablement is L1-derived, not an L2/L3 invention.** The skin *renders* the ready set; it does not decide it. This kills the bug class of ad-hoc `setEnabled(...)` logic drifting out of sync with the model.

**The afforded-ports obligation (a correction made late in the session).**
- The ready set **cannot be precomputed in general** — with data-dependent guards it depends entirely on live state. Only the degenerate finite-control / no-data-guard case is tabulable, and that must not be relied on architecturally.
- It must be computed **on the fly**. The rendering engine cannot do this from outside (it doesn't hold the state; reaching in would breach encapsulation), so it must **ask the component**, and the component's encoding (Wolfram for validation; Python/Qt for product) must compute its currently afforded ports from its own state by evaluating its guards.
- Therefore an **afforded-ports operation is a mandatory part of every faithful encoding's contract**, not an optional projection. It is the single point where pure CCS (which offers only the blocking rendezvous) must be extended with a non-blocking introspection.
- Conformance test: an encoding is faithful iff its reported afforded ports equal `init(P)` at every reachable state.
- Still open: whether the afforded-ports operation is **push** (component emits its new ready set on each state change — maps to a Qt signal) or **pull** (engine queries after each interaction). Push fits signal/slot and the framework-compatibility argument better; pull is simpler to specify. Decide when formalising the binding layer.

**Read-only views are output ports.**
- A state display must not expose state directly (that breaks encapsulation). It is an **output-only port carrying a projection** the agent chooses to publish: `view!(f state)`. "Read-only" = output-only port, no complementary input to write back. So a display is an *instance* of "data crosses only at ports," not an exception.
- The projection `f` (what an agent publishes about itself) is L1; how it's rendered is L2/L3.
- A reflective view (an IDE-style pane showing the agent's own CCS definition) is a **different** projection carrying the process term itself. Keep runtime-state projections and source/reflective projections as distinct ports.

**Bigraphs deferred (with a criterion).**
- Plain CCS gives a **link graph** (connectivity). Bigraphs add an orthogonal **place graph** (nesting/locality). The temptation toward bigraphs comes from wanting to say a pane and certain ports "belong together and are arranged so" — but the belonging-together is already in CCS (same process), and the spatial arrangement is L2/L3, not L1.
- Adopt bigraphs only when locality/nesting becomes **semantically load-bearing and changes at runtime** (agents migrating between contexts; sessions nested in rooms; scoping under reconfiguration). The plausible arrival point is the **multi-user game variant**; the single-user trainer is not there. Same line in the formalism as session-type *delegation* and π-calculus *scope extrusion*.

**Component inventory correction.** The read-only "displays" (Stats Display, History Browser) are most likely **view ports on** the stateful agents (PracticeSession / VocabStore), not standalone L1 agents. Promote one to a standalone agent only if it genuinely owns state. Decide per component.

**Wolfram/RCA framing (corrected).** The earlier docs conflated "spec compiles away, no Wolfram in shipped app" with "first cut in Wolfram." Resolution: running the CCS spec on the RCA executor **is the spec executing** = semantic validation (not a separate implementation). A PyQt build is a separate L3 product against the same L1. Whether the shipped core logic is reimplemented natively or bridged to Wolfram at runtime is an **open decision**; the spec governs either way.

---

## 3. Strategic decisions

- **Stay with VP-CCS on Wolfram.** Reasons accepted: (a) a full working VP-CCS implementation already exists in the Wolfram ecosystem; (b) deep CCS fluency (weighted highest — building on a formalism you understand beats a "better" one you'd fumble; CCS is the conceptual root the fancier systems extend); (c) existing subscription = a live capability (justify by capability, not by sunk cost); (d) established, demonstrated workflow with Claude on VP-CCS.
- **Calibration:** (d) shows the approach is *tractable to develop with an assistant*; it does **not** yet demonstrate H1–H4 (the reliability/migration claims). Keep that distinction sharp so the post/paper doesn't overclaim.
- **Decouple the validation vehicle from the methodology claim.** Use VP-CCS-on-Wolfram as the validation *instrument*, but pitch the contribution **above any single calculus** (it could later be a session type or an mCRL2 model). This protects the sunk investment and keeps the idea portable.
- **Goal = a researched post**, not adoption. What makes methods "win in the large": riding an incumbent rather than replacing it; local/incremental payoff; the *checker* being the asset (sound, fast, actionable feedback); one graspable core idea; a killer worked example + a wave to ride. The current wave to ride is **LLM-agent reliability**.
- **Contrast lines usable in a post:**
  - "mCRL2 would give me an industrial-grade engine, but I already have an executable VP-CCS in Wolfram and the conceptual gain is near zero — same paradigm, new toolchain."
  - "My port-contract is close to a session type, but session types check *code* rather than providing a runnable behavioural model, which is exactly what I need for validation — so I specify in CCS and verify by execution."
- **Statecharts are explicitly out of scope** — they model one component's state space, not composition/interaction; not the user's interest.

---

## 4. Prior-art map (what's covered vs open)

Distinct literatures, with the honest verdict:

- **Statecharts & hybrids.** Statecharts won industrially (Stateflow/Simulink, UML, SCXML, XState) but model single-component state, not interaction. The closest *hybrid* is **ASTDs** (Algebraic State Transition Diagrams): statecharts + CSP/EB3 process-algebra operators, for information systems; still active (TASTD real-time extension, 2023). Cite ASTDs as the acknowledged prior attempt at the statechart/process-algebra marriage; explain why ports+ready-sets differ.
- **Where process calculi landed "in the large."** Not as building languages (Milner himself regarded CCS as theory; early process algebras lacked data types). They won as (1) **verification toolsets** — mCRL2 (ACP + data + time, actively maintained, 2025 release), CADP (LOTOS), FDR (CSP) — used in real industrial verification; and (2) **session / behavioural types**, the thriving PL descendant of the π-calculus (implemented in Scala, Rust, OCaml, Erlang, Links; multiparty session types).
- **Specification-based testing = ioco (BIGGEST COLLISION).** H4 is essentially Tretmans' **ioco**: an input-output conformance relation over LTS, rooted in testing equivalences and **refusal testing** (= the ready/refusal-set machinery), with the conformance condition that the implementation's out-set after each suspension trace is a subset of the spec's; on-the-fly test generation; a compositional version exists. **Frame H4 as instantiating ioco-style conformance for LLM-generated UI skins against a CCS spec — not as a new relation**, or a reviewer rejects on Tretmans alone.
- **LLMs + formal spec (the newest, strongest ground).** The 2024–25 wave (AlphaVerus; AutoVerus/SAFE++; Astrogator; benchmarks CLEVER/VERINA/FVAPPS) is almost all *functional correctness via deductive proof* (Dafny/Verus/Lean) on small self-contained programs. Largely untouched: **behavioural/interaction specs, UI, and migration/refactoring of multi-component apps** — which is the SGSE niche. The refactoring angle is relatively open.
- **RLVR parallel (apt, current).** "RLVF" = RLVR (RL with Verifiable Rewards), the paradigm behind DeepSeek-R1, Tülu 3, o-series; rule-based verifiable rewards, mostly math/code where outcomes are checkable. Frontier: formal verification as the reward instead of flaky unit tests (PSV: Propose-Solve-Verify; AlphaVerus self-improvement). **SGSE is the inference/build-time analogue of RLVR's training-time verifier**, applied to interactive behaviour where unit tests are weak and a CCS/ioco conformance check is strong.

**Positioning that emerges:** formal lineage = ioco (relation) + session/behavioural types (the contract) + ASTD (the statechart hybrid SGSE improves on); novelty sits at the LLM frontier AlphaVerus/PSV define, but they do *functional* correctness on kernels, leaving *behavioural* conformance for interactive systems + migration/refactoring open. For the post: lead with the LLM-verifier/RLVR frontier (where the contribution is), fold in ioco/session-types/ASTD as the formal foundations.

---

## 5. State of the governance docs

`docs/METHODOLOGY.md`, `docs/ARCHITECTURE.md`, `CLAUDE.md`, `docs/PAPER-ABSTRACT.md` were rewritten this session to reflect §2, then patched for the afforded-ports correction (§2). They are current. `CLAUDE.md` governs an *implementing agent in a single session*; it still needs a short whole-repo paragraph for Claude Code (what it may do across `spec/`, `wolfram/`, `skins/`; that `skins/streamlit-legacy/` is reference data, not semantic truth; which validation commands it may run unprompted).

---

## 6. Open questions / next steps

1. Push vs pull for the afforded-ports operation (see §2).
2. Formal definition of the binding-layer protocol, incl. how to verify an encoding reports exactly `init(P)` at each reachable state.
3. Whether single-choice constraint is value typing, port availability (guarding), or both (working answer: both — a finite-choice input whose legal options vary with state is a guarded choice whose summands change).
4. Author the **Practice Session** CCS spec first (highest interaction complexity); no skin code until that spec exists and is reviewed.
5. Draft the related-work section / the post, using §4's positioning.
6. Add the whole-repo paragraph to `CLAUDE.md` (§5).

---

## 7. Repo layout & how Code should operate

```
miolingo/
  spec/                  # L1: CCS specs (.ccs / .nb)
  wolfram/               # RCA executor, WolframScript bridges  (may be a separate repo; use --add-dir)
  skins/
    pyqt/                # L3: new PyQt skin
    streamlit-legacy/    # old Streamlit — migration reference ONLY, not semantic truth
  docs/                  # METHODOLOGY.md, ARCHITECTURE.md, PAPER-ABSTRACT.md, session-notes.md
  CLAUDE.md              # project-context file at root
  .claude/               # commit-able Claude Code config
```

- Launch from the miolingo root: `claude`. Add the RCA repo if separate: `claude --add-dir /path/to/RCA`.
- Treat `spec/` as authority. Never infer dependencies from `skins/streamlit-legacy/`; use it only as reference for *what behaviour existed*, recovered into CCS at L1.
- Use web search / research tools for the literature in §4; the canonical references are in §8.

---

## 8. References

- Milner, R. *Communication and Concurrency.* Prentice Hall, 1989. (CCS.)
- Tretmans, J. "Test Generation with Inputs, Outputs and Repetitive Quiescence." *Software—Concepts and Tools* 17(3):103–120, 1996. **(Origin of ioco — cite as primary.)**
- Tretmans, J. "Testing Concurrent Systems: A Formal Approach." CONCUR'99, LNCS 1664:46–65, 1999.
- Tretmans, J. "Model Based Testing with Labelled Transition Systems." In *Formal Methods and Testing*, LNCS 4949:1–38, 2008. **(Comprehensive tutorial-reference for ioco.)**
- Frappier, M., Gervais, F., Laleau, R., Fraikin, B., St-Denis, R. "Extending statecharts with process algebra operators." *Innovations in Systems and Software Engineering* 4(3):285–292, 2008. (ASTDs.)
- Honda, K. "Types for Dyadic Interaction." CONCUR'93. (Origin of session types.)
- Honda, K., Vasconcelos, V., Kubo, M. "Language primitives and type discipline for structured communication-based programming." ESOP'98.
- Honda, K., Yoshida, N., Carbone, M. "Multiparty Asynchronous Session Types." POPL'08.
- Caires, L., Pfenning, F. "Session Types as Intuitionistic Linear Propositions." CONCUR'10. (Propositions-as-sessions.)
- Groote, J.F., Mousavi, M.R. *Modeling and Analysis of Communicating Systems.* MIT Press, 2014. (mCRL2; tool at https://www.mcrl2.org/.)
- Aggarwal, P., Parno, B., Welleck, S. "AlphaVerus: Bootstrapping Formally Verified Code Generation through Self-Improving Translation and Treefinement." ICML 2025.
- Wilf, A., Aggarwal, P., Parno, B., Fried, D., et al. "Propose, Solve, Verify: Self-Play Through Formal Verification." arXiv:2512.18160, Dec 2025.
