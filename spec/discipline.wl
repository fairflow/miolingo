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
