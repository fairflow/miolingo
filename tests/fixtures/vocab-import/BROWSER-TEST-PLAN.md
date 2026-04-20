# Vocabulary Import — Browser Test Plan (Comet / Claude-in-Chrome)

Run against the preview app on port **8501** (or 8701).
Language must be set to **Portuguese** before starting.
Each test imports into a fresh vocab list — use a dedicated test account or
clear vocab between runs via the delete buttons (or direct DB truncation).

---

## Pre-flight

1. Open the app → sign in → set language to Portuguese (sidebar).
2. Navigate to **📚 My Vocabulary** tab.
3. Confirm vocab list is empty (or note any pre-existing words to subtract from counts).

---

## Test 01 — Words only, no pipes

**File:** `vocab-test-01-words-only.txt` (15 words, no pipes)

Steps:
1. Open "📥 Upload a dictionary file".
2. Uncheck "Auto-fetch missing translation + IPA" (import raw).
3. Upload `vocab-test-01-words-only.txt`.
4. Confirm caption: **"15 words to import"** (no time estimate because enrich=off).
5. Click **Import file**.

Expected result:
- ✅ "Imported — 15 new, 0 updated."
- In the entry list: 15 entries, each showing just the word (no translation, no IPA).
- Expand any entry — translation and IPA fields are blank.

---

## Test 02 — Full 5-field (all fields pre-filled)

**File:** `vocab-test-02-full-5-field.txt` (12 words, all 5 fields)

Steps:
1. Upload `vocab-test-02-full-5-field.txt`.
2. Leave "Auto-fetch" **checked** (verify enrichment does NOT re-fetch already-present fields).
3. Click **Import file**.

Expected result:
- ✅ "Imported — 12 new, 0 updated."
- Expand "Oi": translation = *Hello*, IPA = `ˈoɪ`, source = *pt-phrasebook*, clickable 🔗 Source link.
- Expand "Tchau": translation = *Goodbye*, IPA = `tʃˈaʊ`.
- Speed: import completes in < 5 s despite enrichment checkbox being on (files pre-enriched → no API calls).

---

## Test 03 — Skip translation (`||` in position 2)

**File:** `vocab-test-03-skip-translation.txt` (10 words, format `word || ipa | source`)

Steps:
1. Import `vocab-test-03-skip-translation.txt` (enrichment unchecked).

Expected result:
- ✅ 10 added.
- Expand any entry: translation is **blank**, IPA is set, source = *pt-phrasebook*.
- Entry summary line shows `\`ipa\`` but no italic translation.

---

## Test 04 — Skip IPA (`||` in position 3)

**File:** `vocab-test-04-skip-ipa.txt` (10 words, format `word | translation || source`)

Steps:
1. Import `vocab-test-04-skip-ipa.txt` (enrichment unchecked).

Expected result:
- ✅ 10 added.
- Expand any entry: translation is set, IPA is **blank**.
- No backtick IPA in the summary line.

---

## Test 05 — Word + source only (`|||`)

**File:** `vocab-test-05-word-source-only.txt` (10 words, format `word ||| source`)

Steps:
1. Import `vocab-test-05-word-source-only.txt` (enrichment unchecked).

Expected result:
- ✅ 10 added.
- Expand any entry: translation blank, IPA blank, source set from file.

---

## Test 06 — Mixed patterns + deliberate errors

**File:** `vocab-test-06-mixed.txt` (9 content lines, 2 of which are multi-word)

Steps:
1. Import `vocab-test-06-mixed.txt` (enrichment unchecked).

Expected result:
- ✅ "Imported — 7 new, 0 updated."
- ⚠️ "2 multi-word rows skipped: `bom dia`, `boa noite`"
- The 7 added words cover all patterns: word-only, full 5-field, ||ipa|src, word|||src, translation||src.

---

## Test 07 — Over the 250-word limit

**File:** `vocab-test-07-over-limit.txt` (251 words)

Steps:
1. Upload `vocab-test-07-over-limit.txt`.

Expected result:
- ❌ Error shown immediately after upload (before clicking Import):
  `"⚠️ File has 251 words — maximum is 250. Split into smaller files and import separately."`
- **Import file** button is **not visible** (blocked by limit).
- Nothing imported.

---

## Test 08 — Exactly at the limit (250 words)

**File:** `vocab-test-08-at-limit.txt` (250 words)

Steps:
1. Upload `vocab-test-08-at-limit.txt` (enrichment unchecked).
2. Confirm caption shows **"250 words to import"** (no error).
3. Click **Import file**.

Expected result:
- ✅ Import completes (≤ 250 added; some story-scene tokens may be multi-word and skipped — check warning).
- No limit error.

---

## Checklist summary

| # | File | Expected outcome | Pass/Fail |
|---|------|-----------------|-----------|
| 01 | words-only | 15 added, no translation/IPA | |
| 02 | full-5-field | 12 added, all fields correct, fast even with enrich on | |
| 03 | skip-translation | 10 added, translation blank, IPA set | |
| 04 | skip-ipa | 10 added, IPA blank, translation set | |
| 05 | word-source-only | 10 added, only word+source | |
| 06 | mixed | 7 added, 2 multi-word skipped | |
| 07 | over-limit | Upload shows error, import button hidden | |
| 08 | at-limit | 250 imported, no limit error | |
