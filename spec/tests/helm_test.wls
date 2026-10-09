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

sG = call["Helm", "English", "fr", google, 250, system, base];   (* tts = google *)
sE = call["Helm", "English", "fr", espeak, 250, system, base];    (* tts = espeak *)

Print[hr]; Print["1. ports — set_speed is gated on tts === espeak"]; Print[hr];
(* langRead/targetRead are the internal READ ports (a borrower pulls the pair /
   the target code); STANDALONE they are unrestricted so they show here — in
   mioCore they are restricted to internal taus and do NOT appear externally. *)
assert["google: view + langRead + targetRead + set_source/target/tts + set_asr, NO set_speed",
  ports[sG] === {"langRead", "set_asr", "set_source", "set_target", "set_tts", "targetRead", "view"}];
assert["espeak: + set_speed appears",
  MemberQ[ports[sE], "set_speed"]];
assert["set_speed absent unless espeak", !MemberQ[ports[sG], "set_speed"]];
(* set_asr always available; set_asr_model whisper-only (mirrors set_speed/espeak). *)
assert["set_asr always present", MemberQ[ports[sG], "set_asr"]];
assert["set_asr_model absent unless whisper", !MemberQ[ports[sG], "set_asr_model"]];

(* langRead emits the (source, target) pair; targetRead is the NARROW read —
   only the target code (the scoring borrow; the asymmetry principle) *)
assert["langRead carries {source, target}",
  With[{t = SelectFirst[readyTransitions[transNamed, sG], portName[First[#]] === "langRead" &]},
    First[Cases[First[t], param[p_] :> p, Infinity], None] === {"English", "fr"}]];
assert["targetRead carries ONLY the target code",
  With[{t = SelectFirst[readyTransitions[transNamed, sG], portName[First[#]] === "targetRead" &]},
    First[Cases[First[t], param[p_] :> p, Infinity], None] === "fr"]];

Print[hr]; Print["2. helmView projection — the (source,target) pair others read"]; Print[hr];
v = view[sG];
assert["source / target / language / tts / speed present",
  v["source"] === "English" && v["target"] === "fr" &&
  v["language"] === "French" && v["tts"] === google && v["speed"] === 250];
assert["asr / asrModel present (default system / base)",
  v["asr"] === system && v["asrModel"] === base];
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
(* ASR engine + model, mirroring tts + speed *)
sWh = sup[sG, "set_asr", whisper];
assert["set_asr whisper -> set_asr_model now available", MemberQ[ports[sWh], "set_asr_model"]];
assert["then set_asr_model small -> asrModel small",
  view[sup[sWh, "set_asr_model", small]]["asrModel"] === small];

Print[hr];
Print["ALL ASSERTIONS: ", ok[allOk]];
Print[hr];
If[!allOk, Exit[1]];
