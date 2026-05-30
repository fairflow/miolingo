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
   exposes one `view` per agent — a name clash. Both helpers resolve it by
   relabelling each agent's view! to a qualified {agent}View! (first letter
   downcased: "PS" -> pSView, "Agent" -> agentView) at COMPOSITION time (the
   reusable agents keep the bare `view`; agent NAMES stay capitalised).

   TWO composition helpers, differing only in the representation they leave:

     merge         buildSystems each agent to a mu-term FIRST, then composes.
                   Result is the canonical composed MU-TERM, stepped with
                   transVP. relabel under transVP is a STATIC rewrite, which
                   needs the literal "view" present — hence buildSystem. The
                   cost: the term and every successor are bulky mu-terms.

     mergeDefined  composes the call[...] equations directly (NO buildSystem):
                   successors stay compact, restrict[par[<call>,<call>],chans].
                   Stepped with transNamed. REQUIRES the transition-time
                   transNamed[relabel] engine change (RCA_core, branch
                   relabel-transition-time) — under the old static rule the
                   view-rename would no-op on a bare call. Use this for
                   simulation / trace work; merge stays for the canonical form.

     viewAs[name, term]   relabel view -> decap[name]<>"View" (term = mu-term
                          for merge, or a bare call for mergeDefined).

   Example (note the lowercase WL symbol mioCore; "MioCore" stays capitalised
   only as an agent NAME in call[...]):
     mioCore  = merge[       {"PS" -> call["PS", {}, 0, none, none],
                              "VS" -> call["VS", signedIn, {}, alpha, none, none]},
                             {label["vAdd"], label["pLoad"]}];
     mioCoreD = mergeDefined[ ... same args ... ];   (* compact, transNamed *)
   ===================================================================== *)
(* decapitalise the first letter (Agent -> agentView): WL convention is
   that user actions start lc; agent NAMES in call["..."] stay capitalised. *)
decap[s_String] := ToLowerCase[StringTake[s, 1]] <> StringDrop[s, 1];
viewAs[name_String, term_] := relabel[term, {"view" -> decap[name] <> "View"}];

(* canonical mu-term composition (transVP); buildSystem exposes "view" for
   the static relabel. *)
merge[agents : {(_String -> _) ..}, restrictChans_List] :=
  restrict[
    Fold[par, (viewAs[First[#], buildSystem[Last[#]]] &) /@ agents],
    restrictChans];

(* compact equation composition (transNamed); needs transition-time
   transNamed[relabel] so viewAs renames the view! emitted by a bare call. *)
mergeDefined[agents : {(_String -> _) ..}, restrictChans_List] :=
  restrict[
    Fold[par, (viewAs[First[#], Last[#]] &) /@ agents],
    restrictChans];
