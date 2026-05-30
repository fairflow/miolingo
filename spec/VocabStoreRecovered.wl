(* ::Package:: *)

(* =====================================================================
   miolingo / L1 — VocabStore, RECOVERED (UI-first, stubbed)
   ---------------------------------------------------------------------
   Per SPEC-RECOVERY.md. Recovered from src/ui/vocabulary_tab.py + the
   vocab.py CRUD it calls, NOT invented. See spec/docs/vocabstore-recovery.md.

   FORM: compact guarded-choice with 2-arg if[c, P] sugar. The merge law
   if[c,A] + if[!c,B] == if[c,A,B] is applied where complementary guards
   carry disjoint actions — here for `editing` (entry actions vs edit-mode
   actions). The auth and empty/non-empty splits keep their shared ports
   out front + a one-armed if for the extra (no duplication).
   No `afforded` (readiness = readyPorts[state]); `view` kept.
   LOAD ORDER: RCA_core.wl, discipline.wl, then this.

   STATE: VS[auth, entries, sort, filter, editing]
     auth : anon | signedIn     entries : list     sort : alpha|recent|oldest
     filter : none | filterBy[q]   editing : none | editingRow[id]
     (the edit-mode tag head `editingRow` must DIFFER from the `editing`
      parameter name, else mu-term substitution of the editing binder
      captures the tag head: editing[id] /. {editing->none} -> none[id].)

   READY SETS (analysis; readyPorts, not declared):
     VS[anon,      _,_,_,_]            : view
     VS[signedIn, {}, _,none,none]     : + add, vAdd, import_bulk,
                                           set_sort, set_filter
     VS[signedIn, ne, _,none,none]     : + export, delete, update_notes,
                                           autofill, begin_edit
     VS[signedIn, ne, _,filterBy,none] : + practise_filtered
     VS[signedIn, ne, _,_,editingRow[id]] : update, cancel_edit replace the
                                           per-entry set (export stays)

   MU-TERM VIEW: buildSystem[call["VS", auth, entries, sort, filter, editing]].
   ===================================================================== *)


(* --- top: view always; domain ports when signed in (shared-port split) --- *)
defineAgent["VS", {auth, entries, sort, filter, editing},
  choice[
    precede[label["view", param[vocabView[auth, entries, sort, filter, editing]]],
      call["VS", auth, entries, sort, filter, editing]],
    if[auth === signedIn,
      call["VSAuthed", entries, sort, filter, editing]]]]


(* --- signed in: always-available CRUD-in; per-entry ops when non-empty.
   vAdd is the cross-component relay from PracticeSession (restricted in
   MioCore); `add` is the user paste/upload route. --- *)
defineAgent["VSAuthed", {entries, sort, filter, editing},
  choice[
    precede[coLabel["add", binding[w]],
      call["VS", signedIn, addEntry[entries, w], sort, filter, editing]],
    precede[coLabel["vAdd", binding[w]],
      call["VS", signedIn, addEntry[entries, w], sort, filter, editing]],
    precede[coLabel["import_bulk", binding[f]],
      call["VS", signedIn, importInto[entries, f], sort, filter, editing]],
    precede[coLabel["set_sort", binding[s]],
      call["VS", signedIn, entries, s, filter, editing]],
    precede[coLabel["set_filter", binding[q]],
      call["VS", signedIn, entries, sort, filterBy[q], editing]],
    if[Length[entries] > 0,
      call["VSNonEmpty", entries, sort, filter, editing]]]]


(* --- non-empty: export always; practise_filtered when a filter is set;
   two-armed editing split (entry actions vs edit-mode actions) --- *)
defineAgent["VSNonEmpty", {entries, sort, filter, editing},
  choice[
    precede[label["export", param[exportCsv[entries]]],
      call["VS", signedIn, entries, sort, filter, editing]],
    (* practise_filtered relays to PracticeSession on pLoad (restricted) *)
    if[filter =!= none,
      precede[coLabel["practise_filtered"],
        precede[label["pLoad", param[practiseList[entries, filter]]],
          call["VS", signedIn, entries, sort, filter, editing]]]],
    if[editing === none,
      call["VSEntryActions", entries, sort, filter],
      call["VSEditActions", entries, sort, filter, editing]]]]


(* --- per-entry actions when NOT editing (autofill's missing-fields guard
   is a stubbed value predicate, deferred) --- *)
defineAgent["VSEntryActions", {entries, sort, filter},
  choice[
    precede[coLabel["delete", binding[id]],
      call["VS", signedIn, deleteFrom[entries, id], sort, filter, none]],
    precede[coLabel["update_notes", binding[idn]],
      call["VS", signedIn, updateNotesIn[entries, idn], sort, filter, none]],
    precede[coLabel["autofill", binding[id]],
      call["VS", signedIn, autofillIn[entries, id], sort, filter, none]],
    precede[coLabel["begin_edit", binding[id]],
      call["VS", signedIn, entries, sort, filter, editingRow[id]]]]]


(* --- per-entry actions WHILE editing a row --- *)
defineAgent["VSEditActions", {entries, sort, filter, editing},
  choice[
    precede[coLabel["update", binding[fields]],
      call["VS", signedIn, updateEntry[entries, editing, fields], sort, filter, none]],
    precede[coLabel["cancel_edit"],
      call["VS", signedIn, entries, sort, filter, none]]]]
