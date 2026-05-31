# function-recovery.md
## Recovering the stubbed value-functions from the Python (VS + PS, first pass)

This document governs the **function-recovery pass** that SPEC-RECOVERY.md §4/§6
defers to "later": the UI-first recovery left every value-transformation as a
named stub with no body; here those bodies are recovered **from the Python**,
mechanically, never invented. It covers the first two components — VocabStore
(VS) and PracticeSession (PS).

It is the companion to `vocabstore-recovery.md` / `practice-session-recovery.md`
(which recovered the *interaction* structure). Read it alongside METHODOLOGY.md
(the L1 agent model) and SPEC-RECOVERY.md §4 ("what stubbed means precisely").

---

## 1. Why this pass is safe — and where it stops being mechanical

SPEC-RECOVERY §6 calls the function pass "the safe, mechanical part" because the
pure logic is framework-independent and survived intact in the Python. That is
true **only for the pure fragment**. The Python functions are written against
MySQL and external services, so each stub is a mix of:

- **pure data transformation** over the in-memory domain state (`entries`,
  `phrases`) — recoverable, total, deterministic; and
- **IO**: DB round-trips, the wall clock, autoincrement ids, the translation
  LLM, espeak, and audio→phoneme recognition.

The DB itself is already discarded (SPEC-RECOVERY §1: persistence is framework
bookkeeping; the domain state is the in-memory list). What remains to decide is
the *other* IO. The methodology forces the answer: in the L1 model **data
crosses only at ports** (METHODOLOGY, "Agent Model"). An external service call
is therefore not part of a state-transformation function — it is a
synchronisation. So the recovery rule is:

> **Recover the pure core as a total function; quarantine every residual side
> effect behind a named, uninterpreted oracle the function is parametric in.**

Inventing a body for the oracle would re-import the contamination the project
exists to remove (and violate SPEC-RECOVERY §4 "must not be invented"). Leaving
it as a named stub *records the recovered fact* that the operation is IO-bound.

### The oracles (the IO boundary, kept as stubs)
| oracle | meaning | source |
|---|---|---|
| `vsNow[]` | capture wall-clock | `vocab.py:142` `datetime.now` |
| `enrichOracle[word]` | translation + IPA enrichment | `vocab.py:70` `_enrich` (LLM + espeak) |
| `recognisePhonemes[audio]` | ASR: audio → phoneme string | the speech-recognition step feeding `compare_phonemes` |

`vsNewId[entries]` is a borderline case: the real id is a DB autoincrement (IO),
but its *only* semantic requirement is uniqueness, so it is modelled
**deterministically** as `max(existing ids)+1` — pure and testable. The store
assigns the real id at L3; nothing in L1 depends on its value, only its
freshness.

---

## 2. Provenance table (each stub ← Python, with the split)

| stub (in `*Recovered.wl`) | Python source | pure core recovered | oracle / IO |
|---|---|---|---|
| `addEntry[entries,w]` | `capture_vocab_entry` `vocab.py:106` | upsert by lookup key: dedup, `times_seen+1`, COALESCE fill-don't-overwrite, else append | `enrichOracle` (skipped — `enrich=False` path), `vsNow`, `vsNewId` |
| `deleteFrom[entries,id]` | `delete_vocab_entry:301` | delete by id | — |
| `updateNotesIn[entries,idn]` | `update_vocab_notes:314` | set `notes` on id | — |
| `updateEntry[entries,editingRow[id],fields]` | `update_vocab_entry:343` | reject non-editable keys; `display_word` must preserve lookup key; delta-merge | — |
| `autofillIn[entries,id]` | `autofill_vocab_entry:411` | fill **only** empty translation/ipa | `enrichOracle` |
| `importInto[entries,f]` | `import_from_file_contents:545`, `_parse_import_line:453`, `parse_import_header:486` | header check, pipe-parse, fold `addEntry`, line-limit/target abort | enrich (as addEntry) |
| `exportCsv[entries]` | `_render_export_csv` `vocabulary_tab.py:222` | exact 13-column CSV projection | — |
| `practiseList[entries,filter]` | `vocab_as_practice_phrases:644` | filter+shape `{text,translation,ipa}` | full search grammar (`vocab_search.py`) deferred |
| `vocabView[…]` | `list_vocab:195` | sort+filter projection + mode | — |
| `targetOf[phrases,pos]` | phrase queue / `ipa` field | `phrases[[pos+1]]` (0-based) | — |
| `evaluate[target,rec]` | `compare_phonemes_edit_distance` `comparison.py:83` | Levenshtein → `{exact_match,similarity,distance}`, `similarity = 1-dist/maxlen` | `recognisePhonemes` |
| `sessionView[…]` | practice pane render | current item + pos + rec/score | — |

---

## 3. Data representation (fixed from the schema, not invented)

An `entry` is an `Association` whose keys are the `vocab_entries` columns the
domain touches, traceable to `list_vocab`'s `SELECT *` and `_render_export_csv`'s
column list: `"id" "word"(lookup key) "display_word" "translation" "ipa"
"source_name" "url" "context_before|line|after" "times_seen"
"first_seen_at" "last_seen_at" "notes"`. `entries` is a `List[entry]`. `Null`
encodes a Python NULL column. A practice `phrase` is `<|"text","translation",
"ipa"|>` — exactly `vocab_as_practice_phrases`'s output, which is why
`practiseList` (VS) directly produces a PS `phrases` queue: that is the `pLoad`
relay made concrete.

### Documented abstractions (where the pure model is honestly weaker)
- **Time.** `first_seen_at`/`last_seen_at` are `vsNow[]` (opaque). The `recent`/
  `oldest` sorts therefore fall back to insertion order (newest-last) rather
  than a real clock comparison; `alpha` is fully faithful. Recorded here, not
  silently dropped (SPEC-RECOVERY §1).
- **Search.** `practiseList`/`vocabView` filtering implements only the default
  branch (plain text = substring on word OR translation). The `vocab_search`
  mini-language is a separate module and a separate recovery task.

---

## 4. Additivity (don't overwrite — refine and keep the refinement)

The recovered *agent* files are untouched. The bodies live in **new** files —
`VocabStoreFunctions.wl`, `PracticeSessionFunctions.wl` — loaded *after* the
recovered agents (see `MiolingoSpec.wl`), attaching downvalues to symbols that
were previously uninterpreted stubs. Removing the two `Get` lines returns the
spec to its fully-stubbed state. The interaction structure remains the source of
truth; this pass only gives the value-functions denotations.

---

## 5. Verification

`spec/tests/functions_test.wls` checks the recovered cores against
behaviour stated in the Python docstrings (not against the running DB):
dedup bumps `times_seen`; invalid (multi-word) capture is a no-op; `updateEntry`
rejects a key-changing `display_word` but accepts a casing fix; `exportCsv`
emits the exact header; `practiseList` shapes + filters; and
`comparePhonemes`/`levenshtein` reproduce the stated `similarity = 1-dist/maxlen`
identity and a known edit distance. Oracles are exercised by stubbing them with
a test value (e.g. `recognisePhonemes`), demonstrating the parametricity.
