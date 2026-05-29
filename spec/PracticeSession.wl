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

   LOAD DEPENDENCY: requires RCA_core.wl to be loaded first, which
   provides defineAgent, agentDefs, transNamed, and the combinators
   (precede, choice, par, restrict, call, label, coLabel, param,
   binding, if, nil, ...).  RCA_core.wl lives in the RCA project; run
   the executor with that directory available.
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

   PORT SIGNATURE (the sort of the Practice Session family)
   ---------------------------------------------------------------------
       attempt_made          in    user submits a pronunciation attempt
       evaluation            out   view port: projection of the score
       next_item_requested   in    user asks to advance to the next item

   READY SETS (the point of the whole exercise — enablement is derived
   here, not invented in the skin). For any state p:
       afforded ports of p  ==  First /@ transNamed[p]
   so the executor already gives us the "afforded-ports operation" the
   methodology docs flag as an open problem / mandatory introspection.

       Prompting[item,rest]  ready = { attempt_made }
       Evaluated[ev,rest]    ready = { evaluation, next_item_requested }
       Finished              ready = { }            (quiescent)
   ===================================================================== *)


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
   Only attempt_made is ready. Carries the whole non-empty list; the
   head First[items] is the current item. The attempt value `a` is bound
   and scored against it; score[...] is a STUB pure function standing in
   for the real (e.g. IPA-distance) evaluation. First[items] sits in a
   precede-successor, reached only with a non-empty list, so it never
   errors (see FINDING F2).
   --------------------------------------------------------------------- *)
defineAgent["Prompting", {items},
  precede[coLabel["attempt_made", binding[a]],
    call["Evaluated", score[First[items], a], items]]]


(* ---------------------------------------------------------------------
   Evaluated[ev, items] — the attempt has been scored. Two ports ready:
     - evaluation!(ev)   : a VIEW PORT. Publishes the score projection
                           and loops back to the same state, so it may
                           be read repeatedly without advancing.
     - next_item_requested : advances; re-enters Practice on Rest[items]
                             (the head is dropped here, in a successor).
   --------------------------------------------------------------------- *)
defineAgent["Evaluated", {ev, items},
  choice[
    precede[label["evaluation", param[ev]], call["Evaluated", ev, items]],
    precede[coLabel["next_item_requested"], call["Practice", Rest[items]]]]]


(* ---------------------------------------------------------------------
   Finished — no items remain. Quiescent (nil). See OPEN QUESTION 5:
   should this terminate, loop, or offer a restart port instead?
   --------------------------------------------------------------------- *)
defineAgent["Finished", {}, nil]


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
   1. MISSING PROMPT PORT. The user must see the item to attempt it, but
      ARCHITECTURE.md lists only the three ports above. Is there an
      undeclared `current_item!` view port on this agent, or is the
      prompt a projection of VocabStore shown alongside? Decide where it
      lives — it is currently absent from the sort.

   2. SCORING. score[item, a] is a placeholder. The real evaluation
      (what an "attempt" value is, how it is compared to the target,
      what `evaluation` carries — scalar? structured?) is unspecified.

   3. ITEM SOURCE. Items are baked in as a literal list parameter so the
      agent is standalone and executable. In a fuller spec they would
      arrive across a port from VocabStore; this couples nothing yet.

   4. VIEW-PORT SEMANTICS. evaluation is modelled as repeatedly readable
      (loops to same state). Is re-reading meaningful, or is it one-shot?
      This choice is exactly what determines its membership in the ready
      set over time.

   5. END OF SESSION. Finished = nil (deadlock). Should a session loop,
      offer a restart, or report a summary projection before ending?

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
       NB: verification must load RCA_core.wl from the F1 worktree
       (claude/defineagent-hold-body, PR #31), not feature-work, until
       that PR merges — the spec depends on the F1 fix.
   ===================================================================== *)
