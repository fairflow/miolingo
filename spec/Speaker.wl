(* ::Package:: *)

(* =====================================================================
   miolingo / L1 — Speaker: the USER-as-agent test harness
   ---------------------------------------------------------------------
   A CCS model of the practising USER for closed-loop testing: where walk
   plans supply recording_made values from the open environment, Speaker is
   that environment AS AN AGENT — it works through a script of utterances,
   OUTPUTTING each as a recording on the recording_made channel. Composed
   with mioCore and with recording_made RESTRICTED, "the user speaks"
   becomes an internal τ: the simulator plays the user.

   The recording VALUE is synthAudio[text, lang] — the TTS oracle term
   (uninterpreted at L1; espeak -w at L3). Its partner oracle is
   recognisePhonemes (ASR). The pair obeys the ROUND-TRIP LAW the harness
   tests at both levels:

       recognisePhonemes[synthAudio[text, lang], lang] == phonemesOf[text]

   i.e. speaking a word and recognising it recovers the word's phonemes —
   so scoring the speech of the TARGET item must give an exact match, and
   speaking a DIFFERENT word must score lower. spec/tests/speaker_test.wls
   gives the oracles law-satisfying downvalues and asserts exactly that;
   swift/Miolingo/Sources/MiolingoHarness deploys the same law on the real
   engines (espeak TTS → SFSpeech/Whisper ASR).

   STATE: Speaker[script]   — script : the utterances left to speak (list)

   LEAF agent; one port:
     recording_made!(synthAudio[text, lang])   speak the next utterance
   (Output, where PS has the dual input — exactly like VocabTable's
   vocabRead!/vocabRead? pairing.) Each utterance is <|"text"->_, "lang"->_|>.
   ===================================================================== *)

(* held-until-concrete discipline (cf. deleteFrom's id_Integer): pattern-gate the
   script accessors so they stay symbolic until a NON-EMPTY concrete list lands —
   otherwise First/Rest fire on the empty/symbolic script during held derivation
   (First::nofirst noise). *)
speakTerm[script_List /; Length[script] > 0] :=
  synthAudio[First[script]["text"], First[script]["lang"]];
restScript[script_List /; Length[script] > 0] := Rest[script];

defineAgent["Speaker", {script},
  if[Length[script] > 0,
    precede[
      label["recording_made", param[speakTerm[script]]],
      call["Speaker", restScript[script]]]]]
