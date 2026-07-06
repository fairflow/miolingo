(* ::Package:: *)

(* =====================================================================
   miolingo / L1 — ProgressTable (the attempt store), RECOVERED
   ---------------------------------------------------------------------
   Recovered from src/app_mysql.py (the `user_progress` MySQL table) +
   src/ui/statistics_tab.py + src/ui/history_tab.py, NOT invented. Every
   scored attempt in the app is persisted IMMEDIATELY by save_practice
   (app_mysql.py:1628, an INSERT INTO user_progress) from practice_tab's
   _persist_result (practice_tab.py:44) — and BOTH practice loops go
   through it: Quick Practice and Story practice mode share
   render_practice_interface (story_tab.py:279, quick_practice_tab.py:1030).
   ProgressTable is the agent that OWNS that persisted attempt log.

   (ProgressTable, per the ARCHITECTURE naming rule: store agents are named
   after their TABLE — user_progress — as VocabTable is after vocab_entries.
   This resolves the older "Ledger/AttemptTable" placeholder in the
   Component Inventory.)

   THE POINT (the † Stats/History note, ARCHITECTURE.md): stats and history
   were the flagged incompleteness — "view ports backed by store queries,
   not in-process state, not yet recovered". This is that recovery: the
   store OWNS the records; Statistics and History are PUBLISHED QUERY
   PROJECTIONS on the store (statsView / historyView), not standalone
   interactive agents and not state held by PS. PS/StoryReader only WRITE,
   through the restricted append channel — completing the data flow
     attempt_made · targetRead(τ) · progressAppend(τ)  →  records
     → statsView!(statsOf records) / historyView!(historyOf records).

   STATE: ProgressTable[records] — the persisted attempt log (list, in
   insertion order; the app's practice_date DESC read = newest-first, so
   reads reverse it).

   PORTS (mirror the user_progress SQL surface):
     progressRead!    always — emits the current records (a self-loop,
                  never changing ProgressTable). ≈ get_user_progress SELECT
                  (app_mysql.py:1700). No composed component pulls it yet,
                  so it stays EXTERNAL (the raw query surface); the first
                  internal borrower (e.g. a practise-weakest route) will
                  restrict it exactly as vocabRead is.
     progressAppend   record an attempt — save_practice's plain INSERT
                  (append-only: NO upsert — every attempt is a new row,
                  unlike vocabUpsert's dedup). ONE port, TWO writers sync
                  on it (the vocabUpsert precedent): PS.attempt_made and
                  StoryReader.story_attempt_made. RESTRICTED in mioCore —
                  only the scoring chains write, matching the app (the
                  insert happens inside _persist_result, not at any user-
                  facing surface).
     statsView!   always — get_user_stats (app_mysql.py:1736): total,
                  perfect_count, avg_score, recent_avg (last 10). A
                  query-backed view port (the Statistics tab's read).
     historyView! always — get_user_progress newest-first (history_tab.py:20
                  load_history). A query-backed view port (the History
                  tab's read).

   OUT OF THE MODEL (the walk cloud): user_id (L1 is single-user) and
   practice_date (the DB stamps NOW[] at insert — the CLOCK is external).
   Per-language filtering of the reads (get_user_stats/get_user_progress
   filter by the CURRENT language) is presentation over the published
   projection for now: records CARRY their language_code (baked in at
   write time from the langRead borrow), so the projection can be filtered
   downstream without borrowing at read time. The day a filtered-at-source
   query port is wanted, it enters as a value-carrying read (a query
   protocol) — the † rigging question, now concrete. (2026-07-06: the
   write-time borrow NARROWED to targetRead — records carry exactly the
   target code, the practice identity; see MioCore.wl.)

   LEAF agent (every branch loops back to ProgressTable) — no sub-agent
   expansion. Value-functions (appendAttempt/statsOf/historyOf/
   attemptRecord) live in ProgressFunctions.wl, loaded after (the
   *Functions.wl pattern); they resolve at step time.

   LOAD ORDER: RCA_core.wl, discipline.wl, then this (alongside the other
   recovered agents); ProgressFunctions.wl before MioCore.wl (mioCore's
   merge eagerly computes the initial projections — the helmView rule).
   ===================================================================== *)

defineAgent["ProgressTable", {records},
  choice[
    (* @src app_mysql.py:1700 (get_user_progress) — SELECT * FROM user_progress … *)
    precede[label["progressRead", param[records]],
      call["ProgressTable", records]],
    (* @src app_mysql.py:1628 (save_practice) — INSERT INTO user_progress …
       (plain INSERT: append-only, no dedup). Two writers: PS.attempt_made and
       StoryReader.story_attempt_made, both via _persist_result. *)
    precede[coLabel["progressAppend", binding[r]],
      call["ProgressTable", appendAttempt[records, r]]],
    (* @src app_mysql.py:1736 (get_user_stats) — the Statistics tab's numbers
       (statistics_tab.py:49): total, perfect_count, avg_score, recent_avg. *)
    precede[label["statsView", param[statsOf[records]]],
      call["ProgressTable", records]],
    (* @src history_tab.py:20 (load_history) — newest-first attempt log
       (grouping by practice_date is presentation over the external clock's
       stamp, so it stays below the L1 boundary). *)
    precede[label["historyView", param[historyOf[records]]],
      call["ProgressTable", records]]]]
