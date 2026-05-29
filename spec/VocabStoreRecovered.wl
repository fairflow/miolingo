(* ::Package:: *)

(* =====================================================================
   miolingo / L1 — VocabStore, RECOVERED (UI-first, stubbed)
   ---------------------------------------------------------------------
   Per SPEC-RECOVERY.md. Recovered from the Streamlit source
   (src/ui/vocabulary_tab.py + the vocab.py CRUD it calls), NOT invented.
   See spec/docs/vocabstore-recovery.md for the §3 analysis.

   Supersedes the invented strawman VocabStore.wl (kept for the
   invented-vs-recovered contrast, H1/H3). The strawman's core claim —
   per-entry ops gated on non-empty — is CONFIRMED; the recovery adds the
   real guards it lacked: an AUTH gate over the whole component, a
   search-non-empty guard on "Practise these", a missing-fields guard on
   autofill (stubbed), and an inline EDIT-MODE that swaps a row's actions.

   Cross-component: practise_filtered -> PracticeSession.load_material;
   and PracticeSession.capture_vocab -> this agent's `add`. (bidirectional)

   STUBBED: listVocab/addEntry/updateEntry/... are named, not defined.
   Structural guards (auth, non-empty, filter present, edit-mode) are
   concrete so the ready sets simulate.

   LOAD ORDER: RCA_core.wl, then discipline.wl, then this file.

   STATE: VS[auth, entries, sort, filter, editing]
     auth    : anon | signedIn
     entries : the collection (list)
     sort    : ordering value (alpha | recent | oldest)
     filter  : none | filterBy[q]
     editing : none | editing[id]   (which row is in inline edit-mode)

   VERIFIED on the engine (2026-05-30): ready sets track every mode.
   RECOVERED READY SETS (view!, afforded! in every mode):
     VS[anon,      _, _,_,_ ]          Anon     : (none)
     VS[signedIn, {}, _,none,none]     Empty    : add, import_bulk,
                                                  set_sort, set_filter
     VS[signedIn, ne, _,none,none]     NonEmpty : + export, delete,
                                                  update_notes, autofill,
                                                  begin_edit
     VS[signedIn, ne, _,filterBy,none] +search  : + practise_filtered
     VS[signedIn, ne, _,_,editing[id]] Editing  : per-row -> update,
                                                  cancel_edit (no delete/
                                                  begin_edit); export stays
   ===================================================================== *)


(* --- discipline ports + auth gate --- *)
defineAgent["VS", {auth, entries, sort, filter, editing},
  choice[
    precede[label["view", param[vocabView[auth, entries, sort, filter, editing]]],
      call["VS", auth, entries, sort, filter, editing]],
    choice[
      precede[label["afforded", param[portsOf[call["VS", auth, entries, sort, filter, editing]]]],
        call["VS", auth, entries, sort, filter, editing]],
      (* AUTH gate: no domain ports until signed in *)
      if[auth === signedIn,
         call["VSAuthed", entries, sort, filter, editing],
         nil]]]]


(* --- always-available CRUD-in + non-empty dispatch (signed in) --- *)
defineAgent["VSAuthed", {entries, sort, filter, editing},
  choice[
    precede[coLabel["add", binding[w]],
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
          (* per-entry ops + export + practise only when non-empty *)
          if[Length[entries] == 0,
             nil,
             call["VSNonEmpty", entries, sort, filter, editing]]]]]]]


(* --- non-empty: export, guarded practise, and the edit-mode swap --- *)
defineAgent["VSNonEmpty", {entries, sort, filter, editing},
  choice[
    precede[label["export", param[exportCsv[entries]]],
      call["VS", signedIn, entries, sort, filter, editing]],
    choice[
      (* "Practise these" — guard: a filter is set *)
      if[filter =!= none,
         precede[coLabel["practise_filtered"],
           call["VS", signedIn, entries, sort, filter, editing]],
         nil],
      (* per-entry actions, swapped by edit-mode *)
      if[editing === none,
         call["VSEntryActions", entries, sort, filter],
         call["VSEditActions", entries, sort, filter, editing]]]]]


(* --- per-entry actions when NOT editing --- *)
defineAgent["VSEntryActions", {entries, sort, filter},
  choice[
    precede[coLabel["delete", binding[id]],
      call["VS", signedIn, deleteFrom[entries, id], sort, filter, none]],
    choice[
      precede[coLabel["update_notes", binding[idn]],
        call["VS", signedIn, updateNotesIn[entries, idn], sort, filter, none]],
      choice[
        (* autofill — the missing-fields guard needsAutofill[entries,id] is
           a STUBBED value predicate, deferred; modelled as available per
           entry when non-empty *)
        precede[coLabel["autofill", binding[id]],
          call["VS", signedIn, autofillIn[entries, id], sort, filter, none]],
        precede[coLabel["begin_edit", binding[id]],
          call["VS", signedIn, entries, sort, filter, editing[id]]]]]]]


(* --- per-entry actions WHILE editing a row --- *)
defineAgent["VSEditActions", {entries, sort, filter, editing},
  choice[
    precede[coLabel["update", binding[fields]],
      call["VS", signedIn, updateEntry[entries, editing, fields], sort, filter, none]],
    precede[coLabel["cancel_edit"],
      call["VS", signedIn, entries, sort, filter, none]]]]
