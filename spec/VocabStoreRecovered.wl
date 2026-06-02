(* ::Package:: *)

(* =====================================================================
   miolingo / L1 \[LongDash] VocabStore, RECOVERED (UI-first, stubbed)
   ---------------------------------------------------------------------
   Per SPEC-RECOVERY.md. Recovered from the Streamlit source
   (src/ui/vocabulary_tab.py + the vocab.py CRUD it calls), NOT invented.
   See spec/docs/vocabstore-recovery.md for the \[Section]3 analysis.

   SPEC STYLE: guard-partitioned normal form.
     - No `afforded` channel; readiness is derived from guards + structure.
     - No degenerate conditionals: no if[c,P,nil] / if[c,nil,Q] in the
       written form. Guards are hoisted outermost; every branch is a real
       process expression.

   Supersedes the invented strawman VocabStore.wl (kept for the
   invented-vs-recovered contrast, H1/H3). The strawman's core claim \[LongDash]
   per-entry ops gated on non-empty \[LongDash] is CONFIRMED; the recovery adds the
   real guards it lacked: an AUTH gate over the whole component, a
   search-non-empty guard on "Practise these", a missing-fields guard on
   autofill (stubbed), and an inline EDIT-MODE that swaps a row's actions.

   Cross-component: practise_vocab -> PracticeSession.load_material (via pLoad);
   and PracticeSession.capture_vocab -> this agent's `add` (via vAdd). The two
   are symmetric: practise_vocab sends the vocab view OUT to practice,
   capture_vocab brings a practised word back IN. (bidirectional)

   STUBBED: listVocab/addEntry/updateEntry/... are named, not defined.
   Structural guards (auth, non-empty, filter present, edit-mode) are
   concrete so the ready sets simulate.

   LOAD ORDER: RCA_core.wl, then discipline.wl, then this file.

   STATE: VS[auth, entries, sort, filter, editing]
     auth    : anon | signedIn
     entries : the collection (list)
     sort    : ordering value (alpha | recent | oldest)
     filter  : none | filterBy[q]
     editing : none | editingRow[id]   (which row is in inline edit-mode)

   RECOVERED READY SETS (analysis only; derived from the guards below,
   not explicit channels in the process):
     VS[anon,      _, _,_,_ ]          Anon     : (none)
     VS[signedIn, {}, _,none,none]     Empty    : add, vAdd, import_bulk,
                                                  set_sort, set_filter
     VS[signedIn, ne, _,_,none]        NonEmpty : + export, practise_vocab,
                                                  delete, update_notes,
                                                  autofill, begin_edit
                                                  (practise_vocab any filter;
                                                  payload = practiseList[…,filter],
                                                  all when filter===none)
     VS[signedIn, ne, _,_,editingRow[id]] Editing  : export, practise_vocab,
                                                  per-row update, cancel_edit
                                                  (no delete/begin_edit)

   NOTE: refactored to guard-partitioned normal form 2026-05-30.
   RE-VERIFY on the engine before commit: simulated ready sets per mode
   must be identical to the pre-refactor file (this is a normal-form
   rewrite, meaning-preserving, NOT a semantic change).
   ===================================================================== *)


(* --- top level: view + auth gate --- *)
defineAgent["VS", {auth, entries, sort, filter, editing},
  if[auth === signedIn,
    choice[
      precede[label["view", param[vocabView[auth, entries, sort, filter, editing]]],
        call["VS", auth, entries, sort, filter, editing]],
      call["VSAuthed", entries, sort, filter, editing]],
    precede[label["view", param[vocabView[auth, entries, sort, filter, editing]]],
      call["VS", auth, entries, sort, filter, editing]]]]


(* --- signed in: always-available CRUD-in, then non-empty refinement --- *)
defineAgent["VSAuthed", {entries, sort, filter, editing},
  if[Length[entries] == 0,
    choice[
      precede[coLabel["add", binding[w]],
        call["VS", signedIn, addEntry[entries, w], sort, filter, editing]],
      choice[
        precede[coLabel["vAdd", binding[w]],
          call["VS", signedIn, addEntry[entries, w], sort, filter, editing]],
        choice[
          precede[coLabel["import_bulk", binding[f]],
            call["VS", signedIn, importInto[entries, f], sort, filter, editing]],
          choice[
            precede[coLabel["set_sort", binding[s]],
              call["VS", signedIn, entries, s, filter, editing]],
            precede[coLabel["set_filter", binding[q]],
              call["VS", signedIn, entries, sort, filterBy[q], editing]]]]]],
    choice[
      precede[coLabel["add", binding[w]],
        call["VS", signedIn, addEntry[entries, w], sort, filter, editing]],
      choice[
        precede[coLabel["vAdd", binding[w]],
          call["VS", signedIn, addEntry[entries, w], sort, filter, editing]],
        choice[
          precede[coLabel["import_bulk", binding[f]],
            call["VS", signedIn, importInto[entries, f], sort, filter, editing]],
          choice[
            precede[coLabel["set_sort", binding[s]],
              call["VS", signedIn, entries, s, filter, editing]],
            choice[
              precede[coLabel["set_filter", binding[q]],
                call["VS", signedIn, entries, sort, filterBy[q], editing]],
              call["VSNonEmpty", entries, sort, filter, editing]]]]]]]]


(* --- non-empty: export + practise_vocab always; edit-mode refines per-entry --
   practise_vocab is the SINGLE vocab->practice channel (the app exposes it as
   "Load vocabulary" / "Load filtered" / "Practise these" — unified here). It is
   available whenever the store is non-empty, regardless of filter, and emits the
   CURRENT vocab VIEW to PracticeSession via pLoad (restricted -> tau in mioCore):
   practiseList[entries, filter] is ALL vocab when filter===none ("Load
   vocabulary") and the filtered subset when filterBy[q] ("Load filtered"). The
   filter no longer GATES the route (it only parametrises the payload); the
   previous filter split collapses, leaving just the edit-mode split for per-entry
   actions. *)
defineAgent["VSNonEmpty", {entries, sort, filter, editing},
  choice[
    precede[label["export", param[exportCsv[entries]]],
      call["VS", signedIn, entries, sort, filter, editing]],
    precede[coLabel["practise_vocab"],
      precede[label["pLoad", param[practiseList[entries, filter]]],
        call["VS", signedIn, entries, sort, filter, editing]]],
    if[editing === none,
      call["VSEntryActions", entries, sort, filter],
      call["VSEditActions", entries, sort, filter, editing]]]]


(* --- per-entry actions when NOT editing --- *)
defineAgent["VSEntryActions", {entries, sort, filter},
  choice[
    precede[coLabel["delete", binding[id]],
      call["VS", signedIn, deleteFrom[entries, id], sort, filter, none]],
    choice[
      precede[coLabel["update_notes", binding[idn]],
        call["VS", signedIn, updateNotesIn[entries, idn], sort, filter, none]],
      choice[
        (* autofill \[LongDash] the missing-fields guard needsAutofill[entries,id] is
           a STUBBED value predicate, deferred; modelled as available per
           entry when non-empty.
           BORROWED DATA: enrichment needs the (source, target) language pair,
           which Helm OWNS. So autofill PULLS it fresh as a PREFIX \[LongDash] langRead?(lp)
           sits on the critical path of the action, restricted to Helm's langRead!
           in mioCore (an internal tau). No cached language => no staleness; the
           value read is always Helm's current pair. See ARCHITECTURE.md
           "Borrowed vs owned data". lp = {source, target}. *)
        precede[coLabel["autofill", binding[id]],
          precede[coLabel["langRead", binding[lp]],
            call["VS", signedIn, autofillIn[entries, id, lp], sort, filter, none]]],
        precede[coLabel["begin_edit", binding[id]],
          call["VS", signedIn, entries, sort, filter, editingRow[id]]]]]]]


(* --- per-entry actions WHILE editing a row --- *)
defineAgent["VSEditActions", {entries, sort, filter, editing},
  choice[
    precede[coLabel["update", binding[fields]],
      call["VS", signedIn, updateEntry[entries, editing, fields], sort, filter, none]],
    precede[coLabel["cancel_edit"],
      call["VS", signedIn, entries, sort, filter, none]]]]
