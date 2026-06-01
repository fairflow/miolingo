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

(* --- usage messages (so ?name works in a notebook) ------------------- *)
readyTransitions::usage = "readyTransitions[tf, s] gives the enabled transitions at state s as a list of {action, successor}, normalising the engine's optional 3-tuple form.";
inputBinderOf::usage = "inputBinderOf[action] gives the binder symbol(s) an input action coLabel[nm, binding[x]] introduces (the free variables a supplied value replaces); {} for outputs, taus and value-free inputs.";
valueInputQ::usage = "valueInputQ[action] is True iff action is an input port that binds a value (so the walk must let the user supply one).";
readyInputs::usage = "readyInputs[tf, s] gives the ready transitions that are value-carrying input ports — the places where the user, as the open environment, supplies real data.";
supplyValue::usage = "supplyValue[trans, val] inserts a user value into an input transition's binder via the engine's substVv (scope-aware), returning {action, derivative-with-value}. No validation: the value is the user's responsibility.";
viewProjections::usage = "viewProjections[tf, s] gives <|portName -> projectionValue|> for the published read-only view ports at s (the bare \"view\" or a relabelled \"{Agent}View\").";
dataView::usage = "dataView[tf, s] renders the state's published projections through the data-compaction grid (linearizeGrid of the computed projection).";
traceView::usage = "traceView[traceSymbol] renders the condensed event log of a walk trace (HoldFirst) with a Copy button.";
stateDisplay::usage = "stateDisplay[s] gives a compact render of the CCS process state s (foldAgentDisplay о normalizeSC) — where you are / where a transition leads.";
walkUI::usage = "walkUI[agent, opts] is the interactive Dynamic harness: drive the simulation, type real values into ready input ports, see the data-compaction views + current state + per-transition derivative, run value-carrying test sequences from walkTests, and record a trace. Option \"TransitionFunction\" -> transVP (mu-term, e.g. mioCore) | transNamed (call form, e.g. mioCoreD).";

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
   {action, succ} whose action is coLabel[nm, binding[x]], insert the
   user-supplied value into the binder x of the DERIVATIVE using the engine's
   substVv (NOT ReplaceAll): substVv is scope-aware (filterSubst drops the
   binder when it re-enters a rebinding), so the value lands only at the genuine
   free occurrence and does NOT leak into the re-unfolded continuation clauses
   that rebind the same name. The action's binding is set to val too, so eventOf
   reads the concrete value for the trace.

   The value is the USER's responsibility: the simulator does NOT validate it —
   the spec's own functions (validateWord, the _List match, ...) judge it if and
   when the term becomes concrete. This is the deliberate blend of transition
   function and simulator that lets the user, as the open environment, inject
   real data while navigating the symbolic<->concrete interzone.

   - value-free input or non-input: returned unchanged (nothing to supply).
   - single binder (every port in the current spec): substVv x -> val.
   - multi-binder: val is a list, zipped onto the binders.
--------------------------------------------------------------------- *)
supplyValue[trans_List, val_] := Module[{binders = inputBinderOf[First[trans]]},
  Which[
    binders === {}, trans,
    Length[binders] === 1,
      {First[trans] /. binding[_] :> binding[val],
       substVv[Last[trans], {First[binders] -> val}]},   (* subst is a LIST of
         rules: filterSubst does #[[1]] per element, so a bare rule -> ps[[1]] *)
    True,
      {First[trans] /. binding[__] :> (binding @@ val),
       substVv[Last[trans], MapThread[Rule, {binders, val}]]}]];

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


(* =====================================================================
   DYNAMIC WIDGETS  (notebook front end — drive these; not headless)
   ---------------------------------------------------------------------
   Composable Dynamic pieces, plus walkUI[] that assembles them. Each
   reuses the substrate above + discipline.wl's data-compaction display
   (linearizeGrid) + the engine's action rendering (showAction). They need
   a notebook front end to render; loading this file headlessly only
   DEFINES them (a useful syntax check).
   ===================================================================== *)

(* viewProjections[tf, s] : the published read-only projections at s, as
   <|"portName" -> projectionValue|>. A view port is an OUTPUT (label[...])
   carrying param[projection] whose name is a read-only view: the bare agent's
   "view" port, OR a composition-relabelled "{Agent}View" (vSView, pSView).
   Matched case-insensitively on the "view" suffix so BOTH forms are picked up
   (the bare "view" was previously dropped by a literal "View" test). *)
viewProjections[tf_, s_] := Association[
  (ToString[portName[First[#]]] ->
     First[Cases[First[#], param[p_] :> p, Infinity], None]) & /@
  Select[readyTransitions[tf, s],
    MatchQ[First[#], label[_, param[_]]] &&
    StringEndsQ[ToLowerCase[ToString[portName[First[#]]]], "view"] &]];

(* dataView[tf, s] : the state's DATA through the compaction grid — one
   linearizeGrid per published projection. The "visual data compression".
   The projection comes out of the engine's held `param` with its values
   UNEVALUATED (the recipe, e.g. sortEntries[applyFilter[...]]); Map[Identity, ·]
   rebuilds the association forcing each value, so we linearize the COMPUTED
   data (entries -> {} when empty, the actual rows when populated). *)
forceProj[p_Association] := Map[Identity, p];
forceProj[p_] := p;
dataView[tf_, s_] := Module[{projs = viewProjections[tf, s]},
  If[projs === <||>,
    Style["(no view ports ready)", Italic, GrayLevel[0.5]],
    Column[KeyValueMap[
      Function[{nm, p},
        Column[{Style[nm, Bold, Darker[Blue]], linearizeGrid[forceProj[p]]}, Spacings -> 0.4]],
      projs], Spacings -> 1]]];

(* traceView[traceDyn] : condensed event-log rendering of the trace held in
   the Dynamic-tracked symbol passed by reference, + a Copy button. *)
SetAttributes[traceView, HoldFirst];
traceView[trace_] := Column[{
  Style["Trace (condensed event log)", Bold],
  Pane[Dynamic[If[trace === {},
        Style["(no steps yet)", Italic, GrayLevel[0.5]],
        Style[eventLogForm[trace], FontFamily -> "Courier", FontSize -> 12]]],
    {Automatic, 110}, Scrollbars -> Automatic],
  Button["Copy trace \[SelectionPlaceholder]", CopyToClipboard[trace],
    Enabled -> Dynamic[trace =!= {}]]}];

(* ---------------------------------------------------------------------
   walkUI[agent, opts] : the integrated harness. Drive the sim, PLAY THE
   USER by typing a real value into any ready input port (the InputField
   beside it), watch the data-compaction view + condensed trace update,
   step / back / reset. Untouched input ports step symbolically (binder
   left free), so it degrades to the plain symbolic walk.

   Value entry uses InputField[..., Expression]: type a WL value, e.g.
       "happy"                         (a string, for set_filter)
       <|"word"->"chat","translation"->"cat"|>   (for add)
   Option "TransitionFunction" -> transVP (mioCore) | transNamed (mioCoreD).
--------------------------------------------------------------------- *)
(* stateDisplay[s] : compact render of a process STATE (the derivative) — where
   you are / where a transition leads — via the engine's foldAgentDisplay. This
   is the CCS term, complementing dataView's published data projections. *)
stateDisplay[s_] := If[agentDefs =!= <||>, foldAgentDisplay[normalizeSC[s]], Short[s, 3]];

Options[walkUI] = {"TransitionFunction" -> transVP};
walkUI[agent_, opts : OptionsPattern[]] := With[
  {tf = OptionValue["TransitionFunction"]},
  DynamicModule[{cur = agent, trace = {}, hist = {}, inVals = <||>,
     testSel = First[Keys[If[ValueQ[walkTests], walkTests, <||>]], None]},
    Dynamic[
      Module[{trans = readyTransitions[tf, cur]},
        Framed[Column[{

          Style["Current state \[LongDash] where you are (process term)", Bold, 13],
          Pane[stateDisplay[cur], {Automatic, 140}, Scrollbars -> Automatic],

          Style["Data view \[LongDash] published projections", Bold, 13],
          dataView[tf, cur],

          Style["Transitions \[LongDash] click to step; type into input ports", Bold, 13],
          If[trans === {},
            Style["(deadlocked \[LongDash] no transitions)", Italic, GrayLevel[0.5]],
            Column[
              Map[Function[tr,
                With[{act = First[tr], nm = ToString[portName[First[tr]]]},
                  Row[{
                    Tooltip[
                     Button[showAction[act],
                      Module[{taken},
                        taken = If[valueInputQ[act] && KeyExistsQ[inVals, nm] &&
                                   inVals[nm] =!= Null && inVals[nm] =!= "",
                                 supplyValue[tr, inVals[nm]], tr];
                        AppendTo[hist, cur];
                        AppendTo[trace, eventOf[First[taken]]];
                        cur = Last[taken]; inVals = <||>],
                      Appearance -> "Frameless",
                      ActiveStyle -> {Background -> RGBColor[0.9, 0.95, 1.0]}],
                     (* hover: the derivative this transition leads to (symbolic,
                        i.e. before any supplied value — so e.g. add's collapse to
                        entries {} is visible here) *)
                     Column[{Style["\[RightArrow] goes to:", Bold, GrayLevel[0.4]],
                             stateDisplay[Last[tr]]}]],
                    If[valueInputQ[act],
                      Row[{Spacer[6],
                           Style["\[LeftArrow] " <> ToString[First[inputBinderOf[act]]] <> " = ",
                             GrayLevel[0.5]],
                           (* default to "" (not Missing[KeyAbsent]) when the
                              port has no value yet; write inVals[nm] on edit *)
                           InputField[Dynamic[Lookup[inVals, nm, ""], (inVals[nm] = #) &],
                             Expression, FieldSize -> 20, ContinuousAction -> False]}],
                      Nothing]}]]],
                trans]]],

          Row[{
            Button["\[LeftArrow] Back",
              If[hist =!= {}, cur = Last[hist]; hist = Most[hist];
                 trace = Most[trace]; inVals = <||>],
              Enabled -> Dynamic[hist =!= {}]],
            Spacer[6],
            Button["Reset \[CenterDot]", cur = agent; hist = {}; trace = {};
               inVals = <||>]}],

          (* Run a value-carrying test sequence from walkTests — no typing:
             replays the chosen plan FROM THE INITIAL AGENT, setting the trace
             to its condensed event log and the state to the final state (hist
             keeps the intermediate states so Back walks through it). *)
          Row[{Style["Test: ", Bold, GrayLevel[0.4]], Spacer[4],
               PopupMenu[Dynamic[testSel], Keys[If[ValueQ[walkTests], walkTests, <||>]]],
               Spacer[4],
               Button["Run test \[FilledRightTriangle]",
                 Module[{w = walkSteps[tf, agent, walkTests[testSel]]},
                   hist = Most[w["states"]]; trace = eventLog[w];
                   cur = Last[w["states"]]; inVals = <||>],
                 Enabled -> Dynamic[ValueQ[walkTests] && KeyExistsQ[walkTests, testSel]]]}],

          traceView[trace]

        }, Spacings -> 1.2], FrameStyle -> GrayLevel[0.7], RoundingRadius -> 4]],
      TrackedSymbols :> {cur, inVals, testSel}]]];


(* --- the value-carrying test sequences (walkTests), loaded relative to
   this file so walkUI's "Run test" menu and walkSteps both have them. --- *)
Get[FileNameJoin[{DirectoryName[$InputFileName], "walk-tests.wl"}]];

(* NB: the engine binds `walk = interactiveVP` (an OwnValue), so we do NOT
   reuse that name here — call walkUI[mioCore] for the richer spec harness.
   Whether to rebind `walk` to walkUI is left until the UX settles. *)
