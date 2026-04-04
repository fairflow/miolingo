# Miolingo Refactor Plan

**Status:** Draft — needs team review before implementation begins
**Created:** 2026-04-04
**Branch:** `claude/dev`

---

## Motivation

`src/app.py` is a 4,034-line monolith containing UI, business logic, audio processing,
scoring, authentication, and database interaction. This makes it:

- Hard for AI assistants to navigate (burns context window reading irrelevant sections)
- Fragile to change (a TTS fix risks breaking the login flow)
- Untestable in isolation (no function can be tested without Streamlit session state)

The refactor aims to decompose `app.py` into focused modules while keeping the app
functional at every step.

---

## Principles

1. **Always shippable** — the app must work after every PR, not just at the end
2. **Extract, don't rewrite** — move existing code into modules; minimise logic changes
3. **Test what you extract** — each new module gets at least smoke-test imports
4. **One concern per PR** — each extraction is a reviewable, revertible unit

---

## Target Architecture

```
src/
├── app.py                    # Slim orchestrator: routing, sidebar, session init
├── config.py                 # LANGUAGE_CONFIG, constants, settings load/save
├── auth.py                   # Login, authentication, role checks
├── audio/
│   ├── tts.py                # TTS engines: espeak, Google Cloud, gTTS
│   ├── asr.py                # Whisper, WAV2Vec2 transcription
│   └── recording.py          # Audio capture utilities
├── scoring/
│   ├── phonemes.py           # IPA extraction, phoneme processing
│   ├── comparison.py         # Levenshtein, edit operations, scoring algorithms
│   └── practice.py           # practice_word_from_audio orchestration
├── ui/
│   ├── practice_tab.py       # Quick Practice tab rendering
│   ├── story_tab.py          # Story Reader tab rendering
│   ├── statistics_tab.py     # Statistics tab rendering
│   ├── history_tab.py        # History tab rendering
│   └── components.py         # Shared UI components (IPA display, result cards)
├── translation.py            # Translation providers + LLM translation
├── materials.py              # Language material loading (rename of app_language_materials)
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

---

## Constraints

- MySQL connections: **never** create new tunnels — rule carries through to all modules
- Streamlit session state: modules that need `st.session_state` receive it as a parameter
  or import it at function call time, not module load time
- The app must remain deployable on Streamlit Cloud throughout
- No dependency additions without discussion (keep requirements.txt lean)

---

## Open Questions

- [ ] Should `connection_pool.py` and `connection_monitor.py` merge into `db/`?
- [ ] Is the CCS test framework worth keeping as-is, or should it evolve into pytest fixtures?
- [ ] Target for admin: keep as separate app or fold into main app with role-based routing?
- [ ] What's the minimum test coverage before we start moving code?

---

## Progress Tracking

Updates will be logged here as phases complete.

| Date | Phase | PR | Notes |
|------|-------|----|-------|
| — | — | — | Not yet started |
