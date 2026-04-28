# Plan: IPA Learning Pedagogy Redesign

## Context

Minimal pairs feature now works correctly (genuine minimal pairs detected), but several pedagogical issues surfaced:

1. **Cold start problem**: New users have empty vocabulary → no minimal pairs available
2. **Dual learning goal**: Teaching target language pronunciation AND IPA literacy simultaneously
3. **Learner background variation**: English→Portuguese needs different IPA symbols than Spanish→Portuguese
4. **Inconsistent IPA emphasis**: Currently shown in results but not taught systematically
5. **Progressive disclosure needed**: Can't introduce all IPA symbols at once

## Current State

**Vocabulary Sources:**
- **Personal vocabulary database EXISTS** — `vocab_entries` table with user_id, language_code, source_language_code, word, ipa, translation, context, times_seen
- Minimal pairs CAN be generated from personal vocabulary (integration already exists)
- But: practiced phrases saved to `practice_history`, NOT auto-captured to vocabulary
- Also available: Built-in library phrase/word lists in `language_materials/<lang>/`, user uploads
- **Gap:** Vocabulary must be manually added via Vocabulary tab; new users start empty → no minimal pairs

**IPA Exposure Points:**
- Every practice result (eSpeak IPA for target + user)
- IPA quick reference tooltip (§4.2 implemented)
- Color-coded diff highlighting (§4.2.3 implemented)
- But **NOT** taught as a progressive learning path

**User Journey:**
1. New user → loads phrase list from library or upload
2. Practices phrases → results saved to database (practice_history)
3. Minimal pairs → generated on-demand from currently loaded list
4. Next session → starts fresh (no accumulated vocabulary)

## Recommended Approach

### Option 1: Starter Vocabulary Packs (Immediate, Low-Complexity)

**What:**
- Pre-curated "IPA Starter" word lists (20-30 words) for each language pair
- Designed specifically for minimal pair generation and IPA introduction
- Auto-loaded for new users OR offered as explicit "IPA Learning Mode"

**Why:**
- Solves cold start immediately
- Controls which IPA symbols are introduced (progressive disclosure)
- Language-pair aware (EN→PT starter differs from ES→PT starter)
- No database schema changes
- Reuses existing phrase list infrastructure

**Implementation:**
1. Create `language_materials/<lang>/ipa-starters/` directory
2. Per source language: `en-starter.txt`, `es-starter.txt`, etc.
3. Each file: 20-30 words chosen for:
   - High minimal pair potential (deliberate phoneme contrasts)
   - Core IPA symbols for that language pair
   - Common, practical vocabulary
4. Quick Practice: Add "IPA Learning Mode" toggle
   - When enabled: loads appropriate starter pack
   - Shows IPA primer link prominently
   - Emphasizes minimal pairs section
5. Minimal pairs: Falls back to starter if loaded list < 15 items

**Examples:**
```
# language_materials/pt/ipa-starters/en-starter.txt
# Portuguese IPA Starter for English speakers
# Focus: Nasal vowels, ɾ/ʁ distinction, open/closed vowels

# Nasal vowel contrasts
pão | bread | [pˈɐ̃w̃]
pau | stick | [pˈaw]
bem | well | [bˈeɪ̃]
belo | beautiful | [bˈɛlʊ]

# R contrasts (major challenge for EN speakers)
caro | expensive | [kˈaɾʊ]
carro | car | [kˈaʁʊ]
[... continue to 30 words]
```

### Option 2: Integration with Existing Personal Vocabulary System (ALREADY IMPLEMENTED!)

**What exists:**
- ✅ `vocab_entries` table: (vocab_id, user_id, language_code, **source_language_code**, word, display_word, translation, ipa, context fields, times_seen, first_seen_at, last_seen_at, notes, url)
- ✅ `src/vocab.py`: capture_vocab_entry(), get_user_vocab_list(), update functions
- ✅ `src/ui/vocabulary_tab.py`: Full vocabulary management UI
- ✅ Minimal pairs already use vocabulary: `quick_practice_tab.py` line 226 loads from vocab
- ✅ **Language-pair awareness built-in**: `source_language_code` field distinguishes EN→PT from ES→PT vocab
- ✅ IPA already stored per entry (can be enriched on capture via eSpeak)

**Current cold-start problem:**
- New user → empty `vocab_entries` → minimal pairs can't generate
- User practices phrases → words saved to `practice_history` but NOT auto-captured to vocabulary
- Vocabulary grows manually (user must explicitly add words via Vocabulary tab)

**Clean integration with Starter Packs (Option 1):**

**Approach A: Seed starter as vocabulary entries (Recommended)**
1. When user enables "IPA Learning Mode" for first time:
   - Detect empty/small vocabulary (< 15 entries)
   - Offer: "📚 Would you like to add 25 starter words to your vocabulary?"
   - On accept: Bulk-insert starter pack words into `vocab_entries`
     - Set `source_name = "IPA Starter Pack (EN→PT)"` 
     - Mark with special `source_language_code` for tracking
     - Include pre-generated IPA and translations
2. After insertion: vocabulary persists, minimal pairs work immediately
3. User can review/edit/delete entries via existing Vocabulary tab

**Approach B: Temporary practice mode (Lighter weight)**
1. "IPA Learning Mode" loads starter as temporary phrase list (current behavior)
2. Add checkbox: "☑️ Save these words to my vocabulary"
3. On practice completion: optionally bulk-capture to `vocab_entries`
4. No UI changes needed beyond checkbox

**Recommendation: Approach A** 
- More pedagogically sound (starter becomes foundation vocabulary)
- Reuses existing vocabulary infrastructure
- No new UI surfaces (just a one-time prompt)
- Vocabulary tab already handles viewing/editing/deleting

### Option 3: Explicit IPA Learning Path (Future Consideration)

**What:**
- Separate "Learn IPA" mode/tab alongside Quick Practice
- Structured curriculum: 5-7 lessons introducing symbol groups
- Each lesson: explanation + targeted minimal pairs + practice
- Progress tracking (which symbols mastered)

**Why:**
- Separates pronunciation practice from IPA literacy
- Users can choose: learn IPA explicitly OR ignore it and practice pronunciation
- Progressive disclosure built into lesson structure
- Language-pair aware lessons

**Structure:**
```
Lesson 1 (PT): Nasal Vowels (ɐ̃ ẽ ĩ õ ũ)
  - Brief explanation
  - 5 minimal pairs focusing on oral/nasal contrast
  - Practice session
  - Quiz: "Which word has a nasal vowel?"

Lesson 2 (PT): Open/Closed Mid Vowels (ɛ/e, ɔ/o)
  - Explanation + mouth diagrams
  - 5 minimal pairs: avô/avó, pêlo/pelo
  - Practice session
  
[... continue for 5-7 lessons]
```

**Branching by source language:**
```
EN→PT: Focus on nasals, R sounds, vowel openness
ES→PT: Focus on vowel length, stress, subtle contrasts (ES already has similar phones)
FR→PT: Minimal — many overlapping symbols
```

**Trade-offs:**
- **Content burden:** 7 lessons × 7 languages = 49 lessons to author
- **Scope creep:** Takes app far from core pronunciation practice
- **Competition:** Existing IPA courses (University of Victoria, Interactive IPA, etc.) may do this better
- **UI bloat:** App already crowded, adding full lesson infrastructure is heavy

**Recommendation:** Preserve as future path, but likely better served by linking to external IPA courses while keeping Miolingo focused on pronunciation practice with IPA as a supporting tool (via starter packs + tooltips + minimal pairs)

## Immediate Action Plan (Option 1 + groundwork for Option 2)

### Phase 1: IPA Starter Packs (This PR/Next PR)

**Steps:**
1. Create `src/ipa/starter_packs.py`:
   - `get_starter_pack(lang_code, source_lang='en')` → returns word list
   - Embedded or loaded from `language_materials/<lang>/ipa-starters/`
2. Create starter pack content for Portuguese (EN→PT):
   - 30 words with high minimal pair density
   - Cover nasal vowels, R contrasts, open/closed vowels
   - Include translations + IPA
3. Modify `src/ui/quick_practice_tab.py`:
   - Add "🎓 IPA Learning Mode" checkbox in materials section
   - When enabled + loaded list < 20 items → auto-load starter
   - Show prominent link to IPA primer
   - Highlight minimal pairs section
4. Update minimal pairs generation:
   - If loaded list < 15 items → suggest loading starter pack
   - Show message: "📚 Load IPA Starter Pack for better minimal pair practice"

**Verification:**
- New user enables IPA Learning Mode → gets 30-word starter
- Minimal pairs generated from starter → quality pairs
- Primer link visible and clickable
- Can still use free/guided mode normally
Vocabulary Seeding Integration (Follow-Up PR - Optional)

**Implementation (if using Approach A from Option 2):**
1. Detect cold start: `vocab.get_user_vocab_list(user_id, language_code)` returns < 15 entries
2. On first "IPA Learning Mode" enable → show prompt:
   ```
   📚 Your vocabulary is empty. Add 25 starter words for better minimal pair practice?
   [Load Starter Pack] [Skip]
   ```
3. On accept: Bulk-insert starter pack to `vocab_entries`:
   ```python
   from vocab import capture_vocab_entry
   for word_entry in starter_pack:
       capture_vocab_entry(
           user_id=user_id,
           language=language,
           word=word_entry['text'],
           translation=word_entry['translation'],
           ipa=word_entry['ipa'],
           source_name="IPA Starter Pack (EN→PT)",
           source_language_code=source_lang_code,
           enrich=False  # Already enriched
       )
   ```
4. Minimal pairs now use persistent vocabulary automatically

**Verification:**
- New user enables IPA mode → prompted to seed vocabulary
- Accepts → 25 words inserted to `vocab_entries`
- Minimal pairs generated from vocabulary
- Vocabulary persists across sessions
- User can view/edit/delete via existing Vocabulary tabcab
- Works across sessions (vocabulary persists)

### Phase 3: IPA Learning Path (Future, Separate Feature)

**Deferred to post-MVP.** Requires:
- Content authoring (7 lessons × 7 languages = 49 lessons)
- New UI tab/section
- Progress tracking schema
- Quiz/assessment mechanics

## Decisions & Trade-offs

**Decision 1: Start with Starter Packs (Option 1)**
- **Why:** Immediate impact, low complexity, no schema changes
- **Trade-off:** Not personalized to user, but solves cold start
Integrate with Existing Vocabulary System (Option 2)**
- **Why:** Infrastructure already exists, just needs bootstrap mechanism
- **Trade-off:** Must decide: seed vocabulary (persistent) vs temporary practice mode (ephemeral) UX
- **Trade-off:** Requires schema change, migration effort


**Decision 6: Minimal UI bloat**
- **Why:** App already crowded (Quick Practice materials section, sidebar settings, etc.)
- **Approach:** Reuse existing Vocabulary tab for viewing/managing starter words
- **New UI:** Only one-time seed prompt in Quick Practice, no new tabs/panels
**Decision 3: Defer Full Learning Path (Option 3)**
- **Why:** Content authoring burden too high for MVP
- **Trade-off:** IPA remains incidental, not taught systematically
- **Mitigation:** Starter packs + primer provide scaffolding

**Decision 4: Language-pair awareness in starter packs**
- **Why:** Different source languages need different symbol introductions
- **Implementation:** Filename convention: `{source_lang}-starter.txt`
- **Default:** If source lang unknown → use `en-starter.txt` (widest audience)

**Decision 5: Keep minimal pairs optional, not mandatory**
- **Why:** Some users want pronunciation practice, not IPA literacy
- **Implementation:** Collapsible section, not auto-expanded
- **UX:** Clearly labeled "For IPA Learners" or similar

## Further Considerations

**1. Source language detection**
- **How do we know user's native language?**
- Options:
  - User profile field (requires auth + settings update)
  - Infer from browser locale (unreliable)
  - Explicit selector in IPA Learning Mode
  - **Recommendation:** Explicit selector when enabling IPA mode

**2. Starter pack size trade-off**
- Too small (10-15 words) → insufficient minimal pairs
- Too large (50+ words) → overwhelming for beginners
- **Recommendation:** 25-30 words (Goldilocks zone)

**3. Multi-word phrases in vocabulary table**
- Should we tokenize phrases into individual words?
- **Recommendation:** Yes, for vocabulary building
- **Implementation:** Simple whitespace split initially, improve later

**4. IPA primer integration**
- Currently separate markdown file
- Could be rendered in-app as modal or sidebar
- **Recommendation:** Start with link, enhance to in-app later

**5. Minimal pairs quality threshold**
- Currently accepts any 1-phoneme difference
- Could filter for "pedagogically useful" contrasts
- **Recommendation:** Defer — current implementation good enough

**6. Progress tracking for IPA learning**
- Which symbols has user mastered?
- Needs quiz/assessment mechanism
- **Recommendation:** Defer to Phase 3 (Learning Path)
