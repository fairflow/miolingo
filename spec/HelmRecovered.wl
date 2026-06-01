(* ::Package:: *)

(* =====================================================================
   miolingo / L1 — Helm (Session / language settings), RECOVERED
   ---------------------------------------------------------------------
   Recovered from src/ui/sidebar.py + src/ui/language_state.py, NOT invented.
   language_state.py is explicit that "the sidebar is the sole owner of
   language" (it raises a tripwire if any other module writes the language
   keys); every other module READS via read_source_lang / read_target_code /
   read_training_lang. That is precisely the view!/afforded discipline: Helm
   OWNS the session settings and publishes a read-only projection; VS, PS and
   the oracles (g2pOracle/enrichOracle/TTS) READ that projection — they never
   write it.

   STATE: Helm[source, target, tts, speed]
     source : the user's native language NAME  (e.g. "English")  — source_language
     target : the target/material language CODE (e.g. "fr")      — material_language
     tts    : the TTS engine                    (e.g. google | espeak)
     speed  : speech rate (wpm)                 — only meaningful for espeak

   PORTS (sidebar controls):
     view!         always — the helmView projection everyone reads
     set_source    set the source (native) language name
     set_target    set the target language code (target_language mirrors it)
     set_tts       set the TTS engine
     set_speed     ONLY when tts === espeak  (the wpm slider shows only for
                   espeak in sidebar.py — a genuine guard)

   COMPOSITION (decision — see helm-recovery / the PR): Helm is STANDALONE.
   No control guard in VS/PS reads the language (it is passive data the oracles
   consume, like the logical clock), so Helm is not synced into mioCore; its
   projection feeds the oracles at their boundary. Promote to a synced agent
   only if a guard ever comes to depend on a setting.

   LEAF agent (every branch loops back to Helm) — no sub-agent expansion.
   LOAD ORDER: RCA_core.wl, discipline.wl, then this (+ HelmFunctions.wl).
   ===================================================================== *)

defineAgent["Helm", {source, target, tts, speed},
  choice[
    precede[label["view", param[helmView[source, target, tts, speed]]],
      call["Helm", source, target, tts, speed]],
    precede[coLabel["set_source", binding[s]],
      call["Helm", s, target, tts, speed]],
    precede[coLabel["set_target", binding[t]],
      call["Helm", source, t, tts, speed]],
    precede[coLabel["set_tts", binding[e]],
      call["Helm", source, target, e, speed]],
    (* the wpm slider is espeak-only in sidebar.py (tts_is_espeak guard) *)
    if[tts === espeak,
      precede[coLabel["set_speed", binding[w]],
        call["Helm", source, target, tts, w]]]]]
