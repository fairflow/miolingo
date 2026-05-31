#!/usr/bin/env wolframscript
(* =====================================================================
   spec/tests/merge_defined_test.wls
   ---------------------------------------------------------------------
   Conformance of mergeDefined (compact, transNamed) against merge
   (canonical mu-term, transVP). Validates that the transition-time
   transNamed[relabel] engine change lets the call-based composition
   reproduce the mu-term composition's observable behaviour, far more
   compactly.

     1. external ready sets agree, and equal the documented set
     2. mioCoreD is much smaller than mioCore and stays call-based
        (free of mu / rvar), one step included
     3. the dual-tau deterministic walk runs on mioCoreD (transNamed):
        both vAdd and pLoad internal syncs fire
     4. the visible+tau label trace agrees with merge's (transVP)

   NB: $rca points at the relabel-transition-time WORKTREE (the engine
   change is not yet merged to feature-work). After the engine PR merges,
   revert $rca to the canonical RCA_core.wl path.

   Run headless:  wolframscript -file spec/tests/merge_defined_test.wls
   ===================================================================== *)

$rca  = "/Users/matthew/Projects/private/Mathematica/.claude/worktrees/relabel-transition-time/RCA/RCA_core.wl";
$spec = "/Users/matthew/Software/working/miolingo/spec/";

Quiet[Get[$rca]];
Get[$spec <> "discipline.wl"];
Get[$spec <> "PracticeSessionRecovered.wl"];
Get[$spec <> "VocabStoreRecovered.wl"];
Get[$spec <> "MioCore.wl"];

hr = StringRepeat["=", 70];
ok[b_]      := If[TrueQ[b], "OK", "*** FAIL ***"];
isTau[a_]   := MatchQ[a, tag[\[Tau], ___]] || a === \[Tau];
names[tr_]  := Sort[portName /@ (First /@ tr)];
lab[a_]     := If[MatchQ[a, tag[\[Tau], _, ___]], a[[2]], portName[a]];

mu0 = transVP[mioCore];
de0 = transNamed[mioCoreD];
expected = {"add", "import_bulk", "load_material", "pSView",
            "set_filter", "set_sort", "vSView"};

Print[hr]; Print["1. EXTERNAL READY-SET PARITY"]; Print[hr];
Print["   merge       (transVP)   : ", InputForm[names[mu0]]];
Print["   mergeDefined (transNamed): ", InputForm[names[de0]]];
Print["   agree?             ", ok[names[mu0] === names[de0]]];
Print["   equals documented? ", ok[names[de0] === expected]];

Print[hr]; Print["2. COMPACTNESS / CALL-BASED SUCCESSORS"]; Print[hr];
Print["   LeafCount mioCore  (mu-term)   : ", LeafCount[mioCore]];
Print["   LeafCount mioCoreD (call-based): ", LeafCount[mioCoreD]];
Print["   mioCoreD much smaller? ", ok[LeafCount[mioCoreD] < LeafCount[mioCore]/2]];
Print["   mioCoreD free of mu?   ", ok[FreeQ[mioCoreD, mu]]];
Print["   mioCoreD free of rvar? ", ok[FreeQ[mioCoreD, rvar]]];
With[{succ = Last[First[de0]]},
  Print["   one successor free of mu/rvar? ",
        ok[FreeQ[succ, mu] && FreeQ[succ, rvar]]]];

(* shared deterministic walk, parametrised by the transition function *)
findStep[tf_, s_, vis[nm_]]  := SelectFirst[tf[s], !isTau[First[#]] && portName[First[#]] === nm &];
findStep[tf_, s_, tau[ch_]] := SelectFirst[tf[s], MatchQ[First[#], tag[\[Tau], ch, ___]] &];
plan = {vis["set_filter"], vis["add"], vis["practise_filtered"], tau["pLoad"],
        vis["recording_made"], vis["attempt_made"], vis["capture_vocab"], tau["vAdd"]};
walk[tf_, s0_] := Module[{s = s0, labs = {}, t, stuck = False},
  Do[t = findStep[tf, s, p];
     If[MissingQ[t], stuck = True; Break[]];
     AppendTo[labs, lab[First[t]]];
     s = Last[t], {p, plan}];
  <|"labels" -> labs, "stuck" -> stuck|>];

Print[hr]; Print["3. DUAL-TAU WALK on mioCoreD (transNamed)"]; Print[hr];
wd = walk[transNamed, mioCoreD];
Print["   trace: ", InputForm[wd["labels"]]];
Print["   ran to completion? ", ok[! wd["stuck"]]];
Print["   pLoad tau fired?   ", ok[MemberQ[wd["labels"], "pLoad"]]];
Print["   vAdd  tau fired?   ", ok[MemberQ[wd["labels"], "vAdd"]]];

Print[hr]; Print["4. TRACE PARITY  merge(transVP) vs mergeDefined(transNamed)"]; Print[hr];
wm = walk[transVP, mioCore];
Print["   merge        trace: ", InputForm[wm["labels"]]];
Print["   mergeDefined trace: ", InputForm[wd["labels"]]];
Print["   agree? ", ok[wm["labels"] === wd["labels"]]];
Print[hr]; Print["done."];
