(* ::Package:: *)

(* =====================================================================
   miolingo / L1 — Story Reader, RECOVERED (UI-first)
   ---------------------------------------------------------------------
   Recovered from src/ui/story_tab.py (NOT invented). The Story Reader tab
   lets the user explore one story three ways and practise pronunciation from
   it WITHOUT leaving the story — see spec/docs/story-reader-recovery.md.

   THE DESIGN (plan A, 2026-06-04). The app runs TWO copies of the practice
   loop (Quick Practice, and Story "Practice Mode" via render_practice_interface
   with key_prefix="story" + separate state) — "grew like Topsy". Here both run the
   SAME interaction (StoryPractice mirrors PSActive; value-functions targetOf/
   evaluate are shared). It is written per-context rather than one shared definition
   — an engine constraint, see story-reader-recovery.md "Why the loop isn't a single
   shared definition". And the app's three story views keep INDEPENDENT positions
   (story_practice_index vs the scene-browser's); here StoryReader owns ONE narrative
   position (scene, pos) and the three modes are affordances over it, so switching
   mode PRESERVES the position. That divergence is a deliberate fix (flagged in
   PROVENANCE).

   STATE: StoryReader[scene, pos, mode, rec, res]
     scene : Integer   which scene (sceneOf[scene] gives its phrases)
     pos   : Integer   phrase index within the scene — the narrative position
     mode  : full | browse | practice   the reading mode
     rec   : none | recorded[audio]     (practice only)
     res   : none | scored[r]           (practice only)

   MODES (@src story_tab.py:348 the st.radio mode selector):
     full     "📄 Full Story"   — view! the whole story; no phrase nav
     browse   "🎬 Scene by Scene"— scene with parallel translation; phrase nav
     practice "🎙️ Practice Mode" — the full practice loop over the scene phrases

   Always available: view! (storyView), set_mode (PRESERVES scene,pos; clears
   rec,res), select_scene (new scene ⇒ pos:=0). The mode-specific ports are
   spliced via a bare call[...] summand (its transitions join the choice), gated
   by the mode guard — same idiom as PS splicing PSActive.

   The narrative position lives HERE; practice mode borrows it (StoryPractice
   returns to StoryReader with the moved pos). So flipping browse↔practice keeps
   your place — read scene 5, practise scene 5.

   LOAD ORDER: after discipline.wl and the other recovered agents. storyView/sceneOf
   bodies arrive in StoryFunctions.wl (loaded after, like the other *Functions.wl).
   ===================================================================== *)

defineAgent["StoryReader", {scene, pos, mode, rec, res},
  choice[
    (* @src story_tab.py:295 (render_story_reader) — the tab's published view *)
    precede[label["view", param[storyView[scene, pos, mode, rec, res]]],
      call["StoryReader", scene, pos, mode, rec, res]],
    (* @src story_tab.py:348 — the mode radio. PRESERVES (scene,pos); leaving a
       practice session clears its rec/res. *)
    precede[coLabel["set_mode", binding[m]],
      call["StoryReader", scene, pos, m, none, none]],
    (* @src story_tab.py:193 — scene selector. New scene ⇒ position resets. *)
    precede[coLabel["select_scene", binding[s]],
      call["StoryReader", s, 0, mode, none, none]],
    (* browse: scroll the scene with parallel translation (phrase nav only) *)
    if[mode === browse, call["StoryBrowse", scene, pos]],
    (* practice: the full record/score/capture loop over the scene's phrases *)
    if[mode === practice, call["StoryPractice", scene, pos, rec, res]]]]


(* --- browse mode: phrase navigation over the scene (no record/score) ---
   Ports are story_-prefixed so they are DISTINCT controls from Quick Practice's
   (the app uses key_prefix="story" for exactly this); successors return to
   StoryReader in browse mode, so the narrative position is owned by StoryReader
   and survives a mode switch. *)
defineAgent["StoryBrowse", {scene, pos},
  choice[
    precede[coLabel["story_select_item", binding[i]],
      call["StoryReader", scene, selectPos[sceneOf[scene], i, pos], browse, none, none]],
    if[pos < Length[sceneOf[scene]] - 1,
      precede[coLabel["story_next_item_requested"],
        call["StoryReader", scene, pos + 1, browse, none, none]]],
    if[pos > 0,
      precede[coLabel["story_prev_item_requested"],
        call["StoryReader", scene, pos - 1, browse, none, none]]]]]


(* --- practice mode: the practice loop over the scene's phrases ---
   The SAME interaction as PSActive (the plan's reuse target), written per-context
   (see PSActive's note + story-reader-recovery.md on why it isn't one shared
   definition). Value-functions ARE shared (targetOf, evaluate). Capture relays to
   VocabTable on vocabUpsert (the same store channel PS capture uses); scoring
   borrows the language from Helm on langRead (a τ). Both stay UNPREFIXED — they are
   the store / Helm channels, shared by design; only the user-facing inputs carry
   story_. Successors return to StoryReader (practice mode), preserving (scene,pos). *)
defineAgent["StoryPractice", {scene, pos, rec, res},
  choice[
    precede[coLabel["story_select_item", binding[i]],
      call["StoryReader", scene, selectPos[sceneOf[scene], i, pos], practice, none, none]],
    if[rec === none,
      precede[coLabel["story_recording_made", binding[audio]],
        call["StoryReader", scene, pos, practice, recorded[audio], none]],
      choice[
        precede[coLabel["story_attempt_made"],
          precede[coLabel["langRead", binding[lp]],
            call["StoryReader", scene, pos, practice, rec,
              scored[evaluate[targetOf[sceneOf[scene], pos], rec, lp]]]]],
        precede[coLabel["story_clear_recording"],
          call["StoryReader", scene, pos, practice, none, none]]]],
    if[pos < Length[sceneOf[scene]] - 1,
      precede[coLabel["story_next_item_requested"],
        call["StoryReader", scene, pos + 1, practice, none, none]]],
    if[pos > 0,
      precede[coLabel["story_prev_item_requested"],
        call["StoryReader", scene, pos - 1, practice, none, none]]],
    if[res =!= none,
      precede[coLabel["story_capture_vocab", binding[word]],
        precede[label["vocabUpsert", param[word]],
          call["StoryReader", scene, pos, practice, rec, res]]]]]]
