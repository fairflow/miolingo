#!/usr/bin/env wolframscript
(* =====================================================================
   spec/tests/walk_test.wls
   ---------------------------------------------------------------------
   Headless smoke test for the PURE SUBSTRATE of the walk harness
   (spec/walk.wl): the port-input mechanic by which the user, as the open
   environment, inserts a REAL value into a ready input port's binder via
   substVv (the engine's scope-aware value substitution), so the value
   threads into the derivative and the spec computes. The Dynamic widgets
   on top are driven manually in a notebook.

   The user supplies the value; the simulator does NOT validate it — the
   spec's own functions judge it if/when the term is concrete. So these
   tests check the INSERTION mechanism (correct placement, scope-respect,
   data preserved), not data validity.

   Loads the FULL spec (MiolingoSpec.wl) so the value-functions have bodies.

   Run headless:  wolframscript -file spec/tests/walk_test.wls
   ===================================================================== *)

$dir = ParentDirectory[DirectoryName[$InputFileName]] <> "/";
Get[$dir <> "MiolingoSpec.wl"];
Get[$dir <> "walk.wl"];

ok[b_] := If[TrueQ[b], "OK", "*** FAIL ***"];
allOk = True;
assert[lbl_, b_] := (allOk = allOk && TrueQ[b]; Print["   ", lbl, " ", ok[b]]);
byName[tf_, s_, nm_] := SelectFirst[readyTransitions[tf, s], portName[First[#]] === nm &];
hr = StringRepeat["=", 70];

Print[hr]; Print["1. readyInputs : the value-carrying ports a user can drive (after open_vocab)"]; Print[hr];
(* (i) external-store form: a bare VS first offers the VISIBLE open_vocab (the tab
   entry); taking it reaches VSRead, which reads the store (chRead); then the CRUD
   ports appear. vsRead[es] = VS having entered the tab and read the collection es. *)
vsOpen   = Last[byName[transNamed, call["VS", signedIn, alpha, none, none], "open_vocab"]];
vsRead[es_] := Last[supplyValue[byName[transNamed, vsOpen, "chRead"], es]];
assert["a bare VS first offers open_vocab (the visible tab entry)",
  MemberQ[ToString /@ portName /@ First /@ readyTransitions[transNamed, call["VS", signedIn, alpha, none, none]], "open_vocab"]];
ri = readyInputs[transNamed, vsRead[{}]];
assert["every readyInput is a value-carrying input (has a binder)",
  AllTrue[ri, valueInputQ[First[#]] &]];
assert["after reading, the canonical VS input ports are present",
  SubsetQ[ToString /@ portName /@ First /@ ri, {"add", "set_filter", "set_sort", "import_bulk"}]];

(* viewProjections must pick up the BARE agent's "view" port (case-insensitive),
   and VS projects what it READ from the store. *)
assert["viewProjections finds the bare \"view\" port after reading",
  KeyExistsQ[viewProjections[transNamed, vsRead[{}]], "view"]];
assert["VS projects the entries it read (count reflects the store)",
  Map[Identity, viewProjections[transNamed, vsRead[addEntry[{}, "souris"]]]["view"]]["count"] === 1];

Print[hr]; Print["2. supplyValue : slot binder (load_material on PS) inserts cleanly"]; Print[hr];
lm  = byName[transNamed, call["PS", {}, 0, none, none], "load_material"];
phr = {<|"text" -> "chat", "translation" -> "cat"|>};
lmv = supplyValue[lm, phr];
assert["value inserted into the PS state slot",
  Last[lmv] === call["PS", phr, 0, none, none]];
assert["eventOf reads the concrete value", eventOf[First[lmv]]["value"] === {phr}];

Print[hr]; Print["3. supplyValue : add now WRITES to the store (chUpsert carries the word)"]; Print[hr];
(* under (i) add no longer mutates VS state — it emits chUpsert!(w) to CargoHold.
   supplyValue must thread the word into that emission (data preserved, routed out). *)
ad  = byName[transNamed, vsRead[{}], "add"];
wv  = <|"word" -> "Chat"|>;
adv = supplyValue[ad, wv];
assert["add emits chUpsert carrying the word (data preserved, routed to the store)",
  ! FreeQ[Last[adv], param[wv]] && ! FreeQ[Last[adv], label["chUpsert", ___]]];
assert["the supplied word is NOT lost (binder w replaced by the value)",
  FreeQ[Last[adv], binding[w]]];

Print[hr]; Print["4. substVv is SCOPE-AWARE where ReplaceAll would leak"]; Print[hr];
(* the mu-term add derivative re-unfolds clauses that REBIND w; the supplied
   value must NOT land in those rebound occurrences. (add is gated behind the
   visible open_vocab then chRead under (i); take open_vocab + settle the chRead
   to reach the state offering add.) *)
mioSettled = Last[walkSteps[transVP, mioCore, {vis["open_vocab"]}, "AutoTau" -> True]["states"]];
deriv = Last[byName[transVP, mioSettled, "add"]];
assert["derivative does re-unfold clauses that rebind w (precondition)",
  Length[Cases[deriv, binding[w], Infinity]] > 0];
assert["substVv does NOT leak into a rebound binding",
  Quiet[FreeQ[substVv[deriv, w -> supplied], binding[supplied]]]];
assert["ReplaceAll WOULD leak (why we use substVv, not /.)",
  Quiet[!FreeQ[deriv /. w -> supplied, binding[supplied]]]];

Print[hr]; Print["5. supplyValue is a no-op where there is nothing to supply"]; Print[hr];
assert["value-free input (coLabel[nm]) unchanged",
  supplyValue[{coLabel[ping], stateX}, "v"] === {coLabel[ping], stateX}];
assert["output action unchanged",
  supplyValue[{label[out, param[7]], stateX}, "v"] === {label[out, param[7]], stateX}];

Print[hr]; Print["6. value-driven plan via walkSteps (vis[nm, val])"]; Print[hr];
w1 = walkSteps[transNamed, call["PS", {}, 0, none, none], {vis["load_material", phr]}];
assert["plan ran to completion (not stuck)", !w1["stuck"]];
assert["final state carries the supplied value",
  Last[w1["states"]] === call["PS", phr, 0, none, none]];
assert["recorded event carries the concrete value",
  eventOf[First[w1["actions"]]]["value"] === {phr}];

Print[hr];
Print["ALL ASSERTIONS: ", ok[allOk]];
Print[hr];
If[!allOk, Exit[1]];
