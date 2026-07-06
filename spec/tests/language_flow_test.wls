#!/usr/bin/env wolframscript
(* =====================================================================
   spec/tests/language_flow_test.wls
   ---------------------------------------------------------------------
   THE LANGUAGE-CODE BORROW, made a CHECKED CONTRACT.

   Helm OWNS the (source, target) pair, and the pair is ASYMMETRIC
   (ARCHITECTURE.md "The language pair is asymmetric"): source is an
   authoring parameter, target is the practice identity. Every consumer
   PULLS its language fresh at point of use (borrowed, not cached), through
   the read that matches WHAT it consumes: scoring borrows ONLY the target
   code (targetRead); enrichment borrows the full pair (langRead). A future
   re-derivation that HARDCODES a language, drops a borrow, or widens the
   scoring borrow back to the pair fails LOUDLY here instead of silently.

   Origin: a bug-report trace where valid language codes were not visible at
   the points that consume them. The data was threaded but unchecked; this
   pins it as a regression gate AND demonstrates it is present in the trace.

   What it pins (mioCoreD, transNamed, AutoTau — the live composed system):
     1. PS scoring   : attempt_made fires the targetRead τ carrying ONLY
                       Helm's concrete target code, which reaches the
                       recognise oracle call (recognisePhonemes[_, target]).
     2. FRESH PULL   : change the target (set_target) and the code reaching the
                       oracle CHANGES with it — the decisive "not hardcoded,
                       not cached" check. A constant-language impl fails this.
     3. SOURCE half  : autofill pulls BOTH halves via langRead; set_source is
                       reflected in the borrowed pair (enrich needs source AND
                       target — it renders INTO the source).
     4. STORY path   : story_attempt_made borrows identically (its own loop).
     5. SOURCE-INDEPENDENCE (the narrowing's theorem): switching the source
                       right before an attempt changes NOTHING about the
                       score or the logged attempt row — the borrowed value
                       does not even CONTAIN the source.
     6. VISIBILITY   : the borrowed code is PRESENT in the rendered event log
                       (eventLogForm) — the codes show up in the trace gadget.

   The oracles stay UNINTERPRETED: recognisePhonemes has no downvalue, so the
   score term stays SYMBOLIC and literally contains recognisePhonemes[_, code]
   — the borrowed code is observable BECAUSE it was carried in, not computed.

   Run headless:  wolframscript -file spec/tests/language_flow_test.wls
   ===================================================================== *)

$dir = ParentDirectory[DirectoryName[$InputFileName]] <> "/";
Get[$dir <> "MiolingoSpec.wl"];
Get[$dir <> "walk.wl"];

allOk = True;
assert[lbl_, b_] := (allOk = allOk && TrueQ[b]; Print["   ", If[TrueQ[b], "ok  ", "FAIL "], lbl]);
hr = StringRepeat["=", 70];

(* a walk of `plan` on the live composed system, auto-firing the internal τ's *)
run[plan_] := walkSteps[transNamed, mioCoreD, plan, "AutoTau" -> True];
(* the (source,target) pairs the langRead τ delivered, in order *)
langSubsts[w_] := Cases[w["actions"], tag[\[Tau], "langRead", s_] :> (lp /. s)];
(* the target codes the targetRead τ delivered, in order (the scoring borrow) *)
targetSubsts[w_] := Cases[w["actions"], tag[\[Tau], "targetRead", s_] :> (tc /. s)];
(* the target CODES that reached the recognise oracle in a (symbolic) score *)
oracleCodes[score_] := Cases[score, recognisePhonemes[_, c_] :> c, Infinity];

ph = {<|"text" -> "chat", "translation" -> "cat", "ipa" -> "ʃa"|>};

Print[hr]; Print["1. PS scoring borrows ONLY the target code at attempt_made"]; Print[hr];
w1 = run[{vis["load_material", ph], vis["recording_made", "a"], vis["attempt_made"]}];
assert["walk completed", !w1["stuck"]];
assert["targetRead τ fired, carrying Helm's concrete code \"fr\" (not the pair)",
  targetSubsts[w1] === {"fr"}];
assert["scoring fired NO langRead (the pair borrow is enrichment's, not scoring's)",
  langSubsts[w1] === {}];
sc1 = viewProjections[transNamed, Last[w1["states"]]]["pSView"]["score"];
assert["the recognise oracle was called with the TARGET code \"fr\"",
  oracleCodes[sc1] === {"fr"}];

Print[hr]; Print["2. FRESH PULL — change the target, the oracle's code changes"]; Print[hr];
w2 = run[{vis["set_target", "pt"], vis["load_material", ph],
          vis["recording_made", "a"], vis["attempt_made"]}];
assert["targetRead now carries the NEW code \"pt\"",
  targetSubsts[w2] === {"pt"}];
codes2 = oracleCodes[viewProjections[transNamed, Last[w2["states"]]]["pSView"]["score"]];
assert["the oracle is called with \"pt\" (the live setting)", codes2 === {"pt"}];
assert["NOT the old default \"fr\" — the language is not hardcoded/cached",
  FreeQ[codes2, "fr"]];

Print[hr]; Print["3. SOURCE half — autofill borrows BOTH (source, target)"]; Print[hr];
w3 = run[{vis["set_source", "Italian"], vis["open_vocab"],
          vis["add", <|"word" -> "chat", "translation" -> "cat"|>], vis["autofill", 1]}];
assert["autofill's langRead carries the full pair, source first: {Italian, fr}",
  langSubsts[w3] === {{"Italian", "fr"}}];

Print[hr]; Print["4. STORY path — story_attempt_made borrows identically"]; Print[hr];
w4 = run[{vis["set_mode", practice], vis["story_recording_made", "a"],
          vis["story_attempt_made"]}];
assert["targetRead τ fired for the story score, code \"fr\"",
  targetSubsts[w4] === {"fr"}];
scS = viewProjections[transNamed, Last[w4["states"]]]["storyReaderView"]["score"];
assert["story score's oracle was called with \"fr\"", oracleCodes[scS] === {"fr"}];

Print[hr]; Print["5. SOURCE-INDEPENDENCE — a source switch cannot touch a practice record"]; Print[hr];
(* identical attempts, one with the source switched right before scoring: the
   borrowed value, the score term, and the logged attempt row must be IDENTICAL
   — the narrow borrow means the dependency does not exist to be violated. *)
w5a = run[{vis["load_material", ph], vis["recording_made", "a"], vis["attempt_made"]}];
w5b = run[{vis["load_material", ph], vis["recording_made", "a"],
           vis["set_source", "Italian"], vis["attempt_made"]}];
assert["borrowed value identical under the source switch",
  targetSubsts[w5a] === targetSubsts[w5b]];
assert["score term identical under the source switch",
  viewProjections[transNamed, Last[w5a["states"]]]["pSView"]["score"] ===
  viewProjections[transNamed, Last[w5b["states"]]]["pSView"]["score"]];
assert["logged attempt row identical under the source switch",
  Cases[w5a["actions"], tag[\[Tau], "progressAppend", s_] :> (r /. s)] ===
  Cases[w5b["actions"], tag[\[Tau], "progressAppend", s_] :> (r /. s)]];
assert["...and the borrowed value does not even CONTAIN a source",
  FreeQ[targetSubsts[w5b], "English"] && FreeQ[targetSubsts[w5b], "Italian"]];

Print[hr]; Print["6. VISIBILITY — the borrowed code is present in the rendered trace"]; Print[hr];
log2 = eventLogForm[eventLog[w2]];
assert["the condensed event log shows the targetRead τ", StringContainsQ[log2, "targetRead"]];
assert["...with the borrowed code \"pt\" inline (codes ARE in the trace)",
  StringContainsQ[log2, "pt"]];

Print[hr];
Print["ALL ASSERTIONS: ", If[allOk, "OK", "*** FAIL ***"]];
Print[hr];
If[!allOk, Exit[1]];
