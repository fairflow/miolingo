(* ::Package:: *)

(* =====================================================================
   spec/walk-tests.wl — a batch of value-carrying test SEQUENCES (plans)
   that drive the spec through walk WITHOUT any typing into input fields.
   ---------------------------------------------------------------------
   A test is a PLAN: a list of plan-entries
     vis["port"]          take a visible action by port name (no value)
     vis["port", value]   take a value-carrying input port, supplying value
     tau["chan"]          take an internal sync on a named channel
   (the vocabulary of walkResolve / walkSteps, discipline.wl + walk.wl).

   Run a plan with the existing machinery:
     walkSteps[transVP,   mioCore,  walkTests["full-roundtrip"]]   (* mu-term  *)
     walkSteps[transNamed, mioCoreD, walkTests["full-roundtrip"]]  (* call form *)
   or load one into the GUI from walkUI's "Run test" menu.

   EVERY sequence runs to completion on BOTH mioCore (transVP) and mioCoreD
   (transNamed) — that is the standing invariant (see
   spec/tests/walk_sequences_test.wls). Values are embedded, so nothing has
   to be typed; string words are quoted, sort keys are the Enum symbols
   (alpha|recent|oldest), ids are integers, payloads are Associations.

   NAMING / CLASSIFICATION (kebab-case keys):
     vs-*    : VocabStore-only ports (capture, edit, sort/filter/export)
     ps-*    : PracticeSession-only ports (load, navigate, record/score)
     sync-*  : a single cross-component synchronisation (pLoad / vAdd) —
               only meaningful in the COMPOSED system, not VS/PS alone
     helm-*  : Helm session/language settings. Thin in ISOLATION (a lone Helm
               just flips a field); meaningful only in the COMPOSED system,
               where the (source, target) pair Helm owns is the data the vocab/
               practice sides and the oracles read — so these set the pair and
               then drive a VS/PS step across that seam.
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

  (* --- VocabStore: capture, dedup, sort, filter, export --------------- *)
  "vs-capture" -> {
    vis["add", <|"word" -> "chat", "translation" -> "cat", "ipa" -> "ʃa"|>],
    vis["add", <|"word" -> "chien", "translation" -> "dog"|>],
    vis["add", <|"word" -> "chat"|>],            (* dedup: bumps times_seen *)
    vis["set_sort", recent],
    vis["set_filter", "ch"],
    vis["export"]},

  (* --- VocabStore: bulk import then sort/export ----------------------- *)
  "vs-import" -> {
    vis["import_bulk", <|"contents" -> "(en,fr)\nsouris|mouse\nchien|dog",
                         "expectedTarget" -> "fr"|>],
    vis["set_sort", oldest],
    vis["export"]},

  (* --- VocabStore: the per-entry edit surface ------------------------- *)
  "vs-edit" -> {
    vis["add", <|"word" -> "chat", "translation" -> "cat"|>],
    vis["begin_edit", 1],
    vis["update", <|"translation" -> "feline"|>],   (* in edit-mode *)
    vis["begin_edit", 1],
    vis["cancel_edit"],
    vis["update_notes", <|"id" -> 1, "notes" -> "seen in a book"|>],
    vis["autofill", 1],
    tau["langRead"],                                (* autofill PULLS the language *)
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
    vis["attempt_made"],
    vis["capture_vocab", "souris"],
    tau["vAdd"]},                                   (* capture relays to VS *)

  (* --- sync: VS practise_filtered -> PS load (pLoad) ------------------ *)
  "sync-pload" -> {
    vis["add", <|"word" -> "chat", "translation" -> "cat"|>],
    vis["set_filter", "ch"],
    vis["practise_filtered"],
    tau["pLoad"],
    vis["select_item", 0]},

  (* --- sync: VS autofill PULLS the language from Helm (langRead) ------
     The first BORROWED-DATA read: autofill needs the (source, target) pair to
     enrich, so it reads Helm's langRead as a prefix (internal tau in mioCore).
     Only meaningful in the COMPOSED system (Helm must be present to answer). *)
  "sync-langread" -> {
    vis["add", <|"word" -> "chat", "translation" -> "cat"|>],
    vis["autofill", 1],
    tau["langRead"]},

  (* --- sync: PS capture_vocab -> VS add (vAdd) ----------------------- *)
  "sync-vadd" -> {
    vis["load_material", {<|"text" -> "chat", "translation" -> "cat", "ipa" -> "ʃa"|>}],
    vis["recording_made", "audio"],
    vis["attempt_made"],
    vis["capture_vocab", "chat"],
    tau["vAdd"]},

  (* --- Helm: settings tour + the espeak-only set_speed guard ---------- *)
  "helm-settings" -> {
    vis["set_source", "Italian"],
    vis["set_target", "pt"],          (* language now Portuguese in helmView *)
    vis["set_tts", espeak],           (* unlocks the wpm slider (set_speed) *)
    vis["set_speed", 300],
    vis["set_tts", google]},          (* set_speed disappears again *)

  (* --- Helm -> VocabStore: set the language pair, THEN capture --------- *)
  "helm-then-capture" -> {
    vis["set_target", "pt"],          (* choose the material language code *)
    vis["set_source", "English"],
    vis["add", <|"word" -> "casa", "translation" -> "house"|>],
    vis["set_sort", recent],
    vis["export"]},

  (* --- full end-to-end: both syncs in one run ------------------------- *)
  "full-roundtrip" -> {
    vis["set_filter", "ch"],
    vis["add", <|"word" -> "chat", "translation" -> "cat", "ipa" -> "ʃa"|>],
    vis["practise_filtered"],
    tau["pLoad"],
    vis["recording_made", "audio"],
    vis["attempt_made"],
    vis["capture_vocab", "souris"],
    tau["vAdd"]}

|>;
