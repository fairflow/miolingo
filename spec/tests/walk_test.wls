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
(* (i) external-store form: a bare Vocab first offers the VISIBLE open_vocab (the tab
   entry); taking it reaches VocabRead, which reads the store (vocabRead); then the CRUD
   ports appear. vsRead[es] = Vocab having entered the tab and read the collection es. *)
vsOpen   = Last[byName[transNamed, call["Vocab", signedIn, alpha, none, none], "open_vocab"]];
vsRead[es_] := Last[supplyValue[byName[transNamed, vsOpen, "vocabRead"], es]];
assert["a bare Vocab first offers open_vocab (the visible tab entry)",
  MemberQ[ToString /@ portName /@ First /@ readyTransitions[transNamed, call["Vocab", signedIn, alpha, none, none]], "open_vocab"]];
ri = readyInputs[transNamed, vsRead[{}]];
assert["every readyInput is a value-carrying input (has a binder)",
  AllTrue[ri, valueInputQ[First[#]] &]];
assert["after reading, the canonical Vocab input ports are present",
  SubsetQ[ToString /@ portName /@ First /@ ri, {"add", "set_filter", "set_sort", "import_bulk"}]];

(* viewProjections must pick up the BARE agent's "view" port (case-insensitive),
   and Vocab projects what it READ from the store. *)
assert["viewProjections finds the bare \"view\" port after reading",
  KeyExistsQ[viewProjections[transNamed, vsRead[{}]], "view"]];
assert["Vocab projects the entries it read (count reflects the store)",
  Map[Identity, viewProjections[transNamed, vsRead[addEntry[{}, "souris"]]]["view"]]["count"] === 1];

Print[hr]; Print["2. supplyValue : slot binder (load_material on PS) inserts cleanly"]; Print[hr];
lm  = byName[transNamed, call["PS", {}, 0, none, none], "load_material"];
phr = {<|"text" -> "chat", "translation" -> "cat"|>};
lmv = supplyValue[lm, phr];
assert["value inserted into the PS state slot",
  Last[lmv] === call["PS", phr, 0, none, none]];
assert["eventOf reads the concrete value", eventOf[First[lmv]]["value"] === {phr}];

Print[hr]; Print["3. supplyValue : add now WRITES to the store (vocabUpsert carries the word)"]; Print[hr];
(* under (i) add no longer mutates Vocab state — it emits vocabUpsert!(w) to VocabTable.
   supplyValue must thread the word into that emission (data preserved, routed out). *)
ad  = byName[transNamed, vsRead[{}], "add"];
wv  = <|"word" -> "Chat"|>;
adv = supplyValue[ad, wv];
assert["add emits vocabUpsert carrying the word (data preserved, routed to the store)",
  ! FreeQ[Last[adv], param[wv]] && ! FreeQ[Last[adv], label["vocabUpsert", ___]]];
assert["the supplied word is NOT lost (binder w replaced by the value)",
  FreeQ[Last[adv], binding[w]]];

Print[hr]; Print["4. substVv is SCOPE-AWARE where ReplaceAll would leak"]; Print[hr];
(* the mu-term add derivative re-unfolds clauses that REBIND w; the supplied
   value must NOT land in those rebound occurrences. (add is gated behind the
   visible open_vocab then vocabRead under (i); take open_vocab + settle the vocabRead
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

Print[hr]; Print["7. Copy/Run-trace round-trip : traceToPlan + normalisePlan, both \[Tau]-modes"]; Print[hr];
(* A run WITH internal taus (story practice + capture): set_mode, record, attempt
   (-> langRead tau), capture (-> vocabUpsert tau). traceToPlan must recover an
   executable plan that reproduces it in EITHER tau-mode \[LongDash] the symmetry the Run-
   trace field gives the user via the Auto-advance checkbox. *)
obs[s_] := Sort[Normal[Map[Identity, viewProjections[transVP, s]]]];
tracePlan = {vis["set_mode", practice], vis["story_recording_made", "aud"],
             vis["story_attempt_made"], vis["story_capture_vocab", "Bonjour"]};
runA  = walkSteps[transVP, mioCore, tracePlan, "AutoTau" -> True];   (* the recorded run *)
plan2 = traceToPlan[eventLog[runA]];
assert["traceToPlan keeps the WHOLE log (vis + tau), nothing dropped",
  Length[plan2] === Length[eventLog[runA]]];
assert["traceToPlan keeps the internal taus as tau[chan]", Count[plan2, tau[_]] > 0];
assert["traceToPlan carries values inline (set_mode practice)",
  MemberQ[plan2, vis["set_mode", practice]]];
(* MANUAL-tau replay: drive the tau[…] literally (AutoTau off) -> identical run *)
runMan = walkSteps[transVP, mioCore, plan2, "AutoTau" -> False];
assert["MANUAL-\[Tau] replay: event log === original", eventLog[runMan] === eventLog[runA]];
assert["MANUAL-\[Tau] replay: views === original",
  obs[Last[runMan["states"]]] === obs[Last[runA["states"]]]];
(* AUTO-tau replay: strip the taus (as Run trace does in auto mode); AutoTau refires *)
runAut = walkSteps[transVP, mioCore, DeleteCases[plan2, tau[_]], "AutoTau" -> True];
assert["AUTO-\[Tau] replay (taus stripped): event log === original",
  eventLog[runAut] === eventLog[runA]];
assert["AUTO-\[Tau] replay: views === original",
  obs[Last[runAut["states"]]] === obs[Last[runA["states"]]]];
(* normalisePlan : accept a typed plan, convert a pasted event log, reject junk *)
assert["normalisePlan: a vis/tau plan passes through unchanged",
  normalisePlan[tracePlan] === tracePlan];
assert["normalisePlan: a pasted event log -> traceToPlan",
  normalisePlan[eventLog[runA]] === plan2];
assert["normalisePlan: a non-plan list -> $Failed (status can warn)",
  normalisePlan[{1, 2, 3}] === $Failed];
assert["normalisePlan: a non-list -> $Failed", normalisePlan["nope"] === $Failed];
assert["normalisePlan: {} -> {}", normalisePlan[{}] === {}];

Print[hr];
Print["ALL ASSERTIONS: ", ok[allOk]];
Print[hr];
If[!allOk, Exit[1]];
