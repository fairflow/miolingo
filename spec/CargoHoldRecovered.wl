(* ::Package:: *)

(* =====================================================================
   miolingo / L1 — CargoHold (the external store), RECOVERED
   ---------------------------------------------------------------------
   Recovered from src/vocab.py + src/app_mysql.py (the MySQL persistence
   layer), NOT invented. Every vocab operation in the app opens a
   connection (app_mysql.get_connection) and runs SQL against the
   `vocab_entries` table — capture (INSERT … ON DUPLICATE KEY UPDATE),
   list (SELECT), delete (DELETE), update (UPDATE). CargoHold is the agent
   that OWNS that persisted collection.

   (CargoHold, not Hold: `Hold` is a Wolfram built-in. Nautical theme —
   Helm steers, the cargo hold stores.)

   THE POINT (single source of truth; ARCHITECTURE.md "Borrowed vs owned
   data" / the Stats-History † note): the persisted collection is OWNED here,
   not in VocabStore. VS holds only its UI parameters (sort/filter/editing)
   and READS the collection from CargoHold at the point of use — see PR-2,
   the (i) migration. This file (PR-1) DEFINES CargoHold standalone; it is
   loaded but NOT yet composed into mioCore (so no dual state until VS is
   migrated to read it).

   STATE: CargoHold[entries]   — entries : the persisted collection (list)

   PORTS (mirror the vocab.py SQL surface; see cargohold-recovery.md):
     chRead!    always — emits the current collection (a self-loop, never
                changing CargoHold). The READ a client pulls. ≈ list_vocab SELECT.
     chUpsert   capture/import a word — INSERT … ON DUPLICATE KEY UPDATE
                (dedup/bump): the recovered addEntry IS this upsert.
     chRemove   delete by id — DELETE.
     chAmend    update fields by id — UPDATE. Carries <|"id"->_, "fields"->_|>.

   When composed (PR-2), chRead/chUpsert/chRemove/chAmend are RESTRICTED in
   mioCore (internal taus), and VS reads/writes through them.

   LEAF agent (every branch loops back to CargoHold) — no sub-agent expansion.
   Reuses the already-recovered collection transforms (addEntry/deleteFrom/
   updateEntry, VocabStoreFunctions.wl) — they apply HERE now, where the data
   lives. autofill's enrichment (oracle + borrowed language) is deferred to the
   migration, so chAmend covers plain field updates for now.

   LOAD ORDER: RCA_core.wl, discipline.wl, then this (alongside the other
   recovered agents). Functions resolve at step time, as for the other agents.
   ===================================================================== *)

defineAgent["CargoHold", {entries},
  choice[
    (* @src vocab.py:195 (list_vocab) — SELECT * FROM vocab_entries WHERE … *)
    precede[label["chRead", param[entries]],
      call["CargoHold", entries]],
    (* @src vocab.py:106 (capture_vocab_entry) — INSERT … ON DUPLICATE KEY UPDATE.
       addEntry is the recovered upsert (dedup + times_seen bump). *)
    precede[coLabel["chUpsert", binding[w]],
      call["CargoHold", addEntry[entries, w]]],
    (* @src vocab.py:301 (delete_vocab_entry) — DELETE … WHERE vocab_id=%s *)
    precede[coLabel["chRemove", binding[id]],
      call["CargoHold", deleteFrom[entries, id]]],
    (* @src vocab.py:343 (update_vocab_entry) — UPDATE … WHERE vocab_id=%s.
       u = <|"id" -> _, "fields" -> _Association|>. *)
    precede[coLabel["chAmend", binding[u]],
      call["CargoHold", updateEntry[entries, editingRow[u["id"]], u["fields"]]]]]]
