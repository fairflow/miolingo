# Learn-IPA feature — design proposal (v0.1)

> **Audience:** Claude + humans continuing work. Matthew-facing overview:
> `docs/app-docs/IPA_PRIMER.md` (the user-visible primer shipped alongside
> the feature).
>
> **Status:** preliminary. Font-legibility fix landed; the rest is a
> proposal for review.

## 1. Why this exists

Miolingo was built around Matthew's desire to learn Brazilian Portuguese
pronunciation using IPA as a bridge. The app already:

- stores IPA per entry (`vocab_entries.ipa`, phrase file `[ipa]` column),
- renders it wherever a word or phrase is shown (Quick Practice, Story
  Reader, vocabulary views), and
- uses eSpeak **phonemes** (not IPA per se) for pronunciation scoring —
  so the IPA on screen is already an educational artefact, not a scoring
  input.

The piece missing is pedagogical scaffolding. Most users meeting Miolingo
for the first time have never read an IPA chart. Today the brackets just
sit there. We want to turn them into something a beginner can learn *from*
without adding a heavy new surface.

## 2. Design principles

1. **Tiny surface area.** One new help page/tab + a handful of tooltips.
   No new database tables. No new dependencies.
2. **Reuse what exists.** Phoneme extraction, the `format_ipa()` helper,
   the colour-diff in Practice tab, and `Portuguese-Grammar-IPA.md` in
   `language_materials/` are already doing most of the heavy lifting.
3. **Progressive exposure.** Teach a handful of symbols at a time, anchored
   in words the user is already practising. Full charts are reference,
   not onboarding.
4. **Opt-in depth.** The primer is one click away from Quick Practice, not
   in front of every learner on every screen.
5. **Language-pair aware.** What a Spanish speaker needs to learn to read
   BR Portuguese IPA is very different from what an English speaker needs.
   The primer branches by `source_lang → target_lang`.

## 3. What has already changed

- `src/scoring/phonemes.py :: format_ipa()` — default size bumped from
  `1.0em` to `1.2em`, weight from 400 to 500. Justification is in the
  docstring: nasal-vowel tildes and IPA diacritics are visually dense
  and were sitting at body size. This is the "at least as large and
  legible as normal fonts" fix the user asked for. Every downstream
  caller benefits without per-site edits; callers that want the old
  size for incidental contexts can still pass `size="1.0em"`.

## 4. Proposed additions

### 4.1 User-facing primer — `docs/app-docs/IPA_PRIMER.md`

Short, approachable, branching by learner background. Sections:

- **Why IPA?** (two paragraphs — pronunciation learning as hearing-before-
  speaking, how IPA disambiguates spelling).
- **How to read these brackets** — `[ ]` vs `/ /`, stress mark `ˈ`,
  length `ː`, syllable dot `.`. Seven symbols, no chart.
- **The handful you'll meet first** per target language:
  - Portuguese (BR): nasal vowels `ɐ̃ ẽ ĩ õ ũ`, open vs closed mid
    vowels `ɛ/e`, `ɔ/o`, palatal `ɲ ʎ`, two Rs `ʁ ɾ`.
  - French: nasal vowels `ɑ̃ ɛ̃ ɔ̃ œ̃`, `ʁ`, `y ø œ`, liaison.
  - English: schwa `ə`, `θ/ð`, `ʃ/ʒ`, diphthongs.
  - Italian / Spanish / Dutch / German: one-screen summary each.
- **Matthew's existing BR Portuguese reference** is linked, not
  duplicated — `language_materials/Portuguese-Grammar-IPA.md`.

Implementation: a single Markdown file, rendered inside a new "IPA guide"
expander or tab via `st.markdown(path.read_text())`. No templating engine.

### 4.2 In-app integration points

One integration, one opt-in widget each — nothing more:

| Where | What | Cost |
|---|---|---|
| Sidebar | "📖 About IPA" expander linking to the primer | 5 lines |
| Quick Practice | "ℹ️ What's this?" next to the IPA line — reveals the 5-symbol slice for the current word's target language | ~25 lines |
| Practice tab (existing colour-diff) | One-liner legend above the diff: "🟦 different sound · 🟩 sound you added · 🟥 sound you dropped" | ~3 lines |

### 4.3 Light practice: **minimal pairs from your own vocab**

The one new practice mechanic worth adding. Minimal pairs are the most
consistently recommended IPA/ear-training device in the literature, and
we can generate them *for free* from the user's existing vocabulary —
no new content authoring.

Mechanic:

1. Take the user's personal vocab for the current language.
2. For each word, compute the eSpeak phoneme string (already cached via
   `get_phonemes`).
3. Use `difflib.SequenceMatcher` — already imported in `practice_tab.py`
   — to find pairs whose phoneme strings differ by exactly one symbol.
4. Surface those pairs as an optional drill in Quick Practice:
   *"Say both, then say only the one I ask for."*

This integrates with existing scoring: we already score pronunciation
against eSpeak phonemes, so we can grade the minimal-pair drill with
the scoring path that's already in production. The "clever" part is
zero new data — the user's own word list is the curriculum.

Estimated footprint: one new module `src/ipa/minimal_pairs.py` (~80
lines) + a "Minimal pairs" option in the Quick Practice mode selector
(~15 lines).

## 5. What we are **not** doing

- No clickable IPA chart. Too much UI for too little gain; users who
  want a chart should use one of the excellent existing web tools
  (ipachart.app, Interactive IPA). The primer links out.
- No audio playback of bare IPA symbols. eSpeak doesn't do isolated
  phonemes well; handcrafted audio is out of scope.
- No new DB columns. Minimal-pair computation is session-scoped and
  cheap.
- No AI-generated explanations. The primer is human-written so it
  doesn't hallucinate phoneme claims.

## 6. Rollout

1. Font fix — shipped in this branch.
2. Primer markdown — shipped in this branch (content below).
3. Sidebar "About IPA" expander — separate PR, trivial.
4. Quick Practice "What's this?" — separate PR.
5. Minimal-pairs drill — separate PR, behind a feature flag until
   Matthew has tried it on his own vocab.

Each step stands alone; any can be dropped without breaking the rest.

## 7. Pedagogical basis (research summary)

Short version of the web research done for this proposal:

- **Minimal pairs + explicit articulatory instruction** show measurable
  pronunciation-score improvement in adult L2 learners (multiple recent
  studies, 2020–2024). This is the strongest single intervention.
- **Progressive exposure** — introducing ~5 symbols at a time tied to
  real vocabulary — outperforms chart-first teaching for retention in
  beginner cohorts.
- **Ear training before production** — learners distinguish contrasts
  better if they hear-and-identify before speaking. Miolingo already
  leans this way (TTS playback precedes user recording).
- **IPA is not mandatory** for pronunciation improvement, but *is*
  consistently reported as an accelerator by learners who stick with
  it long enough to internalise a dozen symbols.

All three principles point at the same thing: anchor symbols in the
user's current words, keep the symbol set small, start with listening.
This design does all three.

## 8. Critical files

- `src/scoring/phonemes.py` — `format_ipa()` (font fix done here)
- `docs/app-docs/IPA_PRIMER.md` — primer content (this PR)
- `language_materials/Portuguese-Grammar-IPA.md` — existing BR reference,
  linked from primer
- Future: `src/ipa/minimal_pairs.py`, `src/ui/ipa_guide.py` (tab/expander
  wiring), `src/ui/quick_practice_tab.py` (integration)
