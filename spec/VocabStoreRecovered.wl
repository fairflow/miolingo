(* ::Package:: *)

(* =====================================================================
   miolingo / L1 \[LongDash] VocabStore, RECOVERED \[LongDash] (i) external-store form
   ---------------------------------------------------------------------
   Recovered from src/ui/vocabulary_tab.py + the vocab.py CRUD it calls.
   See spec/docs/vocabstore-recovery.md for the \[Section]3 analysis and the
   provenance table.

   (i) MIGRATION (2026-06-02): the persisted collection is OWNED by
   CargoHold (the external store), NOT by VocabStore. VS holds only its UI
   parameters and READS the collection fresh at the point of use, and WRITES
   through CargoHold. Single source of truth (ARCHITECTURE.md "Borrowed vs
   owned data"; the Stats-History \[Dagger] note). This is the "own it \[RightArrow] store it;
   borrow it \[RightArrow] fetch fresh" rule applied to persistence.

   STATE: VS[auth, sort, filter, editing]   \[LongDash] NO entries (they live in CargoHold)
     auth    : anon | signedIn
     sort    : ordering value (alpha | recent | oldest)   \[LongDash] a VS-owned UI param
     filter  : none | filterBy[q]                         \[LongDash] a VS-owned UI param
     editing : none | editingRow[id]                      \[LongDash] a VS-owned UI param

   WHAT VS READS FROM CARGOHOLD, AND WHY  (one chRead per cycle feeds all):
     read es (chRead!) \[HorizontalLine]\[HorizontalLine]\:252c\[HorizontalLine] ready-set guard   Length[es]==0  \[RightArrow] which ports are afforded
                         \:251c\[HorizontalLine] view! projection  vocabView[\[Ellipsis], es, \[Ellipsis]]   (\[TildeTilde] list_vocab)
                         \:2514\[HorizontalLine] export            exportCsv[es]
     (practise_vocab no longer reads es: it signals PS the filter and PS pulls.)
     Reads are FRESH each cycle (a prefix chRead, restricted \[RightArrow] internal \[Tau] in
     mioCore); there is NO cached copy, hence no staleness. In the app every
     Streamlit rerun re-runs list_vocab \[LongDash] a query \[LongDash] so view! is query-backed.

   ENTRY: VS is the Vocabulary TAB. open_vocab (a VISIBLE, parameter-less input \[LongDash]
   the user selecting the tab) is the entry; it initiates the chRead. Keeping the
   first action visible (not the chRead \[Tau]) keeps VS visibly-guarded so weak
   bisimilarity stays a congruence under composition.

   WHAT VS WRITES TO CARGOHOLD  (VS never mutates a local copy):
     add         \[RightArrow] chUpsert!(w)      type/paste a word (INSERT \[Ellipsis] ON DUPLICATE KEY)
     import_bulk \[RightArrow] chImport!(f)      bulk capture
     delete      \[RightArrow] chRemove!(id)     DELETE
     update / update_notes / autofill \[RightArrow] chAmend!(<|id, fields|>)   UPDATE
   set_sort / set_filter / begin_edit / cancel_edit change VS's OWN params only.

   Cross-component: practise_vocab \[RightArrow] goPractice!(filter) \[RightArrow] PS pulls from CargoHold;
   PracticeSession.capture_vocab \[RightArrow] vAdd \[RightArrow] CargoHold DIRECTLY (capture from practice
   writes to the store, NOT through this tab \[LongDash] the app's capture_vocab_entry is a
   direct DB write, vocabulary_tab.py:7 / vocab.py:106).

   LOAD ORDER: RCA_core.wl, discipline.wl, then this (CargoHold too); MioCore
   composes VS with CargoHold. Functions resolve at step time.
   ===================================================================== *)


(* --- top: the Vocabulary TAB. Signed-in offers a VISIBLE entry, open_vocab
   (the user selecting the tab); taking it initiates the store read. Keeping the
   FIRST action visible (not the chRead \[Tau]) makes VS visibly-guarded, so weak
   bisimilarity stays a congruence under composition \[LongDash] no initial \[Tau] to break it.
   Capture from practice does NOT pass through the tab: it writes to CargoHold
   directly (PS.capture_vocab \[RightArrow] vAdd \[RightArrow] CargoHold). VS is purely the gated
   viewer/editor of the store. *)
defineAgent["VS", {auth, sort, filter, editing},
  if[auth === signedIn,
    precede[coLabel["open_vocab"], call["VSRead", sort, filter, editing]],
    precede[label["view", param[vocabView[anon, {}, sort, filter, editing]]],
      call["VS", anon, sort, filter, editing]]]]

(* --- in the tab: PULL the collection (chRead \[LongDash] AFTER the visible open_vocab),
   then offer the view + the authed surface. Loops back HERE (re-read each cycle),
   NOT to VS: open_vocab is the one-time entry, not a per-action gate.
   @src vocab.py:195 (list_vocab) \[LongDash] read the collection from CargoHold *)
defineAgent["VSRead", {sort, filter, editing},
  precede[coLabel["chRead", binding[es]],
    choice[
      precede[label["view", param[vocabView[signedIn, es, sort, filter, editing]]],
        call["VSRead", sort, filter, editing]],
      call["VSAuthed", es, sort, filter, editing]]]]


(* --- in the tab, signed in: add (type a word) / import write to CargoHold;
   sort/filter are VS-owned params; non-empty adds the rest. NB capture FROM
   PRACTICE does NOT appear here \[LongDash] it goes PS \[RightArrow] CargoHold directly (vAdd). *)
defineAgent["VSAuthed", {es, sort, filter, editing},
  if[Length[es] == 0,
    choice[
      (* @src vocabulary_tab.py (paste/word add); vocab.py:106 \[LongDash] write to store *)
      precede[coLabel["add", binding[w]],
        precede[label["chUpsert", param[w]], call["VSRead", sort, filter, editing]]],
      choice[
        (* @src vocab.py:453 (import_from_file_contents) \[LongDash] bulk capture *)
        precede[coLabel["import_bulk", binding[f]],
          precede[label["chImport", param[f]], call["VSRead", sort, filter, editing]]],
        choice[
          precede[coLabel["set_sort", binding[s]],
            call["VSRead", s, filter, editing]],
          precede[coLabel["set_filter", binding[q]],
            call["VSRead", sort, filterBy[q], editing]]]]],
    choice[
      precede[coLabel["add", binding[w]],
        precede[label["chUpsert", param[w]], call["VSRead", sort, filter, editing]]],
      choice[
        precede[coLabel["import_bulk", binding[f]],
          precede[label["chImport", param[f]], call["VSRead", sort, filter, editing]]],
        choice[
          precede[coLabel["set_sort", binding[s]],
            call["VSRead", s, filter, editing]],
          choice[
            precede[coLabel["set_filter", binding[q]],
              call["VSRead", sort, filterBy[q], editing]],
            call["VSNonEmpty", es, sort, filter, editing]]]]]]]


(* --- non-empty: export + practise_vocab always; edit-mode refines per-entry.
   practise_vocab is the vocab-tab "Practise these" cross-tab nav. It no longer
   PUSHES the data: it signals PS with goPractice!(filter) \[LongDash] the FILTER only \[LongDash] and
   PS pulls the collection FRESH from CargoHold itself. So no snapshot crosses the
   boundary (single source of truth); VS need not even read es to hand off. *)
defineAgent["VSNonEmpty", {es, sort, filter, editing},
  choice[
    (* @src vocabulary_tab.py:69 (Export CSV) *)
    precede[label["export", param[exportCsv[es]]],
      call["VSRead", sort, filter, editing]],
    (* @src vocabulary_tab.py:556 ("\|01f3af Practise these") \[LongDash] SIGNAL to PracticeSession;
       carries the filter, not the entries (PS pulls them). This NAVIGATES AWAY from
       the vocab tab, so VS returns to its un-opened entry (open_vocab), NOT VSRead \[LongDash]
       it does not re-read. That also leaves PS's pull as the unique enabled \[Tau], so
       the hand-off settles deterministically (no competing VS re-read). *)
    precede[coLabel["practise_vocab"],
      precede[label["goPractice", param[filter]],
        call["VS", signedIn, sort, filter, editing]]],
    if[editing === none,
      call["VSEntryActions", es, sort, filter],
      call["VSEditActions", es, sort, filter, editing]]]]


(* --- per-entry actions when NOT editing \[LongDash] each WRITES to CargoHold --- *)
defineAgent["VSEntryActions", {es, sort, filter},
  choice[
    (* @src vocab.py:301 (delete_vocab_entry) *)
    precede[coLabel["delete", binding[id]],
      precede[label["chRemove", param[id]], call["VSRead", sort, filter, none]]],
    choice[
      (* @src vocab.py:314 (update_vocab_notes) *)
      precede[coLabel["update_notes", binding[idn]],
        precede[label["chAmend", param[<|"id" -> idn["id"], "fields" -> <|"notes" -> idn["notes"]|>|>]],
          call["VSRead", sort, filter, none]]],
      choice[
        (* @src vocab.py:411 (autofill_vocab_entry) \[LongDash] read the language (langRead,
           borrowed from Helm), compute the fill, write it via chAmend *)
        precede[coLabel["autofill", binding[id]],
          precede[coLabel["langRead", binding[lp]],
            precede[label["chAmend", param[<|"id" -> id, "fields" -> autofillFields[es, id, lp]|>]],
              call["VSRead", sort, filter, none]]]],
        precede[coLabel["begin_edit", binding[id]],
          call["VSRead", sort, filter, editingRow[id]]]]]]]


(* --- per-entry actions WHILE editing a row \[LongDash] update WRITES via chAmend --- *)
defineAgent["VSEditActions", {es, sort, filter, editing},
  choice[
    (* @src vocab.py:343 (update_vocab_entry) ; editing = editingRow[id].
       Extract the id by PATTERN (editing /. editingRow[i_] :> i), not First[editing]:
       First[editing] would evaluate on the bare `editing` symbol at load (an atom \[RightArrow]
       error). ReplaceAll leaves a non-editingRow value untouched (held). *)
    precede[coLabel["update", binding[fields]],
      precede[label["chAmend", param[<|"id" -> (editing /. editingRow[i_] :> i), "fields" -> fields|>]],
        call["VSRead", sort, filter, none]]],
    precede[coLabel["cancel_edit"],
      call["VSRead", sort, filter, none]]]]
