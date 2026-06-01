(* ::Package:: *)

(* =====================================================================
   miolingo / L1 — Helm value-functions, RECOVERED (function pass)
   ---------------------------------------------------------------------
   The functional bodies for the Helm agent (HelmRecovered.wl), recovered
   from src/ui/sidebar.py + language_state.py. ADDITIVE: attaches downvalues
   only; load AFTER the recovered agent.

   helmView is the read-only projection the rest of the system reads (the
   read_source_lang / read_target_code / read_training_lang helpers). It is
   the espeak/translation/TTS oracles' source of the (source, target) pair:
     g2pOracle      : voice = target (the material language code)
     enrichOracle   : translate source -> target
     TTS            : tts engine + speed
   ===================================================================== *)

trainingNameOf::usage =
  "trainingNameOf[code] gives the training-map full language name for a target \
language code (e.g. \"fr\" -> \"French\"); unknown codes pass through as their \
own string. Recovered from the sidebar's target-code -> name mapping.";
helmView::usage =
  "helmView[source, target, tts, speed] is Helm's read-only session projection \
<|source, target, language, tts, speed|> — the (source, target) language pair \
(plus TTS engine/speed) that the rest of the system reads (it never writes it). \
`language` is trainingNameOf[target].";

(* target-code -> training-map full name (sidebar's language map; the common
   set — unknown codes pass through, so it degrades gracefully) *)
helmTrainingNames = <|
  "en" -> "English", "fr" -> "French", "pt" -> "Portuguese",
  "de" -> "German", "es" -> "Spanish", "it" -> "Italian"|>;
trainingNameOf[code_] := Lookup[helmTrainingNames, ToString[code], ToString[code]];

(* target_String (not target_): the SAME held-until-concrete discipline as
   vocabView[entries_List] / sessionView[phrases_List]. In merge[], buildSystem
   expands Helm into a mu-term EAGERLY; an unrestricted target_ lets helmView
   fire while `target` is still the formal binder SYMBOL, so trainingNameOf[target]
   collapses to trainingNameOf["target"] -> "target" BEFORE substitution puts the
   real "fr" in (the language-stuck-on-the-binder bug, surfaced by composing Helm
   into mioCore). Gating on target_String keeps the whole projection symbolic
   until the concrete code lands, then computes consistently. *)
helmView[source_, target_String, tts_, speed_] := <|
  "source"   -> source,                  (* native language NAME *)
  "target"   -> target,                  (* target language CODE *)
  "language" -> trainingNameOf[target],  (* target's training-map name *)
  "tts"      -> tts,
  "speed"    -> speed|>;
