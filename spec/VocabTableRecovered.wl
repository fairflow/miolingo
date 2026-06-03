(* ::Package:: *)

(* =====================================================================
   miolingo / L1 — VocabTable (the external store), RECOVERED
   ---------------------------------------------------------------------
   Recovered from src/vocab.py + src/app_mysql.py (the MySQL persistence
   layer), NOT invented. Every vocab operation in the app opens a
   connection (app_mysql.get_connection) and runs SQL against the
   `vocab_entries` table — capture (INSERT … ON DUPLICATE KEY UPDATE),
   list (SELECT), delete (DELETE), update (UPDATE). VocabTable is the agent
   that OWNS that persisted collection.

   (VocabTable, not Hold: `Hold` is a Wolfram built-in. Nautical theme —
   Helm steers, the cargo hold stores.)

   THE POINT (single source of truth; ARCHITECTURE.md "Borrowed vs owned
   data" / the Stats-History † note): the persisted collection is OWNED here,
   not in Vocab. Vocab holds only its UI parameters (sort/filter/editing)
   and READS the collection from VocabTable at the point of use — see PR-2,
   the (i) migration. This file (PR-1) DEFINES VocabTable standalone; it is
   loaded but NOT yet composed into mioCore (so no dual state until Vocab is
   migrated to read it).

   STATE: VocabTable[entries]   — entries : the persisted collection (list)

   PORTS (mirror the vocab.py SQL surface; see cargohold-recovery.md):
     vocabRead!    always — emits the current collection (a self-loop, never
                changing VocabTable). The READ a client pulls. ≈ list_vocab SELECT.
     vocabUpsert   capture a word — INSERT … ON DUPLICATE KEY UPDATE
                (dedup/bump): the recovered addEntry IS this upsert.
     vocabImport   bulk capture — importInto (parse + fold upserts).
     vocabRemove   delete by id — DELETE.
     vocabAmend    update fields by id — UPDATE. Carries <|"id"->_, "fields"->_|>.

   When composed (PR-2), vocabRead/vocabUpsert/vocabRemove/vocabAmend are RESTRICTED in
   mioCore (internal taus), and Vocab reads/writes through them.

   LEAF agent (every branch loops back to VocabTable) — no sub-agent expansion.
   Reuses the already-recovered collection transforms (addEntry/deleteFrom/
   updateEntry, VocabFunctions.wl) — they apply HERE now, where the data
   lives. autofill's enrichment (oracle + borrowed language) is deferred to the
   migration, so vocabAmend covers plain field updates for now.

   LOAD ORDER: RCA_core.wl, discipline.wl, then this (alongside the other
   recovered agents). Functions resolve at step time, as for the other agents.
   ===================================================================== *)

defineAgent["VocabTable", {entries},
  choice[
    (* @src vocab.py:195 (list_vocab) — SELECT * FROM vocab_entries WHERE … *)
    precede[label["vocabRead", param[entries]],
      call["VocabTable", entries]],
    (* @src vocab.py:106 (capture_vocab_entry) — INSERT … ON DUPLICATE KEY UPDATE.
       addEntry is the recovered upsert (dedup + times_seen bump). ONE vocabUpsert
       port, TWO writers sync on it: the Vocab tab (type/paste add) and PS capture
       (capture from practice writes the store DIRECTLY, not through the tab — a
       direct DB write, vocabulary_tab.py:7). Formerly two channels (chUpsert + vAdd);
       collapsed at the per-table rename since both are the same upsert. *)
    precede[coLabel["vocabUpsert", binding[w]],
      call["VocabTable", addEntry[entries, w]]],
    (* @src vocab.py:453 (import_from_file_contents) — bulk capture *)
    precede[coLabel["vocabImport", binding[f]],
      call["VocabTable", importInto[entries, f]]],
    (* @src vocab.py:301 (delete_vocab_entry) — DELETE … WHERE vocab_id=%s *)
    precede[coLabel["vocabRemove", binding[id]],
      call["VocabTable", deleteFrom[entries, id]]],
    (* @src vocab.py:343 (update_vocab_entry) — UPDATE … WHERE vocab_id=%s.
       u = <|"id" -> _, "fields" -> _Association|>. *)
    precede[coLabel["vocabAmend", binding[u]],
      call["VocabTable", updateEntry[entries, editingRow[u["id"]], u["fields"]]]]]]
