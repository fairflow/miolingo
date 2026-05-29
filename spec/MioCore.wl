(* ::Package:: *)

(* =====================================================================
   miolingo / L1 — MioCore: PracticeSession || VocabStore (composed)
   ---------------------------------------------------------------------
   The two recovered agents composed in parallel with the cross-component
   channels restricted, so the inter-component links synchronise into
   internal tau steps and are hidden from the outside. This is the single
   unit to reason about from now on (until the next refinement).

   LOAD ORDER: RCA_core.wl, discipline.wl, PracticeSessionRecovered.wl,
   VocabStoreRecovered.wl, then this file.

   Cross-component links (composition refinement, see the two recovered
   specs), each a complementary output/input pair on an internal channel:
     vAdd   : PS.capture_vocab(word)      --vAdd!(word)-->   VS receives, adds
     pLoad  : VS.practise_filtered        --pLoad!(phrases)--> PS receives, loads

   restrict {vAdd, pLoad} makes those channels internal: the matching
   output/input become a single tau synchronisation, and the unsynced
   half-actions are removed from the external interface. Everything else
   (the user-facing ports of both agents, and both agents' view!/afforded!
   discipline ports) stays external.

   NOTE: MioCore inherits BOTH agents' view!/afforded! ports (you can view
   and query each sub-agent). A single unified view!/afforded! projecting
   the joint state is a future refinement.

   Initial state: Practice with no material; VocabStore signed-in, empty.

   VERIFIED on the engine (2026-05-30): MioCore's external ready set hides
   vAdd/pLoad; the relays synchronise into tau with the value passing
   across — tag[τ, vAdd, {w->w0}] and tag[τ, pLoad, {ps->{x1,x2}}].
   ===================================================================== *)

defineAgent["MioCore", {},
  restrict[
    par[
      call["PS", {}, 0, none, none],
      call["VS", signedIn, {}, alpha, none, none]],
    {label["vAdd"], label["pLoad"]}]]
