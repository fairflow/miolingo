#!/usr/bin/env wolframscript
(* =====================================================================
   spec/tests/internal_transitions_test.wls
   ---------------------------------------------------------------------
   A DETERMINISTIC walk over the composed mu-term `mioCore` that drives
   BOTH cross-component internal transitions (the vAdd and pLoad tau
   syncs hidden by the restriction). The earlier random walk never
   reached them because they only fire from specific states.

   One path hits both, because the two relays chain:

     VS: set_filter, add  ->  practise_vocab  --pLoad!-->  (tau)
         => PS receives practiseList[...] and becomes ACTIVE
     PS: recording_made, attempt_made  ->  capture_vocab  --vAdd!--> (tau)
         => VS receives the captured word

   Each tau step is INVISIBLE (isVisible -> False); the external
   triggers around them are visible. The walk picks each transition by
   port name (visible) or by tau channel (internal); if a step has no
   matching transition it prints the ready set and stops, so a failure
   is localised to the exact step.

   Run headless:  wolframscript -file spec/tests/internal_transitions_test.wls
   ===================================================================== *)

Get[FileNameJoin[{ParentDirectory[DirectoryName[$InputFileName]], "paths.wl"}]];

loadEngine[];
loadRecoveredBase[];
mioGet["MioCore.wl"];

hr = StringRepeat["=", 70];
isTau[a_] := MatchQ[a, tag[\[Tau], ___]] || a === \[Tau];

(* The plan lists only EXTERNAL triggers; "AutoTau" -> True fires the internal
   syncs (chRead before each VS action, chUpsert on capture, pLoad/vAdd relays,
   langRead for scoring) between them. The recorded action log therefore contains
   the internal taus, so we confirm pLoad and vAdd actually fired. *)
lab[a_] := If[MatchQ[a, tag[\[Tau], _, ___]], a[[2]], portName[a]];
plan = {vis["open_vocab"], vis["set_filter"], vis["add"], vis["practise_vocab"],
        vis["recording_made"], vis["attempt_made"], vis["capture_vocab"]};

Print[hr];
Print["DETERMINISTIC WALK over mioCore  (external triggers; internal taus auto-fired)"];
Print[hr];

w = walkSteps[transVP, mioCore, plan, "AutoTau" -> True];
labels = lab /@ w["actions"];
failed = w["stuck"];
sawPLoad = MemberQ[labels, "pLoad"];
sawVAdd  = MemberQ[labels, "vAdd"];
Print["trace: ", InputForm[labels]];

Print[hr];
Print["pLoad tau taken (VS --practiseList--> PS) ? ", If[sawPLoad, "OK", "*** FAIL ***"]];
Print["vAdd  tau taken (PS --word--> VS)         ? ", If[sawVAdd,  "OK", "*** FAIL ***"]];
Print["walk completed without a stuck step       ? ", If[!failed, "OK", "*** FAIL ***"]];
Print[hr];
