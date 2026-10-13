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
