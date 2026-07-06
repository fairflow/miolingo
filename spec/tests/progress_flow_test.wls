#!/usr/bin/env wolframscript
(* =====================================================================
   spec/tests/progress_flow_test.wls
   ---------------------------------------------------------------------
   THE ATTEMPT-LOG FLOW, made a CHECKED CONTRACT.

   ProgressTable OWNS the persisted attempt log (the app's user_progress
   table); every scored attempt is WRITTEN to it as part of scoring — the
   chain attempt_made · langRead(τ) · progressAppend(τ) — and Statistics /
   History are the store's query projections (statsView / historyView),
   not state held by PS. This was the † Stats/History incompleteness
   (ARCHITECTURE.md); this test pins the recovered flow so a future
   re-derivation that drops the write, lets PS hoard the log, or exposes
   the append channel externally fails LOUDLY.

   What it pins (both compositions — mioCore/transVP, mioCoreD/transNamed):
     1. BOUNDARY   : progressAppend is RESTRICTED (not in the external
                     ready set); progressRead / statsView / historyView ARE
                     external (the query surface).
     2. THE WRITE  : attempt_made fires the progressAppend τ; the store's
                     projections then show total = 1.
     3. HELD       : with the ASR oracle uninterpreted the appended row is
                     SYMBOLIC — statsView stays an honest Association
                     (total counts it, pending marks it, averages None) and
                     the row still CARRIES the borrowed language pair.
     4. TWO WRITERS: story_attempt_made appends through the SAME channel
                     (the vocabUpsert two-writer precedent).
     5. CONCRETE   : with a test ASR downvalue the numeric pipeline runs
                     end-to-end — perfect_count / avg_score / recent_avg
                     compute, historyView tabulates the row, and the row's
                     language_code is the borrowed target.

   Run headless:  wolframscript -file spec/tests/progress_flow_test.wls
   ===================================================================== *)

$dir = ParentDirectory[DirectoryName[$InputFileName]] <> "/";
Get[$dir <> "MiolingoSpec.wl"];
Get[$dir <> "walk.wl"];

allOk = True;
assert[lbl_, b_] := (allOk = allOk && TrueQ[b]; Print["   ", If[TrueQ[b], "ok  ", "FAIL "], lbl]);
hr = StringRepeat["=", 70];

ph = {<|"text" -> "chat", "translation" -> "cat", "ipa" -> "ʃa"|>};
appends[w_] := Cases[w["actions"], tag[_, "progressAppend", _]];
proj[tf_, w_] := viewProjections[tf, Last[w["states"]]];

Do[Module[{tf = pair[[1]], sys = pair[[2]], nm = pair[[3]], names, w, p, st, hi},

  Print[hr]; Print["=== on ", nm]; Print[hr];

  Print["1. boundary — append restricted, query surface external"];
  names = ToString /@ portName /@ First /@ readyTransitions[tf, sys];
  assert["progressAppend is NOT externally ready (restricted)",
    ! MemberQ[names, "progressAppend"]];
  assert["progressRead / statsView / historyView ARE external",
    SubsetQ[names, {"progressRead", "statsView", "historyView"}]];

  Print["2. the write — scoring appends to the store"];
  w = walkSteps[tf, sys,
        {vis["load_material", ph], vis["recording_made", "a"], vis["attempt_made"]},
        "AutoTau" -> True];
  assert["walk completed", ! w["stuck"]];
  assert["exactly one progressAppend τ fired", Length[appends[w]] === 1];
  p = proj[tf, w];
  st = p["statsView"];
  assert["statsView.total = 1 (the attempt is in the store)", st["total"] === 1];

  Print["3. held — symbolic row while the oracle is uninterpreted"];
  assert["the row is oracle-pending, not fake-scored", st["pending"] === 1];
  assert["averages stay None (no concrete score to aggregate)",
    st["avg_score"] === None && st["recent_avg"] === None];
  hi = p["historyView"];
  assert["historyView counts it but does not tabulate it",
    hi["total"] === 1 && hi["attempts"] === {} && hi["pending"] === 1];
  assert["the pending row CARRIES the borrowed target code \"fr\"",
    MemberQ[Cases[w["actions"], tag[_, "progressAppend", s_] :> (r /. s)],
      row_ /; ! FreeQ[row, "fr"]]];

  Print["4. two writers — story practice appends via the SAME channel"];
  w = walkSteps[tf, sys,
        {vis["set_mode", practice], vis["story_recording_made", "a"],
         vis["story_attempt_made"]},
        "AutoTau" -> True];
  assert["story walk completed", ! w["stuck"]];
  assert["story_attempt_made fired progressAppend", Length[appends[w]] === 1];
  assert["the store shows the story attempt (total = 1)",
    proj[tf, w]["statsView"]["total"] === 1]],

  {pair, {{transVP, mioCore, "mioCore (transVP)"},
          {transNamed, mioCoreD, "mioCoreD (transNamed)"}}}];

Print[hr]; Print["5. concrete — test ASR downvalue, numeric pipeline end-to-end"]; Print[hr];
(* the world plays back a perfect transcript: the recognised phonemes ARE the
   target IPA (the speaker_test round-trip shape, as a plain test downvalue) *)
recognisePhonemes[audio_String, lang_String] := "ʃa";
w5 = walkSteps[transNamed, mioCoreD,
       {vis["load_material", ph], vis["recording_made", "a"], vis["attempt_made"]},
       "AutoTau" -> True];
p5 = proj[transNamed, w5];
st5 = p5["statsView"]; hi5 = p5["historyView"];
assert["total 1, nothing pending", st5["total"] === 1 && st5["pending"] === 0];
assert["perfect match counted", st5["perfect_count"] === 1];
assert["avg_score = 1. (exact repetition)", st5["avg_score"] == 1];
assert["recent_avg = 1.", st5["recent_avg"] == 1];
row5 = First[hi5["attempts"], None];
assert["historyView tabulates the row", AssociationQ[row5]];
assert["row carries the borrowed language_code \"fr\"",
  AssociationQ[row5] && row5["language_code"] === "fr"];
assert["row records the target phrase",
  AssociationQ[row5] && row5["target_phrase"] === "chat"];
assert["row records both phoneme strings",
  AssociationQ[row5] && row5["target_phonemes"] === "ʃa" && row5["user_phonemes"] === "ʃa"];

Print[hr];
Print["ALL ASSERTIONS: ", If[allOk, "OK", "*** FAIL ***"]];
Print[hr];
If[!allOk, Exit[1]];
