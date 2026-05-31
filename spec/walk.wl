(* =====================================================================
   spec/walk.wl — interactive walk harness for the miolingo spec.
   ---------------------------------------------------------------------
   `walk` lets a human live with the spec as it evolves: drive the
   simulation, PLAY THE USER by entering real data into input ports as
   they become ready, see each state through the data-compaction views
   (linearize / condensed event log), and record/replay traces — built
   from Wolfram `Dynamic`.

   This file is loaded ON TOP OF a loaded spec (engine + discipline +
   MioCore); it assumes transVP/transNamed, the coLabel/binding action
   grammar, and discipline.wl's data-view helpers are already present.
   In a notebook:
       Get[".../spec/MiolingoSpec.wl"];   (* engine + spec *)
       Get[".../spec/walk.wl"];           (* this file *)
       walkUI[mioCore]                     (* drive it *)

   THIS SECTION — the PURE SUBSTRATE — is headless-testable (see
   spec/tests/walk_test.wls). The Dynamic widgets that sit on top of it
   are added once the substrate mechanic is proven.

   ACTION GRAMMAR (from discipline.wl:254-267):
     label[nm, param[v]]        output (visible), carries value v
     coLabel[nm, binding[x]]    input  (visible), BINDS x  <- user supplies here
     coLabel[nm]                input  (visible), no value
     tag[Tau, ch, subst] / Tau  internal
   ===================================================================== *)

(* ---------------------------------------------------------------------
   readyTransitions[tf, s] : the enabled transitions at state s as a list
   of {action, successor}.  Normalises the engine's optional 3-tuple form
   ({action, succ, _}) to a 2-list, matching interactiveVP (RCA_core.wl:
   1471-1473) so the widgets and tests share one shape.
--------------------------------------------------------------------- *)
readyTransitions[tf_, s_] := Module[{raw = tf[s]},
  If[raw =!= {} && Length[raw[[1]]] >= 3,
     {#[[1]], #[[2]]} & /@ raw,
     raw]];

(* ---------------------------------------------------------------------
   inputBinderOf[action] : the binder symbol(s) an input action introduces,
   i.e. the free variable(s) a supplied value must replace. {} for outputs,
   taus, and value-free inputs (coLabel[nm]).
--------------------------------------------------------------------- *)
inputBinderOf[coLabel[_, binding[x_]]]  := {x};
inputBinderOf[coLabel[_, binding[x__]]] := {x};   (* multi-binder (none in
                                                     the current spec) *)
inputBinderOf[_] := {};

(* valueInputQ[action] : True iff this is an input port that BINDS a value
   (so the walk must let the user supply one). *)
valueInputQ[a_] := inputBinderOf[a] =!= {};

(* ---------------------------------------------------------------------
   readyInputs[tf, s] : the ready transitions that are value-carrying input
   ports — the places where the human, as the open environment, supplies
   real data.  These are exactly the rows the GUI gives an input field.
--------------------------------------------------------------------- *)
readyInputs[tf_, s_] := Select[readyTransitions[tf, s], valueInputQ[First[#]] &];

(* ---------------------------------------------------------------------
   supplyValue[trans, val] : THE PORT-INPUT MECHANIC.  Given a transition
   {action, succ} whose action is coLabel[nm, binding[x]], bind x := val
   throughout BOTH the action and the successor, so the real value flows in
   and threads through every later state. The action becomes
   coLabel[nm, binding[val]], from which eventOf reads the concrete value
   for the trace automatically.

   - value-free input or non-input: returned unchanged (nothing to supply).
   - single binder (every port in the current spec): substitute x -> val.
   - multi-binder: val is taken as a list, zipped onto the binders.
--------------------------------------------------------------------- *)
supplyValue[trans_List, val_] := Module[{binders = inputBinderOf[First[trans]]},
  Which[
    binders === {},          trans,
    Length[binders] === 1,   trans /. First[binders] -> val,
    True,                    trans /. MapThread[Rule, {binders, val}]]];

(* ---------------------------------------------------------------------
   Value-carrying plan entry: vis[nm, val] resolves the input port `nm`
   (delegating to discipline.wl's existing string-name resolver, so the
   matching convention is shared) and supplies `val` into its binder.
   ADDITIVE downvalue on walkResolve — lets the existing walkSteps run a
   value-driven plan, e.g.
       walkSteps[transVP, mioCore, {vis["set_filter", "happy"], vis["add", w]}]
--------------------------------------------------------------------- *)
walkResolve[tf_, s_, vis[nm_, val_]] := Module[{t = walkResolve[tf, s, vis[nm]]},
  If[MissingQ[t], t, supplyValue[t, val]]];
