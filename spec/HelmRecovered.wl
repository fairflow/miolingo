(* ::Package:: *)

(* =====================================================================
   miolingo / L1 — Helm (Session / language settings), RECOVERED
   ---------------------------------------------------------------------
   Recovered from src/ui/sidebar.py + src/ui/language_state.py, NOT invented.
   language_state.py is explicit that "the sidebar is the sole owner of
   language" (it raises a tripwire if any other module writes the language
   keys); every other module READS via read_source_lang / read_target_code /
   read_training_lang. That is precisely the view!/afforded discipline: Helm
   OWNS the session settings and publishes a read-only projection; Vocab, PS and
   the oracles (g2pOracle/enrichOracle/TTS) READ that projection — they never
   write it.

   STATE: Helm[source, target, tts, speed]
     source : the user's native language NAME  (e.g. "English")  — source_language
     target : the target/material language CODE (e.g. "fr")      — material_language
     tts    : the TTS engine                    (e.g. google | espeak)
     speed  : speech rate (wpm)                 — only meaningful for espeak

   PORTS (sidebar controls):
     view!         always — the helmView projection everyone reads
     langRead!     always — INTERNAL read port (restricted in mioCore): emits
                   the full {source, target} pair for a borrower that needs
                   BOTH halves at point of use — enrichment renders INTO the
                   source (Vocab.autofill only). Not a UI control.
     targetRead!   always — INTERNAL read port (restricted in mioCore): emits
                   ONLY the target code — the app's read_target_code
                   (language_state.py). The SCORING borrow (PS.attempt_made,
                   StoryReader.story_attempt_made): practice identity is the
                   TARGET; narrowing the borrow makes "a source switch cannot
                   affect a practice record" a property of the port structure
                   (ARCHITECTURE.md "The language pair is asymmetric").
     set_source    set the source (native) language name
     set_target    set the target language code (target_language mirrors it)
     set_tts       set the TTS engine
     set_speed     ONLY when tts === espeak  (the wpm slider shows only for
                   espeak in sidebar.py — a genuine guard)

   COMPOSITION (updated 2026-06-01): Helm is composed into mioCore as a PURE
   PARALLEL agent — NO control guard in Vocab/PS reads the language (it is passive
   data the oracles consume, like the logical clock), so there is no restricted
   channel: Helm rides alongside, contributing its helmView projection and its
   set_* inputs to the system ready set. (Originally kept standalone for exactly
   that reason; merging it in costs nothing and surfaces its viewport beside
   pSView/vocabView.) If a guard ever comes to depend on a setting, add the
   corresponding restricted sync at that point.

   LEAF agent (every branch loops back to Helm) — no sub-agent expansion.
   LOAD ORDER: RCA_core.wl, discipline.wl, then this (+ HelmFunctions.wl).
   ===================================================================== *)

defineAgent["Helm", {source, target, tts, speed, asr, asrModel},
  choice[
    precede[label["view", param[helmView[source, target, tts, speed, asr, asrModel]]],
      call["Helm", source, target, tts, speed, asr, asrModel]],
    (* internal READ ports (restricted in mioCore): borrowers PULL fresh at
       the point of use. Self-loops — always offered, never changing Helm —
       so a consumer waiting at the read is forced (by its own sequencing)
       to take it and gets Helm's CURRENT value; no cached copy, no
       staleness. See ARCHITECTURE.md "Borrowed vs owned data". Distinct
       from the external `view` projection. TWO reads, matching the app's
       read functions AND the asymmetry of the pair: langRead = the full
       pair (enrichment needs both); targetRead = the target code only
       (@src language_state.py read_target_code — scoring's borrow, so a
       practice record provably cannot depend on the source). *)
    precede[label["langRead", param[{source, target}]],
      call["Helm", source, target, tts, speed, asr, asrModel]],
    precede[label["targetRead", param[target]],
      call["Helm", source, target, tts, speed, asr, asrModel]],
    precede[coLabel["set_source", binding[s]],
      call["Helm", s, target, tts, speed, asr, asrModel]],
    precede[coLabel["set_target", binding[t]],
      call["Helm", source, t, tts, speed, asr, asrModel]],
    precede[coLabel["set_tts", binding[e]],
      call["Helm", source, target, e, speed, asr, asrModel]],
    (* the wpm slider is espeak-only in sidebar.py (tts_is_espeak guard) *)
    if[tts === espeak,
      precede[coLabel["set_speed", binding[w]],
        call["Helm", source, target, tts, w, asr, asrModel]]],
    (* ASR engine (system | whisper); always settable. *)
    precede[coLabel["set_asr", binding[a]],
      call["Helm", source, target, tts, speed, a, asrModel]],
    (* the Whisper model size (tiny|base|small|medium) is only meaningful for
       whisper — guarded exactly like set_speed is gated on espeak. *)
    if[asr === whisper,
      precede[coLabel["set_asr_model", binding[m]],
        call["Helm", source, target, tts, speed, asr, m]]]]]
