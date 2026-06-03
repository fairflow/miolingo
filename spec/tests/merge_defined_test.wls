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

   Engine + paths come from spec/paths.wl; loadEngine[] asserts the engine
   checkout has the transNamed[relabel] change (#35) this test needs, via
   the $minEngineSha guard — no more hand-pointing $rca at a worktree.

   Run headless:  wolframscript -file spec/tests/merge_defined_test.wls
   ===================================================================== *)

Get[FileNameJoin[{ParentDirectory[DirectoryName[$InputFileName]], "paths.wl"}]];

loadEngine[];
loadRecoveredBase[];
mioGet["MioCore.wl"];

hr = StringRepeat["=", 70];
ok[b_]      := If[TrueQ[b], "OK", "*** FAIL ***"];
isTau[a_]   := MatchQ[a, tag[\[Tau], ___]] || a === \[Tau];
names[tr_]  := Sort[portName /@ (First /@ tr)];
lab[a_]     := If[MatchQ[a, tag[\[Tau], _, ___]], a[[2]], portName[a]];

mu0 = transVP[mioCore];      (* raw transitions — used by the compactness checks *)
de0 = transNamed[mioCoreD];
(* Under the (i) external-store form VS GATES behind an internal chRead: at the
   raw initial state VS offers nothing externally (only the chRead τ). SETTLE that
   τ (maximal progress), then the external ready set is the familiar one — and
   merge (transVP) and mergeDefined (transNamed) settle to the SAME set. *)
settled[tf_, s0_]   := Last[walkSteps[tf, s0, {}, "AutoTau" -> True]["states"]];
extNames[tf_, s_]   := Sort[portName /@ Select[First /@ tf[s], ! isTau[#] &]];
muNames = extNames[transVP,   settled[transVP,   mioCore]];
deNames = extNames[transNamed, settled[transNamed, mioCoreD]];
(* VS now gates behind a VISIBLE open_vocab (the tab entry), so at the (stable)
   initial state VS contributes only open_vocab — its CRUD/view appear once the
   tab is opened. Helm's set_speed is espeak-only (tts=google). *)
expected = {"helmView", "load_material", "open_vocab", "pSView",
            "set_source", "set_target", "set_tts"};

Print[hr]; Print["1. EXTERNAL READY-SET PARITY (settled past the chRead τ)"]; Print[hr];
Print["   merge       (transVP)   : ", InputForm[muNames]];
Print["   mergeDefined (transNamed): ", InputForm[deNames]];
Print["   agree?             ", ok[muNames === deNames]];
Print["   equals documented? ", ok[deNames === expected]];

Print[hr]; Print["2. COMPACTNESS / CALL-BASED SUCCESSORS"]; Print[hr];
Print["   LeafCount mioCore  (mu-term)   : ", LeafCount[mioCore]];
Print["   LeafCount mioCoreD (call-based): ", LeafCount[mioCoreD]];
Print["   mioCoreD much smaller? ", ok[LeafCount[mioCoreD] < LeafCount[mioCore]/2]];
Print["   mioCoreD free of mu?   ", ok[FreeQ[mioCoreD, mu]]];
Print["   mioCoreD free of rvar? ", ok[FreeQ[mioCoreD, rvar]]];
With[{succ = Last[First[de0]]},
  Print["   one successor free of mu/rvar? ",
        ok[FreeQ[succ, mu] && FreeQ[succ, rvar]]]];

(* shared deterministic walk, parametrised by the transition function. Plan lists
   only EXTERNAL actions; "AutoTau" fires the internal syncs (chRead/chUpsert/
   pLoad/langRead/vAdd) between them, so the label trace includes those τs and we
   can confirm pLoad/vAdd fired. *)
plan = {vis["open_vocab"], vis["set_filter"], vis["add"], vis["practise_vocab"],
        vis["recording_made"], vis["attempt_made"], vis["capture_vocab"]};
walk[tf_, s0_] := Module[{w = walkSteps[tf, s0, plan, "AutoTau" -> True]},
  <|"labels" -> (lab /@ w["actions"]), "stuck" -> w["stuck"]|>];

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
