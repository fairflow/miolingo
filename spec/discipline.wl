(* ::Package:: *)

(* =====================================================================
   miolingo / L1 — shared modelling discipline
   ---------------------------------------------------------------------
   Every miolingo agent carries, on top of its domain ports, TWO standing
   output-only ports — always in the ready set (self-loops):

     view!      a projection f(state) of current state (the read-only
                view); state-dependent. A "display" lives here without
                breaking encapsulation — data crosses only at ports.

     afforded!  the agent's OWN ready set (init(P)) — the list of ports it
                currently affords — exported as a first-class port the
                skin queries to render enablement, instead of reaching
                into the agent. Its value is portsOf[self], realised on
                query (below).

   This file is the binding-layer realisation of afforded!.

   CONVENTIONS used across the component specs:
   - INPUT  port:  coLabel[name, binding[x]]  binds x   (pure: coLabel[name])
   - OUTPUT port:  label[name, param[v]]       sends v  (pure: label[name])
   - VIEW port: an OUTPUT action looping to the SAME state (read-only).
   - choice IS BINARY: transNamed[choice[p_, q_]] takes exactly two
     summands; for 3+ offered actions NEST choice[a, choice[b, c]].
     A flat choice[a, b, c] matches no rule and silently mis-steps.

   LOAD DEPENDENCY: RCA_core.wl must be loaded first (provides transNamed,
   label, coLabel, ...). Load THIS before any component spec.
   =====================================================================

   portsOf[s] — an inert HoldAll thunk carrying a STATE term. It holds its
   argument and has no value of its own, so it (a) survives the engine's
   ReleaseHold of an agent body — a plain Hold would be stripped — and
   (b) does NOT trigger transNamed while transitions are being computed,
   which would recurse since afforded! is itself one of those transitions.
   affordedNames realises it on query: First /@ transNamed[s] -> the port
   names — the very afforded-ports operation, exported through a port. *)

SetAttributes[portsOf, HoldAll];
portName[label[n_, ___]]   := n;
portName[coLabel[n_, ___]] := n;
portName[a_]               := a;             (* tau / any bare action *)
affordedNames[portsOf[s_]] := portName /@ (First /@ transNamed[s]);

(* readyPorts[s]: the ANALYSIS-ONLY readiness query (the role the removed
   `afforded` port used to play, now where it belongs — derived from the
   live state, not a channel in the process). *)
readyPorts[s_] := portName /@ (First /@ transNamed[s]);

(* =====================================================================
   Core-language forms (NATIVE in RCA_core.wl via the native-guard-choice
   change, PR #33). No desugaring here — the written syntax is preserved
   into transitions and buildSystem mu-terms.
   ---------------------------------------------------------------------
   if[c, P]     guarded summand (= if[c, P, nil] semantically), handled
                directly by transNamed/transVP/transSymbolic/substVv/substRv.
                Merge law for complementary guards (ANY actions):
                  if[c, A] + if[!c, B] == if[c, A, B]
                corollaries: if[c,p.P]+if[!c,p.Q] == if[c,p.P,p.Q] (may
                prefix-factor to p.if[c,P,Q]); if[c,A]+if[!c,A] == A
                (vacuous guard collapses). Optional, never a forced 2^n
                hoist. (Duplication caution is for splits sharing an
                UNGUARDED summand, not this merge.)

   choice[a,b,c,...]  variadic choice (binary is the 2-arg case; ABP
                unaffected).

   REQUIRES the native engine (PR #33). Until it is merged into feature-work,
   load RCA_core.wl from the native-guard-choice worktree.
   ===================================================================== *)


(* =====================================================================
   Composition with view-disambiguation
   ---------------------------------------------------------------------
   view! is a per-agent discipline port, so a naive parallel composition
   exposes one `view` per agent — a name clash. merge resolves it by
   relabelling each agent's view! to a qualified {Name}View! at COMPOSITION
   time (the reusable agents keep the bare `view`). relabel renames inside a
   mu-term but no-ops on a bare call[...], so merge buildSystems each agent
   to its mu-term first — the result is the canonical composed MU-TERM,
   stepped with transVP.

     viewAs[name, muTerm]   relabel view -> name<>"View" in a mu-term.
     merge[{name -> agentCall, ...}, {restrictChans}]
                            buildSystem each agent, view-qualify it, compose
                            in parallel (nested binary par), and restrict the
                            given cross-component channels (-> internal tau).

   Example:
     MioCore = merge[{"PS" -> call["PS", {}, 0, none, none],
                      "VS" -> call["VS", signedIn, {}, alpha, none, none]},
                     {label["vAdd"], label["pLoad"]}];
   ===================================================================== *)
viewAs[name_String, muTerm_] := relabel[muTerm, {"view" -> name <> "View"}];
merge[agents : {(_String -> _) ..}, restrictChans_List] :=
  restrict[
    Fold[par, (viewAs[First[#], buildSystem[Last[#]]] &) /@ agents],
    restrictChans];
