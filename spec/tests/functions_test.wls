#!/usr/bin/env wolframscript
(* function-recovery pass — golden cases for VS + PS value-functions,
   checked against behaviour stated in the Python docstrings (NOT a live DB).
   Paths + engine version come from spec/paths.wl, located relative to this
   test, so it runs unchanged in any worktree or the canonical spec. *)

Get[FileNameJoin[{ParentDirectory[DirectoryName[$InputFileName]], "paths.wl"}]];
loadEngine[];
loadRecoveredBase[];
mioGet["VocabStoreFunctions.wl"];
mioGet["PracticeSessionFunctions.wl"];

ok[b_] := If[TrueQ[b], "OK", "*** FAIL ***"];

Print["== VocabStore =="];

(* addEntry: new word appends with times_seen 1 *)
e1 = addEntry[{}, <|"word" -> "Maison", "translation" -> "house"|>];
Print["  add new -> 1 entry, times_seen 1, key lowercased? ",
  ok[Length[e1] === 1 && e1[[1]]["times_seen"] === 1 && e1[[1]]["word"] === "maison"
     && e1[[1]]["display_word"] === "Maison"]];

(* addEntry dedup: same lookup key bumps times_seen, fills null (COALESCE) *)
e2 = addEntry[e1, <|"word" -> "maison", "ipa" -> "mɛzɔ̃"|>];
Print["  add dup -> still 1 entry, times_seen 2, ipa filled? ",
  ok[Length[e2] === 1 && e2[[1]]["times_seen"] === 2 && e2[[1]]["ipa"] === "mɛzɔ̃"]];

(* COALESCE never overwrites a non-null field *)
e2b = addEntry[e2, <|"word" -> "maison", "translation" -> "HOME"|>];
Print["  add dup -> translation NOT overwritten? ",
  ok[e2b[[1]]["translation"] === "house" && e2b[[1]]["times_seen"] === 3]];

(* invalid (multi-word) capture is a no-op *)
e3 = addEntry[e2, <|"word" -> "deux mots"|>];
Print["  multi-word capture is no-op? ", ok[e3 === e2]];
Print["  punct-only capture is no-op? ", ok[addEntry[e2, "..."] === e2]];

(* deleteFrom by id *)
id1 = e2[[1]]["id"];
Print["  deleteFrom removes by id? ", ok[deleteFrom[e2, id1] === {}]];

(* updateNotesIn *)
e4 = updateNotesIn[e2, <|"id" -> id1, "notes" -> "irregular"|>];
Print["  updateNotesIn sets notes? ", ok[e4[[1]]["notes"] === "irregular"]];

(* updateEntry: casing fix preserves key -> accepted *)
e5 = updateEntry[e2, editingRow[id1], <|"display_word" -> "MAISON"|>];
Print["  updateEntry casing fix accepted? ",
  ok[e5[[1]]["display_word"] === "MAISON" && e5[[1]]["word"] === "maison"]];

(* updateEntry: key-changing display_word -> rejected (unchanged) *)
e6 = updateEntry[e2, editingRow[id1], <|"display_word" -> "chateau"|>];
Print["  updateEntry key-change rejected (no-op)? ", ok[e6 === e2]];

(* updateEntry: unknown field rejected *)
e7 = updateEntry[e2, editingRow[id1], <|"word" -> "x"|>];
Print["  updateEntry unknown field rejected? ", ok[e7 === e2]];

(* autofillIn: oracle fills only empty fields *)
enrichOracle["chien"] = <|"translation" -> "dog", "ipa" -> "ʃjɛ̃"|>;
ed = addEntry[{}, <|"word" -> "chien"|>];
ef = autofillIn[ed, ed[[1]]["id"]];
Print["  autofillIn fills empty translation+ipa via oracle? ",
  ok[ef[[1]]["translation"] === "dog" && ef[[1]]["ipa"] === "ʃjɛ̃"]];
(* never overwrites an existing field *)
eg = addEntry[{}, <|"word" -> "chien", "translation" -> "hound"|>];
eh = autofillIn[eg, eg[[1]]["id"]];
Print["  autofillIn does NOT overwrite existing translation? ",
  ok[eh[[1]]["translation"] === "hound" && eh[[1]]["ipa"] === "ʃjɛ̃"]];

(* exportCsv: exact 13-column header *)
csv = exportCsv[e2];
hdr = First[StringSplit[csv, "\n"]];
Print["  exportCsv header exact? ",
  ok[hdr === "word,translation,ipa,source_language,source,context_before,context_line,context_after,times_seen,first_seen_at,last_seen_at,notes,url"]];

(* import: header + pipe parse + fold addEntry; dedup across rows *)
contents = "(fr, en)\n# a comment\nchat | cat | [ʃa]\nchat | | \nchien|dog";
ei = importInto[{}, <|"contents" -> contents, "expectedTarget" -> "en"|>];
Print["  importInto: 2 distinct entries (chat bumped)? ",
  ok[Length[ei] === 2 && SelectFirst[ei, #["word"] === "chat" &]["times_seen"] === 2]];
Print["  importInto: ipa bracket-stripped? ",
  ok[SelectFirst[ei, #["word"] === "chat" &]["ipa"] === "ʃa"]];
(* target mismatch aborts with no capture *)
Print["  importInto target mismatch -> no-op? ",
  ok[importInto[{}, <|"contents" -> contents, "expectedTarget" -> "de"|>] === {}]];
(* missing header -> no-op *)
Print["  importInto missing header -> no-op? ",
  ok[importInto[{}, <|"contents" -> "chat|cat", "expectedTarget" -> "en"|>] === {}]];

(* logical clock: recent/oldest order by last_seq/first_seq, bump-aware *)
lc0 = addEntry[addEntry[{}, "alpha"], "beta"];   (* alpha older, beta newer *)
Print["  oldest = capture order [alpha,beta]? ",
  ok[#["word"] & /@ sortEntries[lc0, oldest] === {"alpha", "beta"}]];
Print["  recent = reverse [beta,alpha]? ",
  ok[#["word"] & /@ sortEntries[lc0, recent] === {"beta", "alpha"}]];
lc1 = addEntry[lc0, "alpha"];                    (* re-capture alpha: bump *)
Print["  recent after re-capturing alpha -> [alpha,beta]? ",
  ok[#["word"] & /@ sortEntries[lc1, recent] === {"alpha", "beta"}]];
Print["  oldest unchanged after bump -> [alpha,beta]? ",
  ok[#["word"] & /@ sortEntries[lc1, oldest] === {"alpha", "beta"}]];
Print["  no wall-clock keys on entries? ",
  ok[FreeQ[lc1, "first_seen_at" | "last_seen_at" | _vsNow]]];

(* practiseList: filter + shape to {text,translation,ipa} *)
pl = practiseList[ei, none];
Print["  practiseList shape {text,translation,ipa}? ",
  ok[Length[pl] === 2 && Sort[Keys[pl[[1]]]] === {"ipa", "text", "translation"}]];
plf = practiseList[ei, filterBy["chien"]];
Print["  practiseList filterBy substring? ",
  ok[Length[plf] === 1 && plf[[1]]["text"] === "chien"]];

Print["== PracticeSession =="];

(* levenshtein known value: kitten -> sitting = 3 *)
Print["  levenshtein[kitten,sitting]===3? ", ok[levenshtein["kitten", "sitting"] === 3]];

(* comparePhonemes identity: similarity = 1 - dist/maxlen *)
cp = comparePhonemes["abcd", "abxd"];
Print["  comparePhonemes dist 1, similarity 0.75? ",
  ok[cp["distance"] === 1 && cp["similarity"] === 0.75 && cp["exact_match"] === False]];
Print["  comparePhonemes exact -> similarity 1.0? ",
  ok[comparePhonemes["abc", "abc"]["similarity"] === 1.0 && comparePhonemes["abc", "abc"]["exact_match"]]];

(* targetOf 0-based; evaluate composes ASR oracle with pure compare *)
phr = practiseList[ei, none];
tgt = targetOf[plf, 0];
Print["  targetOf[_,0] is first phrase? ", ok[tgt["text"] === "chien"]];
recognisePhonemes[aud_] := "dxg";          (* stub the IO oracle *)
ev = evaluate[<|"ipa" -> "dog"|>, recorded["audio-blob"]];
Print["  evaluate composes oracle+compare (dist 1)? ",
  ok[ev["distance"] === 1 && ev["exact_match"] === False]];

(* sessionView projection *)
sv = sessionView[plf, 0, recorded["a"], scored[<|"similarity" -> 0.9|>]];
Print["  sessionView publishes pos/hasRecording/score? ",
  ok[sv["pos"] === 0 && sv["hasRecording"] === True && sv["score"]["similarity"] === 0.9]];

Print["done."];
