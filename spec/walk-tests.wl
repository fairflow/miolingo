(* ::Package:: *)

(* =====================================================================
   spec/walk-tests.wl — a batch of value-carrying test SEQUENCES (plans)
   that drive the spec through walk WITHOUT any typing into input fields.
   ---------------------------------------------------------------------
   A test is a PLAN: a list of plan-entries. These plans list ONLY EXTERNAL
   actions:
     vis["port"]          take a visible action by port name (no value)
     vis["port", value]   take a value-carrying input port, supplying value
   The internal syncs (vocabUpsert / goPractice / langRead / vocabRead — the VocabTable reads
   and writes) are fired AUTOMATICALLY between steps by walkSteps' maximal-progress
   mode ("AutoTau" -> True) — so plans stay readable and robust as new internal
   syncs are added (no plan edits). (A plan MAY still force a specific sync with
   tau["chan"] when a step is genuinely ambiguous; none need to here.)

   Run a plan with maximal progress (the GUI "Run test" and walk_sequences_test
   do this):
     walkSteps[transVP,   mioCore,  walkTests["full-roundtrip"], "AutoTau" -> True]
     walkSteps[transNamed, mioCoreD, walkTests["full-roundtrip"], "AutoTau" -> True]

   EVERY sequence runs to completion on BOTH mioCore (transVP) and mioCoreD
   (transNamed) — that is the standing invariant (see
   spec/tests/walk_sequences_test.wls). Values are embedded, so nothing has
   to be typed; string words are quoted, sort keys are the Enum symbols
   (alpha|recent|oldest), ids are integers, payloads are Associations.

   NAMING / CLASSIFICATION (kebab-case keys):
     vs-*    : Vocab-only ports (capture, edit, sort/filter/export)
     ps-*    : PracticeSession-only ports (load, navigate, record/score)
     sync-*  : a single cross-component synchronisation (goPractice / vocabUpsert) —
               only meaningful in the COMPOSED system, not Vocab/PS alone
     helm-*  : Helm session/language settings. Thin in ISOLATION (a lone Helm
               just flips a field); meaningful only in the COMPOSED system,
               where the (source, target) pair Helm owns is the data the vocab/
               practice sides and the oracles read — so these set the pair and
               then drive a Vocab/PS step across that seam.
     full-*  : an end-to-end run touching both syncs
   Add new sequences under the same prefixes.
   ===================================================================== *)

walkTests::usage =
  "walkTests is an Association <|name -> plan|> of value-carrying test \
sequences for the walk simulator. Each plan is a list of vis[\"port\"], \
vis[\"port\", value] and tau[\"chan\"] entries; run with walkSteps[tf, s0, \
plan] or from walkUI's \"Run test\" menu. Every sequence completes on both \
mioCore (transVP) and mioCoreD (transNamed).";

walkTests = <|

  (* --- Vocab: capture, dedup, sort, filter, export --------------- *)
  "vs-capture" -> {
    vis["open_vocab"],                           (* enter the Vocabulary tab *)
    vis["add", <|"word" -> "chat", "translation" -> "cat", "ipa" -> "ʃa"|>],
    vis["add", <|"word" -> "chien", "translation" -> "dog"|>],
    vis["add", <|"word" -> "chat"|>],            (* dedup: bumps times_seen *)
    vis["set_sort", recent],
    vis["set_filter", "ch"],
    vis["export"]},

  (* --- Vocab: bulk import then sort/export ----------------------- *)
  "vs-import" -> {
    vis["open_vocab"],
    vis["import_bulk", <|"contents" -> "(en,fr)\nsouris|mouse\nchien|dog",
                         "expectedTarget" -> "fr"|>],
    vis["set_sort", oldest],
    vis["export"]},

  (* --- Vocab: the per-entry edit surface ------------------------- *)
  "vs-edit" -> {
    vis["open_vocab"],
    vis["add", <|"word" -> "chat", "translation" -> "cat"|>],
    vis["begin_edit", 1],
    vis["update", <|"translation" -> "feline"|>],   (* in edit-mode *)
    vis["begin_edit", 1],
    vis["cancel_edit"],
    vis["update_notes", <|"id" -> 1, "notes" -> "seen in a book"|>],
    vis["autofill", 1],                             (* langRead auto-fires (pull language) *)
    vis["delete", 1]},

  (* --- PracticeSession: load + navigate ------------------------------- *)
  "ps-navigate" -> {
    vis["load_material", {<|"text" -> "chat", "translation" -> "cat", "ipa" -> "ʃa"|>,
                          <|"text" -> "chien", "translation" -> "dog", "ipa" -> "ʃjɛ̃"|>,
                          <|"text" -> "souris", "translation" -> "mouse", "ipa" -> "muʁi"|>}],
    vis["next_item_requested"],
    vis["next_item_requested"],
    vis["prev_item_requested"],
    vis["select_item", 0],
    vis["clear_material"]},

  (* --- PracticeSession: record, re-record, attempt (score) ------------ *)
  "ps-score" -> {
    vis["load_material", {<|"text" -> "chat", "translation" -> "cat", "ipa" -> "ʃa"|>}],
    vis["recording_made", "audio-A"],
    vis["clear_recording"],
    vis["recording_made", "audio-B"],
    vis["attempt_made"],                            (* langRead auto-fires for scoring *)
    vis["capture_vocab", "souris"]},                (* vocabUpsert auto-fires (relay to Vocab) *)

  (* --- sync: Vocab practise_vocab (FILTERED) -> PS pull (goPractice+vocabRead) ---
     a filter is set, so PS pulls then shapes with the filtered subset. *)
  "sync-practise" -> {
    vis["open_vocab"],
    vis["add", <|"word" -> "chat", "translation" -> "cat"|>],
    vis["set_filter", "ch"],
    vis["practise_vocab"],                          (* goPractice→vocabRead auto-fires *)
    vis["select_item", 0]},

  (* --- sync: Vocab practise_vocab (ALL, no filter) -> PS pull (goPractice+vocabRead) ---
     no filter, so the SAME signal makes PS pull the whole vocab.
     practiseList[entries, none] = all entries. *)
  "practise-all" -> {
    vis["open_vocab"],
    vis["add", <|"word" -> "chat", "translation" -> "cat"|>],
    vis["add", <|"word" -> "chien", "translation" -> "dog"|>],
    vis["practise_vocab"],                          (* goPractice→vocabRead auto-fires *)
    vis["select_item", 1]},

  (* --- PS PULL route: open_practice reads VocabTable, then load the whole vocab.
     open_practice is the VISIBLE entry; the vocabRead pull auto-fires after it. --- *)
  "ps-pull-all" -> {
    vis["open_vocab"],
    vis["add", <|"word" -> "chat", "translation" -> "cat"|>],
    vis["open_practice"],                           (* vocabRead auto-fires (PS pulls) *)
    vis["load_vocab"],
    vis["select_item", 0]},

  (* --- PS PULL route, filtered: load_filtered carries the filter string --- *)
  "ps-pull-filtered" -> {
    vis["open_vocab"],
    vis["add", <|"word" -> "chat", "translation" -> "cat"|>],
    vis["add", <|"word" -> "souris", "translation" -> "mouse"|>],
    vis["open_practice"],                           (* vocabRead auto-fires (PS pulls) *)
    vis["load_filtered", "ch"]},

  (* --- sync: Vocab autofill PULLS the language from Helm (langRead) ------
     The first BORROWED-DATA read: autofill needs the (source, target) pair to
     enrich, so it reads Helm's langRead as a prefix (internal tau in mioCore).
     Only meaningful in the COMPOSED system (Helm must be present to answer). *)
  "sync-langread" -> {
    vis["open_vocab"],
    vis["add", <|"word" -> "chat", "translation" -> "cat"|>],
    vis["autofill", 1]},                            (* langRead auto-fires *)

  (* --- sync: PS capture_vocab -> Vocab add (vocabUpsert) ----------------------- *)
  "sync-vadd" -> {
    vis["load_material", {<|"text" -> "chat", "translation" -> "cat", "ipa" -> "ʃa"|>}],
    vis["recording_made", "audio"],
    vis["attempt_made"],                            (* langRead auto-fires for scoring *)
    vis["capture_vocab", "chat"],                   (* vocabUpsert auto-fires -> VocabTable (direct) *)
    vis["open_vocab"]},                             (* now view the captured word in the tab *)

  (* --- Helm: settings tour + the espeak-only set_speed guard ---------- *)
  "helm-settings" -> {
    vis["set_source", "Italian"],
    vis["set_target", "pt"],          (* language now Portuguese in helmView *)
    vis["set_tts", espeak],           (* unlocks the wpm slider (set_speed) *)
    vis["set_speed", 300],
    vis["set_tts", google]},          (* set_speed disappears again *)

  (* --- Helm -> Vocab: set the language pair, THEN capture --------- *)
  "helm-then-capture" -> {
    vis["set_target", "pt"],          (* choose the material language code *)
    vis["set_source", "English"],
    vis["open_vocab"],
    vis["add", <|"word" -> "casa", "translation" -> "house"|>],
    vis["set_sort", recent],
    vis["export"]},

  (* --- full end-to-end: both syncs in one run ------------------------- *)
  "full-roundtrip" -> {
    vis["open_vocab"],
    vis["set_filter", "ch"],
    vis["add", <|"word" -> "chat", "translation" -> "cat", "ipa" -> "ʃa"|>],
    vis["practise_vocab"],                          (* goPractice→vocabRead auto-fires *)
    vis["recording_made", "audio"],
    vis["attempt_made"],                            (* langRead auto-fires for scoring *)
    vis["capture_vocab", "souris"]}                 (* vocabUpsert auto-fires (relay to Vocab) *)

|>;
