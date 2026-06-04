(* ::Package:: *)

(* =====================================================================
   miolingo / L1 — Story Reader value-functions
   ---------------------------------------------------------------------
   Bodies for the stubs StoryReaderRecovered.wl names: the scene-content
   boundary (sceneOf) and the published projection (storyView). ADDITIVE;
   load AFTER StoryReaderRecovered.wl. See spec/docs/story-reader-recovery.md.

   sceneOf[scene] — the STORY-CONTENT BOUNDARY. In the app the scenes live in
   per-language JSON files (story_tab.py:_extract_scene_phrases reads them) — an
   external, read-only data source. Properly this is a `StoryLibrary` STORE agent
   read across a port (parallel to VocabTable; see the Naming/store tier in
   ARCHITECTURE.md) — DEFERRED this round to keep the focus on the interaction +
   the practice-loop reuse. Until then sceneOf is a small in-spec FIXTURE standing
   in for that store, shaped EXACTLY as _extract_scene_phrases returns
   ({text, translation, ipa}) so the practice loop runs over it unchanged.
   When the store lands, StoryReader gains a visible `open_story` entry guarding a
   `storyRead` τ (the open_vocab / open_practice pattern), and sceneOf is replaced
   by that pull. Marked here so the cloud/incompleteness inventory stays honest. *)
sceneOf[0] := {
  <|"text" -> "Bonjour", "translation" -> "Hello", "ipa" -> "bɔ̃ʒuʁ"|>,
  <|"text" -> "Comment ça va?", "translation" -> "How are you?", "ipa" -> "kɔmɑ̃ sa va"|>};
sceneOf[1] := {
  <|"text" -> "Au revoir", "translation" -> "Goodbye", "ipa" -> "o ʁəvwaʁ"|>};
sceneOf[_Integer] := {};


(* storyView[scene, pos, mode, rec, res] — the read-only projection the tab
   publishes; the skin renders it per mode (full ⇒ whole story; browse ⇒ scene +
   parallel translation at pos; practice ⇒ item + recording/score). A projection,
   never raw state. `item`/`score` reuse the PS shape so a skin can share render
   code, mirroring the loop reuse. sceneOf is held _List so Length/targetOf only
   compute once the scene is concrete. *)
storyView[scene_, pos_, mode_, rec_, res_] := With[{phrases = sceneOf[scene]},
  <|"scene" -> scene,
    "mode" -> mode,
    "pos" -> pos,
    "count" -> Length[phrases],
    "phrases" -> phrases,
    "item" -> If[Length[phrases] > 0, targetOf[phrases, pos], None],
    "hasRecording" -> (rec =!= none),
    "score" -> Replace[res, {scored[r_] :> r, none -> None}]|>];
