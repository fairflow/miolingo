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
