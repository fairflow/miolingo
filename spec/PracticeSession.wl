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
   When the list is empty the session is Finished; otherwise the head
   item is put on offer and the tail is carried forward.
   --------------------------------------------------------------------- *)
defineAgent["Practice", {items},
  if[Length[items] == 0,
     call["Finished"],
     call["Prompting", First[items], Rest[items]]]]


(* ---------------------------------------------------------------------
   Prompting[item, rest] — an item is on offer, awaiting the user's
   attempt. Only attempt_made is ready. The attempt value `a` is bound
   and scored against the current item; score[...] is a STUB pure
   function standing in for the real (e.g. IPA-distance) evaluation.
   --------------------------------------------------------------------- *)
defineAgent["Prompting", {item, rest},
  precede[coLabel["attempt_made", binding[a]],
    call["Evaluated", score[item, a], rest]]]


(* ---------------------------------------------------------------------
   Evaluated[ev, rest] — the attempt has been scored. Two ports ready:
     - evaluation!(ev)   : a VIEW PORT. Publishes the score projection
                           and loops back to the same state, so it may
                           be read repeatedly without advancing.
     - next_item_requested : advances; re-enters Practice on the tail.
   --------------------------------------------------------------------- *)
defineAgent["Evaluated", {ev, rest},
  choice[
    precede[label["evaluation", param[ev]], call["Evaluated", ev, rest]],
    precede[coLabel["next_item_requested"], call["Practice", rest]]]]


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

   F1. defineAgent evaluates the body at STORE time, with parameters
       still symbolic. Length[symbolicItems] -> 0, so a guard written
       Length[items] == 0 freezes to True and never resolves after
       substitution. Worked around here with `items == {}` (inert
       against a symbol). A robust fix would have defineAgent hold the
       body unevaluated until params are substituted.

   F2. The CCS `if` symbol is eager in its branches: if[g, p, q]
       evaluates BOTH p and q before transNamed's real If selects one.
       Harmless to routing (the dead branch only errors and freezes),
       but it emits First::nofirst / Rest::norest noise on e.g.
       Practice[{}]. A HoldRest (or HoldAll) attribute on `if` would
       make the conditional lazy and silence this.

   Both fixes belong in the executor (RCA_core.wl, the other project),
   so they are reported here rather than applied. VERIFIED: the ready
   sets above were produced by transNamed on the live engine.
   ===================================================================== *)
