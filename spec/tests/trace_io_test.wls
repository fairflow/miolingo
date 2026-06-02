#!/usr/bin/env wolframscript
(* =====================================================================
   spec/tests/trace_io_test.wls
   ---------------------------------------------------------------------
   Trace I/O round-trips: that a walk on mioCoreD (transNamed) can be
   exported and re-imported in three forms and faithfully replayed:

     A. raw recorded actions -> replayTrace reproduces the run
     B. a portable plan (vis/tau labels) -> walkSteps re-derives the
        identical actions (values re-derived from labels alone)
     C. a rendered TEXT trace (eventLogForm) -> parseEventLog/importTrace
        recovers the plan and re-running reproduces the actions
     D. cross-engine parity: the same plan run through mioCore/transVP
        and mioCoreD/transNamed yields identical event logs

   replayTrace / walk need engine PR #36; loadEngine[] (spec/paths.wl) asserts
   the engine checkout contains it via the $minEngineSha guard and aborts with
   a clear message if not — replacing the old hand-rolled fallback that reached
   into a feature worktree.

   Run headless:  wolframscript -file spec/tests/trace_io_test.wls
   ===================================================================== *)

Get[FileNameJoin[{ParentDirectory[DirectoryName[$InputFileName]], "paths.wl"}]];

loadEngine[];
loadRecoveredBase[];
mioGet["MioCore.wl"];

hr      = StringRepeat["=", 70];
ok[b_] := If[TrueQ[b], "OK", "*** FAIL ***"];

(* the known dual-tau deterministic plan (see merge_defined_test.wls) *)
plan = {vis["set_filter"], vis["add"], vis["practise_vocab"], tau["pLoad"],
        vis["recording_made"], vis["attempt_made"], tau["langRead"], vis["capture_vocab"], tau["vAdd"]};

(* NB: do NOT name any variable `w` — the spec's agent equations use the
   bare symbol `w` as a value binder (binding[w]); assigning to w here would
   substitute it into every recorded action and corrupt the trace. Use wlk. *)
wlk = walkSteps[transNamed, mioCoreD, plan];

(* temp files *)
tmpfile  = FileNameJoin[{$TemporaryDirectory, "trace_io_actions.m"}];
tmpfile2 = FileNameJoin[{$TemporaryDirectory, "trace_io_plan.m"}];
txtfile  = FileNameJoin[{$TemporaryDirectory, "trace_io_text.txt"}];

Print[hr]; Print["A. FAITHFUL ROUND-TRIP via replayTrace"]; Print[hr];
Put[wlk["actions"], tmpfile];
acts = Get[tmpfile];
r = replayTrace[mioCoreD, acts, "TransitionFunction" -> transNamed];
Print["   replay ok?            ", ok[r["ok"]]];
Print["   steps === plan length? ", ok[r["steps"] === Length[plan]]];
Print["   final state matches?   ", ok[r["final"] === Last[wlk["states"]]]];

Print[hr]; Print["B. PORTABLE-PLAN ROUND-TRIP"]; Print[hr];
Put[plan, tmpfile2];
wlk2 = walkSteps[transNamed, mioCoreD, Get[tmpfile2]];
Print["   actions re-derived from labels? ", ok[wlk2["actions"] === wlk["actions"]]];

Print[hr]; Print["C. TEXT GOLDEN + parser ROUND-TRIP"]; Print[hr];
txt = eventLogForm[eventLog[wlk]];
Export[txtfile, txt, "Text"];
plan2 = importTrace[txtfile];
Print["   plan2 === plan?        ", ok[plan2 === plan]];
wlk3 = walkSteps[transNamed, mioCoreD, plan2];
Print["   text->plan->replay actions match? ", ok[wlk3["actions"] === wlk["actions"]]];

Print[hr]; Print["D. CROSS-ENGINE PARITY  transVP vs transNamed"]; Print[hr];
logVP = eventLog[walkSteps[transVP, mioCore, plan]];
logND = eventLog[walkSteps[transNamed, mioCoreD, plan]];
polSeq[log_] := {#["port"], #["polarity"]} & /@ log;
Print["   event logs identical? ", ok[polSeq[logVP] === polSeq[logND]]];

(* cleanup *)
DeleteFile /@ Select[{tmpfile, tmpfile2, txtfile}, FileExistsQ];

Print[hr]; Print["done."];
