(* ::Package:: *)

(* =====================================================================
   miolingo / L1 — VocabStore value-functions, RECOVERED (function pass)
   ---------------------------------------------------------------------
   The function-recovery pass for VS: the stubbed value-functions named in
   VocabStoreRecovered.wl get real bodies, RECOVERED from src/vocab.py (NOT
   invented). See spec/docs/function-recovery.md for the IO-extraction
   process (pure core vs. quarantined oracle) and the provenance table.

   This file is ADDITIVE: it only attaches downvalues to symbols that were
   uninterpreted stubs. It does NOT modify VocabStoreRecovered.wl. Load it
   AFTER the recovered agent (see MiolingoSpec.wl).

   DATA REPRESENTATION (fixed from the vocab_entries schema, not invented;
   cf. list_vocab SELECT * and _render_export_csv column list):
     entry   : Association with keys
       "id" "word"(lookup key) "display_word" "translation" "ipa"
       "source_name" "url" "context_before" "context_line" "context_after"
       "times_seen" "first_seen_at" "last_seen_at" "notes"
     entries : List[entry]
   Null marks an absent column (Python NULL). vsNow[] / vsNewId[...] below
   isolate the two impurities (wall-clock, autoincrement id).
   ===================================================================== *)


(* --- oracles / impurity isolation -------------------------------------
   vsNow[]   : wall-clock at capture (datetime.now, vocab.py:142). Left
               uninterpreted: timestamps are IO, used only as opaque CSV
               fillers here. (Comparable-time sorts noted below.)
   vsNewId   : DB autoincrement vocab_id. Modelled DETERMINISTICALLY from
               the current list (max existing id + 1) so the pure model is
               testable; the real id is assigned by the store at L3. *)
vsNewId[entries_List] := 1 + Max[Append[Cases[entries, e_ /; KeyExistsQ[e, "id"] :> e["id"]], 0]];

emptyToNull[x_]   := If[x === "" || x === Null || MissingQ[x], Null, x];
coalesce[old_, new_] := If[old === Null || old === "" || MissingQ[old], emptyToNull[new], old];


(* --- _normalise + validate_single_word (vocab.py:31, 50) --------------
   Strip surrounding (never inner) punctuation; display keeps case, key is
   lowercased. validateWord returns {display, key} or $Failed (empty /
   punct-only / contains whitespace / >100 chars). *)
(* _TRIM_PUNCT (vocab.py:28): ASCII + curly quotes, guillemets, dashes,
   ellipsis. Built from code points to avoid longname ambiguity:
   8220 8221 = curly double quotes; 8216 8217 = curly single; 171 187 =
   guillemets; 8212 8211 = em/en dash; 8230 = ellipsis. *)
vsTrimChars = Join[Characters[".,;:!?\"'-"],
  FromCharacterCode /@ {8220, 8221, 8216, 8217, 171, 187, 8212, 8211, 8230}];

normalise[word_String] := Module[{trimmed},
  trimmed = StringTrim[word];
  trimmed = StringReplace[trimmed,
    {StartOfString ~~ (Alternatives @@ vsTrimChars) .. -> "",
     (Alternatives @@ vsTrimChars) .. ~~ EndOfString -> ""}];
  {trimmed, ToLowerCase[trimmed]}];

validateWord[word_String] := Module[{display, key},
  If[StringTrim[word] === "", Return[$Failed]];
  {display, key} = normalise[word];
  Which[
    key === "",                          $Failed,   (* only punctuation *)
    StringContainsQ[key, Whitespace],    $Failed,   (* not single word  *)
    StringLength[key] > 100,             $Failed,   (* too long         *)
    True,                                {display, key}]];
validateWord[_] := $Failed;


(* --- addEntry[entries, w] : capture_vocab_entry pure core (vocab.py:106)
   w is the captured payload (Association with at least "word"; a bare
   String is lifted to <|"word"->w|>). UPSERT by lookup key:
     - invalid word        -> entries unchanged (ok:False path)
     - new key             -> append fresh entry (times_seen 1)
     - existing key        -> bump times_seen, fill-but-never-overwrite
                              (the SQL ON DUPLICATE KEY COALESCE clause)
   enrich (translation/IPA via _enrich) is IO and is NOT performed here —
   it is the enrich=False path the hermetic tests use. Any translation/ipa
   already present on w (e.g. from an import line) is carried in. *)
addEntry[entries_List, w_] := Module[
  {a = If[AssociationQ[w], w, <|"word" -> w|>], v, display, key, pos},
  v = validateWord[Lookup[a, "word", ""]];
  If[v === $Failed, Return[entries]];
  {display, key} = v;
  pos = FirstPosition[entries, e_ /; AssociationQ[e] && e["word"] === key,
                      None, {1}, Heads -> False];
  If[pos === None,
    Append[entries, <|
      "id" -> vsNewId[entries], "word" -> key, "display_word" -> display,
      "translation" -> emptyToNull[Lookup[a, "translation", Null]],
      "ipa" -> emptyToNull[Lookup[a, "ipa", Null]],
      "source_name" -> emptyToNull[Lookup[a, "source_name", Null]],
      "url" -> emptyToNull[Lookup[a, "url", Null]],
      "context_before" -> emptyToNull[Lookup[a, "context_before", Null]],
      "context_line" -> emptyToNull[Lookup[a, "context_line", Null]],
      "context_after" -> emptyToNull[Lookup[a, "context_after", Null]],
      "times_seen" -> 1, "first_seen_at" -> vsNow[], "last_seen_at" -> vsNow[],
      "notes" -> Null|>],
    MapAt[
      Function[e, Module[{m = e},
        m["times_seen"]    = m["times_seen"] + 1;
        m["last_seen_at"]  = vsNow[];
        Scan[(m[#] = coalesce[m[#], Lookup[a, #, Null]]) &,
          {"translation", "ipa", "source_name", "url",
           "context_before", "context_line", "context_after"}];
        m]],
      entries, pos]]];


(* --- deleteFrom[entries, id] : delete_vocab_entry (vocab.py:301) ------- *)
deleteFrom[entries_List, id_] := DeleteCases[entries, e_ /; e["id"] === id];


(* --- updateNotesIn[entries, idn] : update_vocab_notes (vocab.py:314).
   idn carries both target and value: Association <|"id"->_, "notes"->_|>. *)
updateNotesIn[entries_List, idn_Association] :=
  Replace[entries, e_ /; e["id"] === idn["id"] :>
    Append[e, "notes" -> emptyToNull[idn["notes"]]], {1}];


(* --- updateEntry[entries, editingRow[id], fields] : update_vocab_entry
   (vocab.py:343). Rejects keys outside _EDITABLE_FIELDS; display_word must
   round-trip to the SAME lookup key (casing fixes allowed, key change is
   not); empty -> Null; delta-merge. On any rejection the list is returned
   unchanged (the ValueError path makes no DB write). *)
vsEditableFields = {"display_word", "translation", "ipa", "source_name",
  "url", "context_before", "context_line", "context_after"};

updateEntry[entries_List, editingRow[id_], fields_Association] := Module[
  {pos, row, bad},
  bad = Complement[Keys[fields], vsEditableFields];
  If[bad =!= {}, Return[entries]];                       (* unknown field   *)
  pos = FirstPosition[entries, e_ /; e["id"] === id, None, {1}, Heads -> False];
  If[pos === None, Return[entries]];                     (* row not present *)
  row = Extract[entries, pos];
  If[KeyExistsQ[fields, "display_word"] &&
       Last[normalise[ToString[fields["display_word"]]]] =!= row["word"],
    Return[entries]];                                    (* key change -> reject *)
  MapAt[
    Function[e, Module[{m = e},
      KeyValueMap[(m[#1] = emptyToNull[#2]) &, fields]; m]],
    entries, pos]];
(* tolerate a bare id (no editingRow wrapper) for direct calls/tests *)
updateEntry[entries_List, id : Except[_editingRow], fields_Association] :=
  updateEntry[entries, editingRow[id], fields];


(* --- autofillIn[entries, id] : autofill_vocab_entry (vocab.py:411).
   Fills ONLY empty translation/ipa, never overwrites. The enrichment is
   the whole point of the function and is IO: it is the oracle
   enrichOracle[word] -> <|"translation"->_, "ipa"->_|> (uninterpreted;
   the spec is parametric in it). Existing-value fields are left intact. *)
autofillIn[entries_List, id_] := Module[{pos, row, fill, m},
  pos = FirstPosition[entries, e_ /; e["id"] === id, None, {1}, Heads -> False];
  If[pos === None, Return[entries]];
  row = Extract[entries, pos];
  fill = enrichOracle[row["display_word"]];
  If[!AssociationQ[fill], Return[entries]];
  MapAt[Function[e, Module[{n = e},
      If[(n["translation"] === Null || n["translation"] === "") &&
         emptyToNull[Lookup[fill, "translation", Null]] =!= Null,
        n["translation"] = fill["translation"]];
      If[(n["ipa"] === Null || n["ipa"] === "") &&
         emptyToNull[Lookup[fill, "ipa", Null]] =!= Null,
        n["ipa"] = fill["ipa"]];
      n]], entries, pos]];


(* --- import: _parse_import_line / parse_import_header / import_from_file_contents
   (vocab.py:453, 486, 545). f = <|"contents"->_String, "expectedTarget"->_|>.
   Pipe-delimited `word|translation|ipa|source|url`; IPA may be []-wrapped.
   Header (src,tgt) is mandatory; target mismatch or >250 data lines abort
   with NO capture (returns entries unchanged). Each valid row folds through
   addEntry (so dedup/bump apply); invalid single-word rows are skipped. *)
parseImportLine[line_String] := Module[{parts, word, get},
  parts = StringTrim /@ StringSplit[line, "|", All];
  word = First[parts, ""];
  If[word === "", Return[Missing[]]];
  get[i_] := If[Length[parts] >= i, parts[[i]], ""];
  Module[{ipa = get[3]},
    If[StringLength[ipa] >= 2 && StringStartsQ[ipa, "["] && StringEndsQ[ipa, "]"],
      ipa = StringTake[ipa, {2, -2}]];
    <|"word" -> word, "translation" -> get[2], "ipa" -> ipa,
      "source_name" -> get[4], "url" -> get[5]|>]];

(* (src, tgt) header, optionally #-prefixed; returns {src,tgt} lowercased *)
parseImportHeader[contents_String] := Module[{out = $Failed},
  Do[Module[{line = StringTrim[raw], m},
      If[line === "", Continue[]];
      m = StringCases[line,
        "(" ~~ s : (Except["," | ")"] ..) ~~ "," ~~ Whitespace ... ~~
          t : (Except["," | ")"] ..) ~~ ")" :>
          {ToLowerCase[StringTrim[s]], ToLowerCase[StringTrim[t]]}];
      If[m =!= {}, out = First[m]; Break[]];
      If[StringStartsQ[line, "#"], Continue[]];
      Break[]                                       (* first data line -> reject *)
    ], {raw, StringSplit[contents, "\n"]}];
  out];

isImportDataLine[raw_String] := Module[{line = StringTrim[raw]},
  line =!= "" && !StringStartsQ[line, "#"] && !StringStartsQ[line, "("]];

importLineLimit = 250;

importInto[entries_List, f_Association] := Module[{contents, hdr, dataLines},
  contents = Lookup[f, "contents", ""];
  hdr = parseImportHeader[contents];
  If[hdr === $Failed, Return[entries]];                            (* no header *)
  If[KeyExistsQ[f, "expectedTarget"] && Last[hdr] =!= ToLowerCase[ToString[f["expectedTarget"]]],
    Return[entries]];                                              (* target mismatch *)
  dataLines = Select[StringSplit[contents, "\n"], isImportDataLine];
  If[Length[dataLines] > importLineLimit, Return[entries]];        (* too many *)
  Fold[
    Function[{acc, raw}, Module[{p = parseImportLine[StringTrim[raw]]},
      If[MissingQ[p], acc, addEntry[acc, p]]]],
    entries, dataLines]];


(* --- exportCsv[entries] : _render_export_csv (vocabulary_tab.py:222).
   The exact 13-column header + per-row order. Pure projection -> CSV string. *)
exportCsvHeader = {"word", "translation", "ipa", "source_language", "source",
  "context_before", "context_line", "context_after",
  "times_seen", "first_seen_at", "last_seen_at", "notes", "url"};

csvCell[x_] := Which[x === Null || MissingQ[x], "", True, ToString[x]];
(* RFC-4180 / csv.writer minimal quoting: quote only when the cell contains
   a comma, quote, or newline; double any embedded quote. (csv.writer's
   default \r\n line terminator is a rendering detail; we join with \n.) *)
csvField[x_] := Module[{s = csvCell[x]},
  If[StringContainsQ[s, "," | "\"" | "\n" | "\r"],
    "\"" <> StringReplace[s, "\"" -> "\"\""] <> "\"", s]];
exportCsvRow[cells_List] := StringRiffle[csvField /@ cells, ","];
exportCsv[entries_List] := StringRiffle[
  Prepend[
    (Function[r, exportCsvRow[{
       Lookup[r, "display_word", Lookup[r, "word", ""]],
       r["translation"], r["ipa"],
       Lookup[r, "source_language_code", Null], r["source_name"],
       r["context_before"], r["context_line"], r["context_after"],
       Lookup[r, "times_seen", 1], r["first_seen_at"], r["last_seen_at"],
       r["notes"], r["url"]}]]) /@ entries,
    exportCsvRow[exportCsvHeader]],
  "\n"];


(* --- sort + filter (list_vocab order map + search; vocab.py:195) ------
   alpha is fully recovered (by lookup key). recent/oldest order by
   last_seen_at / first_seen_at, which are the wall-clock oracle vsNow[];
   absent a comparable clock in the pure model they fall back to insertion
   order (newest-last), documented as the clock-IO abstraction. *)
sortEntries[entries_List, "alpha"]  := SortBy[entries, #["word"] &];
sortEntries[entries_List, "recent"] := Reverse[entries];
sortEntries[entries_List, "oldest"] := entries;
sortEntries[entries_List, _]        := SortBy[entries, #["word"] &];

(* filterMatch: the DEFAULT search branch (plain text = substring on word
   OR translation, lowercased). The full vocab_search mini-language grammar
   is its own module (src/vocab_search.py) and is deferred. *)
filterMatch[_, none] := True;
filterMatch[e_, filterBy[q_]] := Module[{needle = ToLowerCase[ToString[q]]},
  needle === "" ||
  StringContainsQ[ToLowerCase[ToString[Lookup[e, "display_word", e["word"]]]], needle] ||
  StringContainsQ[ToLowerCase[ToString[coalesce[e["translation"], ""]]], needle]];

applyFilter[entries_List, filter_] := Select[entries, filterMatch[#, filter] &];


(* --- practiseList[entries, filter] : vocab_as_practice_phrases (vocab.py:644).
   Filter then shape to the practice phrase interface {text, translation,
   ipa}. This list becomes a PracticeSession `phrases` queue (the pLoad /
   load_material payload). *)
practiseList[entries_List, filter_] :=
  (<|"text" -> Lookup[#, "display_word", #["word"]],
     "translation" -> coalesce[#["translation"], ""],
     "ipa" -> coalesce[#["ipa"], ""]|>) & /@ applyFilter[entries, filter];


(* --- vocabView[auth, entries, sort, filter, editing] : the read-only view
   projection (what list_vocab + the tab publish). A projection f, never raw
   state: emits a summary Association the skin renders. *)
vocabView[auth_, entries_, sort_, filter_, editing_] := <|
  "auth" -> auth,
  "count" -> Length[entries],
  "sort" -> sort,
  "filter" -> filter,
  "editing" -> editing,
  "entries" -> sortEntries[applyFilter[entries, filter], ToString[sort]]|>;
