# Miolingo Refactor Plan

**Status:** Draft — needs team review before implementation begins
**Created:** 2026-04-04
**Updated:** 2026-04-04
**Branch:** `claude/dev`

---

## Motivation

`src/app.py` is a 4,034-line monolith containing UI, business logic, audio processing,
scoring, authentication, and database interaction. This makes it:

- Hard for AI assistants to navigate (burns context window reading irrelevant sections)
- Fragile to change (a TTS fix risks breaking the login flow)
- Untestable in isolation (no function can be tested without Streamlit session state)

Beyond structure, the app has a **baked-in language assumption**: English is always the
helper/base language, and the practice target is always one of PT/FR/DE/ES/IT/NL. This
prevents use cases like "French speaker learning English" or "Portuguese speaker learning
German with Portuguese glosses". The refactor addresses both concerns, in the right order.

---

## Principles

1. **Always shippable** — the app must work after every PR, not just at the end
2. **Extract, don't rewrite** — move existing code into modules; minimise logic changes
3. **Test what you extract** — each new module gets at least smoke-test imports
4. **One concern per PR** — each extraction is a reviewable, revertible unit
5. **Structure first, semantics second** — decompose the monolith before changing
   language behaviour; never both at once

---

## Target Architecture

```
src/
├── app.py                    # Slim orchestrator: routing, sidebar, session init
├── config.py                 # LANGUAGE_CONFIG, constants, settings load/save
├── language_context.py       # UserLanguageContext: practice/helper language, fallback chain
├── auth.py                   # Login, authentication, role checks
├── audio/
│   ├── tts.py                # TTS engines: espeak, Google Cloud, gTTS
│   ├── asr.py                # Whisper, WAV2Vec2 transcription
│   └── recording.py          # Audio capture utilities
├── scoring/
│   ├── phonemes.py           # IPA extraction, phoneme processing, file-based IPA cache
│   ├── comparison.py         # Levenshtein, edit operations, scoring algorithms
│   └── practice.py           # practice_word_from_audio orchestration
├── ui/
│   ├── practice_tab.py       # Quick Practice tab rendering
│   ├── story_tab.py          # Story Reader tab rendering
│   ├── statistics_tab.py     # Statistics tab rendering
│   ├── history_tab.py        # History tab rendering
│   └── components.py         # Shared UI components (IPA display, result cards)
├── translation.py            # Translation providers + LLM translation
├── materials.py              # Normalised phrase store, material loading
├── db/
│   ├── connection.py         # Connection pool + tunnel (merge connection_pool + app_mysql)
│   └── queries.py            # Query functions extracted from app_mysql
├── session_manager.py        # (existing, may need minor updates)
└── admin/
    ├── dashboard.py           # Admin app entry point
    ├── admin_db.py            # Admin DB operations
    └── unified.py             # Admin router
```

---

## Extraction Order (proposed)

Each phase is one or more PRs. Later phases depend on earlier ones.

### Phase 1 — Low-risk extractions (no UI changes)

| Step | Extract from app.py | Into | Lines moved |
|------|-------------------|------|-------------|
| 1.1 | Constants, LANGUAGE_CONFIG, load/save settings | `config.py` | ~290 |
| 1.2 | Translation utilities + providers | `translation.py` | ~330 |
| 1.3 | IPA/phoneme functions | `scoring/phonemes.py` | ~90 |
| 1.4 | Scoring algorithms | `scoring/comparison.py` | ~140 |

### Phase 2 — Audio layer

| Step | Extract from app.py | Into | Lines moved |
|------|-------------------|------|-------------|
| 2.1 | TTS functions (speak_text_*) | `audio/tts.py` | ~285 |
| 2.2 | ASR functions (transcribe_audio_*) | `audio/asr.py` | ~125 |
| 2.3 | practice_word_from_audio | `scoring/practice.py` | ~140 |

### Phase 3 — Auth

| Step | Extract from app.py | Into | Lines moved |
|------|-------------------|------|-------------|
| 3.1 | show_login_page, check_authentication | `auth.py` | ~450 |

### Phase 4 — UI decomposition

| Step | Extract from app.py | Into | Lines moved |
|------|-------------------|------|-------------|
| 4.1 | render_practice_interface/results | `ui/practice_tab.py` | ~375 |
| 4.2 | render_story_reader, scene modes | `ui/story_tab.py` | ~340 |
| 4.3 | Statistics and History tabs | `ui/statistics_tab.py`, `ui/history_tab.py` | TBD |

### Phase 5 — main() cleanup

After phases 1–4, `app.py` should be ~500 lines: imports, session init, sidebar,
and tab routing via the extracted modules.

### Phase 6 — Language-parametric model

**Prerequisites:** Phases 1–5 complete (modules exist and are tested).

This phase removes the hard-coded "English = helper" assumption and makes any
language usable as either practice target or helper language.

#### 6.1 — UserLanguageContext

Introduce a context object that replaces scattered `st.session_state` language reads:

```python
@dataclass
class UserLanguageContext:
    practice_language: str   # what the user is pronouncing
    helper_language: str     # glosses, translations, UI hints
```

No hardcoded defaults. Both fields set by the UI. All modules that care about
"which language?" receive this context rather than reading session state directly.

#### 6.2 — Normalised phrase format

Migrate from the current per-language files (one file per language, English
embedded as helper) to a normalised format where each phrase carries direct
translations into all available languages:

```json
{
  "phrase_id": "scene01-01",
  "source_language": "fr",
  "text": {
    "de": "Hallo Sophie, wie geht's?",
    "en": "Hello Sophie, how are you?",
    "fr": "Bonjour Sophie, comment ça va ?"
  },
  "translation_provenance": {
    "en": "direct_from:fr",
    "de": "direct_from:fr"
  },
  "ipa_cache": {
    "de": "[ˈhalo ˈzoːfi viː ˈɡeːts]"
  }
}
```

Key design decisions:

- **Each `text` entry is a direct translation**, not a round-trip through English.
  Translation is not a bijection: FR→EN→DE loses nuance that FR→DE preserves.
  Direct pairwise translations are preferred; English is a fallback, not a pivot.
- **Translation provenance tracks the shortest path.** `source_language` records
  which language the phrase was originally authored in. `translation_provenance`
  records how each translation was derived (e.g. `direct_from:fr` vs
  `pivot_via:en`). This lets us later identify translations that could be improved
  by regenerating directly from the source language instead of via a pivot.
  No single pivot language is optimal for all pairs — French may be better for
  Romance↔Germanic, but worse for NL↔DE where a direct path is far shorter.
- **`ipa_cache` is optional and per-language.** espeak generates IPA on-the-fly
  for any language (including English) at runtime. Pre-computed IPA in files is a
  **performance cache** for fast scrolling through stories, not a replacement for
  runtime generation. Users can always enter arbitrary phrases and get IPA live.
- **IPA cache is file-based, not DB** — speed matters for scrolling through
  story scenes with many phrases.
- **Sparse translations are fine.** A phrase with only `{fr, en}` works for
  FR↔EN practice. Other pairs are added over time via the translation pipeline.
- **Fallback chain** when a direct translation is missing:
  `direct(practice, helper)` → `English as pivot` → `"[translation not available]"`
- **Schema must be extensible to per-user annotations.** A planned personal
  vocabulary feature will let users track words with source context (which story
  scene, poem, or news item they first encountered a word in). The phrase format
  and `materials.py` data model should not preclude attaching user-level metadata
  that references back to source materials.

#### 6.3 — Materials migration

A one-time script converts current per-language files to normalised format:

1. Read all `language_materials/<lang>/story-scenes-json/*.json`
2. Match phrases across languages by `phrase_id` (or by English text as
   initial join key, then assign stable IDs)
3. Merge into normalised files with all available translations inline
4. Generate missing IPA cache entries via espeak
5. Populate `source_language` and `translation_provenance` from known
   authoring history (e.g. story scenes were authored in French)

The existing `scripts/language-generation/` pipeline adapts to produce
normalised output. New translations are generated as direct pairs (FR→DE)
rather than pivoting through English.

#### 6.4 — Add English to LANGUAGE_CONFIG

English becomes a first-class practice language with voice mappings, espeak
config, and material support — exactly like PT/FR/DE today.

#### 6.5 — UI: language pair selector

Replace the current single "language" dropdown with a practice/helper pair
selector. The existing language dropdown becomes the practice language;
a new helper language dropdown appears alongside it.

---

## Constraints

- MySQL connections: **never** create new tunnels — rule carries through to all modules
- Streamlit session state: modules that need `st.session_state` receive it as a parameter
  or import it at function call time, not module load time
- The app must remain deployable on Streamlit Cloud throughout
- No dependency additions without discussion (keep requirements.txt lean)
- espeak is a **runtime dependency** everywhere — required for on-the-fly IPA generation
  of arbitrary user-entered phrases. The binary is called `espeak` (not `espeak-ng`)
- **Storage scales linearly, not quadratically.** The normalised phrase format stores one
  entry per language per phrase. With 7 languages that's 7 entries, not 42 files.
  Adding language 8 is O(phrases), not O(phrases × languages). We do not pre-generate
  all possible language pairs; translations are added as needed.

---

## Open Questions

- [ ] Should `connection_pool.py` and `connection_monitor.py` merge into `db/`?
- [ ] Is the CCS test framework worth keeping as-is, or should it evolve into pytest fixtures?
- [ ] Target for admin: keep as separate app or fold into main app with role-based routing?
- [ ] What's the minimum test coverage before we start moving code?
- [ ] For materials migration: use English text as initial join key, or assign phrase IDs
      manually? (English text is available in all current files but is semantically lossy)
- [ ] Translation provider preference for direct pairs: DeepL (high quality, limited
      languages) vs OpenAI (broad coverage, variable quality)?

---

## Progress Tracking

Updates will be logged here as phases complete.

| Date | Phase | PR | Notes |
|------|-------|----|-------|
| 2026-04-04 | Pre-work | #26 | Project organisation: AGENTS.md, CLAUDE.md update, REFACTOR_PLAN.md, legacy file cleanup |
| 2026-04-04 | Pre-work | #27 | Script cleanup (credential leak fix) + pytest scaffolding (25 tests) |
