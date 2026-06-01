#!/usr/bin/env wolframscript
(* =====================================================================
   spec/tests/functions_unit_test.wls
   ---------------------------------------------------------------------
   Systematic UNIT tests for every value-function in VocabStoreFunctions.wl
   and PracticeSessionFunctions.wl — leaves and helpers included, with edge
   cases. Complements functions_test.wls (golden end-to-end cases); this one
   pins each function's contract directly so behaviour can be validated
   without hand-driving the interface.

   The two IO oracles (no downvalue in the spec) are interpreted here with
   canned values so the functions that compose them are testable:
     enrichOracle[word]      -> a fixed translation/ipa
     recognisePhonemes[audio] -> a fixed phoneme string

   Run headless:  wolframscript -file spec/tests/functions_unit_test.wls
   ===================================================================== *)

$dir = ParentDirectory[DirectoryName[$InputFileName]] <> "/";
Get[$dir <> "MiolingoSpec.wl"];

enrichOracle[_, _, _] := <|"translation" -> "ORC", "ipa" -> "ɔrk"|>;  (* word, source, target *)
recognisePhonemes[_]  := "abc";

ok[b_] := If[TrueQ[b], "OK", "*** FAIL ***"];
allOk = True; n = 0;
assert[lbl_, b_] := (n++; allOk = allOk && TrueQ[b];
  Print["   ", If[TrueQ[b], "ok  ", "FAIL "], lbl]);
hr = StringRepeat["=", 70];
sec[t_] := (Print[hr]; Print[t]; Print[hr]);

(* ---------------- VocabStore: id / seq / null helpers ---------------- *)
sec["vsNewId / vsNextSeq / emptyToNull / coalesce"];
assert["vsNewId {} -> 1", vsNewId[{}] === 1];
assert["vsNewId max(id)+1", vsNewId[{<|"id" -> 1|>, <|"id" -> 3|>}] === 4];
assert["vsNewId ignores id-less entries", vsNewId[{<|"x" -> 9|>}] === 1];
assert["vsNextSeq {} -> 1", vsNextSeq[{}] === 1];
assert["vsNextSeq max(last_seq)+1", vsNextSeq[{<|"last_seq" -> 2|>, <|"last_seq" -> 5|>}] === 6];
assert["emptyToNull \"\" -> Null", emptyToNull[""] === Null];
assert["emptyToNull Null -> Null", emptyToNull[Null] === Null];
assert["emptyToNull Missing -> Null", emptyToNull[Missing[]] === Null];
assert["emptyToNull keeps 0 (not empty)", emptyToNull[0] === 0];
assert["emptyToNull keeps value", emptyToNull["x"] === "x"];
assert["coalesce keeps non-null old", coalesce["old", "new"] === "old"];
assert["coalesce null old -> new", coalesce[Null, "new"] === "new"];
assert["coalesce empty old -> new", coalesce["", "new"] === "new"];
assert["coalesce null old + empty new -> Null", coalesce[Null, ""] === Null];

(* ---------------- normalise / validateWord -------------------------- *)
sec["normalise / validateWord"];
assert["normalise keeps case in display, lowercases key",
  normalise["Maison"] === {"Maison", "maison"}];
assert["normalise strips surrounding punct, keeps inner",
  normalise[" .Chat! "] === {"Chat", "chat"}];
assert["normalise keeps inner apostrophe", normalise["l'eau"] === {"l'eau", "l'eau"}];
assert["validateWord ok -> {display,key}", validateWord["Maison"] === {"Maison", "maison"}];
assert["validateWord empty -> $Failed", validateWord[""] === $Failed];
assert["validateWord punct-only -> $Failed", validateWord["..."] === $Failed];
assert["validateWord multi-word -> $Failed", validateWord["deux mots"] === $Failed];
assert["validateWord >100 chars -> $Failed", validateWord[StringRepeat["a", 101]] === $Failed];
assert["validateWord non-string -> $Failed", validateWord[5] === $Failed];

(* ---------------- addEntry ------------------------------------------ *)
sec["addEntry (upsert, dedup, COALESCE, payload shape)"];
e1 = addEntry[{}, <|"word" -> "Maison", "translation" -> "house"|>];
assert["new entry appended, key lowercased, display kept, times_seen 1",
  Length[e1] === 1 && e1[[1]]["word"] === "maison" &&
  e1[[1]]["display_word"] === "Maison" && e1[[1]]["times_seen"] === 1];
assert["bare string lifts to <|word->..|>", addEntry[{}, "chat"][[1]]["word"] === "chat"];
assert["payload WITHOUT \"word\" is a no-op (the text-vs-word case)",
  addEntry[{}, <|"text" -> "chat"|>] === {}];
e2 = addEntry[e1, <|"word" -> "maison", "ipa" -> "mɛzɔ̃"|>];
assert["dedup by key: times_seen bumped, null ipa filled",
  Length[e2] === 1 && e2[[1]]["times_seen"] === 2 && e2[[1]]["ipa"] === "mɛzɔ̃"];
e3 = addEntry[e2, <|"word" -> "maison", "translation" -> "HOME"|>];
assert["COALESCE never overwrites a non-null field",
  e3[[1]]["translation"] === "house" && e3[[1]]["times_seen"] === 3];
assert["invalid word -> unchanged", addEntry[e2, <|"word" -> "deux mots"|>] === e2];

(* ---------------- deleteFrom / updateNotesIn ------------------------ *)
sec["deleteFrom / updateNotesIn"];
d0 = addEntry[addEntry[{}, "chat"], "chien"];
assert["deleteFrom removes by id", Length[deleteFrom[d0, 1]] === 1];
assert["deleteFrom missing id -> unchanged", deleteFrom[d0, 99] === d0];
un = updateNotesIn[d0, <|"id" -> 1, "notes" -> "n1"|>];
assert["updateNotesIn sets notes", SelectFirst[un, #["id"] === 1 &]["notes"] === "n1"];
assert["updateNotesIn empty notes -> Null",
  SelectFirst[updateNotesIn[d0, <|"id" -> 1, "notes" -> ""|>], #["id"] === 1 &]["notes"] === Null];
assert["updateNotesIn missing id -> unchanged",
  updateNotesIn[d0, <|"id" -> 99, "notes" -> "x"|>] === d0];

(* ---------------- updateEntry --------------------------------------- *)
sec["updateEntry (editable, key-change, casing, both clauses)"];
u0 = addEntry[{}, "chat"];   (* id 1, word/display "chat" *)
assert["casing fix accepted (same key)",
  updateEntry[u0, editingRow[1], <|"display_word" -> "Chat"|>][[1]]["display_word"] === "Chat"];
assert["key-change rejected -> unchanged",
  updateEntry[u0, editingRow[1], <|"display_word" -> "dog"|>] === u0];
assert["unknown field rejected -> unchanged",
  updateEntry[u0, editingRow[1], <|"bogus" -> "x"|>] === u0];
assert["missing row -> unchanged",
  updateEntry[u0, editingRow[99], <|"translation" -> "x"|>] === u0];
assert["empty value -> Null",
  updateEntry[u0, editingRow[1], <|"translation" -> ""|>][[1]]["translation"] === Null];
assert["bare-id clause delegates to editingRow",
  updateEntry[u0, 1, <|"translation" -> "cat"|>][[1]]["translation"] === "cat"];

(* ---------------- autofillIn ---------------------------------------- *)
sec["autofillIn (oracle fills only empty fields)"];
af0 = addEntry[{}, "chat"];   (* translation/ipa Null *)
afL = {"English", "fr"};       (* the borrowed (source, target) pair *)
af1 = autofillIn[af0, 1, afL];
assert["fills empty translation + ipa via oracle",
  af1[[1]]["translation"] === "ORC" && af1[[1]]["ipa"] === "ɔrk"];
af2 = autofillIn[updateEntry[af0, 1, <|"translation" -> "keep"|>], 1, afL];
assert["does NOT overwrite existing translation", af2[[1]]["translation"] === "keep"];
assert["missing id -> unchanged", autofillIn[af0, 99, afL] === af0];

(* ---------------- import parser ------------------------------------- *)
sec["parseImportLine / parseImportHeader / isImportDataLine / importInto"];
pl = parseImportLine["chat|cat|[ʃa]|bk|http://u"];
assert["parseImportLine fields + ipa bracket-stripped",
  pl["word"] === "chat" && pl["translation"] === "cat" && pl["ipa"] === "ʃa" &&
  pl["source_name"] === "bk" && pl["url"] === "http://u"];
assert["parseImportLine empty -> Missing", MissingQ[parseImportLine[""]]];
assert["parseImportLine missing fields -> empty strings",
  parseImportLine["chat"]["translation"] === ""];
assert["parseImportLine ipa without brackets kept", parseImportLine["x||ab"]["ipa"] === "ab"];
assert["parseImportHeader (src,tgt) lowercased", parseImportHeader["(EN, FR)\nx|y"] === {"en", "fr"}];
assert["parseImportHeader skips #comment", parseImportHeader["# note\n(en,fr)"] === {"en", "fr"}];
assert["parseImportHeader no header (data first) -> $Failed",
  parseImportHeader["chat|cat"] === $Failed];
assert["isImportDataLine: data True", isImportDataLine["chat|cat"]];
assert["isImportDataLine: blank False", isImportDataLine["   "] === False];
assert["isImportDataLine: comment False", isImportDataLine["# x"] === False];
assert["isImportDataLine: header-paren False", isImportDataLine["(en,fr)"] === False];
imp = importInto[{}, <|"contents" -> "(en,fr)\nchat|cat\nchien|dog", "expectedTarget" -> "fr"|>];
assert["importInto adds the data rows", Length[imp] === 2];
assert["importInto target mismatch -> unchanged",
  importInto[{}, <|"contents" -> "(en,de)\nchat|cat", "expectedTarget" -> "fr"|>] === {}];
assert["importInto no header -> unchanged",
  importInto[{}, <|"contents" -> "chat|cat"|>] === {}];

(* ---------------- CSV ----------------------------------------------- *)
sec["csvCell / csvField / exportCsv"];
assert["csvCell Null -> empty", csvCell[Null] === ""];
assert["csvCell Missing -> empty", csvCell[Missing[]] === ""];
assert["csvCell number -> string", csvCell[5] === "5"];
assert["csvField plain unquoted", csvField["plain"] === "plain"];
assert["csvField comma -> quoted", csvField["a,b"] === "\"a,b\""];
assert["csvField quote -> doubled+quoted", csvField["a\"b"] === "\"a\"\"b\""];
assert["csvField newline -> quoted", csvField["a\nb"] === "\"a\nb\""];
csv = exportCsv[addEntry[{}, <|"word" -> "Chat", "translation" -> "cat"|>]];
csvLines = StringSplit[csv, "\n"];
assert["exportCsv header is the exact 13 columns",
  First[csvLines] === StringRiffle[exportCsvHeader, ","]];
assert["exportCsv row uses display_word + empty time columns",
  StringContainsQ[csvLines[[2]], "Chat,cat"] &&
  StringContainsQ[csvLines[[2]], ",1,,,"]];   (* times_seen,first,last empty *)

(* ---------------- sort / filter / view ------------------------------ *)
sec["sortEntries / filterMatch / applyFilter / practiseList / vocabView"];
se = {<|"word" -> "beta", "first_seq" -> 2, "last_seq" -> 2|>,
      <|"word" -> "alpha", "first_seq" -> 1, "last_seq" -> 1|>};
assert["sortEntries alpha = word ASC", #["word"] & /@ sortEntries[se, alpha] === {"alpha", "beta"}];
assert["sortEntries recent = last_seq DESC", #["word"] & /@ sortEntries[se, recent] === {"beta", "alpha"}];
assert["sortEntries oldest = first_seq ASC", #["word"] & /@ sortEntries[se, oldest] === {"alpha", "beta"}];
assert["sortEntries unknown key -> word ASC (catch-all)",
  #["word"] & /@ sortEntries[se, bogus] === {"alpha", "beta"}];
fe = <|"word" -> "chat", "display_word" -> "Chat", "translation" -> "cat"|>;
assert["filterMatch none -> True", filterMatch[fe, none]];
assert["filterMatch substring on word", filterMatch[fe, filterBy["ch"]]];
assert["filterMatch case-insensitive on translation", filterMatch[fe, filterBy["CAT"]]];
assert["filterMatch no match -> False", filterMatch[fe, filterBy["xyz"]] === False];
assert["filterMatch empty needle -> True", filterMatch[fe, filterBy[""]]];
assert["applyFilter selects matching", applyFilter[{fe}, filterBy["zzz"]] === {}];
pls = practiseList[{fe}, none];
assert["practiseList shape {text,translation,ipa} from display_word",
  pls[[1]]["text"] === "Chat" && pls[[1]]["translation"] === "cat" && KeyExistsQ[pls[[1]], "ipa"]];
vv = vocabView[signedIn, {fe}, alpha, none, none];
assert["vocabView projection shape + count",
  vv["auth"] === signedIn && vv["count"] === 1 && vv["sort"] === alpha &&
  vv["filter"] === none && vv["editing"] === none && ListQ[vv["entries"]]];

(* ---------------- PracticeSession ----------------------------------- *)
sec["targetOf / correctPhonemesOf / audioOf / levenshtein / comparePhonemes / evaluate / sessionView"];
phr = {<|"text" -> "chat", "translation" -> "cat", "ipa" -> "ʃa"|>,
       <|"text" -> "chien", "translation" -> "dog", "ipa" -> "ʃjɛ̃"|>};
assert["targetOf pos 0 -> first phrase", targetOf[phr, 0] === phr[[1]]];
assert["targetOf pos 1 -> second phrase", targetOf[phr, 1] === phr[[2]]];
assert["targetOf out-of-range high -> empty target", targetOf[phr, 5]["text"] === ""];
assert["targetOf out-of-range low -> empty target", targetOf[phr, -1]["text"] === ""];
assert["correctPhonemesOf reads ipa", correctPhonemesOf[<|"ipa" -> "abc"|>] === "abc"];
assert["correctPhonemesOf missing ipa -> empty", correctPhonemesOf[<||>] === ""];
assert["audioOf recorded -> audio", audioOf[recorded["snd"]] === "snd"];
assert["audioOf other -> Missing", MissingQ[audioOf[none]]];
assert["levenshtein kitten/sitting = 3", levenshtein["kitten", "sitting"] === 3];
assert["levenshtein equal = 0", levenshtein["abc", "abc"] === 0];
assert["levenshtein empty = len other", levenshtein["", "abc"] === 3];
cpe = comparePhonemes["abc", "abc"];
assert["comparePhonemes exact: match, sim 1.0, dist 0",
  cpe["exact_match"] && cpe["similarity"] === 1.0 && cpe["distance"] === 0];
cp1 = comparePhonemes["abc", "abd"];
assert["comparePhonemes 1 edit: dist 1, sim 1.0-1/3 (Real), not exact",
  cp1["distance"] === 1 && cp1["similarity"] === 1.0 - 1/3 && cp1["exact_match"] === False];
cp0 = comparePhonemes["abc", ""];
assert["comparePhonemes empty correct: sim 0.0, dist = len(user)",
  cp0["similarity"] === 0.0 && cp0["distance"] === 3];
ev = evaluate[<|"ipa" -> "abd"|>, recorded["x"]];   (* recognise->"abc" vs "abd" *)
assert["evaluate composes oracle+compare (dist 1)", ev["distance"] === 1];
sv = sessionView[phr, 1, recorded["x"], scored[<|"distance" -> 1|>]];
assert["sessionView total/pos/item/hasRecording/score",
  sv["total"] === 2 && sv["pos"] === 1 && sv["item"] === phr[[2]] &&
  sv["hasRecording"] === True && sv["score"] === <|"distance" -> 1|>];
assert["sessionView no recording / no score",
  sessionView[phr, 0, none, none]["hasRecording"] === False &&
  sessionView[phr, 0, none, none]["score"] === None];
assert["sessionView empty phrases -> item None", sessionView[{}, 0, none, none]["item"] === None];

Print[hr];
Print[ToString[n], " assertions \[LongDash] ", ok[allOk]];
Print[hr];
If[!allOk, Exit[1]];
