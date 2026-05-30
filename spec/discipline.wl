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
   Syntactic sugar (candidate for promotion into RCA_core.wl)
   ---------------------------------------------------------------------
   if[c, P]     2-arg overload of the conditional = if[c, P, nil]: a
                guarded summand, fewer characters than a `when`. The 3-arg
                if[c, P, Q] is unaffected (it does not match the 2-arg
                rule). Merge law for complementary guards (ANY actions):
                  if[c, A] + if[!c, B] == if[c, A, B]
                with corollaries if[c,p.P]+if[!c,p.Q] == if[c,p.P,p.Q]
                (mergeable; may prefix-factor to p.if[c,P,Q]) and
                if[c,A]+if[!c,A] == A (vacuous guard collapses). Optional
                optimisation, applied per-agent, never a forced 2^n hoist.
                (The duplication caution is for splits whose branches share
                an UNGUARDED summand — not for this complement-merge.)

   choice[a,b,c,...]  VARIADIC choice, desugared to right-nested binary
                so the engine's binary choice rules (transNamed, transVP,
                substVv, substRv, fAD, scRules) are untouched. Binary
                choice[p,q] is unaffected; ABP and all existing terms keep
                their behaviour. choice[a] (cong a) / choice[] (cong nil)
                may be normed away separately; not forced here.
   ===================================================================== *)
if[c_, p_] := if[c, p, nil];
choice[a_, b_, c__] := choice[a, choice[b, c]];
