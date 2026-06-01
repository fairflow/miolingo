#!/usr/bin/env wolframscript
(* =====================================================================
   spec/tests/grouping_test.wls
   ---------------------------------------------------------------------
   The walk harness's transition-grouping substrate: componentPortMap (port
   -> providing agent, by a pure syntactic sort scan), transGroup (which frame
   a ready transition belongs in) and inputsFirst (inputs before outputs).
   A walk-UI affordance, but the logic is pure and headless-testable.

   Run headless:  wolframscript -file spec/tests/grouping_test.wls
   ===================================================================== *)

$dir = ParentDirectory[DirectoryName[$InputFileName]] <> "/";
Get[$dir <> "MiolingoSpec.wl"];
Get[$dir <> "walk.wl"];

ok[b_] := If[TrueQ[b], "OK", "*** FAIL ***"];
allOk = True;
assert[lbl_, b_] := (allOk = allOk && TrueQ[b]; Print["   ", If[TrueQ[b], "ok  ", "FAIL "], lbl]);
hr = StringRepeat["=", 70];

pm = componentPortMap[mioComponents];

Print[hr]; Print["1. componentPortMap — each external port to its owning agent"]; Print[hr];
assert["add -> VS",            pm["add"] === "VS"];
assert["import_bulk -> VS",    pm["import_bulk"] === "VS"];
assert["load_material -> PS",  pm["load_material"] === "PS"];
assert["set_target -> Helm",   pm["set_target"] === "Helm"];
assert["set_speed -> Helm",    pm["set_speed"] === "Helm"];
(* the view ports are renamed per agent to match the composition *)
assert["pSView -> PS",   pm["pSView"] === "PS"];
assert["vSView -> VS",   pm["vSView"] === "VS"];
assert["helmView -> Helm", pm["helmView"] === "Helm"];

Print[hr]; Print["2. transGroup / inputsFirst"]; Print[hr];
(* a real tau transition: drive capture_vocab so vAdd is pending *)
sV = Last[walkSteps[transVP, mioCore,
   {vis["load_material", {<|"text" -> "chat", "translation" -> "cat", "ipa" -> "S"|>}],
    vis["recording_made", "audio"], vis["attempt_made"], tau["langRead"], vis["capture_vocab", "chat"]}]["states"]];
tauTr = SelectFirst[readyTransitions[transVP, sV], isTauAct[First[#]] &];
assert["a tau transition groups into internal (tau)",
  transGroup[pm, tauTr] === "internal (\[Tau])"];
assert["a named input groups into its agent (add -> VS)",
  transGroup[pm, SelectFirst[readyTransitions[transVP, mioCore],
     portName[First[#]] === "add" &]] === "VS"];
(* inputsFirst: coLabel before label *)
mix = {{label["x", param[1]], s1}, {coLabel["y", binding[z]], s2}};
assert["inputsFirst puts the coLabel (input) before the label (output)",
  MatchQ[First[First[inputsFirst[mix]]], coLabel[___]]];

Print[hr]; Print["3. the initial mioCore ready set partitions cleanly (no 'other')"]; Print[hr];
grp = GroupBy[readyTransitions[transVP, mioCore], transGroup[pm, #] &];
assert["groups are exactly {VS, PS, Helm}", Sort[Keys[grp]] === {"Helm", "PS", "VS"}];
assert["no port falls into 'other'", ! KeyExistsQ[grp, "other"]];

Print[hr]; Print["4. auto-grouping registry — walkUI groups known systems by default"]; Print[hr];
assert["defaultComponents[mioCore] === mioComponents",
  defaultComponents[mioCore] === mioComponents];
assert["defaultComponents[mioCoreD] === mioComponents",
  defaultComponents[mioCoreD] === mioComponents];
assert["a bare agent resolves to {} (flat, ungrouped)",
  defaultComponents[call["VS", signedIn, {}, alpha, none, none]] === {}];

Print[hr];
Print["ALL ASSERTIONS: ", ok[allOk]];
Print[hr];
If[!allOk, Exit[1]];
