#!/usr/bin/env wolframscript
(* =====================================================================
   spec/tests/story_reader_test.wls
   ---------------------------------------------------------------------
   Behavioural assertions for StoryReader, AND a regression guard that
   PracticeSession (PSActive) is unchanged by this PR — explicit ready-set
   checks at representative states, not just "walk didn't get stuck".

   Run headless:  wolframscript -file spec/tests/story_reader_test.wls
   ===================================================================== *)

$dir = ParentDirectory[DirectoryName[$InputFileName]] <> "/";
Get[$dir <> "MiolingoSpec.wl"];   (* full spec, so sceneOf / storyView have bodies *)
Get[$dir <> "walk.wl"];

ok[b_]   := If[TrueQ[b], "OK", "*** FAIL ***"];
allOk    = True;
assert[lbl_, b_] := (allOk = allOk && TrueQ[b]; Print["   ", If[TrueQ[b], "ok  ", "FAIL "], lbl]);
ports[s_] := Sort[ToString /@ portName /@ First /@ transNamed[s]];
hr = StringRepeat["=", 70];
ph2 = {<|"text" -> "chat", "translation" -> "cat", "ipa" -> "ʃa"|>,
       <|"text" -> "chien", "translation" -> "dog", "ipa" -> "ʃjɛ̃"|>};
sc  = <|"sim" -> 0.9|>;   (* a stand-in score value *)

Print[hr]; Print["1. PS REGRESSION — PSActive ready sets are exactly as before"]; Print[hr];
assert["PS active (2-phrase, pos 0, no rec): exact port set",
  ports[call["PS", ph2, 0, none, none]] ===
    {"clear_material", "goPractice", "load_material", "next_item_requested",
     "open_practice", "recording_made", "select_item", "view"}];
assert["PS pos 1 (last): prev present, next gone",
  With[{p = ports[call["PS", ph2, 1, none, none]]},
    MemberQ[p, "prev_item_requested"] && ! MemberQ[p, "next_item_requested"]]];
assert["PS with recording: attempt_made + clear_recording, recording_made gone",
  With[{p = ports[call["PS", ph2, 0, recorded["a"], none]]},
    MemberQ[p, "attempt_made"] && MemberQ[p, "clear_recording"] && ! MemberQ[p, "recording_made"]]];
assert["PS scored: capture_vocab present",
  MemberQ[ports[call["PS", ph2, 0, recorded["a"], scored[sc]]], "capture_vocab"]];
assert["PS empty: no loop ports (just view/load/open_practice/goPractice)",
  ports[call["PS", {}, 0, none, none]] ===
    {"goPractice", "load_material", "open_practice", "view"}];

Print[hr]; Print["2. StoryReader per-mode port sets (scene 0 has 2 phrases)"]; Print[hr];
assert["full mode: only set_mode / select_scene / view (no phrase nav)",
  ports[call["StoryReader", 0, 0, full, none, none]] === {"select_scene", "set_mode", "view"}];
assert["browse: story nav present, NO record/capture",
  With[{p = ports[call["StoryReader", 0, 0, browse, none, none]]},
    SubsetQ[p, {"story_select_item", "story_next_item_requested"}] &&
    ! MemberQ[p, "story_recording_made"] && ! MemberQ[p, "story_capture_vocab"]]];
assert["practice (no rec): story_recording_made present, no attempt/capture",
  With[{p = ports[call["StoryReader", 0, 0, practice, none, none]]},
    MemberQ[p, "story_recording_made"] && ! MemberQ[p, "story_attempt_made"] &&
    ! MemberQ[p, "story_capture_vocab"]]];
assert["practice (recorded): story_attempt_made + story_clear_recording, no recording_made",
  With[{p = ports[call["StoryReader", 0, 0, practice, recorded["a"], none]]},
    MemberQ[p, "story_attempt_made"] && MemberQ[p, "story_clear_recording"] &&
    ! MemberQ[p, "story_recording_made"]]];
assert["practice (scored): story_capture_vocab present",
  MemberQ[ports[call["StoryReader", 0, 0, practice, recorded["a"], scored[sc]]], "story_capture_vocab"]];

Print[hr]; Print["3. THE design property — mode switch PRESERVES (scene,pos)"]; Print[hr];
sb = Last[walkSteps[transNamed, call["StoryReader", 0, 0, browse, none, none],
        {vis["story_next_item_requested"]}]["states"]];
assert["browse next -> (scene 0, pos 1)", sb === call["StoryReader", 0, 1, browse, none, none]];
assert["set_mode practice PRESERVES (0,1)",
  Last[walkSteps[transNamed, sb, {vis["set_mode", practice]}]["states"]] ===
    call["StoryReader", 0, 1, practice, none, none]];
assert["set_mode full PRESERVES (0,1)",
  Last[walkSteps[transNamed, sb, {vis["set_mode", full]}]["states"]] ===
    call["StoryReader", 0, 1, full, none, none]];
assert["select_scene RESETS pos to 0",
  Last[walkSteps[transNamed, sb, {vis["select_scene", 1]}]["states"]] ===
    call["StoryReader", 1, 0, browse, none, none]];

Print[hr]; Print["4. COMPOSED — story-practice capture reaches VocabTable"]; Print[hr];
(* practise scene 0 phrase 0 (Bonjour), capture it; then open the vocab tab and
   confirm the store now holds it (proves story_capture_vocab -> vocabUpsert -> VocabTable). *)
wcap = walkSteps[transVP, mioCore,
  {vis["set_mode", practice], vis["story_recording_made", "a"], vis["story_attempt_made"],
   vis["story_capture_vocab", "Bonjour"], vis["open_vocab"]}, "AutoTau" -> True];
lab[a_] := If[MatchQ[a, tag[\[Tau], _, ___]], a[[2]], portName[a]];
assert["the capture relayed via vocabUpsert (a τ)", MemberQ[lab /@ wcap["actions"], "vocabUpsert"]];
vp = Map[Identity, viewProjections[transVP, Last[wcap["states"]]]];
(* addEntry lowercases the lookup "word" key (dedup) and keeps the original case in
   "display_word" — so the captured "Bonjour" shows as display_word "Bonjour". *)
assert["VocabTable now holds the captured word (visible via the vocab tab)",
  KeyExistsQ[vp, "vocabView"] &&
    MemberQ[#["display_word"] & /@ vp["vocabView"]["entries"], "Bonjour"]];

Print[hr]; Print["5. select_item BOUNDS — out-of-range select is a no-op (regression)"]; Print[hr];
(* The interleaving bug (2026-06-04): select_item bound the index raw, so pos could go
   out of range; targetOf then returned the empty item and attempt_made scored zero.
   selectPos keeps pos valid. *)
assert["selectPos keeps a valid index", selectPos[ph2, 1, 0] === 1];
assert["selectPos rejects out-of-range (keeps current)", selectPos[ph2, 5, 0] === 0];
assert["selectPos rejects negative (keeps current)", selectPos[ph2, -3, 1] === 1];
(* PS: load 1 item, select_item to a non-existent index 1 -> pos STAYS 0 (was: pos 1). *)
assert["PS: invalid select_item is a no-op (pos stays 0)",
  MatchQ[Last[walkSteps[transNamed, call["PS", {}, 0, none, none],
    {vis["load_material", {First[ph2]}], vis["select_item", 1]}]["states"]],
    call["PS", {_}, 0, none, none]]];
(* Story: story_select_item out of range -> pos unchanged (scene 0, was 0) *)
assert["Story: invalid story_select_item is a no-op (pos stays 0)",
  Last[walkSteps[transNamed, call["StoryReader", 0, 0, browse, none, none],
    {vis["story_select_item", 9]}]["states"]] === call["StoryReader", 0, 0, browse, none, none]];
(* COMPOSED end-to-end (your interleaving trace): after the invalid PS select + a
   StoryReader practice detour, PS's own attempt_made scores its REAL item, not the
   empty-target zero. langRead resolves via Helm in the composed system. *)
wInter = walkSteps[transVP, mioCore,
  {vis["load_material", {First[ph2]}], vis["select_item", 1], vis["recording_made", "a"],
   vis["select_scene", 1], vis["set_mode", practice], vis["story_select_item", 2],
   vis["story_recording_made", "a"], vis["story_attempt_made"], vis["attempt_made"]},
  "AutoTau" -> True];
assert["interleaved PS attempt scores the REAL item (not empty / not stuck)",
  ! wInter["stuck"] &&
    (Map[Identity, viewProjections[transVP, Last[wInter["states"]]]]["pSView"]["item"]["text"]) === "chat"];

Print[hr]; Print["ALL ASSERTIONS: ", ok[allOk]]; Print[hr];
If[! allOk, Exit[1]];
