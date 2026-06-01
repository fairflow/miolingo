(* ::Package:: *)

(* =====================================================================
   spec/g2p.wl — espeak grapheme-to-phoneme bridge
   ---------------------------------------------------------------------
   The FIRST external service made to run FOR REAL inside the spec: a
   WolframScript -> espeak bridge (RunProcess) that turns a written word
   into its IPA transcription. This is the IO mechanism behind the espeak
   half of the `enrichOracle` (the "ipa" it would produce); ASR
   (recognisePhonemes, audio -> phonemes) is a DIFFERENT service, not this.

   Standalone and pure-WL (no engine needed). It is NOT yet wired into the
   agents: whether to consume it as a PURE LIVE ORACLE (a function the spec
   calls) or to model espeak as a CCS SERVICE AGENT (a process with
   request/reply ports, synchronised on a channel) is an open architectural
   decision — the per-service stub->live promotion keeps the port signature
   invariant either way (see spec/docs/co-development.md).

   NB: the binary is `espeak` (NOT espeak-ng).
   ===================================================================== *)

espeakAvailableQ::usage =
  "espeakAvailableQ[] is True iff the `espeak` binary is callable.";
espeakG2P::usage =
  "espeakG2P[word, voice:\"en\"] gives espeak's IPA transcription of word \
(grapheme->phoneme) via RunProcess, or $Failed if espeak is unavailable / \
errors. Output includes stress marks (ˈ ˌ); espeakG2Pplain strips them. The \
binary is `espeak`, not espeak-ng.";
espeakG2Pplain::usage =
  "espeakG2Pplain[word, voice:\"en\"] is espeakG2P with stress marks (ˈ ˌ) \
removed — matching the spec's stress-free ipa style (e.g. \"ʃa\").";

espeakAvailableQ[] :=
  Quiet[TrueQ[RunProcess[{"espeak", "--version"}]["ExitCode"] === 0]];

espeakG2P[word_String, voice_String : "en"] := Module[{res},
  res = Quiet[RunProcess[{"espeak", "-q", "--ipa", "-v", voice, word}]];
  If[AssociationQ[res] && res["ExitCode"] === 0,
     (* RunProcess hands back stdout as raw bytes; decode UTF-8 so the IPA is
        proper Unicode (ʃ ˈ a), not the byte sequence {202,131,203,136,97}. *)
     StringTrim[FromCharacterCode[ToCharacterCode[res["StandardOutput"]], "UTF-8"]],
     $Failed]];

espeakG2Pplain[word_String, voice_String : "en"] :=
  With[{ipa = espeakG2P[word, voice]},
    If[StringQ[ipa], StringDelete[ipa, "ˈ" | "ˌ"], ipa]];
