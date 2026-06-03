#!/usr/bin/env wolframscript
(* =====================================================================
   spec/tests/vocab_table_test.wls
   ---------------------------------------------------------------------
   VocabTable (the external store) — STANDALONE (PR-1: defined, not yet
   composed into mioCore). Drives the agent call-based (transNamed) and
   checks the read self-loop and the three write ops against the recovered
   collection transforms:
     vocabRead    emits the current collection (and leaves VocabTable unchanged)
     vocabUpsert  capture/dedup (addEntry — INSERT … ON DUPLICATE KEY UPDATE)
     vocabRemove  delete by id (deleteFrom)
     vocabAmend   update fields by id (updateEntry)

   Run headless:  wolframscript -file spec/tests/vocab_table_test.wls
   ===================================================================== *)

$dir = ParentDirectory[DirectoryName[$InputFileName]] <> "/";
Get[$dir <> "MiolingoSpec.wl"];   (* loads VocabTableRecovered via loadRecoveredBase *)
Get[$dir <> "walk.wl"];           (* readyTransitions / supplyValue / walkSteps / vis *)

ok[b_] := If[TrueQ[b], "OK", "*** FAIL ***"];
allOk = True;
assert[lbl_, b_] := (allOk = allOk && TrueQ[b]; Print["   ", If[TrueQ[b], "ok  ", "FAIL "], lbl]);
hr = StringRepeat["=", 70];

(* VocabTable is call-based → step with transNamed *)
held[entries_] := Last[walkSteps[transNamed, call["VocabTable", entries], {}]["states"]];  (* identity, sanity *)
(* read the collection a VocabTable state would emit on vocabRead *)
vocabReadOf[s_] := Module[{t = SelectFirst[readyTransitions[transNamed, s],
     portName[First[#]] === "vocabRead" &]},
  First[Cases[First[t], param[p_] :> p, Infinity], None]];
ports[s_] := Sort[ToString /@ portName /@ First /@ readyTransitions[transNamed, s]];

Print[hr]; Print["1. ports — read self-loop + three writes"]; Print[hr];
s0 = call["VocabTable", {}];
assert["empty store offers vocabRead + the four writes (vocabUpsert = tab add AND PS capture)",
  ports[s0] === {"vocabAmend", "vocabImport", "vocabRead", "vocabRemove", "vocabUpsert"}];
assert["vocabRead on empty emits {}", vocabReadOf[s0] === {}];

Print[hr]; Print["2. vocabUpsert — capture + dedup (addEntry)"]; Print[hr];
s1 = Last[walkSteps[transNamed, s0, {vis["vocabUpsert", <|"word" -> "chat", "translation" -> "cat"|>]}]["states"]];
r1 = vocabReadOf[s1];
assert["after one upsert: 1 entry", Length[r1] === 1];
assert["the entry's word is chat", r1[[1]]["word"] === "chat"];
assert["times_seen starts at 1", r1[[1]]["times_seen"] === 1];
(* upsert the SAME word again — dedup bumps, does not duplicate *)
s2 = Last[walkSteps[transNamed, s1, {vis["vocabUpsert", <|"word" -> "chat"|>]}]["states"]];
r2 = vocabReadOf[s2];
assert["re-upsert same word: still 1 entry (dedup)", Length[r2] === 1];
assert["times_seen bumped to 2", r2[[1]]["times_seen"] === 2];

Print[hr]; Print["3. vocabAmend — update fields by id (updateEntry)"]; Print[hr];
id1 = r2[[1]]["id"];
s3 = Last[walkSteps[transNamed, s2,
   {vis["vocabAmend", <|"id" -> id1, "fields" -> <|"translation" -> "feline"|>|>]}]["states"]];
assert["amend updates the field", vocabReadOf[s3][[1]]["translation"] === "feline"];

Print[hr]; Print["4. vocabRemove — delete by id (deleteFrom)"]; Print[hr];
s4 = Last[walkSteps[transNamed, s3, {vis["vocabRemove", id1]}]["states"]];
assert["after remove: empty store", vocabReadOf[s4] === {}];

Print[hr]; Print["5. vocabRead is a self-loop — leaves the store unchanged"]; Print[hr];
s5 = Last[walkSteps[transNamed, s1, {vis["vocabRead"]}]["states"]];
assert["vocabRead does not change the collection", vocabReadOf[s5] === r1];

Print[hr];
Print["ALL ASSERTIONS: ", ok[allOk]];
Print[hr];
If[!allOk, Exit[1]];
