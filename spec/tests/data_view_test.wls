#!/usr/bin/env wolframscript
(* =====================================================================
   spec/tests/data_view_test.wls
   ---------------------------------------------------------------------
   Exercises the DATA-VIEW COMPACTION helpers added to discipline.wl:

     linearize / linearizeForm  — let-form (A-normal) CSE pretty-printer for
        the nested stub-application snapshot terms. LOSSLESS: re-substituting
        the bindings reproduces the original term.

     walkSteps / eventLog / condense / eventLogForm — condensed trace export:
        per step keep only {port, polarity, isVisible, value}, NOT the
        cumulative state term (recoverable by replay).

   PLAN: the dual-tau deterministic walk from internal_transitions_test /
   merge_defined_test (set_filter, add, practise_vocab, tau goPractice,
   recording_made, attempt_made, capture_vocab, tau vAdd) over mioCoreD
   (transNamed). It drives both cross-component internal taus.

   Run headless:  wolframscript -file spec/tests/data_view_test.wls
   ===================================================================== *)

Get[FileNameJoin[{ParentDirectory[DirectoryName[$InputFileName]], "paths.wl"}]];

loadEngine[];
loadRecoveredBase[];
mioGet["MioCore.wl"];

hr = StringRepeat["=", 70];
ok[b_] := If[TrueQ[b], "OK", "*** FAIL ***"];
allOk = True;
assert[lbl_, b_] := (allOk = allOk && TrueQ[b]; Print["   ", lbl, " ", ok[b]]);

(* ---------------------------------------------------------------------
   1. linearize the canonical nested data-view term
--------------------------------------------------------------------- *)
Print[hr]; Print["1. linearize  (let-form / A-normal CSE pretty-print)"]; Print[hr];

big = exportCsv[autofillIn[updateEntry[updateNotesIn[deleteFrom[
        addEntry[addEntry[addEntry[importInto[{}, f], w], w], w],
        id], idn], editingRow[id], fields], id, lang]];

lin = linearize[big];
Print["   raw term:"];
Print["     ", ToString[big, InputForm]];
Print["   linearized let-form:"];
Print[StringReplace[linearizeForm[big], StartOfLine -> "     "]];
Print[""];
Print["   raw LeafCount        : ", LeafCount[big]];
Print["   linearize  #bindings : ", Length[lin["bindings"]]];
assert["bindings fewer than LeafCount?", Length[lin["bindings"]] < LeafCount[big]];
assert["lossless round-trip (expand === raw)?", linearizeExpand[lin] === big];
(* inline-leaf discipline: tag leaves stay inline (not given a binding) *)
assert["editingRow[id] kept inline (not a binding)?",
       FreeQ[Keys[lin["bindings"]], "editingRow"] &&
       MemberQ[lin["bindings"], _ -> _?(! FreeQ[#, editingRow[id]] &)]];

(* ---------------------------------------------------------------------
   2. run the dual-tau walk on mioCoreD and linearize a real state view
--------------------------------------------------------------------- *)
Print[hr]; Print["2. linearize a LIVE projection from the dual-tau walk"]; Print[hr];

(* external-only plan; AutoTau fires the internal syncs (chRead/chUpsert/goPractice/
   langRead/vAdd) between steps — so the action log includes them *)
plan = {vis["open_vocab"], vis["set_filter"], vis["add"], vis["practise_vocab"],
        vis["recording_made"], vis["attempt_made"], vis["capture_vocab"]};
wlk = walkSteps[transNamed, mioCoreD, plan, "AutoTau" -> True];
assert["walk ran to completion (not stuck)?", ! wlk["stuck"]];

(* Pull the VS `vocabView` projection out of the final composed state's view
   action. The VS export/view value-function term is the nested snapshot. *)
finalState = Last[wlk["states"]];
viewActs = Cases[transNamed[finalState],
                 {label[_, param[v_]], _} :> v, {0, Infinity}];
vsViews = Select[viewActs, ! FreeQ[#, vocabView] || ! FreeQ[#, exportCsv] &];
proj = If[vsViews === {}, First[viewActs, big], First[vsViews]];
Print["   live VS projection (raw):"];
Print["     ", ToString[proj, InputForm]];
linP = linearize[proj];
Print["   linearized:"];
Print[StringReplace[linearizeForm[proj], StartOfLine -> "     "]];
Print["   raw LeafCount        : ", LeafCount[proj]];
Print["   linearize  #bindings : ", Length[linP["bindings"]]];
assert["live projection round-trips losslessly?", linearizeExpand[linP] === proj];

(* ---------------------------------------------------------------------
   3. condensed event log vs raw cumulative per-step terms
--------------------------------------------------------------------- *)
Print[hr]; Print["3. condensed EVENT LOG vs raw cumulative per-step terms"]; Print[hr];

log = eventLog[wlk];
Print["   event log:"];
Print[StringReplace[eventLogForm[log], StartOfLine -> "     "]];
Print[""];
(* sizes: condensed log vs the list of full successor state terms *)
rawStatesSize = LeafCount[wlk["states"]];
condensedSize = LeafCount[log];
Print["   raw  trace (all cumulative state terms) LeafCount : ", rawStatesSize];
Print["   condensed event-log                     LeafCount : ", condensedSize];
assert["condensed log strictly smaller than raw trace?", condensedSize < rawStatesSize];
assert["at least one event per plan step (AutoTau adds internal taus)?", Length[log] >= Length[plan]];
assert["both taus present (goPractice, vAdd)?",
       SubsetQ[#["port"] & /@ Select[log, #["polarity"] === "tau" &], {"goPractice", "vAdd"}]];
assert["each event has exactly the 4 fields?",
       AllTrue[log, Sort[Keys[#]] === Sort[{"port","polarity","isVisible","value"}] &]];

(* replay: snapshot is DERIVED, not stored — fold explicit ops onto a seed *)
Print[hr]; Print["4. replay: snapshot is derived (Fold), not stored"]; Print[hr];
ops = {importInto[#, f] &, addEntry[#, w] &, addEntry[#, w] &, addEntry[#, w] &,
       deleteFrom[#, id] &, updateNotesIn[#, idn] &,
       updateEntry[#, editingRow[id], fields] &, autofillIn[#, id, lang] &};
snap = exportCsv[replay[{}, ops]];
Print["   replay[{}, ops] then exportCsv:"];
Print["     ", ToString[snap, InputForm]];
assert["replay reconstructs the canonical nested term?", snap === big];

Print[hr];
Print["ALL ASSERTIONS: ", If[allOk, "OK", "*** SOME FAILED ***"]];
Print[hr];
