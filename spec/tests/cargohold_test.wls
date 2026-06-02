#!/usr/bin/env wolframscript
(* =====================================================================
   spec/tests/cargohold_test.wls
   ---------------------------------------------------------------------
   CargoHold (the external store) — STANDALONE (PR-1: defined, not yet
   composed into mioCore). Drives the agent call-based (transNamed) and
   checks the read self-loop and the three write ops against the recovered
   collection transforms:
     chRead    emits the current collection (and leaves CargoHold unchanged)
     chUpsert  capture/dedup (addEntry — INSERT … ON DUPLICATE KEY UPDATE)
     chRemove  delete by id (deleteFrom)
     chAmend   update fields by id (updateEntry)

   Run headless:  wolframscript -file spec/tests/cargohold_test.wls
   ===================================================================== *)

$dir = ParentDirectory[DirectoryName[$InputFileName]] <> "/";
Get[$dir <> "MiolingoSpec.wl"];   (* loads CargoHoldRecovered via loadRecoveredBase *)
Get[$dir <> "walk.wl"];           (* readyTransitions / supplyValue / walkSteps / vis *)

ok[b_] := If[TrueQ[b], "OK", "*** FAIL ***"];
allOk = True;
assert[lbl_, b_] := (allOk = allOk && TrueQ[b]; Print["   ", If[TrueQ[b], "ok  ", "FAIL "], lbl]);
hr = StringRepeat["=", 70];

(* CargoHold is call-based → step with transNamed *)
held[entries_] := Last[walkSteps[transNamed, call["CargoHold", entries], {}]["states"]];  (* identity, sanity *)
(* read the collection a CargoHold state would emit on chRead *)
chReadOf[s_] := Module[{t = SelectFirst[readyTransitions[transNamed, s],
     portName[First[#]] === "chRead" &]},
  First[Cases[First[t], param[p_] :> p, Infinity], None]];
ports[s_] := Sort[ToString /@ portName /@ First /@ readyTransitions[transNamed, s]];

Print[hr]; Print["1. ports — read self-loop + three writes"]; Print[hr];
s0 = call["CargoHold", {}];
assert["empty store offers chRead, chUpsert, chRemove, chAmend",
  ports[s0] === {"chAmend", "chRead", "chRemove", "chUpsert"}];
assert["chRead on empty emits {}", chReadOf[s0] === {}];

Print[hr]; Print["2. chUpsert — capture + dedup (addEntry)"]; Print[hr];
s1 = Last[walkSteps[transNamed, s0, {vis["chUpsert", <|"word" -> "chat", "translation" -> "cat"|>]}]["states"]];
r1 = chReadOf[s1];
assert["after one upsert: 1 entry", Length[r1] === 1];
assert["the entry's word is chat", r1[[1]]["word"] === "chat"];
assert["times_seen starts at 1", r1[[1]]["times_seen"] === 1];
(* upsert the SAME word again — dedup bumps, does not duplicate *)
s2 = Last[walkSteps[transNamed, s1, {vis["chUpsert", <|"word" -> "chat"|>]}]["states"]];
r2 = chReadOf[s2];
assert["re-upsert same word: still 1 entry (dedup)", Length[r2] === 1];
assert["times_seen bumped to 2", r2[[1]]["times_seen"] === 2];

Print[hr]; Print["3. chAmend — update fields by id (updateEntry)"]; Print[hr];
id1 = r2[[1]]["id"];
s3 = Last[walkSteps[transNamed, s2,
   {vis["chAmend", <|"id" -> id1, "fields" -> <|"translation" -> "feline"|>|>]}]["states"]];
assert["amend updates the field", chReadOf[s3][[1]]["translation"] === "feline"];

Print[hr]; Print["4. chRemove — delete by id (deleteFrom)"]; Print[hr];
s4 = Last[walkSteps[transNamed, s3, {vis["chRemove", id1]}]["states"]];
assert["after remove: empty store", chReadOf[s4] === {}];

Print[hr]; Print["5. chRead is a self-loop — leaves the store unchanged"]; Print[hr];
s5 = Last[walkSteps[transNamed, s1, {vis["chRead"]}]["states"]];
assert["chRead does not change the collection", chReadOf[s5] === r1];

Print[hr];
Print["ALL ASSERTIONS: ", ok[allOk]];
Print[hr];
If[!allOk, Exit[1]];
