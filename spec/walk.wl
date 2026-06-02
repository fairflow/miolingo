(* ::Package:: *)

(* =====================================================================
   spec/walk.wl \[LongDash] interactive walk harness for the miolingo spec.
   ---------------------------------------------------------------------
   `walk` lets a human live with the spec as it evolves: drive the
   simulation, PLAY THE USER by entering real data into input ports as
   they become ready, see each state through the data-compaction views
   (linearize / condensed event log), and record/replay traces \[LongDash] built
   from Wolfram `Dynamic`.

   This file is loaded ON TOP OF a loaded spec (engine + discipline +
   MioCore); it assumes transVP/transNamed, the coLabel/binding action
   grammar, and discipline.wl's data-view helpers are already present.
   In a notebook:
       Get[".../spec/MiolingoSpec.wl"];   (* engine + spec *)
       Get[".../spec/walk.wl"];           (* this file *)
       walkUI[mioCore]                     (* drive it *)

   THIS SECTION \[LongDash] the PURE SUBSTRATE \[LongDash] is headless-testable (see
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
readyInputs::usage = "readyInputs[tf, s] gives the ready transitions that are value-carrying input ports \[LongDash] the places where the user, as the open environment, supplies real data.";
supplyValue::usage = "supplyValue[trans, val] inserts a user value into an input transition's binder via the engine's substVv (scope-aware), returning {action, derivative-with-value}. No validation: the value is the user's responsibility.";
viewProjections::usage = "viewProjections[tf, s] gives <|portName -> projectionValue|> for the published read-only view ports at s (the bare \"view\" or a relabelled \"{Agent}View\").";
dataView::usage = "dataView[tf, s] renders the state's published projections through the data-compaction grid (linearizeGrid of the computed projection).";
traceView::usage = "traceView[traceSymbol] renders the condensed event log of a walk trace (HoldFirst) with a Copy button.";
stateDisplay::usage = "stateDisplay[s] gives a compact render of the CCS process state s (foldAgentDisplay \:043e normalizeSC) \[LongDash] where you are / where a transition leads.";
walkUI::usage = "walkUI[agent, opts] is the interactive Dynamic harness: drive the simulation, type real values into ready input ports, see the data-compaction views + current state + per-transition derivative, run value-carrying test sequences from walkTests, step Back/Forward through a run, and record a trace. Option \"TransitionFunction\" -> transVP (mu-term, e.g. mioCore) | transNamed (call form, e.g. mioCoreD).";

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
   ports \[LongDash] the places where the human, as the open environment, supplies
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

   The value is the USER's responsibility: the simulator does NOT validate it \[LongDash]
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
   ADDITIVE downvalue on walkResolve \[LongDash] lets the existing walkSteps run a
   value-driven plan, e.g.
       walkSteps[transVP, mioCore, {vis["set_filter", "happy"], vis["add", w]}]
--------------------------------------------------------------------- *)
walkResolve[tf_, s_, vis[nm_, val_]] := Module[{t = walkResolve[tf, s, vis[nm]]},
  If[MissingQ[t], t, supplyValue[t, val]]];


(* ---------------------------------------------------------------------
   autoTau[tf, s] : MAXIMAL-PROGRESS advance \[LongDash] a SIMULATION STRATEGY, not a
   language change. CCS itself has no priority: an offered internal sync is
   declinable while the agent has other transitions (the asynchrony that makes
   push-to-cache unfaithful). But the SIMULATOR is free to choose how it walks
   the LTS, and "fire internal syncs before offering external choices" is one
   such walk. It leaves the spec's meaning (the full transition relation)
   untouched \[LongDash] see ARCHITECTURE.md ("Borrowed vs owned data").

   It fires the UNIQUE enabled internal tau repeatedly until the state is
   tau-stable. Deliberately conservative:
     - 0 taus ready        -> stop (tau-stable; offer the external ready set);
     - exactly 1 tau ready -> fire it (forced-by-the-only-thing-to-do);
     - >= 2 taus ready     -> STOP and hand back to the user. Auto-firing here
                              would silently resolve a genuine nondeterministic
                              tau-CHOICE; we never bury that.
   A safety cap bounds the loop against a (here unexpected) tau-cycle.

   Returns <|"state" -> tau-stable state, "events" -> {eventOf each tau fired},
   "states" -> {pre-state of each tau}|> so the caller can extend trace + hist
   (every auto-fired tau is RECORDED and Back-steppable \[LongDash] maximal progress
   speeds driving, it does not hide the internal flow). *)
autoTau::usage = "autoTau[tf, s] is the maximal-progress simulation strategy: fire the unique enabled internal tau repeatedly until tau-stable (stopping if >=2 taus are ready, leaving the genuine choice to the user). Returns <|state, events, states|>. A walk strategy over the LTS, not a change to the spec.";
autoTau[tf_, s_] := Module[{cur = s, evs = {}, sts = {}, taus, guard = 0},
  While[guard++ < 500 &&
        Length[taus = Select[readyTransitions[tf, cur], isTauAct[First[#]] &]] === 1,
    AppendTo[sts, cur];
    AppendTo[evs, eventOf[First[First[taus]]]];
    cur = Last[First[taus]]];
  <|"state" -> cur, "events" -> evs, "states" -> sts|>];


(* =====================================================================
   DYNAMIC WIDGETS  (notebook front end \[LongDash] drive these; not headless)
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

(* dataView[tf, s] : the state's DATA as one compact PANEL per published
   projection. The "visual data compression". The projection comes out of the
   engine's held `param` with its values UNEVALUATED (the recipe, e.g.
   sortEntries[applyFilter[...]]); Map[Identity, \[CenterDot]] rebuilds the association
   forcing each value, so we render the COMPUTED data.

   Panel layout (chosen 2026-06-01): an agent's view Association is almost
   always SCALARS + one COLLECTION (entries / history), and that collection is
   a list of homogeneous Associations \[LongDash] which IS a table. So:
     scalar keys           -> a tight "key=value" strip;
     a list-of-Associations -> a column-headed table (columns = union of the
                               records' keys, one row per record).
   This is the most compact LOSSLESS form and stacks cleanly as N view ports
   grow (pSView / vSView / helmView, then more). *)
forceProj[p_Association] := Map[Identity, p];
forceProj[p_] := p;

(* scalarForm[v] : a value as compact display text (strings unquoted, sym[]
   unwrapped, None spelled out). *)
scalarForm[s_String] := s;
scalarForm[None] := "None";
scalarForm[v_] := ToString[v /. sym[z_] :> z];

(* recordTable[rows] : a list of Associations as a column-headed Grid. Columns
   are the union of the records' keys (so heterogeneous rows align), but EMPTY
   columns are dropped: a single freshly-added entry carries the full DB schema
   (~14 keys, most Null), so without pruning the table is mostly empty columns
   with long headings (the casa-row display problem). A column empty in every
   row carries no information \[LongDash] dropping it is lossless. Empty cells blank, and
   a still-wide table scrolls horizontally rather than breaking the layout. *)
emptyCellQ[v_] := MatchQ[v, Null | "" | None | _Missing];
cellForm[v_] := If[emptyCellQ[v], "", scalarForm[v]];
recordTable[rows : {__Association}] := Module[
  {allCols = DeleteDuplicates[Join @@ (Keys /@ rows)], cols},
  cols = Select[allCols, Function[c, AnyTrue[rows, ! emptyCellQ[Lookup[#, c, Null]] &]]];
  If[cols === {},
    Style["(entries present, all fields empty)", Italic, GrayLevel[0.6]],
    Pane[
      Grid[
        Prepend[
          (Function[r, cellForm[Lookup[r, #, Null]] & /@ cols] /@ rows),
          (Style[ToString[#], Italic, GrayLevel[0.45]] & /@ cols)],
        Frame -> All, FrameStyle -> GrayLevel[0.85], Alignment -> Left,
        Spacings -> {1.2, 0.3}],
      {UpTo[760], Automatic}, Scrollbars -> {Automatic, False},
      AppearanceElements -> None]]];

(* viewPanel[nm, p] : one agent's projection as a compact panel. *)
tabularKeyQ[v_] := MatchQ[v, {__Association}];
viewPanel[nm_String, p_Association] := Module[
  {tabKeys = Select[Keys[p], tabularKeyQ[p[#]] &], scalKeys, strip, tables},
  scalKeys = Complement[Keys[p], tabKeys];
  strip = Row[Riffle[
      (Row[{Style[ToString[#], GrayLevel[0.45]], "=", scalarForm[p[#]]}] & /@ scalKeys),
      Spacer[14]]];
  tables = recordTable[p[#]] & /@ tabKeys;
  Framed[
    Column[Join[{Style[nm, Bold, Darker[Blue]]}, {strip}, tables], Spacings -> 0.5],
    RoundingRadius -> 5, FrameStyle -> GrayLevel[0.8], FrameMargins -> 8,
    Background -> GrayLevel[0.99]]];
(* A view projection that did NOT reduce to an Association (every view! function
   \[LongDash] sessionView/vocabView/helmView \[LongDash] returns one when it computes). The usual
   cause: a supplied value of the wrong SHAPE, so the projection function's
   pattern (e.g. sessionView[phrases_List, ...]) doesn't match and it stays held.
   Show the raw term (so you can see what didn't reduce) under a clear warning,
   rather than a cryptic linearised stub. *)
viewPanel[nm_String, other_] := Framed[
  Column[{Style[nm, Bold, Darker[Blue]],
          Style["\[WarningSign] projection did not reduce to data \[LongDash] the supplied \
value is probably the wrong shape (e.g. a single entry, or `word`-keyed, where a \
LIST of `text`-keyed phrases is expected). Use practise_vocab for vocab, or a list \
like {<|\"text\"->...|>} for load_material.", Italic, Darker[Orange], 10],
          linearizeGrid[other]}, Spacings -> 0.5],
  RoundingRadius -> 5, FrameStyle -> Darker[Orange], FrameMargins -> 8];

dataView[tf_, s_] := Module[{projs = viewProjections[tf, s]},
  If[projs === <||>,
    Style["(no view ports ready)", Italic, GrayLevel[0.5]],
    Column[KeyValueMap[viewPanel[#1, forceProj[#2]] &, projs], Spacings -> 0.8]]];

(* Per-event render: port + polarity glyph + the value as a NAKED expression
   (no ToString — Wolfram boxes read fine), dropping the {} wrapper for <=1
   parameter (eventOf wraps every value in a list; we unwrap the singleton).
   When `short`, the value is Short[…]'d to tame bulky payloads. *)
renderTraceVal[{v_}, short_] := If[TrueQ[short], Short[v, 1], v];   (* <=1 param: NAKED, no {} *)
renderTraceVal[v_, short_]   := If[TrueQ[short], Short[v, 1], v];   (* multi-param list / tau subst *)
eventRow[e_Association, short_] := Row[{
  Style[If[e["isVisible"], "", "\[Tau] "], GrayLevel[0.6]],
  Style[e["port"], Bold, Darker[Blue]],
  Style[Switch[e["polarity"], "out", "!", "in", "?", _, ""], GrayLevel[0.5]],
  If[e["value"] === None, "", Row[{"\[ThinSpace]", renderTraceVal[e["value"], short]}]]}];

(* traceView[trace, short] : the trace rendered as naked-expression rows (not a
   string), so it copies/reads cleanly. `short` (a Bool, tracked by walkUI) wraps
   bulky values in Short. eventLogForm (string form) is kept for trace round-trip
   (trace_io_test) and Copy. *)
SetAttributes[traceView, HoldFirst];
traceView[trace_, short_ : False] := Column[{
  Style["Trace (condensed event log)", Bold],
  Pane[Dynamic[If[trace === {},
        Style["(no steps yet)", Italic, GrayLevel[0.5]],
        Column[eventRow[#, short] & /@ trace, Spacings -> 0.15]]],
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
(* stateDisplay[s] : compact render of a process STATE (the derivative) \[LongDash] where
   you are / where a transition leads \[LongDash] via the engine's foldAgentDisplay. This
   is the CCS term, complementing dataView's published data projections. *)
stateDisplay[s_] := If[agentDefs =!= <||>, foldAgentDisplay[normalizeSC[s]], Short[s, 3]];

(* --- grouping the ready transitions by the agent that provides each port ---
   sortOf[term] : the port NAMES (as strings) a process term offers, by a pure
   SYNTACTIC scan (Cases over label/coLabel) \[LongDash] no execution, so guards and
   infinite data state never bite. componentPortMap inverts the per-agent sorts
   into <|"port" -> "Agent"|>. The merge decomposition is passed in (the same
   {"PS"->call[...], ...} list merge uses); each agent's sort is scanned from its
   built term, with the bare "view" renamed to decap[name]<>"View" to match the
   composition's relabelled pSView/vSView/helmView (relabel is a lazy wrapper
   under transVP, so we rename the name set directly). Dual (restricted) actions
   vAdd/pLoad/langRead live in two
   sorts, but they are internal taus in the composed system and never queried as
   named ports here, so the overlap is harmless. *)
sortOf::usage = "sortOf[term] gives the set of port names (strings) appearing syntactically in a process term \[LongDash] a pure scan, no execution.";
componentPortMap::usage = "componentPortMap[{name->call,...}] gives <|portName -> agentName|> for grouping ready transitions by the component that provides each port (sort scanned from each agent's view-relabelled built term).";
sortOf[term_] := Union[Cases[term, (label | coLabel)[nm_, ___] :> ToString[nm], Infinity]];
componentPortMap[components : {(_String -> _) ..}] := Association @@
  Flatten[Function[nc,
      With[{name = First[nc]},
        (Replace[#, "view" -> decap[name] <> "View"] -> name) & /@
          sortOf[buildSystem[Last[nc]]]]] /@ components];

(* Auto-grouping registry: a composed-system term -> its component decomposition,
   so walkUI with "Components" -> Automatic (the default) groups a KNOWN system
   without being told each time. Generic \[LongDash] any composed system can register; the
   miolingo systems (mioCore/mioCoreD) register at the bottom of this file. An
   unregistered / bare agent resolves to {} (a flat, ungrouped list). *)
$walkComponents = {};
registerWalkComponents::usage = "registerWalkComponents[term, components] records that the composed term `term` decomposes into `components` ({name->call,...}), so walkUI[term] groups its transitions automatically.";
registerWalkComponents[term_, comps_] := AppendTo[$walkComponents, {term, comps}];
defaultComponents[agent_] := Replace[
  SelectFirst[$walkComponents, First[#] === agent &],
  {{_, c_} :> c, _Missing -> {}}];

(* transGroup: the frame a ready transition belongs in (its providing agent, or
   an internal-tau group for a sync). inputsFirst: order a group's rows inputs
   (coLabel) before outputs (label). *)
transGroup[pmap_Association, tr_] := If[isTauAct[First[tr]], "internal (\[Tau])",
  Lookup[pmap, ToString[portName[First[tr]]], "other"]];
inputsFirst[ts_List] := Join[
  Select[ts, MatchQ[First[#], coLabel[___]] &],
  Select[ts, MatchQ[First[#], label[___]] &],
  Select[ts, ! MatchQ[First[#], coLabel[___] | label[___]] &]];

(* --- the "cloud": an honest INVENTORY of what the simulated agents read but
   do NOT own \[LongDash] data whose owner is not (yet) modelled. A standing reminder that
   the agents are not complete in themselves (ARCHITECTURE.md "Borrowed vs owned
   data" / the Stats-History note). It SHRINKS as each owner is modelled: the
   language used to be here, but pull-on-use (langRead) brought it into the model,
   so it is gone \[LongDash] what remains is the genuinely external world (oracle knowledge,
   persistence). Hand-maintained in lockstep with the spec, like the ARCHITECTURE
   notes. Each item lights up when a ready action would CONSULT it, so the cloud
   visibly changes as you walk. *)
$walkCloud = {
  <|"item" -> "enrichOracle", "owner" -> "external translation / G2P service",
    "why" -> "VS.autofill's translation + IPA are produced OUTSIDE the model; only the (source,target) pull (langRead) is in it.",
    "ports" -> {"autofill"}|>,
  <|"item" -> "recognisePhonemes", "owner" -> "external ASR / acoustic model",
    "why" -> "PS scoring recognises audio -> phonemes outside the model; only the target-language pull (langRead) is in it.",
    "ports" -> {"attempt_made"}|>,
  <|"item" -> "vocab persistence", "owner" -> "external store (DB)",
    "why" -> "entries are modelled in VS state in-process; really an external store. To become a DB agent (ARCHITECTURE \[Dagger]).",
    "ports" -> {"add", "import_bulk", "delete", "update", "update_notes", "autofill"}|>,
  <|"item" -> "stats / history", "owner" -> "external store (query-backed views)",
    "why" -> "not yet recovered; will be queries/views on the external store, not in-process state.",
    "ports" -> {}|>};
cloudActiveQ[item_Association, readyNames_List] := IntersectingQ[item["ports"], readyNames];
cloudActiveQ::usage = "cloudActiveQ[item, readyPortNames] is True iff a currently-ready port would consult this external item (so the cloud panel highlights it).";
(* the set of cloud-item names CONSULTED at state s — walkUI pops the panel open
   when this set CHANGES (otherwise it leaves the panel as the user set it). *)
cloudActiveNames[tf_, s_] := With[
  {ready = ToString /@ portName /@ First /@ readyTransitions[tf, s]},
  #["item"] & /@ Select[$walkCloud, cloudActiveQ[#, ready] &]];
cloudRow[item_Association, ready_List] := With[{active = cloudActiveQ[item, ready]},
  Framed[
    Column[{
      Row[{If[active, Style["\[FilledCircle] ", Darker[Orange]], Style["\[EmptyCircle] ", GrayLevel[0.75]]],
           Style[item["item"], Bold, If[active, Darker[Orange], GrayLevel[0.4]]],
           Style["  \[LongDash] owned by " <> item["owner"], Italic, GrayLevel[0.55], 10]}],
      Style[item["why"], GrayLevel[0.5], 10]}, Spacings -> 0.2],
    FrameStyle -> If[active, Darker[Orange], GrayLevel[0.88]], RoundingRadius -> 3,
    FrameMargins -> 5, Background -> If[active, RGBColor[1, 0.97, 0.88], White]]];
cloudPanel::usage = "cloudPanel[tf, s, open] renders the external-dependency inventory ($walkCloud) as a collapsible panel; items a ready port would consult are highlighted. `open` (default False, or a Dynamic) is the opener state, so it can persist across steps.";
cloudPanel[tf_, s_, open_ : False] := With[
  {ready = ToString /@ portName /@ First /@ readyTransitions[tf, s]},
  OpenerView[{
    Style[Row[{"Outside the model \[LongDash] read but not owned (",
               Length[$walkCloud], " items; \[FilledCircle] = consulted by a ready action)"}],
      Bold, 12, GrayLevel[0.45]],
    Column[cloudRow[#, ready] & /@ $walkCloud, Spacings -> 0.4]}, open]];

(* --- build stamp: read the loaded checkout's git HEAD so the harness shows
   exactly which spec build a cell is running \[LongDash] the merge commit's PR number,
   short SHA, date, and a +local-edits flag if the tree is dirty. Read at walkUI
   creation (cheap: a few git calls), so each fresh cell reflects what's on disk
   NOW; a stale cell keeps its old stamp (a visible tell to re-make it).
   $walkDir is captured at LOAD time ($InputFileName is only valid during Get). *)
walkVersion::usage = "walkVersion[dir] gives a one-line build stamp for the git checkout at `dir` (PR #, short SHA, date, +local edits) \[LongDash] shown in walkUI so you can confirm which spec build the cell is running.";
walkVersion[dir_] := Module[{run, sha, subj, date, dirty, pr},
  run[a_] := Module[{r = Quiet @ RunProcess[Join[{"git", "-C", dir}, a]]},
    If[AssociationQ[r] && r["ExitCode"] === 0, StringTrim[r["StandardOutput"]], $Failed]];
  sha = run[{"rev-parse", "--short=9", "HEAD"}];
  If[sha === $Failed, Return["(version unknown \[LongDash] not a git checkout)"]];
  subj  = run[{"log", "-1", "--format=%s"}];
  date  = run[{"log", "-1", "--format=%cs"}];
  dirty = StringTrim[ToString[run[{"status", "--porcelain"}]]] =!= "";
  pr = FirstCase[StringCases[ToString[subj], "#" ~~ d : DigitCharacter .. :> d], _, None];
  StringJoin[
    If[pr =!= None, "PR #" <> pr <> " \[CenterDot] ", ""],
    ToString[sha], " \[CenterDot] ", ToString[date],
    If[dirty, " \[CenterDot] +local edits", ""]]];
$walkDir = DirectoryName[$InputFileName];

Options[walkUI] = {"TransitionFunction" -> transVP, "Components" -> Automatic};
walkUI[agent_, opts : OptionsPattern[]] := With[
  {tf = OptionValue["TransitionFunction"],
   (* Automatic (the default): group if `agent` is a registered composed system,
      else flat. An explicit list / {} overrides. *)
   components = Replace[OptionValue["Components"], Automatic :> defaultComponents[agent]]},
  With[{pmap = If[components === {}, <||>, componentPortMap[components]],
        ver = walkVersion[$walkDir]},
  DynamicModule[{cur = agent, trace = {}, hist = {}, inVals = <||>, future = {},
     maxprog = False, stateOpen = False, cloudOpen = False,
     shortTrace = True, prevCloudActive = cloudActiveNames[tf, agent],
     testSel = First[Keys[If[ValueQ[walkTests], walkTests, <||>]], None]},
    Dynamic[
      Module[{trans = readyTransitions[tf, cur]},
        Framed[Column[{

          (* build stamp (captured when THIS cell was created) \[LongDash] confirms which
             spec build you're running; a stale cell shows an old PR#/SHA *)
          Style["spec build: " <> ver, GrayLevel[0.35], 13],

          (* collapsible (default closed) so the process term doesn't eat space;
             open state persists across steps via stateOpen *)
          OpenerView[{
            Style["Current state \[LongDash] where you are (process term)", Bold, 13],
            Pane[stateDisplay[cur], {Automatic, 140}, Scrollbars -> Automatic]},
            Dynamic[stateOpen]],

          Style["Data view \[LongDash] published projections", Bold, 13],
          dataView[tf, cur],

          (* the cloud: external data the agents read but don't own (collapsible;
             open state persists across steps via cloudOpen); items light up when
             a ready action would consult them *)
          cloudPanel[tf, cur, Dynamic[cloudOpen]],

          Style["Transitions \[LongDash] click to step; type into input ports", Bold, 13],
          (* maximal-progress toggle: a SIMULATION strategy (auto-fire internal
             syncs between your actions), not a language change. Switching it ON
             also settles the current state. The system plays the SYSTEM for you;
             you still play the user (and the world). *)
          Row[{Checkbox[Dynamic[maxprog, (maxprog = #;
                 If[TrueQ[#],
                   With[{a = autoTau[tf, cur]},
                     hist = Join[hist, a["states"]];
                     trace = Join[trace, a["events"]]; cur = a["state"]]]) &]],
               Spacer[4],
               Style["Auto-advance internal syncs (maximal progress)",
                 GrayLevel[0.35], 11]}],
          If[trans === {},
            Style["(deadlocked \[LongDash] no transitions)", Italic, GrayLevel[0.5]],
            With[{row = Function[tr,
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
                        cur = Last[taken]; inVals = <||>; future = {};
                        (* maximal progress: let the system settle its internal
                           syncs before offering the next external choice *)
                        If[TrueQ[maxprog],
                          With[{a = autoTau[tf, cur]},
                            hist = Join[hist, a["states"]];
                            trace = Join[trace, a["events"]]; cur = a["state"]]];
                        (* cloud auto-open: pop the externals panel open ONLY when
                           the set of consulted externals changes; otherwise leave
                           it as the user set it *)
                        With[{na = cloudActiveNames[tf, cur]},
                          If[na =!= prevCloudActive, cloudOpen = True];
                          prevCloudActive = na]],
                      Appearance -> "Frameless"(*,
                      ActiveStyle -> {Background -> RGBColor[0.9, 0.95, 1.0]}*)],
                     (* hover: the derivative this transition leads to (symbolic,
                        i.e. before any supplied value \[LongDash] so e.g. add's collapse to
                        entries {} is visible here) *)
                     Column[{Style["\[RightArrow] goes to:", Bold, GrayLevel[0.4]],
                             stateDisplay[Last[tr]]}]],
                    If[valueInputQ[act],
                      Row[{Spacer[6], Style["\[LeftArrow] ", GrayLevel[0.5]],
                           (* pre-fill with the port's first binder SYMBOL as the
                              editable starting point (via inputBinderOf \[LongDash] a
                              pattern match, never Part-indexing, so it is safe
                              for any action shape; cf. issue #150). Untouched
                              fields don't set inVals[nm], so the step stays
                              symbolic; the user types over the symbol to supply. *)
                           InputField[
                             Dynamic[Lookup[inVals, nm, First[inputBinderOf[act], ""]],
                                     (inVals[nm] = #) &],
                             Expression, FieldSize -> 20, ContinuousAction -> False]}],
                      Nothing]}]]]},
            (* GROUP the ready transitions by the agent that provides each (a
               frame per component, inputs before outputs). Flat list when no
               "Components" option is given. Internal syncs (taus) fall into
               their own "internal (tau)" frame. *)
            If[pmap === <||>,
              Column[row /@ trans],
              With[{grp = GroupBy[trans, transGroup[pmap, #] &]},
                Column[
                  Function[k,
                    Framed[
                      Column[{Style[k, Bold, Darker[Blue], 11],
                              Column[row /@ inputsFirst[grp[k]], Spacings -> 0.2]},
                        Spacings -> 0.4],
                      FrameStyle -> GrayLevel[0.82], RoundingRadius -> 4,
                      FrameMargins -> 6]] /@
                  Select[Join[Keys[components], {"other", "internal (\[Tau])"}],
                    KeyExistsQ[grp, #] &],
                  Spacings -> 0.5]]]]],

          (* Back / Forward scrub the run: Back pushes the current step onto a
             `future` stack; Forward replays it. A fresh step or Run test clears
             `future` (you've branched off the redo line). *)
          Row[{
            Button["\[LeftArrow] Back",
              If[hist =!= {},
                AppendTo[future, {cur, Last[trace]}];
                cur = Last[hist]; hist = Most[hist]; trace = Most[trace];
                inVals = <||>],
              Enabled -> Dynamic[hist =!= {}]],
            Spacer[4],
            Button["Forward \[RightArrow]",
              If[future =!= {},
                Module[{f = Last[future]},
                  AppendTo[hist, cur]; cur = f[[1]]; AppendTo[trace, f[[2]]];
                  future = Most[future]; inVals = <||>]],
              Enabled -> Dynamic[future =!= {}]],
            Spacer[6],
            Button["Reset \[CenterDot]", cur = agent; hist = {}; trace = {};
               future = {}; inVals = <||>]}],

          (* Run a value-carrying test sequence from walkTests \[LongDash] no typing:
             replays the chosen plan FROM THE INITIAL AGENT, setting the trace
             to its condensed event log and the state to the final state (hist
             keeps the intermediate states so Back walks through it). *)
          Row[{Style["Test: ", Bold, GrayLevel[0.4]], Spacer[4],
               (* group the dropdown by prefix (vs- / ps- / sync- / helm- / …)
                  with a horizontal Delimiter between groups, so it's clear which
                  tests belong where *)
               PopupMenu[Dynamic[testSel],
                 Flatten[Riffle[
                   SplitBy[Keys[If[ValueQ[walkTests], walkTests, <||>]],
                           First[StringSplit[#, "-"], #] &],
                   Delimiter]]],
               Spacer[4],
               Button["Run test \[FilledRightTriangle]",
                 (* "AutoTau" -> True : the plans list only external actions, so
                    fire the internal syncs (vAdd/pLoad/langRead/chRead) for us *)
                 Module[{w = walkSteps[tf, agent, walkTests[testSel], "AutoTau" -> True]},
                   hist = Most[w["states"]]; trace = eventLog[w];
                   cur = Last[w["states"]]; future = {}; inVals = <||>],
                 Enabled -> Dynamic[ValueQ[walkTests] && KeyExistsQ[walkTests, testSel]]]}],

          Row[{Checkbox[Dynamic[shortTrace]], Spacer[4],
               Style["Short trace values (truncate bulky data)", GrayLevel[0.35], 11]}],
          traceView[trace, shortTrace]

        }, Spacings -> 1.2], FrameStyle -> GrayLevel[0.7], RoundingRadius -> 4]],
      TrackedSymbols :> {cur, inVals, testSel, future, maxprog, shortTrace}]]]];


(* --- register the miolingo systems so walkUI[mioCore] / walkUI[mioCoreD] GROUP
   by component automatically (no "Components" option needed). mioComponents is
   the single source of truth for the decomposition (MioCore.wl). --- *)
If[ValueQ[mioCore]  && ValueQ[mioComponents], registerWalkComponents[mioCore,  mioComponents]];
If[ValueQ[mioCoreD] && ValueQ[mioComponents], registerWalkComponents[mioCoreD, mioComponents]];

(* convenience entry points. walkUI[mioCore] now groups on its own (via the
   registry); walkMioD[] additionally wires transNamed for the call-based twin. *)
walkMio::usage = "walkMio[] = walkUI[mioCore] (grouped by component via the registry). walkMioD[] is the transNamed/mioCoreD twin.";
walkMio[]  := walkUI[mioCore];
walkMioD[] := walkUI[mioCoreD, "TransitionFunction" -> transNamed];

(* --- the value-carrying test sequences (walkTests), loaded relative to
   this file so walkUI's "Run test" menu and walkSteps both have them. --- *)
Get[FileNameJoin[{DirectoryName[$InputFileName], "walk-tests.wl"}]];

(* NB: the engine binds `walk = interactiveVP` (an OwnValue), so we do NOT
   reuse that name here \[LongDash] call walkUI[mioCore] for the richer spec harness.
   Whether to rebind `walk` to walkUI is left until the UX settles. *)
