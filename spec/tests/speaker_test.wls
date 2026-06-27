#!/usr/bin/env wolframscript
(* =====================================================================
   spec/tests/speaker_test.wls
   ---------------------------------------------------------------------
   The CLOSED-LOOP harness at the CCS level: Speaker (the user-as-agent,
   spec/Speaker.wl) speaks scripted utterances on recording_made; composed
   with mioCore (recording_made RESTRICTED → τ), the simulator plays the
   user. The TTS/ASR oracle pair is given law-satisfying downvalues

       recognisePhonemes[synthAudio[text, lang], lang] := ipaOf[text]

   so scoring the speech of the TARGET item must be an EXACT match, and a
   WRONG word must score lower. The Swift twin (MiolingoHarness) runs the
   same law on the real engines (espeak → SFSpeech/Whisper).

   Run headless:  wolframscript -file spec/tests/speaker_test.wls
   ===================================================================== *)

$dir = ParentDirectory[DirectoryName[$InputFileName]] <> "/";
Get[$dir <> "MiolingoSpec.wl"];
mioGet["Speaker.wl"];
Get[$dir <> "walk.wl"];

ok[b_] := If[TrueQ[b], "OK", "*** FAIL ***"];
allOk = True;
assert[lbl_, b_] := (allOk = allOk && TrueQ[b]; Print["   ", If[TrueQ[b], "ok  ", "FAIL "], lbl]);
hr = StringRepeat["=", 70];

(* --- the round-trip LAW (test-local downvalues; the spec keeps both
   oracles uninterpreted). ipaOf is the test's tiny pronunciation fixture. *)
ipaOf["chat"]  = "ʃa";
ipaOf["chien"] = "ʃjɛ̃";
recognisePhonemes[synthAudio[text_, lang_], lang_] := ipaOf[text];

ph = {<|"text" -> "chat", "translation" -> "cat", "ipa" -> "ʃa"|>};

Print[hr]; Print["1. Speaker standalone — speaks its script in order, then stops"]; Print[hr];
sp = call["Speaker", {<|"text" -> "chat", "lang" -> "fr"|>}];
t1 = transNamed[sp];
assert["one ready transition (the utterance)", Length[t1] === 1];
assert["it is recording_made!(synthAudio[chat, fr])",
  First[First[t1]] === label["recording_made", param[synthAudio["chat", "fr"]]]];
assert["script exhausted -> deadlock (no further speech)",
  transNamed[Last[First[t1]]] === {}];

Print[hr]; Print["2. CLOSED LOOP — speak the TARGET, score is an exact match"]; Print[hr];
(* mioCore components + Speaker; recording_made restricted → the speech is a τ. *)
loop[script_] := mergeDefined[
  Join[mioComponents, {"Speaker" -> call["Speaker", script]}],
  Append[mioRestricted, label["recording_made"]]];
wGood = walkSteps[transNamed,
  loop[{<|"text" -> "chat", "lang" -> "fr"|>}],
  {vis["load_material", ph], vis["attempt_made"]}, "AutoTau" -> True];
assert["walk completed (speech fired as a τ between the externals)", !wGood["stuck"]];
assert["the speech IS the internal recording_made sync",
  MemberQ[wGood["actions"], tag[\[Tau], "recording_made", _]]];
vGood = Map[Identity, viewProjections[transNamed, Last[wGood["states"]]]];
assert["pSView shows a score", vGood["pSView"]["score"] =!= None];
assert["speaking the TARGET scores an EXACT match (the round-trip law)",
  vGood["pSView"]["score"]["exact_match"] === True &&
  vGood["pSView"]["score"]["similarity"] == 1.0];

Print[hr]; Print["3. CONTROL — speak the WRONG word, score must NOT be exact"]; Print[hr];
wBad = walkSteps[transNamed,
  loop[{<|"text" -> "chien", "lang" -> "fr"|>}],
  {vis["load_material", ph], vis["attempt_made"]}, "AutoTau" -> True];
assert["walk completed", !wBad["stuck"]];
vBad = Map[Identity, viewProjections[transNamed, Last[wBad["states"]]]];
assert["wrong word: NOT exact",
  vBad["pSView"]["score"]["exact_match"] === False];
assert["wrong word scores strictly lower than the match",
  vBad["pSView"]["score"]["similarity"] < vGood["pSView"]["score"]["similarity"]];

Print[hr];
Print["ALL ASSERTIONS: ", ok[allOk]];
Print[hr];
If[!allOk, Exit[1]];
