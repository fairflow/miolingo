(* ::Package:: *)

(* =====================================================================
   miolingo / L1 \[LongDash] CargoHold (the external store), RECOVERED
   ---------------------------------------------------------------------
   Recovered from src/vocab.py + src/app_mysql.py (the MySQL persistence
   layer), NOT invented. Every vocab operation in the app opens a
   connection (app_mysql.get_connection) and runs SQL against the
   `vocab_entries` table \[LongDash] capture (INSERT \[Ellipsis] ON DUPLICATE KEY UPDATE),
   list (SELECT), delete (DELETE), update (UPDATE). CargoHold is the agent
   that OWNS that persisted collection.

   (CargoHold, not Hold: `Hold` is a Wolfram built-in. Nautical theme \[LongDash]
   Helm steers, the cargo hold stores.)

   THE POINT (single source of truth; ARCHITECTURE.md "Borrowed vs owned
   data" / the Stats-History \[Dagger] note): the persisted collection is OWNED here,
   not in VocabStore. VS holds only its UI parameters (sort/filter/editing)
   and READS the collection from CargoHold at the point of use \[LongDash] see PR-2,
   the (i) migration. This file (PR-1) DEFINES CargoHold standalone; it is
   loaded but NOT yet composed into mioCore (so no dual state until VS is
   migrated to read it).

   STATE: CargoHold[entries]   \[LongDash] entries : the persisted collection (list)

   PORTS (mirror the vocab.py SQL surface; see cargohold-recovery.md):
     chRead!    always \[LongDash] emits the current collection (a self-loop, never
                changing CargoHold). The READ a client pulls. \[TildeTilde] list_vocab SELECT.
     chUpsert   capture a word \[LongDash] INSERT \[Ellipsis] ON DUPLICATE KEY UPDATE
                (dedup/bump): the recovered addEntry IS this upsert.
     chImport   bulk capture \[LongDash] importInto (parse + fold upserts).
     chRemove   delete by id \[LongDash] DELETE.
     chAmend    update fields by id \[LongDash] UPDATE. Carries <|"id"->_, "fields"->_|>.

   When composed (PR-2), chRead/chUpsert/chRemove/chAmend are RESTRICTED in
   mioCore (internal taus), and VS reads/writes through them.

   LEAF agent (every branch loops back to CargoHold) \[LongDash] no sub-agent expansion.
   Reuses the already-recovered collection transforms (addEntry/deleteFrom/
   updateEntry, VocabStoreFunctions.wl) \[LongDash] they apply HERE now, where the data
   lives. autofill's enrichment (oracle + borrowed language) is deferred to the
   migration, so chAmend covers plain field updates for now.

   LOAD ORDER: RCA_core.wl, discipline.wl, then this (alongside the other
   recovered agents). Functions resolve at step time, as for the other agents.
   ===================================================================== *)

defineAgent["CargoHold", {entries},
  choice[
    (* @src vocab.py:195 (list_vocab) \[LongDash] SELECT * FROM vocab_entries WHERE \[Ellipsis] *)
    precede[label["chRead", param[entries]],
      call["CargoHold", entries]],
    (* @src vocab.py:106 (capture_vocab_entry) \[LongDash] INSERT \[Ellipsis] ON DUPLICATE KEY UPDATE.
       addEntry is the recovered upsert (dedup + times_seen bump). Two writers feed
       it: chUpsert from the VS tab (type/paste), and vAdd from PS capture (capture
       from practice writes the store DIRECTLY, not through the tab). *)
    precede[coLabel["chUpsert", binding[w]],
      call["CargoHold", addEntry[entries, w]]],
    (* @src vocabulary_tab.py:7 \[LongDash] PS.capture_vocab relays here (a direct DB write) *)
    precede[coLabel["vAdd", binding[w]],
      call["CargoHold", addEntry[entries, w]]],
    (* @src vocab.py:453 (import_from_file_contents) \[LongDash] bulk capture *)
    precede[coLabel["chImport", binding[f]],
      call["CargoHold", importInto[entries, f]]],
    (* @src vocab.py:301 (delete_vocab_entry) \[LongDash] DELETE \[Ellipsis] WHERE vocab_id=%s *)
    precede[coLabel["chRemove", binding[id]],
      call["CargoHold", deleteFrom[entries, id]]],
    (* @src vocab.py:343 (update_vocab_entry) \[LongDash] UPDATE \[Ellipsis] WHERE vocab_id=%s.
       u = <|"id" -> _, "fields" -> _Association|>. *)
    precede[coLabel["chAmend", binding[u]],
      call["CargoHold", updateEntry[entries, editingRow[u["id"]], u["fields"]]]]]]
