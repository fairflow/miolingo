(* ::Package:: *)

(* =====================================================================
   miolingo / L1 specification — VocabStore  (CRUD-with-IPA store)
   ---------------------------------------------------------------------
   STATUS: STRAWMAN. The human architect OWNS this. Second worked example,
   written to exercise the modelling discipline a second time and — the
   point here — to show STATE-DEPENDENT ENABLEMENT: remove/update are
   afforded only when the store is non-empty. Enablement is derived from
   the guard at L1, rendered (never decided) by the skin.

   Equational (defineAgent). LOAD ORDER: RCA_core.wl, then discipline.wl,
   then this file. discipline.wl provides view!/afforded! helpers
   (portsOf, portName, affordedNames) and the conventions.

   PORT SIGNATURE (the sort)
   ---------------------------------------------------------------------
       add        in    add an entry            (free-form input)
       remove     in    remove the entry keyed k (gated: non-empty)
       update     in    update the entry keyed k (gated: non-empty)
       view!      out    the collection projection (the entries)
       afforded!  out    the current ready set (the discipline port)

   READY SETS (the headline — guarding gives enablement for free):
       VocabStore[{}]        ready = { add, view, afforded }
       VocabStore[non-empty] ready = { add, view, afforded, remove, update }

   The R of CRUD is the view! port (a collection projection); there is no
   separate "read/list" port — reading is the published projection.
   ===================================================================== *)


(* ---------------------------------------------------------------------
   VocabStore[entries] — entries is a list of vocab entries (each an
   opaque {word, ipa}-shaped value; their structure is not fixed at L1).
   Always offers add + the two discipline ports; the conditional summand
   admits remove/update only when the store is non-empty.

   IDIOM (FINDING F2): the if branches are inert continuations — nil when
   empty, call["VocabMutate", entries] when not. The partial/keyed
   operations live in VocabMutate's successors, reached only non-empty.
   add uses Append (a list-producing op that PRESERVES the bound entry e
   as a list element, so it is recoverable under value-passing and keeps
   Length working for the guard).
   --------------------------------------------------------------------- *)
defineAgent["VocabStore", {entries},
  choice[
    precede[coLabel["add", binding[e]],
      call["VocabStore", Append[entries, e]]],
    choice[
      precede[label["view", param[entries]],
        call["VocabStore", entries]],
      choice[
        precede[label["afforded", param[portsOf[call["VocabStore", entries]]]],
          call["VocabStore", entries]],
        (* state-dependent: remove/update only when non-empty *)
        if[Length[entries] == 0,
           nil,
           call["VocabMutate", entries]]]]]]


(* ---------------------------------------------------------------------
   VocabMutate[entries] — reached only with a non-empty store; offers the
   keyed mutations. removeEntry/updateEntry are STUB functions (inert, so
   the bound key k survives symbolically and is recoverable under value-
   passing): their real key-matching semantics — what a key is, how it
   identifies an entry — are deliberately unspecified at this stage.
   NOTE: because they are stubs, a post-mutation state's emptiness guard
   is not evaluable until the binding layer realises them concretely (the
   same value-passing/hold discipline). The ready-set enablement is shown
   directly by comparing empty vs non-empty stores; we do not step through
   a stubbed mutation here.
   --------------------------------------------------------------------- *)
defineAgent["VocabMutate", {entries},
  choice[
    precede[coLabel["remove", binding[k]],
      call["VocabStore", removeEntry[entries, k]]],
    precede[coLabel["update", binding[ke]],
      call["VocabStore", updateEntry[entries, ke]]]]]


(* =====================================================================
   OPEN QUESTIONS (for the architect)
   ---------------------------------------------------------------------
   1. ENTRY / KEY MODEL. What is an entry ({word, ipa}? + metadata?) and
      what is a key (the word? a surrogate id?). removeEntry/updateEntry
      are stubs until this is fixed.
   2. DUPLICATES / VALIDATION. May add accept a duplicate word, or a
      malformed IPA string? If add can be rejected, that is a guard on add
      (and a state-dependent ready set), not a silent no-op.
   3. COUPLING TO PRACTICE. PracticeSession currently takes items as a
      literal list. Should it instead pull from VocabStore across a port
      (the architecture's open "items source" question)? That makes
      VocabStore.view! the items source for a session.
   4. UPDATE SHAPE. update takes a single bound value ke conflating key +
      new data; likely should be two values or a structured record.
   ===================================================================== *)
