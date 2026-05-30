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
   form). Hence the merged unit is a mu-term VALUE — lowercase WL symbol
   `mioCore` (only "MioCore" as an agent NAME would be capitalised) — stepped
   with transVP[mioCore], not a call-based agent / transNamed.

   viewAs (defined in discipline.wl) relabels view -> decap[name]<>"View"
   (Agent->agentView, so PS->pSView, VS->vSView). It is NOT redefined here:
   doing so would shadow discipline.wl's decap version and re-expose the
   capitalised PSView/VSView.

   Cross-component links (each a complementary output/input pair, restricted):
     vAdd  : PS.capture_vocab(word)  --vAdd!(word)-->   VS adds the word
     pLoad : VS.practise_filtered    --pLoad!(phrases)--> PS loads them

   LOAD ORDER: RCA_core.wl, discipline.wl, PracticeSessionRecovered.wl,
   VocabStoreRecovered.wl, then this file. Initial state: Practice with no
   material; VocabStore signed-in, empty.

   VERIFIED on the engine (2026-05-31): transVP[mioCore] external ready set is
   {add, import_bulk, load_material, pSView, set_filter, set_sort, vSView}
   — no bare `view` clash; vAdd/pLoad restricted (internal tau).
   ===================================================================== *)

mioCore =
  merge[
    {"PS" -> call["PS", {}, 0, none, none],
     "VS" -> call["VS", signedIn, {}, alpha, none, none]},
    {label["vAdd"], label["pLoad"]}];

(* Compact call-based twin (mergeDefined): same composition, but stepped with
   transNamed and with call-based successors — no mu-term bulk. Use this for
   simulation / trace work; mioCore stays as the canonical mu-term. Requires
   the transition-time transNamed[relabel] engine change (RCA_core branch
   relabel-transition-time); under the old static rule the view-rename no-ops
   on the bare calls and the views would clash. *)
mioCoreD =
  mergeDefined[
    {"PS" -> call["PS", {}, 0, none, none],
     "VS" -> call["VS", signedIn, {}, alpha, none, none]},
    {label["vAdd"], label["pLoad"]}];
