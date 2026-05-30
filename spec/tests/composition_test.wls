#!/usr/bin/env wolframscript
(* =====================================================================
   spec/tests/composition_test.wls
   ---------------------------------------------------------------------
   Self-contained test + diagnostic for the MioCore composition.
   Loads RCA_core.wl and the spec files IN ORDER, then:
     1. confirms the agents are registered (agentDefs),
     2. steps each composition layer (sub-agent -> par -> restrict ->
        call[MioCore]) so a transNamed that returns UNEVALUATED is
        localised to the exact layer that fails,
     3. checks the external ready set and the vAdd / pLoad tau syncs.

   Run headless:   wolframscript -file spec/tests/composition_test.wls
   Or Get it into a session (NB: re-Getting RCA_core.wl resets agentDefs,
   so always reload the spec files after, exactly as below).
   ===================================================================== *)

$rca = "/Users/matthew/Projects/private/Mathematica/RCA/RCA_core.wl";
$spec = "/Users/matthew/Software/working/miolingo/spec/";

Print["Loading engine + spec (order matters: discipline before components,",
      " components before MioCore) ..."];
Quiet[Get[$rca]];
Get[$spec <> "discipline.wl"];
Get[$spec <> "PracticeSessionRecovered.wl"];
Get[$spec <> "VocabStoreRecovered.wl"];
Get[$spec <> "MioCore.wl"];

bar = StringRepeat["=", 64];
ok[b_] := If[TrueQ[b], "OK", "*** FAIL ***"];
evaluatedQ[x_] := ListQ[x];   (* transNamed returns a list of {action,succ} *)

Print[bar];
Print["1. AGENT REGISTRATION (agentDefs)"];
Print[bar];
need = {"PS", "PSActive", "VS", "VSAuthed", "VSNonEmpty",
        "VSEntryActions", "VSEditActions", "MioCore"};
Do[Print["   ", StringPadRight[n, 16], KeyExistsQ[agentDefs, n] // ok], {n, need}];
Print["   discipline helper portsOf has HoldAll? ",
      ok[MemberQ[Attributes[portsOf], HoldAll]]];

Print[bar];
Print["2. LAYER-BY-LAYER transNamed (find where it stops evaluating)"];
Print[bar];
ps0 = call["PS", {}, 0, none, none];
vs0 = call["VS", signedIn, {}, alpha, none, none];
parTerm = par[ps0, vs0];
resTerm = restrict[parTerm, {label["vAdd"], label["pLoad"]}];

tPS  = transNamed[ps0];   Print["   transNamed[PS]            evaluated? ", ok[evaluatedQ[tPS]]];
tVS  = transNamed[vs0];   Print["   transNamed[VS]            evaluated? ", ok[evaluatedQ[tVS]]];
tPar = transNamed[parTerm]; Print["   transNamed[par[PS,VS]]    evaluated? ", ok[evaluatedQ[tPar]]];
tRes = transNamed[resTerm]; Print["   transNamed[restrict[...]] evaluated? ", ok[evaluatedQ[tRes]]];
tMio = transNamed[call["MioCore"]];
Print["   transNamed[call[MioCore]] evaluated? ", ok[evaluatedQ[tMio]]];
If[! evaluatedQ[tMio],
  Print["   >>> MioCore did not evaluate. Head of result: ", Head[tMio]];
  Print["   >>> Likely cause: a sub-agent above shows FAIL (not loaded), or"];
  Print["   >>> this engine's transNamed lacks the par/restrict clauses."];
];

Print[bar];
Print["3. EXTERNAL READY SET (vAdd / pLoad must be hidden by restriction)"];
Print[bar];
nm[s_] := Sort[portName /@ (First /@ transNamed[s])];
If[evaluatedQ[tMio],
  Module[{ns = nm[call["MioCore"]]},
    Print["   ", InputForm[ns]];
    Print["   vAdd hidden?  ", ok[! MemberQ[ns, "vAdd"]]];
    Print["   pLoad hidden? ", ok[! MemberQ[ns, "pLoad"]]]]];

Print[bar];
Print["4. CROSS-COMPONENT SYNCHRONISATION (step the composite to a tau)"];
Print[bar];
R = {label["vAdd"], label["pLoad"]};
isTau[a_] := MatchQ[a, tag[\[Tau], ___]] || a === \[Tau];
stepTo[s_, name_] := Module[{t = SelectFirst[transNamed[s], portName[#[[1]]] === name &]},
  If[MissingQ[t], $Failed, t[[2]]]];
taus[s_] := Cases[First /@ transNamed[s], _?isTau];

cv = restrict[par[call["PS", {p1}, 0, recorded[a], scored[r]], vs0], R];
cv2 = stepTo[cv, "capture_vocab"];
Print["   capture_vocab -> tau(vAdd)?  ",
  ok[cv2 =!= $Failed && AnyTrue[taus[cv2], MatchQ[#, tag[\[Tau], "vAdd", ___]] &]]];
If[cv2 =!= $Failed, Print["      ", InputForm[taus[cv2]]]];

pf = restrict[par[call["PS", {}, 0, none, none],
                  call["VS", signedIn, {e1}, alpha, filterBy["q"], none]], R];
pf2 = stepTo[pf, "practise_filtered"];
Print["   practise_filtered -> tau(pLoad)?  ",
  ok[pf2 =!= $Failed && AnyTrue[taus[pf2], MatchQ[#, tag[\[Tau], "pLoad", ___]] &]]];
If[pf2 =!= $Failed, Print["      ", InputForm[taus[pf2]]]];

Print[bar];
Print["done."];
