#!/usr/bin/env wolframscript
(* =====================================================================
   spec/tests/helm_test.wls
   ---------------------------------------------------------------------
   Helm (session/language settings) — the recovered agent + functions.
   Checks the port structure (the set_speed-only-when-espeak guard), the
   read-only helmView projection (the source/target pair the oracles read),
   and value-driven settings changes. Helm is a STANDALONE call-based agent
   (transNamed), not composed into mioCore.

   Run headless:  wolframscript -file spec/tests/helm_test.wls
   ===================================================================== *)

$dir = ParentDirectory[DirectoryName[$InputFileName]] <> "/";
Get[$dir <> "MiolingoSpec.wl"];   (* loads HelmRecovered + HelmFunctions *)
Get[$dir <> "walk.wl"];           (* readyTransitions / supplyValue / viewProjections *)

ok[b_] := If[TrueQ[b], "OK", "*** FAIL ***"];
allOk = True;
assert[lbl_, b_] := (allOk = allOk && TrueQ[b]; Print["   ", If[TrueQ[b], "ok  ", "FAIL "], lbl]);
ports[s_] := Sort[ToString /@ portName /@ First /@ readyTransitions[transNamed, s]];
sup[s_, nm_, v_] := Last[supplyValue[SelectFirst[readyTransitions[transNamed, s], portName[First[#]] === nm &], v]];
view[s_] := Map[Identity, viewProjections[transNamed, s]["view"]];
hr = StringRepeat["=", 70];

sG = call["Helm", "English", "fr", google, 250];   (* tts = google *)
sE = call["Helm", "English", "fr", espeak, 250];    (* tts = espeak *)

Print[hr]; Print["1. ports — set_speed is gated on tts === espeak"]; Print[hr];
(* langRead is the internal READ port (a borrower pulls {source,target} from it);
   STANDALONE it is unrestricted so it shows here — in mioCore it is restricted
   to an internal tau and does NOT appear externally. *)
assert["google: view + langRead + set_source/target/tts, NO set_speed",
  ports[sG] === {"langRead", "set_source", "set_target", "set_tts", "view"}];
assert["espeak: + set_speed appears",
  MemberQ[ports[sE], "set_speed"]];
assert["set_speed absent unless espeak", !MemberQ[ports[sG], "set_speed"]];

(* langRead emits the (source, target) pair the borrowers pull *)
assert["langRead carries {source, target}",
  With[{t = SelectFirst[readyTransitions[transNamed, sG], portName[First[#]] === "langRead" &]},
    First[Cases[First[t], param[p_] :> p, Infinity], None] === {"English", "fr"}]];

Print[hr]; Print["2. helmView projection — the (source,target) pair others read"]; Print[hr];
v = view[sG];
assert["source / target / language / tts / speed present",
  v["source"] === "English" && v["target"] === "fr" &&
  v["language"] === "French" && v["tts"] === google && v["speed"] === 250];
assert["trainingNameOf maps the target code", trainingNameOf["pt"] === "Portuguese"];
assert["unknown code passes through", trainingNameOf["xx"] === "xx"];

Print[hr]; Print["3. value-driven settings changes (no typing)"]; Print[hr];
assert["set_target pt -> target pt, language Portuguese",
  view[sup[sG, "set_target", "pt"]]["language"] === "Portuguese"];
assert["set_source -> updates source",
  view[sup[sG, "set_source", "Italian"]]["source"] === "Italian"];
sEsp = sup[sG, "set_tts", espeak];
assert["set_tts espeak -> set_speed now available", MemberQ[ports[sEsp], "set_speed"]];
assert["then set_speed 300 -> speed 300", view[sup[sEsp, "set_speed", 300]]["speed"] === 300];

Print[hr];
Print["ALL ASSERTIONS: ", ok[allOk]];
Print[hr];
If[!allOk, Exit[1]];
