(* ::Package:: *)

(* =====================================================================
   MiolingoSpec.wl — single entry point: load the whole L1 spec in order.
   ---------------------------------------------------------------------
   ONE Get loads everything (from anywhere — it self-locates):
       Get[".../spec/MiolingoSpec.wl"]

   It (re)loads the ENGINE first, then the spec files in dependency order.
   Loading the engine first is deliberate: it pins the NATIVE engine
   (native if[c,P] + variadic choice, PR #33; the substVv touch-gate,
   PR #34; F1/F3/F4) that the recovered specs require — the recovered
   agents use if[c,P] and flat choice with NO desugaring, so a stale
   embedded engine would fail to step them. Getting RCA_core also resets
   agentDefs, so this is a clean full reload every time.

   Paths + engine version come from spec/paths.wl (loaded relative to this
   file). The engine path is $RCA_CORE (env) or its canonical default, and
   loadEngine[] aborts if the engine checkout is behind the version this
   spec requires — see paths.wl. NB: nested Gets are fine in WL.

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

Get[FileNameJoin[{DirectoryName[$InputFileName], "paths.wl"}]];

loadEngine[];
loadRecoveredBase[];
(* function-recovery pass: give the stubbed value-functions bodies recovered
   from the Python. ADDITIVE — loaded after the recovered agents, attaches
   downvalues only. See spec/docs/function-recovery.md. *)
mioGet["VocabStoreFunctions.wl"];
mioGet["PracticeSessionFunctions.wl"];
(* Helm value-functions. HelmRecovered (the AGENT) is already loaded by
   loadRecoveredBase[]; here we only add its function bodies. helmView MUST be
   defined BEFORE MioCore: mioCore = merge[...] eagerly buildSystems each agent
   into a mu-term, computing helmView["English","fr",...] with the concrete
   initial values at that point. (mioCoreD defers to step time and tolerates
   either order; mioCore needs it now.) Helm is composed as a PURE PARALLEL
   agent — no control guard reads the language, so no restricted sync. *)
mioGet["HelmFunctions.wl"];
mioGet["MioCore.wl"];
