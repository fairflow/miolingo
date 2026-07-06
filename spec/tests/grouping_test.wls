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
assert["add -> Vocab",            pm["add"] === "Vocab"];
assert["import_bulk -> Vocab",    pm["import_bulk"] === "Vocab"];
assert["load_material -> PS",  pm["load_material"] === "PS"];
assert["set_target -> Helm",   pm["set_target"] === "Helm"];
assert["set_speed -> Helm",    pm["set_speed"] === "Helm"];
assert["set_asr -> Helm",      pm["set_asr"] === "Helm"];
(* the view ports are renamed per agent to match the composition *)
assert["pSView -> PS",   pm["pSView"] === "PS"];
assert["vocabView -> Vocab",   pm["vocabView"] === "Vocab"];
assert["helmView -> Helm", pm["helmView"] === "Helm"];

Print[hr]; Print["2. transGroup / inputsFirst"]; Print[hr];
(* a real tau transition: drive capture_vocab so vocabUpsert is pending *)
sV = Last[walkSteps[transVP, mioCore,
   {vis["load_material", {<|"text" -> "chat", "translation" -> "cat", "ipa" -> "S"|>}],
    vis["recording_made", "audio"], vis["attempt_made"],
    tau["langRead"], tau["progressAppend"], vis["capture_vocab", "chat"]}]["states"]];
tauTr = SelectFirst[readyTransitions[transVP, sV], isTauAct[First[#]] &];
assert["a tau transition groups into internal (tau)",
  transGroup[pm, tauTr] === "internal (\[Tau])"];
(* add is not externally ready at mioCore init (Vocab gates behind vocabRead), so use a
   synthetic transition — transGroup only looks at the action's port name *)
assert["a named input groups into its agent (add -> Vocab)",
  transGroup[pm, {coLabel["add", binding[w]], dummyState}] === "Vocab"];
(* inputsFirst: coLabel before label *)
mix = {{label["x", param[1]], s1}, {coLabel["y", binding[z]], s2}};
assert["inputsFirst puts the coLabel (input) before the label (output)",
  MatchQ[First[First[inputsFirst[mix]]], coLabel[___]]];

Print[hr]; Print["3. the SETTLED mioCore ready set partitions cleanly (no 'other')"]; Print[hr];
(* Vocab gates behind open_vocab so it contributes that; StoryReader is live (browse
   mode) so it contributes its view/mode/nav ports; PS (empty) and Helm contribute
   too. VocabTable's ports are all restricted (internal τ), so it never appears in the
   external grouping. ProgressTable DOES appear: its append is restricted but its
   query surface (progressRead + statsView/historyView) is external. *)
sInit = Last[walkSteps[transVP, mioCore, {}, "AutoTau" -> True]["states"]];
grp = GroupBy[readyTransitions[transVP, sInit], transGroup[pm, #] &];
assert["groups are exactly {Vocab, PS, Helm, StoryReader, ProgressTable}",
  Sort[Keys[grp]] === Sort[{"Helm", "PS", "ProgressTable", "StoryReader", "Vocab"}]];
assert["no port falls into 'other'", ! KeyExistsQ[grp, "other"]];

Print[hr]; Print["4. auto-grouping registry — walkUI groups known systems by default"]; Print[hr];
assert["defaultComponents[mioCore] === mioComponents",
  defaultComponents[mioCore] === mioComponents];
assert["defaultComponents[mioCoreD] === mioComponents",
  defaultComponents[mioCoreD] === mioComponents];
assert["a bare agent resolves to {} (flat, ungrouped)",
  defaultComponents[call["Vocab", signedIn, {}, alpha, none, none]] === {}];

Print[hr]; Print["5. the cloud — external-dependency inventory lights up on consulting ports"]; Print[hr];
enrichItem = SelectFirst[$walkCloud, #["item"] === "enrichOracle" &];
asrItem    = SelectFirst[$walkCloud, #["item"] === "recognisePhonemes" &];
assert["enrichOracle active when autofill is ready",  cloudActiveQ[enrichItem, {"autofill", "delete"}]];
assert["enrichOracle NOT active without autofill",  ! cloudActiveQ[enrichItem, {"add", "set_sort"}]];
assert["recognisePhonemes active on attempt_made",   cloudActiveQ[asrItem, {"attempt_made"}]];
(* the "stats / history — not yet recovered" item is GONE (ProgressTable owns the
   log now; the cloud shrinks as owners are modelled); what remains external is
   the real DB and the clock/user identity, which light on the writing ports *)
assert["stats/history item retired from the cloud (recovered)",
  ! MemberQ[#["item"] & /@ $walkCloud, "stats / history"]];
clockItem = SelectFirst[$walkCloud, #["item"] === "clock + user identity" &];
assert["clock/user-identity active on attempt_made (the row is stamped at insert)",
  cloudActiveQ[clockItem, {"attempt_made"}]];
assert["clock/user-identity NOT active on a non-writing port",
  ! cloudActiveQ[clockItem, {"add", "set_sort"}]];
assert["cloudPanel builds (Head OpenerView)", Head[cloudPanel[transVP, mioCore]] === OpenerView];

Print[hr];
Print["ALL ASSERTIONS: ", ok[allOk]];
Print[hr];
If[!allOk, Exit[1]];
