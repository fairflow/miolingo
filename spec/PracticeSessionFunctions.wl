(* ::Package:: *)

(* =====================================================================
   miolingo / L1 — PracticeSession value-functions, RECOVERED (function pass)
   ---------------------------------------------------------------------
   The function-recovery pass for PS: the stubs named in
   PracticeSessionRecovered.wl (targetOf, evaluate, sessionView) get bodies
   RECOVERED from src/scoring/comparison.py and the practice queue shape
   (NOT invented). See spec/docs/function-recovery.md.

   ADDITIVE: attaches downvalues to stub symbols only; does not modify
   PracticeSessionRecovered.wl. Load AFTER it.

   STATE (from PracticeSessionRecovered.wl):
     phrases : queue, each a phrase Association <|"text","translation","ipa"|>
               (this is exactly practiseList's output — VS feeds PS via pLoad)
     pos     : 0-based index      rec : none | recorded[audio]
     res     : none | scored[r]   (r is the evaluate result)
   ===================================================================== *)


(* --- targetOf[phrases, pos] : the current practice item -----------------
   0-based pos (the agent increments pos as an Integer). Out of range -> the
   empty target (defensive; the agent guards pos < Length-1 / pos > 0). The
   correct phonemes for scoring are the phrase's "ipa". *)
targetOf[phrases_List, pos_Integer] :=
  If[0 <= pos < Length[phrases], phrases[[pos + 1]], <|"text" -> "", "translation" -> "", "ipa" -> ""|>];

correctPhonemesOf[target_Association] := ToString[Lookup[target, "ipa", ""]];
audioOf[recorded[audio_]] := audio;
audioOf[_] := Missing[];


(* --- oracle: audio -> recognised phonemes -------------------------------
   The ASR / espeak-from-audio step. Genuinely IO (a model / external
   process); left UNINTERPRETED. evaluate is parametric in it.
   recognisePhonemes[audio, lang] -- stub oracle, no downvalue. lang is the
   target language CODE (which ASR model); BORROWED from Helm and pulled fresh
   at the attempt_made port (ARCHITECTURE.md "Borrowed vs owned data"). *)


(* --- levenshtein + compare_phonemes_edit_distance (comparison.py:9, 83).
   Pure functions, no external dependency (the file says so). similarity =
   1 - distance/max(len), exact_match on string equality, distance the
   Levenshtein edit count. *)
levenshtein[s1_String, s2_String] := Module[{a = Characters[s1], b = Characters[s2]},
  Last[Fold[
    Function[{prev, ca},
      FoldList[
        Function[{cur, jc}, Module[{j = First[jc], cb = Last[jc]},
          Min[prev[[j + 1]] + 1, cur + 1, prev[[j]] + Boole[ca =!= cb]]]],
        First[prev] + 1, Transpose[{Range[Length[b]], b}]]],
    Range[0, Length[b]], a]]];

comparePhonemes[user_String, correct_String] := Module[{dist, maxLen},
  If[StringLength[correct] === 0,
    Return[<|"exact_match" -> (user === correct), "similarity" -> 0.0,
             "distance" -> StringLength[user]|>]];
  dist = levenshtein[user, correct];
  maxLen = Max[StringLength[user], StringLength[correct]];
  <|"exact_match" -> (user === correct),
    "similarity" -> 1.0 - dist/maxLen,
    "distance" -> dist|>];


(* --- evaluate[target, rec, lang] : the scoring of an attempt -----------
   PURE core (comparePhonemes) composed with the ASR oracle. The recorded
   audio is recognised to phonemes (IO oracle, in the target language), then
   compared against the target item's correct phonemes (pure). lang is the
   BORROWED {source, target} pair pulled from Helm at attempt_made; the ASR
   uses Last[lang] (the target code). The result Association is what the agent
   wraps in scored[...]. *)
evaluate[target_, rec_, lang_List] :=
  comparePhonemes[
    ToString[recognisePhonemes[audioOf[rec], Last[lang]]],
    correctPhonemesOf[target]];


(* --- sessionView[phrases, pos, rec, res] : read-only view projection ----
   What the practice pane publishes: the current item, position, whether a
   recording is held, and the score if scored. A projection, never raw
   state. *)
sessionView[phrases_List, pos_, rec_, res_] := <|
  "total" -> Length[phrases],
  "pos" -> pos,
  "item" -> If[Length[phrases] > 0, targetOf[phrases, pos], None],
  "hasRecording" -> (rec =!= none),
  "score" -> Replace[res, {scored[r_] :> r, none -> None}]|>;
