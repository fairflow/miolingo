#!/usr/bin/env wolframscript
(* =====================================================================
   spec/tests/walk_sequences_test.wls
   ---------------------------------------------------------------------
   The standing invariant for the walk test batch (spec/walk-tests.wl):
   EVERY named sequence in walkTests runs to completion (not stuck, all
   actions fire) on BOTH compositions —
       mioCore  via transVP   (mu-term)
       mioCoreD via transNamed (call form)
   — with its embedded values, so the GUI's "Run test" menu and walkSteps
   both replay them with no typing. Also checks the value-carrying ports
   actually computed (a captured word reaches the VS entries via the
   vAdd sync; a practise relay reaches the PS queue via pLoad).

   Run headless:  wolframscript -file spec/tests/walk_sequences_test.wls
   ===================================================================== *)

$dir = ParentDirectory[DirectoryName[$InputFileName]] <> "/";
Get[$dir <> "MiolingoSpec.wl"];
Get[$dir <> "walk.wl"];   (* loads walk-tests.wl -> walkTests *)

ok[b_] := If[TrueQ[b], "OK", "*** FAIL ***"];
allOk = True;
assert[lbl_, b_] := (allOk = allOk && TrueQ[b]; Print["   ", If[TrueQ[b], "ok  ", "FAIL "], lbl]);
hr = StringRepeat["=", 70];

Print[hr]; Print["walkTests batch loaded"]; Print[hr];
assert["walkTests is defined and non-empty", AssociationQ[walkTests] && Length[walkTests] > 0];
assert["walkTests::usage is set (?walkTests works)", StringQ[walkTests::usage]];
assert["loadEngine::usage is set (?loadEngine works)", StringQ[loadEngine::usage]];
assert["walkUI::usage is set", StringQ[walkUI::usage]];

Print[hr]; Print["every sequence completes on BOTH mioCore and mioCoreD"]; Print[hr];
(* plans list only external actions; "AutoTau" -> True fires the internal syncs
   between steps, so we check completion (not stuck) — the action count now
   includes the auto-fired taus, so it exceeds Length[plan]. *)
runs[tf_, s0_, plan_] := Module[{w = walkSteps[tf, s0, plan, "AutoTau" -> True]},
  !w["stuck"] && Length[w["actions"]] >= Length[plan]];
Do[Module[{plan = walkTests[k]},
   assert[StringPadRight[k, 16] <> " on mioCore (transVP)",   runs[transVP, mioCore, plan]];
   assert[StringPadRight[k, 16] <> " on mioCoreD (transNamed)", runs[transNamed, mioCoreD, plan]]],
  {k, Keys[walkTests]}];

Print[hr]; Print["syncs actually move data across components"]; Print[hr];
(* sync-vadd: a captured word ends up in the VS entries via vAdd *)
vsEntriesAfter[plan_] := Module[{s = Last[walkSteps[transVP, mioCore, plan, "AutoTau" -> True]["states"]], vp},
  vp = Map[Identity, viewProjections[transVP, s]];
  If[KeyExistsQ[vp, "vSView"], #["word"] & /@ vp["vSView"]["entries"], $Failed]];
assert["sync-vadd: captured \"chat\" reaches VS entries",
  MemberQ[vsEntriesAfter[walkTests["sync-vadd"]], "chat"]];
(* sync-pload: the practise relay loads PS (pSView total > 0) *)
psTotalAfter[plan_] := Module[{s = Last[walkSteps[transVP, mioCore, plan, "AutoTau" -> True]["states"]], vp},
  vp = Map[Identity, viewProjections[transVP, s]];
  If[KeyExistsQ[vp, "pSView"], vp["pSView"]["total"], $Failed]];
assert["sync-pload: practise relay loads the PS queue (total > 0)",
  TrueQ[psTotalAfter[walkTests["sync-pload"]] > 0]];

Print[hr];
Print["ALL ASSERTIONS: ", ok[allOk]];
Print[hr];
If[!allOk, Exit[1]];
