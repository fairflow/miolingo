# data

Extracted by `build_data.py` from Miolingo's `language_materials/` (parent
checkout `~/Software/working/miolingo`, branch `claude/weighted-phone-scorer`
at `ac88c35`; the `main` snapshot lacks `unified/`). Nothing is taken from
`data/user-data`. These are Miolingo's own tracked teaching materials.

* `en.json`, `fr.json`, `de.json`: `phrases` (48 each: 12 evenly spaced from
  each of `language_materials/<lang>/phrases/phrases-001, -003, -004, -005.txt`;
  `-002` is a placeholder), each with `text`, `gloss`, `gloss_language`
  (English for fr and de; French for en, as the English phrase files are
  paired with French), `source`, and `ipa` (computed here by `target_ipa`,
  not copied: the files' own IPA column is ignored). `vocabulary` (40 each,
  evenly spaced over `language_materials/fr/words/dictionary-complete.txt`,
  `de/words/dictionary-complete.txt`, and `en/words/dictionary1-4.txt`, whose
  glosses are Portuguese: `gloss_language` says so); words of 3+ letters only.
* `gloss.json`: lookup for `env.gloss`: normalised text -> {language: text}.
  Phrases: `language_materials/unified/phrases/common-phrases-001/003/004/005.json`
  (each phrase in en, fr, de, es, it, nl, pt). Words: French and German
  dictionaries above, with English glosses only.
* `cost_table.json`: written by `env.write_cost_table()`; see `env/tables.py`.
* **The data lint** (locus `docs/neolingo-test-design.md` 4E): `build_data.py` writes nothing when one fails, and
  `tests/check_data.py` runs the same checks on the committed files. D1: a practised text has no bracket, slash or digit.
  D2: every word of a practised text has a target (one per word, none empty, each sound a cost key, no symbol of the
  transcription lost by the cutter: `env.ipa.DROPPED`), a word listed in
  `ipa_exceptions.json` has the table's target, a stored target is the one `env.target_ipa` computes. D3: a rebuild
  only adds keys to `gloss.json`. D4 (15 October): a word written in capitals in a phrase (an abbreviation; espeak
  spells it in a phrase) has a target in `ipa_exceptions.json`, whose keys written with capitals match only the word
  written so ("PIN": en [pɪn], fr [pin], de [pɪn], "PIN-Code" [pɪnkoːt]). `build_data.py --out DIR` rebuilds into a
  scratch folder.

* `words_en.json`, `words_fr.json`, `words_de.json`, `gloss.json` (extended): made by `build_words.py` (run after `build_data.py`), from the same
  parent checkout and branch; plain text only, nothing from `data/user-data`. Each file is `[{name, lang, words, source}]`.
  - fr: the level files `language_materials/fr/words/words-001.txt` to `-004.txt` (levels A to D; 63, 60, 87, 90 words; a word appears in the first level it occurs in).
  - de: Miolingo has no German level files, so the levels are those of the phrase files `language_materials/de/phrases/phrases-001, -003, -004, -005.txt`:
    the words of each, new at that level, kept when `language_materials/de/words/dictionary-complete.txt` has them (66, 55, 89, 88 words; lower case, as the dictionary).
  - en: `language_materials/en/words/words-001.txt` to `-004.txt` (levels A to D; 22, 25, 24, 29 words), then 200 words spread evenly over
    `language_materials/en/words/dictionary-complete.txt` in alphabetical order, in four chunks of 50 (named by first and last word).
  - Words of one letter, and words with an apostrophe or a hyphen, are left out: the model's upload drops the piece after an apostrophe and turns a hyphen into a space ("e-mail" is stored as "e mail").
  - Meanings: Miolingo's English files are paired with PORTUGUESE, so English words carry `pt` meanings in `gloss.json` (own language `pt`; not a language
    the app offers) and French or German meanings only where the unified phrase files have the word as a one-word phrase (9 of 300). French and German words carry
    English meanings: the files' own column, and `language_materials/fr/words/dictionary-complete.txt` / `de/.../dictionary-complete.txt` (all 300 French and all 298 German).
    No reverse index (English word -> the French or German word whose English gloss it is) is made: it would give some wrong meanings.

## Meanings for added words: `meanings.json` (13 October 2026)

When a learner adds a word, the engine asks the host `fill(word, own, variant)`; `env.gloss` answers from `meanings.json`, then `gloss.json`.
`build_meanings.py` (reading `materials.py`) makes `meanings.json` (260 KiB; `{practised language: {normalised text: {own language: meaning}}}`,
en/fr/de both ways) and `meanings_inverted.json` (37 KiB, off by default). Same parent checkout and branch as above; nothing from `data/user-data`,
no database, no model, no machine translation. Run: `venv/bin/python neolingo/data/build_meanings.py [--survey]`.

Lookup: case-insensitive, punctuation as `env.gloss._key`; the exact form, then without one leading article, reflexive pronoun or "to"
(fr le la les l un une des du se s; de der die das den dem des ein eine einen einem einer eines sich; en the a an to). Several meanings in one source stay as
written ("hello / good day"). When sources disagree, the first of: level files, dictionaries, swift lexicon, phrasebook topics, phrasebook, phrase files,
story scenes, unified phrases, unified stories wins (the level files were chosen for the phrase lists: "cherche | look for", "bureau | desk"; the dictionaries
come from the story's context: "cherche | search", "cartes | maps"); the others are counted, not merged.

Survey of the translation material of the Miolingo checkout (entries; IPA = the source carries IPA; sample = 20 entries read):

| Source | Pair | Entries | IPA | Used | Quality (20-entry sample) |
|---|---|---|---|---|---|
| `fr/words/dictionary-complete.txt` | fr -> en | 1255 | yes | yes | right; one meaning per form, from the story's context ("cartes \| maps", "distributer"), not inflection-aware ("sa \| her") |
| `de/words/dictionary-complete.txt` | de -> en | 1399 | yes | yes | right, same limits; all lower case |
| `fr/words/words-001..004.txt` | fr -> en | 428 | yes | yes (first) | best: several senses ("santé \| health / cheers") |
| `fr/phrases`, `de/phrases`, `en/phrases` (4 files each) | fr, de -> en; en -> fr | 200 each | yes | yes | right (phrases, with register notes in brackets) |
| `*/phrasebook-topics`, `*/phrasebook_complete.json` | fr, de -> en; en -> fr | 103 each | yes (en: French's) | yes | right |
| `fr/story-scenes-json`, `de/story-scenes-json` | fr, de -> en | 501 each | yes | yes | right, a few cut-off fragments |
| `unified/phrases`, `unified/phrasebook` | every pair of en fr de (also es it nl pt) | 303 | yes | yes | right; the only source for fr <-> de |
| `unified/stories` | fr <-> en only | 501 | yes | fr <-> en | right for fr/en; the German line localises place names (Berlin for Paris), so not used with de |
| `en/words/dictionary-complete.txt`, `dictionary1-4`, `words-00N`, `words-pt/` | en -> pt | 905 | yes | no (pt is not offered) | right |
| `en/words-fr/`, `-de/`, `-es/`, `-it/`, `-nl/` | en -> fr, de ... | 905 each | yes | no | the meaning column is EMPTY (only IPA) |
| `es it nl pt` dictionaries, phrases, scenes, `dictionary_pt.csv`, `data/practice-sets` | -> en | 1100-1400 | yes | no | not offered pairs (practice sets and csv are Portuguese) |
| `scripts/language-generation/*translated.json` | fr -> en | 82 | yes | NO | English lines are misaligned with the French (not used) |
| `swift/.../lexicon.json` | fr -> en | 18 | no | yes | right |

Not in the material: any English -> French or English -> German word list (the `words-fr`, `words-de` files have no meanings), and any
French <-> German word list (only the 250 phrases and one-word phrases of `unified/`). `meanings.json` therefore holds: fr -> en 2006 texts,
de -> en 2122, en -> fr 754, en -> de 261, fr -> de 255, de -> fr 253 (words and phrases; most en entries are phrases).

`meanings_inverted.json`: the French and German dictionaries inverted where exact in the sense one headword <-> one English word, in both
directions (the English meaning is that of exactly one headword, which has exactly one meaning, both single words): 718 of 1188 distinct
meanings for French, 880 of 1176 for German. A sample of 30 for each is NOT all right: the dictionaries are not inflection-aware ("recommandez |
recommend", "festes | solid", "willst | want"), the German side is lower case ("tiere"), about one in four is a wrong form. So it is read only with
`NEOLINGO_INVERTED=1` (it lifts the 300 English words offered from 12 to 151 French and 162 German meanings).

IPA of the material is not used for scoring (target sounds come from espeak). `study_ipa.py` writes `var/study/ipa_material_vs_espeak.txt` (not
committed): 200 sampled dictionary entries per language, the sounds that differ. The material's IPA is itself espeak output (an English reading of
"enthousiasme" appears), 88-96% of the entries are sound for sound the same as `env.target_ipa`.
