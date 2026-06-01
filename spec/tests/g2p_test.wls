#!/usr/bin/env wolframscript
(* =====================================================================
   spec/tests/g2p_test.wls
   ---------------------------------------------------------------------
   The espeak G2P bridge (spec/g2p.wl) runs for real: a written word ->
   its IPA. Robust assertions (key phonemes present, not exact strings,
   so it survives espeak version drift). Skips cleanly if espeak is absent
   (the bridge degrades to $Failed; this is an external-service spike).

   Run headless:  wolframscript -file spec/tests/g2p_test.wls
   ===================================================================== *)

$dir = ParentDirectory[DirectoryName[$InputFileName]] <> "/";
Get[$dir <> "g2p.wl"];

ok[b_] := If[TrueQ[b], "OK", "*** FAIL ***"];
allOk = True;
assert[lbl_, b_] := (allOk = allOk && TrueQ[b]; Print["   ", If[TrueQ[b], "ok  ", "FAIL "], lbl]);
hr = StringRepeat["=", 70];

Print[hr];
If[!espeakAvailableQ[],
  Print["espeak not available on this machine — SKIPPING (bridge -> $Failed)."];
  Print["  espeakG2P[\"chat\"] = ", InputForm[espeakG2P["chat"]]];
  Print[hr]; Exit[0]];

Print["espeak G2P bridge runs for real"]; Print[hr];
Print["   espeak version: ", StringTrim[RunProcess[{"espeak", "--version"}]["StandardOutput"]]];

(* IPA chars built from codepoints (ASCII source, so encoding-proof) — the
   bridge returns proper Unicode, so we match against decoded chars:
   esh = ʃ (U+0283), rr = ʁ (U+0281), stress = ˈ (U+02C8) *)
esh = FromCharacterCode[643]; rr = FromCharacterCode[641]; stress = FromCharacterCode[712];

assert["fr chat -> non-empty IPA containing ʃ",
  StringQ[espeakG2P["chat", "fr"]] && StringContainsQ[espeakG2P["chat", "fr"], esh]];
assert["fr souris -> contains ʁ",
  StringContainsQ[espeakG2P["souris", "fr"], rr]];
assert["en chat -> non-empty IPA",
  StringQ[espeakG2P["chat", "en"]] && espeakG2P["chat", "en"] =!= ""];
assert["bridge decodes UTF-8 (ʃ is one char U+0283, not two bytes)",
  MemberQ[ToCharacterCode[espeakG2P["chat", "fr"]], 643]];
assert["espeakG2Pplain strips the stress mark (no ˈ)",
  !StringContainsQ[espeakG2Pplain["chat", "fr"], stress]];
assert["plain fr chat is the spec-style ipa (ʃ kept, no stress)",
  StringContainsQ[espeakG2Pplain["chat", "fr"], esh]];

Print["   (fr chat codepoints = ", ToCharacterCode[espeakG2P["chat", "fr"]],
      " ; plain = ", ToCharacterCode[espeakG2Pplain["chat", "fr"]], ")"];

Print[hr];
Print["ALL ASSERTIONS: ", ok[allOk]];
Print[hr];
If[!allOk, Exit[1]];
