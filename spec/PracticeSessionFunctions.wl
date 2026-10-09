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
               (this is exactly practiseList's output — PS pulls it from VocabTable)
     pos     : 0-based index      rec : none | recorded[audio]
     res     : none | scored[r]   (r is the evaluate result)
   ===================================================================== *)


(* --- targetOf[phrases, pos] : the current practice item -----------------
   0-based pos (the agent increments pos as an Integer). Out of range -> the
   empty target (defensive; the agent guards pos < Length-1 / pos > 0). The
   correct phonemes for scoring are the phrase's "ipa". *)
targetOf[phrases_List, pos_Integer] :=
  If[0 <= pos < Length[phrases], phrases[[pos + 1]], <|"text" -> "", "translation" -> "", "ipa" -> ""|>];

(* selectPos[phrases, i, cur] : the recovered "select item i" guard (the stub named
   in practice-session-recovery.md §"Stub list"). select_item?(i) takes its index
   from the open environment; the app only renders rows for EXISTING items, so an
   out-of-range index can't arise there. At L1 we therefore keep pos VALID: selecting
   a non-existent index is a no-op (pos stays put). Without this, select_item bound the
   index raw, so pos could walk off the end — then targetOf returns the empty item and
   attempt_made scores a meaningless zero (the interleaving bug, 2026-06-04).
   Gated on _Integer so it stays held until the supplied index is concrete. *)
selectPos[phrases_List, i_Integer, cur_Integer] := If[0 <= i < Length[phrases], i, cur];

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


(* --- normalisePhonemes[ipa] : the scoring normalisation (phonemes.py
   normalize_for_phoneme_scoring). Strip word-boundary whitespace so scoring is
   on pronunciation phonemes only. We feed CLEAN IPA (espeak --ipa, stress already
   removed) — NOT espeak's -x internal codes — so whitespace removal suffices; the
   pause-phoneme markers the app also stripped only arise from -x output. *)
normalisePhonemes[ipa_String] := StringReplace[ipa, Whitespace -> ""];

(* --- alignPhonemes[user, correct] : the matched/unmatched structure
   (comparison.py get_edit_operations) — a Levenshtein BACKTRACE aligning the
   target (correct) against the user's phonemes. Returns a list of segments
     <|"op" -> equal|sub|ins|del, "target" -> _, "user" -> _|>
   oriented target-vs-user (as practice_tab.py _colorize_diff renders, two parallel
   rows): equal = same phoneme; sub = differing phonemes; ins = user has an extra
   phoneme (target ""); del = target phoneme missing from the user ("" user). The
   skin colours these (sub/ins/del/equal). Pure; this is the heart of the feedback. *)
alignPhonemes[user_String, correct_String] := Module[
  {a = Characters[correct], b = Characters[user], m, n, dp, ops, i, j},
  m = Length[a]; n = Length[b];
  dp = Table[0, {m + 1}, {n + 1}];
  Do[dp[[i + 1, 1]] = i, {i, 0, m}];
  Do[dp[[1, j + 1]] = j, {j, 0, n}];
  Do[
    dp[[i + 1, j + 1]] = If[a[[i]] === b[[j]], dp[[i, j]],
      1 + Min[dp[[i, j + 1]], dp[[i + 1, j]], dp[[i, j]]]],
    {i, 1, m}, {j, 1, n}];
  ops = {}; i = m; j = n;
  While[i > 0 || j > 0,
    Which[
      i > 0 && j > 0 && a[[i]] === b[[j]],
        PrependTo[ops, <|"op" -> "equal", "target" -> a[[i]], "user" -> b[[j]]|>]; i--; j--,
      i > 0 && j > 0 && dp[[i + 1, j + 1]] == dp[[i, j]] + 1,
        PrependTo[ops, <|"op" -> "sub", "target" -> a[[i]], "user" -> b[[j]]|>]; i--; j--,
      j > 0 && dp[[i + 1, j + 1]] == dp[[i + 1, j]] + 1,
        PrependTo[ops, <|"op" -> "ins", "target" -> "", "user" -> b[[j]]|>]; j--,
      True,
        PrependTo[ops, <|"op" -> "del", "target" -> a[[i]], "user" -> ""|>]; i--]];
  ops];

(* --- scoreDetail[user, correct] : the FULL scored result the practice pane
   shows — the comparePhonemes numbers PLUS the phoneme strings and the alignment.
   A superset of comparePhonemes (keeps exact_match/similarity/distance), so older
   consumers still read those keys. *)
scoreDetail[user_String, correct_String] :=
  Join[comparePhonemes[user, correct],
    <|"user" -> user, "target" -> correct, "alignment" -> alignPhonemes[user, correct]|>];

(* --- evaluate[target, rec, tc] : the scoring of an attempt -------------
   PURE core (scoreDetail) composed with the ASR oracle. The recorded audio is
   recognised to phonemes (IO oracle, in the target language), both sides are
   normalised, then aligned + scored (pure). tc is the BORROWED target CODE
   pulled from Helm at attempt_made via targetRead — the NARROW read: scoring
   consumes only the target (practice identity), never the source, so the
   borrow declares exactly that (ARCHITECTURE.md "The language pair is
   asymmetric"). The lang_List form is kept below for the pre-narrowing
   callers (round-trip law tests, ad-hoc use with a pair). The result
   Association is what the agent wraps in scored[...] and the view publishes.
   (The recognised TEXT/word is an oracle detail surfaced by the skin, below
   the L1 boundary; L1 scores phonemes.) *)
(* recognisedOf: held-until-concrete gate on the ORACLE's result. The old
   ToString here coerced an UNINTERPRETED recognisePhonemes[...] term into its
   printed form, which then got character-Levenshteined against the target IPA —
   garbage scores (sim 0.02, 40 ins ops) whenever the oracle had no downvalues.
   Gating on _String keeps the whole score SYMBOLIC until a real transcript
   exists (the same discipline as vocabView[entries_List] / deleteFrom[id_Integer]). *)
recognisedOf[r_String] := r;

evaluate[target_, rec_, tc_String] :=
  scoreDetail[
    normalisePhonemes[recognisedOf[recognisePhonemes[audioOf[rec], tc]]],
    normalisePhonemes[correctPhonemesOf[target]]];
(* pair form: delegates to the code form on the target half (Last) *)
evaluate[target_, rec_, lang_List] :=
  scoreDetail[
    normalisePhonemes[recognisedOf[recognisePhonemes[audioOf[rec], Last[lang]]]],
    normalisePhonemes[correctPhonemesOf[target]]];


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
