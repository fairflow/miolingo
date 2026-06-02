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


(* =====================================================================
   DATA-VIEW COMPACTION
   ---------------------------------------------------------------------
   The domain value-functions (addEntry, importInto, deleteFrom, updateEntry,
   updateNotesIn, autofillIn, exportCsv, sessionView, vocabView, practiseList,
   evaluate, targetOf, ...) are uninterpreted STUBS (no downvalues). A state
   projection is therefore the whole applicative history, e.g.

     exportCsv[autofillIn[updateEntry[updateNotesIn[deleteFrom[
       addEntry[addEntry[addEntry[importInto[{}, f], w], w], w],
       id], idn], editingRow[id], fields], id]]

   These nested terms balloon along a trace. TWO complementary compactions
   are provided, both PURE Wolfram (no engine change), both LOSSLESS:

     linearize / linearizeForm  — let-form (A-normal-form) pretty-printer:
         name each distinct compound subterm ONCE (CSE via structural
         equality), in bottom-up evaluation order.

     eventLog / condense        — condensed trace export: per step keep only
         {port, polarity, isVisible, boundValue}, NOT the cumulative state.
         The full snapshot is DERIVED on demand, never stored.
   ===================================================================== *)

(* ---------------------------------------------------------------------
   linearize[term] — common-subexpression-eliminating let-form.

   nameableQ decides which subterms get a binding. The rule names exactly the
   "state-threading spine": a compound application that either is the root, or
   sits in the FIRST-argument position of another named compound (where the
   value-functions thread the collection/state), PLUS any compound shared 2+
   times (genuine CSE). Tag/constructor leaves whose arguments are all atoms
   (editingRow[id], filterBy[q], scored[r], param[v], binding[x]) stay INLINE,
   matching the documented inline-leaf set; a tag that happens to wrap a
   compound (scored[evaluate[...]]) still names the inner compound.

   compoundQ: a non-atomic application h_Symbol[args__] with >=1 argument.
   Bare lists ({}, {a,b}) are treated as inline leaves (state seeds / literals).
--------------------------------------------------------------------- *)
compoundQ[t_] := !AtomQ[t] && Head[t] =!= List && Head[Head[t]] === Symbol &&
                 Length[t] >= 1;

(* spineNodes[term]: positions whose subterm is on the first-argument spine
   (reachable from the root by repeatedly descending into argument 1 of a
   compound). Returned as the set of those subterms (structural). *)
ClearAll[linearizeNameSet];
linearizeNameSet[term_] :=
  Module[{spine = {}, shared, counts, t = term},
    (* walk the first-argument spine from the root *)
    While[compoundQ[t],
      AppendTo[spine, t];
      t = First[t]];
    (* genuine CSE: any compound occurring 2+ times anywhere *)
    counts = Counts[Cases[term, x_ /; compoundQ[x], {0, Infinity}]];
    shared = Keys[Select[counts, # >= 2 &]];
    DeleteDuplicates[Join[spine, shared]]];

(* linearize[term] -> <|"bindings" -> {name -> rhs, ...}, "root" -> name|>
   bindings are in bottom-up (dependency) order; "root" is the name of the
   last (whole-term) binding, rendered as `out` by linearizeForm. Names are
   s1, s2, ... in bottom-up order. In each binding's rhs every OTHER named
   subterm is replaced by sym[itsName] (a printable let-variable reference);
   re-substituting (linearizeExpand) reproduces `term` exactly (LOSSLESS). *)
ClearAll[linearize];
linearize[term_] := Module[
  {named, ordered, names, i = 0, rhsOf, bindings},
  named = linearizeNameSet[term];
  If[named === {} || !compoundQ[term],
    Return[<|"bindings" -> {}, "root" -> term, "isAtomic" -> True|>]];
  (* bottom-up order: a node must follow every named node it contains. Sorting
     by LeafCount ascending guarantees a contained (smaller) node comes first.
     Ties broken stably; structurally-equal duplicates already collapsed. *)
  ordered = SortBy[named, LeafCount];
  names = Association[(# -> "s" <> ToString[++i]) & /@ ordered];
  (* refsIn[expr, self]: top-down replace each named PROPER subterm of expr by
     sym[name]; once a subterm is named, do NOT descend into it. `self` is the
     node being defined (never replaced by its own name). Recurse on arguments
     only, so the node's own head/structure is preserved. *)
  bindings = Map[
    Function[node,
      Module[{nameRefs},
        nameRefs[e_] := If[e =!= node && KeyExistsQ[names, e],
          sym[names[e]],
          If[compoundQ[e], Head[e] @@ (nameRefs /@ List @@ e), e]];
        names[node] -> nameRefs[node]]],
    ordered];
  <|"bindings" -> bindings, "root" -> names[term], "isAtomic" -> False|>];

(* sym[name] is the printable placeholder for a let-variable inside a binding's
   right-hand side. linearizeForm renders it as the bare variable name. *)
Format[sym[s_String], OutputForm] := s;

(* linearizeExpand[lin] : re-substitute the bindings to recover the ORIGINAL
   term (round-trip / losslessness check). *)
linearizeExpand[lin_Association] := Module[
  {env = <||>, bindings = lin["bindings"]},
  If[TrueQ[lin["isAtomic"]], Return[lin["root"]]];
  Do[env[First[b]] = (Last[b] /. sym[s_] :> env[s]), {b, bindings}];
  env[lin["root"]]];

(* linearizeForm[term] : a printable straight-line block. Headless-friendly
   String of "name = rhs;" lines (root line shown as "out = rhs"). The bindings
   are also returned by linearize for machine use. *)
linearizeForm[term_] := Module[{lin = linearize[term]},
  If[TrueQ[lin["isAtomic"]],
    Return["out = " <> ToString[lin["root"], InputForm]]];
  StringRiffle[
    (Module[{nm = First[#], rhs = Last[#], lbl},
       lbl = If[nm === lin["root"], "out", nm];
       lbl <> " = " <> StringReplace[ToString[rhs, InputForm],
                "sym[\"" ~~ s : (Except["\""] ..) ~~ "\"]" :> s] <>
       If[nm === lin["root"], "", ";"]] &) /@ lin["bindings"],
    "\n"]];

(* linearizeGrid[term] : notebook display (Grid of name | rhs). *)
linearizeGrid[term_] := Module[{lin = linearize[term], rows},
  If[TrueQ[lin["isAtomic"]],
    Return[Grid[{{"out", lin["root"]}}, Frame -> All]]];
  rows = (Module[{nm = First[#], rhs = Last[#]},
            {If[nm === lin["root"], "out", nm], "=",
             rhs /. sym[s_] :> s}] &) /@ lin["bindings"];
  Grid[rows, Alignment -> Left, Frame -> All]];


(* ---------------------------------------------------------------------
   Condensed event log.  An engine transition's ACTION is one of:
     label[name, param[v]]          OUTPUT (visible)   value v
     coLabel[name, binding[x]]      INPUT  (visible)   binds x
     coLabel[name]                  INPUT  (visible)   no binding
     tag[\[Tau], chan, subst]       internal SYNC tau  subst (a rule list)
     tag[\[Tau], chan]              internal tau       (no subst)
     \[Tau]                         plain tau

   eventOf[action] -> <|"port", "polarity", "isVisible", "value"|>
     polarity : "out" | "in" | "tau"
     value    : the param value (out), the binder(s) (in), the subst (tau),
                or None.
--------------------------------------------------------------------- *)
eventOf[label[nm_, param[v___]]] :=
  <|"port" -> nm, "polarity" -> "out", "isVisible" -> True, "value" -> {v}|>;
eventOf[label[nm_]] :=
  <|"port" -> nm, "polarity" -> "out", "isVisible" -> True, "value" -> None|>;
eventOf[coLabel[nm_, binding[x___]]] :=
  <|"port" -> nm, "polarity" -> "in", "isVisible" -> True, "value" -> {x}|>;
eventOf[coLabel[nm_]] :=
  <|"port" -> nm, "polarity" -> "in", "isVisible" -> True, "value" -> None|>;
eventOf[tag[\[Tau], ch_, subst_]] :=
  <|"port" -> ch, "polarity" -> "tau", "isVisible" -> False, "value" -> subst|>;
eventOf[tag[\[Tau], ch_]] :=
  <|"port" -> ch, "polarity" -> "tau", "isVisible" -> False, "value" -> None|>;
eventOf[\[Tau]] :=
  <|"port" -> \[Tau], "polarity" -> "tau", "isVisible" -> False, "value" -> None|>;
eventOf[a_] :=
  <|"port" -> portName[a], "polarity" -> "tau", "isVisible" -> False,
    "value" -> None|>;          (* fallback for any other bare action *)

(* walkSteps[tf, s0, plan] : generalises internal_transitions_test's label
   list. `plan` is a list of plan-entries vis["port"] | tau["chan"]. Returns
   <|"actions" -> {action...}, "states" -> {s0, s1, ...}, "stuck" -> bool|>.
   tf is the transition function (transNamed for mioCoreD, transVP for mioCore).
   The plan-entry resolver mirrors the test's findStep. *)
isTauAct[a_] := MatchQ[a, tag[\[Tau], ___]] || a === \[Tau];
walkResolve[tf_, s_, vis[nm_]] :=
  SelectFirst[tf[s], !isTauAct[First[#]] && portName[First[#]] === nm &];
walkResolve[tf_, s_, tau[ch_]] :=
  SelectFirst[tf[s], MatchQ[First[#], tag[\[Tau], ch, ___]] &];

Options[walkSteps] = {"AutoTau" -> False};
walkSteps[tf_, s0_, plan_List, OptionsPattern[]] := Module[
  {s = s0, acts = {}, states = {s0}, t, stuck = False,
   auto = TrueQ[OptionValue["AutoTau"]], settle},
  (* "AutoTau" -> True : maximal-progress between steps — fire the UNIQUE enabled
     internal tau repeatedly (stop on 0, or on >=2, which is a real choice left to
     an explicit tau[ch] entry). Lets a plan list only EXTERNAL actions, and stays
     robust as new internal syncs (langRead, chRead, …) are added — no plan edits.
     Same strategy as autoTau (walk.wl); kept here so walkSteps is self-contained.
     Default off, so explicit-tau plans + the tau-checking tests are unchanged. *)
  settle[] := If[auto,
    Module[{taus, g = 0},
      While[g++ < 500 && Length[taus = Select[tf[s], isTauAct[First[#]] &]] === 1,
        AppendTo[acts, First[First[taus]]]; s = Last[First[taus]]; AppendTo[states, s]]]];
  settle[];                                  (* settle taus reachable from s0 *)
  Do[t = walkResolve[tf, s, p];
     If[MissingQ[t], stuck = True; Break[]];
     AppendTo[acts, First[t]];
     s = Last[t];
     AppendTo[states, s];
     settle[],                               (* settle taus after each external step *)
     {p, plan}];
  <|"actions" -> acts, "states" -> states, "stuck" -> stuck|>];

(* eventLog[walk] : the COMPACT event log — one eventOf per action taken. *)
eventLog[walk_Association] := eventOf /@ walk["actions"];

(* condense[tf, s0, plan] : run the walk and return only the event log
   (the cumulative state terms are discarded — recoverable by replay). *)
condense[tf_, s0_, plan_List] := eventLog[walkSteps[tf, s0, plan]];

(* eventLogForm[log] : printable one-line-per-event rendering. *)
eventLogForm[log_List] := StringRiffle[
  (Module[{e = #, polTag},
     polTag = Switch[e["polarity"], "out", "!", "in", "?", _, "\[Tau]"];
     StringJoin[
       If[e["isVisible"], "[vis] ", "[TAU] "],
       ToString[e["port"]], polTag,
       If[e["value"] === None, "",
          " " <> ToString[e["value"], InputForm]]]] &) /@ log,
  "\n"];

(* parseEventLog[text] : INVERSE of eventLogForm — recover an EXECUTABLE plan
   (a list of vis["port"] | tau["chan"] entries) from a rendered text trace.
   Logged values are IGNORED: walkSteps re-derives them from the labels alone,
   so the parser only needs the port/channel and the [vis]/[TAU] prefix.
     - split on newlines, drop blank lines (tolerant of surrounding whitespace);
     - "[vis] ..." : take the next whitespace token, keep its LEADING run of
                     word chars (drops the trailing ! / ? polarity tag),
                     emit vis[port];
     - "[TAU] ..." : likewise, keep the leading word-char run (drops the
                     trailing \[Tau] polarity tag), emit tau[chan];
     - lines NOT starting with "[vis]"/"[TAU]" (e.g. wrapped value text, or a
       bare \[Tau] event with no named channel) are skipped — the dual-tau
       plan uses named channels so that edge does not arise there.
   The port token is matched as a leading run of word characters rather than
   by stripping a specific glyph, so it is robust to the \[Tau] polarity tag
   surviving a text-file round-trip as multi-byte (UTF-8) bytes.
   Round-trip target: parseEventLog[eventLogForm[condense[tf,s0,plan]]] === plan. *)
(* port/channel names are ASCII [A-Za-z0-9_]+; matching the LEADING ASCII-word
   run drops any trailing polarity glyph, INCLUDING a \[Tau] that survived a
   text round-trip as raw UTF-8 bytes (which a Unicode \w would wrongly keep). *)
leadingPort[tok_String] := First[StringCases[tok, RegularExpression["^[A-Za-z0-9_]+"]], ""];
parseEventLog[text_String] := Module[
  {lines, parseLine},
  lines = Select[StringTrim /@ StringSplit[text, "\n"], # =!= "" &];
  parseLine[line_] := Module[{rest, port},
    Which[
      StringStartsQ[line, "[vis]"],
        rest = StringTrim[StringDrop[line, StringLength["[vis]"]]];
        port = leadingPort[First[StringSplit[rest], ""]];
        If[port === "", {}, {vis[port]}],
      StringStartsQ[line, "[TAU]"],
        rest = StringTrim[StringDrop[line, StringLength["[TAU]"]]];
        port = leadingPort[First[StringSplit[rest], ""]];
        If[port === "", {}, {tau[port]}],
      True, {}]];
  Flatten[parseLine /@ lines, 1]];

(* importTrace[file] : parseEventLog of a text-trace file's contents. *)
importTrace[file_String] := parseEventLog[ReadString[file]];

(* replay[init, ops] : DERIVE a cumulative snapshot from a log of value-function
   OPERATIONS by folding them onto an initial state term. Each op is a function
   that maps the running term to the next (e.g. (addEntry[#, w] &)). This makes
   the snapshot derived-on-demand rather than stored. For the engine event log,
   the per-step value-function is symbolic (it lives in the agent equation, not
   the action), so replay is offered for the EXPLICIT-op form; the engine path
   documents that the snapshot equals Fold[apply, init, ops]. *)
replay[init_, ops_List] := Fold[#2[#1] &, init, ops];
snapshot[init_, ops_List] := replay[init, ops];
