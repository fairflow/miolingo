(* ::Package:: *)

(* =====================================================================
   miolingo / L1 — MioCore: PracticeSession || VocabStore (composed)
   ---------------------------------------------------------------------
   The merged unit. The two recovered agents are composed in parallel,
   their cross-component channels restricted (so the inter-component links
   become internal tau steps), AND each agent's view! port is RENAMED to a
   qualified {AgentName}View! so the per-agent view ports do not clash.

   view! is a per-agent discipline port, so a naive par would expose two
   `view` ports. The merge resolves this with `relabel` — renaming happens
   at COMPOSITION time; the reusable agents keep the bare `view`. Renaming
   needs the port name visible, which it is in a mu-term but NOT in a bare
   call[...], so the merge composes the buildSystem MU-TERMS (the canonical
   form). Hence MioCore is a mu-term, stepped with transVP[MioCore] (not a
   call-based agent / transNamed).

   viewAs[name, muTerm] := relabel[muTerm, {"view" -> name<>"View"}].

   Cross-component links (each a complementary output/input pair, restricted):
     vAdd  : PS.capture_vocab(word)  --vAdd!(word)-->   VS adds the word
     pLoad : VS.practise_filtered    --pLoad!(phrases)--> PS loads them

   LOAD ORDER: RCA_core.wl, discipline.wl, PracticeSessionRecovered.wl,
   VocabStoreRecovered.wl, then this file. Initial state: Practice with no
   material; VocabStore signed-in, empty.

   VERIFIED on the engine (2026-05-31): external ready set is
   {add, import_bulk, load_material, PSView, set_filter, set_sort, VSView}
   — no bare `view` clash; vAdd/pLoad restricted (internal tau).
   ===================================================================== *)

viewAs[name_String, muTerm_] := relabel[muTerm, {"view" -> name <> "View"}];

MioCore =
  merge[
    {"PS" -> call["PS", {}, 0, none, none],
     "VS" -> call["VS", signedIn, {}, alpha, none, none]},
    {label["vAdd"], label["pLoad"]}];
