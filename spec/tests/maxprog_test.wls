#!/usr/bin/env wolframscript
(* =====================================================================
   spec/tests/maxprog_test.wls
   ---------------------------------------------------------------------
   autoTau[tf, s] — the walk harness's MAXIMAL-PROGRESS strategy. A
   SIMULATION strategy over the existing LTS (not a language change): fire
   the unique enabled internal tau until the state is tau-stable, stopping
   if >= 2 taus are ready (a real choice is never silently resolved).

   Checks, on BOTH mioCore (transVP) and mioCoreD (transNamed):
     - a state with one pending internal sync (vocabUpsert, just after capture_vocab)
       has exactly one ready tau;
     - autoTau fires it (one recorded event, polarity "tau", the vocabUpsert channel)
       and reaches a tau-stable state;
     - autoTau is a no-op on an already tau-stable state;
     - every fired tau is recorded with its pre-state (Back-steppable).

   Run headless:  wolframscript -file spec/tests/maxprog_test.wls
   ===================================================================== *)

$dir = ParentDirectory[DirectoryName[$InputFileName]] <> "/";
Get[$dir <> "MiolingoSpec.wl"];
Get[$dir <> "walk.wl"];

ok[b_] := If[TrueQ[b], "OK", "*** FAIL ***"];
allOk = True;
assert[lbl_, b_] := (allOk = allOk && TrueQ[b]; Print["   ", If[TrueQ[b], "ok  ", "FAIL "], lbl]);
hr = StringRepeat["=", 70];

readyTaus[tf_, s_] := Select[readyTransitions[tf, s], isTauAct[First[#]] &];

(* drive to just AFTER capture_vocab — PS is now mid-relay (vocabUpsert!) and Vocab is at
   its vocabRead prefix, so an internal tau is pending. Under the (i) store form the
   capture relay is a SEQUENCE of taus: vocabRead (Vocab reads) → vocabUpsert (PS→Vocab) → vocabUpsert
   (Vocab→store) → vocabRead — autoTau fires them to stability, landing the word in the
   store. (Setup plan keeps the explicit langRead; it is PS-side, no AutoTau.) *)
plan = {vis["load_material", {<|"text" -> "chat", "translation" -> "cat", "ipa" -> "S"|>}],
        vis["recording_made", "audio"], vis["attempt_made"], tau["langRead"], vis["capture_vocab", "chat"]};

check[label_, tf_, s0_] := Module[{s, a, stable},
  Print[hr]; Print[label]; Print[hr];
  s = Last[walkSteps[tf, s0, plan]["states"]];
  assert["an internal tau is pending after capture_vocab", Length[readyTaus[tf, s]] >= 1];
  a = autoTau[tf, s];
  assert["autoTau fired >=1 event, all taus",
    Length[a["events"]] >= 1 && AllTrue[a["events"], #["polarity"] === "tau" &]];
  assert["one recorded pre-state per fired tau (Back-steppable)",
    Length[a["states"]] === Length[a["events"]]];
  stable = a["state"];
  assert["resulting state is tau-stable (no tau ready)", readyTaus[tf, stable] === {}];
  assert["autoTau is a no-op on a tau-stable state",
    autoTau[tf, stable]["events"] === {} && autoTau[tf, stable]["states"] === {}];
  (* the relay completed: the capture wrote to the store via the vocabUpsert tau
     (PS.capture_vocab -> vocabUpsert -> VocabTable; viewing it would need open_vocab) *)
  assert["the capture relay fired (vocabUpsert tau among the auto-fired events)",
    AnyTrue[a["events"], StringContainsQ[ToString[#["port"]], "vocabUpsert"] &]];];

check["1. mioCore  (transVP)",   transVP,   mioCore];
check["2. mioCoreD (transNamed)", transNamed, mioCoreD];

Print[hr];
Print["ALL ASSERTIONS: ", ok[allOk]];
Print[hr];
If[!allOk, Exit[1]];
