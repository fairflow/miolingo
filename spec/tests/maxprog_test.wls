#!/usr/bin/env wolframscript
(* =====================================================================
   spec/tests/maxprog_test.wls
   ---------------------------------------------------------------------
   autoTau[tf, s] — the walk harness's MAXIMAL-PROGRESS strategy. A
   SIMULATION strategy over the existing LTS (not a language change): fire
   the unique enabled internal tau until the state is tau-stable, stopping
   if >= 2 taus are ready (a real choice is never silently resolved).

   Checks, on BOTH mioCore (transVP) and mioCoreD (transNamed):
     - a state with one pending internal sync (vAdd, just after capture_vocab)
       has exactly one ready tau;
     - autoTau fires it (one recorded event, polarity "tau", the vAdd channel)
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

(* drive to just AFTER capture_vocab, BEFORE the vAdd tau *)
plan = {vis["load_material", {<|"text" -> "chat", "translation" -> "cat", "ipa" -> "S"|>}],
        vis["recording_made", "audio"], vis["attempt_made"], vis["capture_vocab", "chat"]};

check[label_, tf_, s0_] := Module[{s, taus, a, stable},
  Print[hr]; Print[label]; Print[hr];
  s = Last[walkSteps[tf, s0, plan]["states"]];
  taus = readyTaus[tf, s];
  assert["exactly one tau (vAdd) pending after capture_vocab", Length[taus] === 1];
  (* channel rep is incidental (symbol / string / label[]); match on its text *)
  assert["that tau's channel is vAdd",
    StringContainsQ[ToString[eventOf[First[First[taus]]]["port"]], "vAdd"]];
  a = autoTau[tf, s];
  assert["autoTau fired exactly one event", Length[a["events"]] === 1];
  assert["fired event polarity is tau", First[a["events"]]["polarity"] === "tau"];
  assert["fired event port is vAdd",
    StringContainsQ[ToString[First[a["events"]]["port"]], "vAdd"]];
  assert["one pre-state recorded (Back-steppable)", Length[a["states"]] === 1];
  stable = a["state"];
  assert["resulting state is tau-stable (no tau ready)", readyTaus[tf, stable] === {}];
  assert["autoTau is a no-op on a tau-stable state",
    autoTau[tf, stable]["events"] === {} && autoTau[tf, stable]["states"] === {}];];

check["1. mioCore  (transVP)",   transVP,   mioCore];
check["2. mioCoreD (transNamed)", transNamed, mioCoreD];

Print[hr];
Print["ALL ASSERTIONS: ", ok[allOk]];
Print[hr];
If[!allOk, Exit[1]];
