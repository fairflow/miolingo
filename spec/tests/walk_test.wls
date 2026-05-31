#!/usr/bin/env wolframscript
(* =====================================================================
   spec/tests/walk_test.wls
   ---------------------------------------------------------------------
   Headless smoke test for the PURE SUBSTRATE of the walk harness
   (spec/walk.wl): the port-input mechanic by which a human, as the open
   environment, supplies REAL data into a ready input port and watches it
   thread through the spec. The Dynamic widgets that sit on top are driven
   manually in a notebook; here we prove the substrate they call.

   Loads the FULL spec (MiolingoSpec.wl) so the recovered value-functions
   (addEntry, exportCsv, ...) have bodies — otherwise inputs would thread
   inert stubs and there would be no real data to walk through.

   Run headless:  wolframscript -file spec/tests/walk_test.wls
   ===================================================================== *)

$dir = ParentDirectory[DirectoryName[$InputFileName]] <> "/";
Get[$dir <> "MiolingoSpec.wl"];   (* engine + discipline + recovered + Functions + MioCore *)
Get[$dir <> "walk.wl"];

ok[b_] := If[TrueQ[b], "OK", "*** FAIL ***"];
allOk = True;
assert[lbl_, b_] := (allOk = allOk && TrueQ[b]; Print["   ", lbl, " ", ok[b]]);
byName[tf_, s_, nm_] := SelectFirst[readyTransitions[tf, s], portName[First[#]] === nm &];
eventNamed[log_, nm_] := SelectFirst[log, ToString[#["port"]] === nm &];
hr = StringRepeat["=", 70];

Print[hr]; Print["0. full spec loaded -> value-functions compute real data"]; Print[hr];
assert["addEntry has a body (Functions loaded)", DownValues[addEntry] =!= {}];
assert["exportCsv of a capture yields a real data row (word 'Chat')",
  StringContainsQ[exportCsv[addEntry[{}, <|"word" -> "Chat", "translation" -> "cat"|>]], "Chat,cat"]];

Print[hr]; Print["1. readyInputs : the value-carrying ports a user can drive"]; Print[hr];
ri = readyInputs[transVP, mioCore];
assert["every readyInput is a value-carrying input (has a binder)",
  AllTrue[ri, valueInputQ[First[#]] &]];
assert["the canonical input ports are present",
  SubsetQ[ToString /@ portName /@ First /@ ri,
          {"add", "set_filter", "set_sort", "import_bulk", "load_material"}]];

Print[hr]; Print["2. supplyValue : a string value flows into set_filter"]; Print[hr];
sf  = byName[transVP, mioCore, "set_filter"];
qsym = First[inputBinderOf[First[sf]]];
sfv = supplyValue[sf, "happy"];
assert["action becomes coLabel[set_filter, binding[\"happy\"]]",
  MatchQ[First[sfv], coLabel[_, binding["happy"]]]];
assert["eventOf reads the concrete value {\"happy\"}", eventOf[First[sfv]]["value"] === {"happy"}];
assert["binder symbol no longer in successor", FreeQ[Last[sfv], qsym]];
assert["\"happy\" threaded into successor", !FreeQ[Last[sfv], "happy"]];

Print[hr]; Print["3. supplyValue : a structured value flows into add"]; Print[hr];
ad  = byName[transVP, mioCore, "add"];
wsym = First[inputBinderOf[First[ad]]];
wv  = <|"word" -> "Chat", "translation" -> "cat"|>;
adv = supplyValue[ad, wv];
assert["word assoc threaded into successor", !FreeQ[Last[adv], wv]];
assert["binder symbol no longer in successor", FreeQ[Last[adv], wsym]];
assert["eventOf reads the concrete assoc value", eventOf[First[adv]]["value"] === {wv}];

Print[hr]; Print["4. supplyValue is a no-op where there is nothing to supply"]; Print[hr];
assert["value-free input (coLabel[nm]) unchanged",
  supplyValue[{coLabel[ping], stateX}, "v"] === {coLabel[ping], stateX}];
assert["output action unchanged",
  supplyValue[{label[out, param[7]], stateX}, "v"] === {label[out, param[7]], stateX}];

Print[hr]; Print["5. value-driven plan via walkSteps + condensed event log"]; Print[hr];
valPlan = {vis["set_filter", "happy"], vis["add", wv]};
symPlan = {vis["set_filter"], vis["add"]};
valLog  = condense[transVP, mioCore, valPlan];
symLog  = condense[transVP, mioCore, symPlan];
assert["value plan runs to completion (not stuck)",
  !walkSteps[transVP, mioCore, valPlan]["stuck"]];
assert["set_filter event records \"happy\" (concrete)",
  eventNamed[valLog, "set_filter"]["value"] === {"happy"}];
assert["add event records the word assoc (concrete)",
  eventNamed[valLog, "add"]["value"] === {wv}];
assert["symbolic plan leaves set_filter value as a free symbol (contrast)",
  MatchQ[eventNamed[symLog, "set_filter"]["value"], {_Symbol}]];

Print[hr];
Print["ALL ASSERTIONS: ", ok[allOk]];
Print[hr];
If[!allOk, Exit[1]];
