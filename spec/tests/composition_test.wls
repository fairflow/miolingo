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
     3. checks the external ready set and the vocabUpsert / goPractice tau syncs.

   Run headless:   wolframscript -file spec/tests/composition_test.wls
   Or Get it into a session (NB: re-Getting RCA_core.wl resets agentDefs,
   so always reload the spec files after, exactly as below).
   ===================================================================== *)

Get[FileNameJoin[{ParentDirectory[DirectoryName[$InputFileName]], "paths.wl"}]];

Print["Loading engine + spec (order matters: discipline before components,",
      " components before MioCore) ..."];
loadEngine[];
loadRecoveredBase[];
mioGet["StoryFunctions.wl"];   (* sceneOf — StoryReader's nav guard reads Length[sceneOf[scene]] *)
mioGet["MioCore.wl"];
mioGet["walk.wl"];   (* walkSteps "AutoTau" + value-carrying vis[nm,val] for §4 *)

bar = StringRepeat["=", 64];
ok[b_] := If[TrueQ[b], "OK", "*** FAIL ***"];
evaluatedQ[x_] := ListQ[x];   (* transNamed returns a list of {action,succ} *)
isTau[a_] := MatchQ[a, tag[\[Tau], ___]] || a === \[Tau];
lab[a_]   := If[MatchQ[a, tag[\[Tau], _, ___]], a[[2]], portName[a]];

Print[bar];
Print["1. AGENT REGISTRATION (agentDefs)"];
Print[bar];
need = {"PS", "PSActive", "PSBrowse", "Vocab", "VocabAuthed", "VocabNonEmpty",
        "VocabEntryActions", "VocabEditActions", "Helm", "VocabTable",
        "StoryReader", "StoryBrowse", "StoryPractice"};
(* MioCore is now a composed MU-TERM value (relabeled view!), not a
   defineAgent; it is stepped with transVP[MioCore], not call["MioCore"]. *)
Do[Print["   ", StringPadRight[n, 16], KeyExistsQ[agentDefs, n] // ok], {n, need}];
Print["   discipline helper portsOf has HoldAll? ",
      ok[MemberQ[Attributes[portsOf], HoldAll]]];

Print[bar];
Print["2. LAYER-BY-LAYER transNamed (find where it stops evaluating)"];
Print[bar];
ps0 = call["PS", {}, 0, none, none];
vs0 = call["Vocab", signedIn, alpha, none, none];          (* (i): no entries *)
ch0 = call["VocabTable", {}];                            (* the store owns the entries *)
helm0 = call["Helm", "English", "fr", google, 250];
R = {label["vocabUpsert"], label["goPractice"], label["langRead"],
     label["vocabRead"], label["vocabUpsert"], label["vocabImport"], label["vocabRemove"], label["vocabAmend"]};
parTerm = par[par[par[ps0, vs0], helm0], ch0];
resTerm = restrict[parTerm, R];

tPS  = transNamed[ps0];   Print["   transNamed[PS]            evaluated? ", ok[evaluatedQ[tPS]]];
tVS  = transNamed[vs0];   Print["   transNamed[Vocab]            evaluated? ", ok[evaluatedQ[tVS]]];
tCH  = transNamed[ch0];   Print["   transNamed[VocabTable]     evaluated? ", ok[evaluatedQ[tCH]]];
tPar = transNamed[parTerm]; Print["   transNamed[par[…]]        evaluated? ", ok[evaluatedQ[tPar]]];
tRes = transNamed[resTerm]; Print["   transNamed[restrict[...]] evaluated? ", ok[evaluatedQ[tRes]]];
tMio = transVP[mioCore];   (* composed mu-term: step with transVP *)
Print["   transVP[mioCore] evaluated? ", ok[evaluatedQ[tMio]]];
If[! evaluatedQ[tMio],
  Print["   >>> MioCore did not evaluate. Head of result: ", Head[tMio]];
  Print["   >>> Likely cause: a sub-agent above shows FAIL (not loaded)."];
];

Print[bar];
Print["3. EXTERNAL READY SET (all restricted channels hidden)"];
Print[bar];
(* Vocab gates behind vocabRead under (i): settle, then the external (non-tau) ready set
   is the familiar one (now incl. open_practice, the PS pull entry) — and the
   restricted channels (vocabUpsert/goPractice and the ch* store channels) are NOT among
   the external named ports. *)
If[evaluatedQ[tMio],
  Module[{ns = Sort[portName /@ Select[First /@
       transVP[Last[walkSteps[transVP, mioCore, {}, "AutoTau" -> True]["states"]]], ! isTau[#] &]]},
    Print["   (settled) ", InputForm[ns]];
    Print["   open_practice shown? ", ok[MemberQ[ns, "open_practice"]]];
    Print["   vocabUpsert hidden?       ", ok[! MemberQ[ns, "vocabUpsert"]]];
    Print["   goPractice hidden? ", ok[! MemberQ[ns, "goPractice"]]];
    Print["   vocabRead hidden?     ", ok[! MemberQ[ns, "vocabRead"]]];
    Print["   vocabUpsert hidden?   ", ok[! MemberQ[ns, "vocabUpsert"]]]]];

Print[bar];
Print["4. CROSS-COMPONENT SYNCHRONISATION (via AutoTau on mioCoreD)"];
Print[bar];
labelsOf[plan_] := lab /@ walkSteps[transNamed, mioCoreD, plan, "AutoTau" -> True]["actions"];
capLabels = labelsOf[{vis["load_material", {<|"text" -> "chat", "translation" -> "cat"|>}],
                      vis["recording_made", "a"], vis["attempt_made"], vis["capture_vocab", "chat"]}];
Print["   capture_vocab relays via vocabUpsert?   ", ok[MemberQ[capLabels, "vocabUpsert"]]];
Print["      ", InputForm[capLabels]];
plLabels = labelsOf[{vis["open_vocab"], vis["add", <|"word" -> "chat"|>], vis["set_filter", "ch"], vis["practise_vocab"]}];
Print["   practise_vocab signals via goPractice? ", ok[MemberQ[plLabels, "goPractice"]]];
Print["      ", InputForm[plLabels]];
ppLabels = labelsOf[{vis["open_practice"], vis["load_vocab"]}];
Print["   open_practice pulls via vocabRead?        ", ok[MemberQ[ppLabels, "vocabRead"]]];
Print["      ", InputForm[ppLabels]];

Print[bar];
Print["done."];
