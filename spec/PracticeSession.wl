(* ::Package:: *)

(* =====================================================================
   miolingo / L1 specification — Practice Session
   ---------------------------------------------------------------------
   STATUS: STRAWMAN. Drafted by Claude to get the spec off the ground.
   The human architect OWNS this; every equation below is a proposal to
   be reviewed, corrected, or thrown away. It is not yet authoritative.

   This is an *equational* spec: each agent is a named equation via
   defineAgent (the "agent equation registry" in RCA_core.wl), with
   recursion through call[...]. It is NOT a single mu-term.

   LOAD DEPENDENCY: load RCA_core.wl first (provides defineAgent,
   agentDefs, transNamed, and the combinators precede, choice, par,
   restrict, call, label, coLabel, param, binding, if, nil, ...), THEN
   discipline.wl (provides the view!/afforded! discipline helpers:
   portsOf, portName, affordedNames). RCA_core.wl lives in the RCA
   project; run the executor with that directory available.
   =====================================================================

   CONVENTIONS (mirroring the ABP example in RCA_core.wl)
   ---------------------------------------------------------------------
   - label[name, ...] and coLabel[name, ...] are complementary actions
     that synchronise across a port.
   - INPUT port  (partner -> agent):  coLabel[name, binding[x]]   binds x
                 pure handshake:       coLabel[name]
   - OUTPUT port (agent -> partner):  label[name, param[v]]       sends v
                 pure handshake:       label[name]
   - VIEW PORT (read-only projection): an OUTPUT action carrying a
     projection of state, that loops back to the SAME state (no state
     change). The partner may read it; it cannot write back.
   - CHOICE IS BINARY: transNamed[choice[p_, q_]] takes exactly two
     summands. For 3+ offered actions, NEST: choice[a, choice[b, c]].
     A flat choice[a, b, c] matches no rule and silently mis-steps.

   MODELLING DISCIPLINE — every agent carries two standing ports
   ---------------------------------------------------------------------
   On top of its domain ports, EVERY agent (in every observable state)
   offers two output-only ports, always in the ready set:

     view!      a projection f(state) of the agent's current state — the
                read-only view. State-dependent: it shows whatever is
                relevant now. A "display" lives here without breaking
                encapsulation (data crosses only at ports).

     afforded!  the agent's OWN ready set — the list of ports it currently
                affords (its init(P)). This makes the methodology's
                "afforded-ports operation" a first-class declared port:
                the skin synchronises on afforded! to learn what to
                enable, rather than reaching into the agent. Its value is
                portsOf[self] — a deferred thunk realised on query.

   Both are self-loops (reading them never advances the protocol), so both
   sit in every state's ready set beside the domain ports.

   PORT SIGNATURE (the sort of the Practice Session agent)
   ---------------------------------------------------------------------
       attempt_made          in    user submits a pronunciation attempt
       next_item_requested   in    user asks to advance to the next item
       view!                 out   state projection (the discipline view)
       afforded!             out   the current ready set (the discipline)

   There is NO separate `evaluation` port and NO separate `prompt` port:
   each is just what view! projects in a given state — the evaluation
   while Evaluated, the current item while Prompting (see OPEN Q1/Q4).

   READY SETS (enablement is derived here, not invented in the skin).
   For any state p:  afforded ports of p  ==  First /@ transNamed[p].
       Prompting[items]    ready = { view, afforded, attempt_made }
       Evaluated[ev,items] ready = { view, afforded, next_item_requested }
       Finished            ready = { view, afforded }   (no domain port)
   ===================================================================== *)


(* The view!/afforded! discipline helpers (portsOf, portName,
   affordedNames) now live in discipline.wl — load it before this file. *)


(* ---------------------------------------------------------------------
   Practice[items] — drive a session over a list of practice items.
   When the list is empty the session is Finished; otherwise the whole
   (now guaranteed non-empty) list is handed to Prompting.

   IDIOM (see FINDING F2): the `if` branches are inert call[...]
   continuations — no partial op (First/Rest) appears in a branch.
   `if` is eager, so a First[{}] sitting in the dead branch would error
   on the empty case; keeping branches inert defers all destructuring to
   agents reached only when the precondition (non-empty) holds. This is
   exactly the discipline ABP follows.
   --------------------------------------------------------------------- *)
defineAgent["Practice", {items},
  if[Length[items] == 0,
     call["Finished"],
     call["Prompting", items]]]


(* ---------------------------------------------------------------------
   Prompting[items] — an item is on offer, awaiting the user's attempt.
   Carries the whole non-empty list; the head First[items] is the current
   item. The attempt value `a` is bound and scored against it; score[...]
   is a STUB pure function for the real (e.g. IPA-distance) evaluation.
   First[items] sits in precede-successors, reached only with a non-empty
   list, so it never errors (see FINDING F2).
   Discipline ports: view! projects the current item — THE PROMPT that was
   "missing" — and afforded! exports this state's ready set.
   --------------------------------------------------------------------- *)
defineAgent["Prompting", {items},
  choice[
    precede[label["view", param[First[items]]],
      call["Prompting", items]],
    choice[
      precede[label["afforded", param[portsOf[call["Prompting", items]]]],
        call["Prompting", items]],
      precede[coLabel["attempt_made", binding[a]],
        call["Evaluated", score[First[items], a], items]]]]]


(* ---------------------------------------------------------------------
   Evaluated[ev, items] — the attempt has been scored.
     - view!(ev)           : projects the evaluation — this IS the former
                             `evaluation` port, now just the view in this
                             state; re-readable (self-loop).
     - afforded!           : exports this state's ready set.
     - next_item_requested : advances; re-enters Practice on Rest[items]
                             (the head is dropped here, in a successor).
   --------------------------------------------------------------------- *)
defineAgent["Evaluated", {ev, items},
  choice[
    precede[label["view", param[ev]],
      call["Evaluated", ev, items]],
    choice[
      precede[label["afforded", param[portsOf[call["Evaluated", ev, items]]]],
        call["Evaluated", ev, items]],
      precede[coLabel["next_item_requested"],
        call["Practice", Rest[items]]]]]]


(* ---------------------------------------------------------------------
   Finished — no items remain. NOT a deadlock: per the discipline it
   still offers view! (a session-complete projection) and afforded!. Its
   domain ready set is empty, which is exactly how completion shows — the
   skin sees only {view, afforded} and renders "session over".
   --------------------------------------------------------------------- *)
defineAgent["Finished", {},
  choice[
    precede[label["view", param[sessionComplete]],
      call["Finished"]],
    precede[label["afforded", param[portsOf[call["Finished"]]]],
      call["Finished"]]]]


(* =====================================================================
   EXAMPLE (commented — run inside the executor, not on load)
   ---------------------------------------------------------------------
     session0 = call["Practice", {item1, item2}];
     transNamed[session0]              (* immediate {action, successor}s *)
     First /@ transNamed[session0]     (* the ready set / afforded ports *)
   ===================================================================== *)


(* =====================================================================
   OPEN QUESTIONS / FLAGGED ASSUMPTIONS (for the architect)
   ---------------------------------------------------------------------
   1. [SETTLED] MISSING PROMPT PORT. Resolved by the modelling discipline:
      the prompt is not a separate port, it is what view! projects in the
      Prompting state (the current item). Likewise `evaluation` is just
      view! in the Evaluated state. One state-dependent view! per agent,
      always afforded, replaces both bespoke projections.

   2. SCORING. score[item, a] is a placeholder. The real evaluation
      (what an "attempt" value is, how it is compared to the target,
      what `evaluation` carries — scalar? structured?) is unspecified.

   3. ITEM SOURCE. Items are baked in as a literal list parameter so the
      agent is standalone and executable. In a fuller spec they would
      arrive across a port from VocabStore; this couples nothing yet.

   4. VIEW-PORT SEMANTICS. view! is modelled as repeatedly readable (self-
      loop), in every state. Is re-reading always meaningful, or should
      some projections be one-shot? The self-loop is what keeps view! in
      the ready set over time. (The richer question — should view! project
      a structured record, e.g. {item, score}, rather than a single value
      — is open; f[state] can return whatever the designer wants.)

   5. [PARTLY SETTLED] END OF SESSION. Finished is no longer a deadlock:
      it offers view!(sessionComplete) + afforded!, with an empty domain
      ready set. Still open: should it also offer a `restart` domain port,
      and what should the completion projection actually carry (score
      summary, item count)?

   6. NO ABANDON. There is no mid-session quit/abandon port. Likely a
      real port; deliberately omitted from this first cut.
   =====================================================================

   EXECUTOR FINDINGS (research data — about RCA_core.wl, not this spec)
   ---------------------------------------------------------------------
   Surfaced by being the first equation-based agent to do real data
   computation on its parameters; the ABP example never exercised this.

   F1. [RESOLVED in executor] defineAgent evaluated the body at STORE
       time, with parameters still symbolic. Length[symbolicItems] -> 0,
       so a guard written Length[items] == 0 froze to True and never
       resolved after substitution; First/Rest on the symbol also errored
       at load. FIX: defineAgent now stores "body" -> Hold[body]; readers
       substitute concrete params into the held body and ReleaseHold only
       then (transNamed, transSymbolic, buildAgent, buildSystemRec).
       VERIFIED: the natural guard Length[items] == 0 now routes correctly
       and the load-time noise is gone; the ABP example is byte-identical
       before/after the fix.

   F2. [ANALYSED — do NOT fix in executor] The CCS `if` symbol is eager
       in its branches: if[g, p, q] evaluates BOTH p and q before
       transNamed's real If selects one. This emits First::nofirst /
       Rest::norest noise on e.g. Practice[{}] (routing stays correct).
       BUT the eager evaluation is LOAD-BEARING: it normalises in-branch
       value expressions into canonical form. Evidence from the ABP
       baseline: SendingN[0] yields successor call[AcceptN, 1], i.e.
       negate[0] was eagerly reduced to 1. A Hold attribute on `if` would
       leave call[AcceptN, negate[0]] unreduced, so the weak-bisimulation
       game (which compares states by structural === ) would see the same
       semantic state under two syntactic forms — state blow-up and very
       likely a broken abpN ~w BuffN result.
       RECOMMENDATION: leave `if` alone. Follow the ABP idiom instead —
       `if` branches are inert call[...] continuations; never place a
       partial op (First/Rest) directly in a branch. Destructure inside a
       sub-agent reached only by the non-empty branch, or carry the whole
       list as a parameter. If a lazy data-guard is ever wanted as L1
       vocabulary, add a NEW combinator (e.g. ifL, HoldRest) used only by
       data-destructuring agents, leaving `if` untouched.
       STATUS: idiom APPLIED above and VERIFIED on the engine — Practice's
       branch is the inert call["Prompting", items]; First/Rest moved into
       Prompting/Evaluated successors, reached only with a non-empty list.
       Confirmed: no First/Rest messages on any state (incl. Practice[{}]),
       live-state ready sets unchanged, and a full session walk cycles
       Practice -> Evaluated -> ... -> Practice[{}] correctly.
       NB: the spec depends on the F1 fix, now merged into feature-work
       via PR #31, so RCA_core.wl loads from the normal checkout.
   ===================================================================== *)
