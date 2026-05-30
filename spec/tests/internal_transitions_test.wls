#!/usr/bin/env wolframscript
(* =====================================================================
   spec/tests/internal_transitions_test.wls
   ---------------------------------------------------------------------
   A DETERMINISTIC walk over the composed mu-term `mioCore` that drives
   BOTH cross-component internal transitions (the vAdd and pLoad tau
   syncs hidden by the restriction). The earlier random walk never
   reached them because they only fire from specific states.

   One path hits both, because the two relays chain:

     VS: set_filter, add  ->  practise_filtered  --pLoad!-->  (tau)
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

$rca  = "/Users/matthew/Projects/private/Mathematica/RCA/RCA_core.wl";
$spec = "/Users/matthew/Software/working/miolingo/spec/";

Quiet[Get[$rca]];
Get[$spec <> "discipline.wl"];
Get[$spec <> "PracticeSessionRecovered.wl"];
Get[$spec <> "VocabStoreRecovered.wl"];
Get[$spec <> "MioCore.wl"];

bar = StringRepeat["=", 70];
isTau[a_] := MatchQ[a, tag[\[Tau], ___]] || a === \[Tau];

(* a plan entry is  vis["port"]  (an external action, visible)
                 or tau["chan"]  (an internal sync on that channel)      *)
findStep[s_, vis[nm_]]  := SelectFirst[transVP[s], !isTau[First[#]] && portName[First[#]] === nm &];
findStep[s_, tau[ch_]] := SelectFirst[transVP[s], MatchQ[First[#], tag[\[Tau], ch, ___]] &];

plan = {
  vis["set_filter"], vis["add"], vis["practise_filtered"], tau["pLoad"],
  vis["recording_made"], vis["attempt_made"], vis["capture_vocab"], tau["vAdd"]
};

Print[bar];
Print["DETERMINISTIC WALK over mioCore  (visible triggers + internal taus)"];
Print[bar];

state = mioCore;
sawPLoad = False; sawVAdd = False; failed = False;
Do[
  Module[{spec = plan[[k]], t},
    t = findStep[state, spec];
    If[MissingQ[t],
      failed = True;
      Print["step ", k, "  *** NO TRANSITION for ", InputForm[spec], " ***"];
      Print["   ready now: ",
            InputForm[Sort[portName /@ (First /@ transVP[state])]]];
      Break[]];
    Module[{act = First[t], vq},
      vq = !isTau[act];
      If[MatchQ[spec, tau["pLoad"]], sawPLoad = True];
      If[MatchQ[spec, tau["vAdd"]],  sawVAdd  = True];
      Print["step ", StringPadLeft[ToString[k], 2], "  ",
            If[vq, "[vis] ", "[TAU] "], InputForm[act]];
      state = Last[t]];
  ],
  {k, Length[plan]}];

Print[bar];
Print["pLoad tau taken (VS --practiseList--> PS) ? ", If[sawPLoad, "OK", "*** FAIL ***"]];
Print["vAdd  tau taken (PS --word--> VS)         ? ", If[sawVAdd,  "OK", "*** FAIL ***"]];
Print["walk completed without a stuck step       ? ", If[!failed, "OK", "*** FAIL ***"]];
Print[bar];
