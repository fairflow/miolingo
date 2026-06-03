(* ::Package:: *)

(* =====================================================================
   miolingo / L1 — Vocab, RECOVERED — (i) external-store form
   ---------------------------------------------------------------------
   Recovered from src/ui/vocabulary_tab.py + the vocab.py CRUD it calls.
   See spec/docs/vocabstore-recovery.md for the §3 analysis and the
   provenance table.

   (i) MIGRATION (2026-06-02): the persisted collection is OWNED by
   VocabTable (the external store), NOT by Vocab. Vocab holds only its UI
   parameters and READS the collection fresh at the point of use, and WRITES
   through VocabTable. Single source of truth (ARCHITECTURE.md "Borrowed vs
   owned data"; the Stats-History † note). This is the "own it → store it;
   borrow it → fetch fresh" rule applied to persistence.

   STATE: Vocab[auth, sort, filter, editing]   — NO entries (they live in VocabTable)
     auth    : anon | signedIn
     sort    : ordering value (alpha | recent | oldest)   — a Vocab-owned UI param
     filter  : none | filterBy[q]                         — a Vocab-owned UI param
     editing : none | editingRow[id]                      — a Vocab-owned UI param

   WHAT Vocab READS FROM CARGOHOLD, AND WHY  (one vocabRead per cycle feeds all):
     read es (vocabRead!) ──┬─ ready-set guard   Length[es]==0  → which ports are afforded
                         ├─ view! projection  vocabView[…, es, …]   (≈ list_vocab)
                         └─ export            exportCsv[es]
     (practise_vocab no longer reads es: it signals PS the filter and PS pulls.)
     Reads are FRESH each cycle (a prefix vocabRead, restricted → internal τ in
     mioCore); there is NO cached copy, hence no staleness. In the app every
     Streamlit rerun re-runs list_vocab — a query — so view! is query-backed.

   ENTRY: Vocab is the Vocabulary TAB. open_vocab (a VISIBLE, parameter-less input —
   the user selecting the tab) is the entry; it initiates the vocabRead. Keeping the
   first action visible (not the vocabRead τ) keeps Vocab visibly-guarded so weak
   bisimilarity stays a congruence under composition.

   WHAT Vocab WRITES TO CARGOHOLD  (Vocab never mutates a local copy):
     add         → vocabUpsert!(w)      type/paste a word (INSERT … ON DUPLICATE KEY)
     import_bulk → vocabImport!(f)      bulk capture
     delete      → vocabRemove!(id)     DELETE
     update / update_notes / autofill → vocabAmend!(<|id, fields|>)   UPDATE
   set_sort / set_filter / begin_edit / cancel_edit change Vocab's OWN params only.

   Cross-component: practise_vocab → goPractice!(filter) → PS pulls from VocabTable;
   PracticeSession.capture_vocab → vocabUpsert → VocabTable DIRECTLY (capture from practice
   writes to the store, NOT through this tab — the app's capture_vocab_entry is a
   direct DB write, vocabulary_tab.py:7 / vocab.py:106).

   LOAD ORDER: RCA_core.wl, discipline.wl, then this (VocabTable too); MioCore
   composes Vocab with VocabTable. Functions resolve at step time.
   ===================================================================== *)


(* --- top: the Vocabulary TAB. Signed-in offers a VISIBLE entry, open_vocab
   (the user selecting the tab); taking it initiates the store read. Keeping the
   FIRST action visible (not the vocabRead τ) makes Vocab visibly-guarded, so weak
   bisimilarity stays a congruence under composition — no initial τ to break it.
   Capture from practice does NOT pass through the tab: it writes to VocabTable
   directly (PS.capture_vocab → vocabUpsert → VocabTable). Vocab is purely the gated
   viewer/editor of the store. *)
defineAgent["Vocab", {auth, sort, filter, editing},
  if[auth === signedIn,
    precede[coLabel["open_vocab"], call["VocabRead", sort, filter, editing]],
    precede[label["view", param[vocabView[anon, {}, sort, filter, editing]]],
      call["Vocab", anon, sort, filter, editing]]]]

(* --- in the tab: PULL the collection (vocabRead — AFTER the visible open_vocab),
   then offer the view + the authed surface. Loops back HERE (re-read each cycle),
   NOT to Vocab: open_vocab is the one-time entry, not a per-action gate.
   @src vocab.py:195 (list_vocab) — read the collection from VocabTable *)
defineAgent["VocabRead", {sort, filter, editing},
  precede[coLabel["vocabRead", binding[es]],
    choice[
      precede[label["view", param[vocabView[signedIn, es, sort, filter, editing]]],
        call["VocabRead", sort, filter, editing]],
      call["VocabAuthed", es, sort, filter, editing]]]]


(* --- in the tab, signed in: add (type a word) / import write to VocabTable;
   sort/filter are Vocab-owned params; non-empty adds the rest. NB capture FROM
   PRACTICE does NOT appear here — it goes PS → VocabTable directly (vocabUpsert). *)
defineAgent["VocabAuthed", {es, sort, filter, editing},
  if[Length[es] == 0,
    choice[
      (* @src vocabulary_tab.py (paste/word add); vocab.py:106 — write to store *)
      precede[coLabel["add", binding[w]],
        precede[label["vocabUpsert", param[w]], call["VocabRead", sort, filter, editing]]],
      choice[
        (* @src vocab.py:453 (import_from_file_contents) — bulk capture *)
        precede[coLabel["import_bulk", binding[f]],
          precede[label["vocabImport", param[f]], call["VocabRead", sort, filter, editing]]],
        choice[
          precede[coLabel["set_sort", binding[s]],
            call["VocabRead", s, filter, editing]],
          precede[coLabel["set_filter", binding[q]],
            call["VocabRead", sort, filterBy[q], editing]]]]],
    choice[
      precede[coLabel["add", binding[w]],
        precede[label["vocabUpsert", param[w]], call["VocabRead", sort, filter, editing]]],
      choice[
        precede[coLabel["import_bulk", binding[f]],
          precede[label["vocabImport", param[f]], call["VocabRead", sort, filter, editing]]],
        choice[
          precede[coLabel["set_sort", binding[s]],
            call["VocabRead", s, filter, editing]],
          choice[
            precede[coLabel["set_filter", binding[q]],
              call["VocabRead", sort, filterBy[q], editing]],
            call["VocabNonEmpty", es, sort, filter, editing]]]]]]]


(* --- non-empty: export + practise_vocab always; edit-mode refines per-entry.
   practise_vocab is the vocab-tab "Practise these" cross-tab nav. It no longer
   PUSHES the data: it signals PS with goPractice!(filter) — the FILTER only — and
   PS pulls the collection FRESH from VocabTable itself. So no snapshot crosses the
   boundary (single source of truth); Vocab need not even read es to hand off. *)
defineAgent["VocabNonEmpty", {es, sort, filter, editing},
  choice[
    (* @src vocabulary_tab.py:69 (Export CSV) *)
    precede[label["export", param[exportCsv[es]]],
      call["VocabRead", sort, filter, editing]],
    (* @src vocabulary_tab.py:556 ("🎯 Practise these") — SIGNAL to PracticeSession;
       carries the filter, not the entries (PS pulls them). This NAVIGATES AWAY from
       the vocab tab, so Vocab returns to its un-opened entry (open_vocab), NOT VocabRead —
       it does not re-read. That also leaves PS's pull as the unique enabled τ, so
       the hand-off settles deterministically (no competing Vocab re-read). *)
    precede[coLabel["practise_vocab"],
      precede[label["goPractice", param[filter]],
        call["Vocab", signedIn, sort, filter, editing]]],
    if[editing === none,
      call["VocabEntryActions", es, sort, filter],
      call["VocabEditActions", es, sort, filter, editing]]]]


(* --- per-entry actions when NOT editing — each WRITES to VocabTable --- *)
defineAgent["VocabEntryActions", {es, sort, filter},
  choice[
    (* @src vocab.py:301 (delete_vocab_entry) *)
    precede[coLabel["delete", binding[id]],
      precede[label["vocabRemove", param[id]], call["VocabRead", sort, filter, none]]],
    choice[
      (* @src vocab.py:314 (update_vocab_notes) *)
      precede[coLabel["update_notes", binding[idn]],
        precede[label["vocabAmend", param[<|"id" -> idn["id"], "fields" -> <|"notes" -> idn["notes"]|>|>]],
          call["VocabRead", sort, filter, none]]],
      choice[
        (* @src vocab.py:411 (autofill_vocab_entry) — read the language (langRead,
           borrowed from Helm), compute the fill, write it via vocabAmend *)
        precede[coLabel["autofill", binding[id]],
          precede[coLabel["langRead", binding[lp]],
            precede[label["vocabAmend", param[<|"id" -> id, "fields" -> autofillFields[es, id, lp]|>]],
              call["VocabRead", sort, filter, none]]]],
        precede[coLabel["begin_edit", binding[id]],
          call["VocabRead", sort, filter, editingRow[id]]]]]]]


(* --- per-entry actions WHILE editing a row — update WRITES via vocabAmend --- *)
defineAgent["VocabEditActions", {es, sort, filter, editing},
  choice[
    (* @src vocab.py:343 (update_vocab_entry) ; editing = editingRow[id].
       Extract the id by PATTERN (editing /. editingRow[i_] :> i), not First[editing]:
       First[editing] would evaluate on the bare `editing` symbol at load (an atom →
       error). ReplaceAll leaves a non-editingRow value untouched (held). *)
    precede[coLabel["update", binding[fields]],
      precede[label["vocabAmend", param[<|"id" -> (editing /. editingRow[i_] :> i), "fields" -> fields|>]],
        call["VocabRead", sort, filter, none]]],
    precede[coLabel["cancel_edit"],
      call["VocabRead", sort, filter, none]]]]
