(* ::Package:: *)

(* =====================================================================
   MiolingoSpec.wl — single entry point: load the whole L1 spec in order.
   ---------------------------------------------------------------------
   ONE Get loads everything:
       Get["/Users/matthew/Software/working/miolingo/spec/MiolingoSpec.wl"]

   It (re)loads the ENGINE first, then the spec files in dependency order.
   Loading the engine first is deliberate: it pins the NATIVE engine
   (native if[c,P] + variadic choice, PR #33; the substVv touch-gate,
   PR #34; F1/F3/F4) that the recovered specs require — the recovered
   agents use if[c,P] and flat choice with NO desugaring, so a stale
   embedded engine would fail to step them. Getting RCA_core also resets
   agentDefs, so this is a clean full reload every time.

   NB: nested Gets are fine in WL. Adjust $rca if RCA_core.wl moves.

   What is loaded (and what is NOT):
     RCA_core.wl                  the CCS engine (feature-work, native)
     discipline.wl                view!/readyPorts + viewAs/merge helpers
     PracticeSessionRecovered.wl  PS / PSActive  (recovered, canonical)
     VocabStoreRecovered.wl       VS / VSAuthed / ...  (recovered)
     MioCore.wl                   mioCore = merge[...]  (composed mu-term value)
   The invented strawmen PracticeSession.wl / VocabStore.wl are NOT loaded
   here — they are kept only for the invented-vs-recovered contrast.

   USAGE after loading:
     transNamed[call["PS", {p1,p2}, 0, none, none]]   (* simulate an agent *)
     readyPorts[call["VS", signedIn, {e1}, alpha, none, none]]
     transVP[mioCore]                                  (* step the merged unit *)
     buildSystem[call["PS", {p1,p2}, 0, none, none]]   (* canonical mu-term *)
   ===================================================================== *)

$rca   = "/Users/matthew/Projects/private/Mathematica/RCA/RCA_core.wl";
$mlspec = "/Users/matthew/Software/working/miolingo/spec/";

Get[$rca];
Get[$mlspec <> "discipline.wl"];
Get[$mlspec <> "PracticeSessionRecovered.wl"];
Get[$mlspec <> "VocabStoreRecovered.wl"];
Get[$mlspec <> "MioCore.wl"];
