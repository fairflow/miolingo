(* ::Package:: *)

(* =====================================================================
   miolingo / L1 — ProgressTable value-functions, RECOVERED (function pass)
   ---------------------------------------------------------------------
   The function-recovery pass for ProgressTable: the stubs named in
   ProgressTableRecovered.wl (appendAttempt, statsOf, historyOf) and the
   writers' record builder (attemptRecord) get bodies RECOVERED from
   src/app_mysql.py (save_practice / get_user_stats / get_user_progress)
   and src/ui/history_tab.py — NOT invented. See
   spec/docs/function-recovery.md for the pass discipline.

   ADDITIVE: attaches downvalues to stub symbols only; does not modify
   ProgressTableRecovered.wl. Load AFTER it and BEFORE MioCore.wl (the
   helmView rule: mioCore's merge computes the initial projections
   eagerly, so statsOf[{}]/historyOf[{}] must already have bodies).

   RECORD SHAPE (save_practice's INSERT columns, app_mysql.py:1660):
     <|"language_code", "target_phrase", "recognized_phrase",
       "similarity_score", "perfect_match", "target_phonemes",
       "user_phonemes"|>
   user_id and practice_date are OUT OF THE MODEL (single-user L1; the DB
   stamps NOW[] — the clock is external; see the walk cloud).

   HELD-UNTIL-CONCRETE (the recognisedOf discipline, commit "hold the
   score symbolic"): while the ASR oracle is uninterpreted, evaluate[…]
   stays a symbolic term — so attemptRow stays held (gated on _Association)
   and the APPENDED RECORD is symbolic. The append τ still fires (the app
   always inserts); the stats/history projections then compute over the
   CONCRETE rows only and surface the symbolic ones as a "pending" count,
   keeping the views honest Associations rather than warning-panel stubs.
   ===================================================================== *)


(* --- attemptRecord[target, rec, tc] : the row a scoring chain writes ------
   What _persist_result (practice_tab.py:44) passes to save_practice, built
   from the SAME evaluate the chain wraps in scored[…] (value-passing CCS has
   no let; the duplicated evaluate term is the idiom, and with bodies loaded
   both occurrences compute identically). tc is the BORROWED target CODE the
   chain just pulled on targetRead (the NARROW read — scoring never consumes
   the source; ARCHITECTURE.md "The language pair is asymmetric") — the
   record carries it as language_code, which is what lets reads filter
   per-language WITHOUT borrowing at read time.
   NB the app's recognized_phrase is the ASR transcript TEXT — an oracle
   detail below the L1 boundary (function-recovery.md: L1 scores phonemes);
   the recognised PHONEME string stands in for it here. *)
attemptRow[r_Association, target_Association, tc_String] := <|
  "language_code"     -> tc,
  "target_phrase"     -> Lookup[target, "text", ""],
  "recognized_phrase" -> Lookup[r, "user", ""],
  "similarity_score"  -> Lookup[r, "similarity", 0],
  "perfect_match"     -> Lookup[r, "exact_match", False],
  "target_phonemes"   -> Lookup[r, "target", ""],
  "user_phonemes"     -> Lookup[r, "user", ""]|>;
attemptRecord[target_, rec_, tc_] :=
  attemptRow[evaluate[target, rec, tc], target, tc];

(* --- appendAttempt[records, r] : save_practice's INSERT (app_mysql.py:1628).
   Plain append — NO dedup/upsert (every attempt is a new row; contrast
   addEntry's INSERT … ON DUPLICATE KEY UPDATE). NOT gated on r_Association:
   the insert always happens in the app, so the τ always extends the log —
   a symbolic record is an honest "scored, oracle pending" row. *)
appendAttempt[records_List, r_] := Append[records, r];

(* --- statsOf[records] : get_user_stats (app_mysql.py:1736) ---------------
   the row COUNT, SUM of perfect_match, AVG of similarity_score, and the AVG
   over the last-10-by-practice_date subquery (insertion order stands in for
   the date ordering — same total order, no external clock needed). Keys mirror
   the app's dict ('total', 'perfect_count', 'avg_score', 'recent_avg').
   Aggregates run over the CONCRETE rows; symbolic (oracle-pending) rows
   are counted in "pending" rather than poisoning the numbers. No rows →
   None (the tab's "No practice history yet"), not the app's 0.0 coercion
   (a display choice, below L1). *)
statsOf[records_List] := Module[
  {c = Select[records, AssociationQ], scores},
  scores = Lookup[#, "similarity_score", 0] & /@ c;
  <|"total"         -> Length[records],
    "perfect_count" -> Count[c, r_ /; TrueQ[Lookup[r, "perfect_match", False]]],
    "avg_score"     -> If[scores === {}, None, Mean[scores]],
    "recent_avg"    -> If[scores === {}, None,
                          Mean[Take[scores, -Min[10, Length[scores]]]]],
    "pending"       -> Length[records] - Length[c]|>];

(* --- historyOf[records] : load_history (history_tab.py:20) ---------------
   get_user_progress ORDER BY practice_date DESC (newest first; insertion
   order reversed — same total order) with the per-practice fields the tab
   renders (history_tab.py:34). The app's LIMIT 100 and group-by-date are
   presentation over the external clock's stamp — below the L1 boundary.
   Concrete rows tabulate; oracle-pending rows surface as a count. *)
historyOf[records_List] := <|
  "total"    -> Length[records],
  "attempts" -> Reverse[Select[records, AssociationQ]],
  "pending"  -> Count[records, Except[_Association]]|>;
