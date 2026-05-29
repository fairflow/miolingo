# Practice Session — UI-first spec recovery (pre-draft analysis)

Per `SPEC-RECOVERY.md` §3. Component: **Quick Practice** (the "🎯 Quick Practice" tab — highest interaction complexity). Recovered from the Streamlit source, *not invented*. All value-transformation logic is left as named stubs (§4).

**Source files read:**
- `src/app.py` — `initialize_session_state()` (state init) + `main()` tab orchestration.
- `src/ui/practice_tab.py` — `render_practice_interface` (record → check → clear) and `render_practice_results` (scored display).
- `src/ui/quick_practice_tab.py` — material loading, the phrase queue, prev/next/select navigation.

**Headline recovery findings (divergences from the earlier invented strawman):**
- The session is **free navigation over a bounded queue** (prev / next / select), *not* a linear consume-to-`Finished`. There is no deadlock end state; the user simply stops. `next`/`prev` are *disabled at the ends*, which is a ready-set guard, not a transition to `Finished`.
- Recording and checking are **two steps**: `st.audio_input` produces a recording (a field), and only `if audio_data:` are **Check** and **Remove** offered. That `if` is a CCS guard — Check/Remove are afforded *only when a recording exists*.
- A practice **result** is per-position and is cleared by navigation or by Remove.
- There is a genuine **cross-component port**: a multi-word result offers "add a word to my vocabulary" → this is a synchronisation with `VocabStore` (`capture_vocab`).

---

## (1) State inventory with read/write dependencies

### Domain state (becomes CCS process-local state)
| Variable | Type | Written by | Read by | Meaning |
|---|---|---|---|---|
| `phrase_list` | list | material loaders (`load_builtin`, `use_upload`, vocab/minimal-pairs loaders), `Clear Material` | navigation, target lookup | the practice queue (the items) |
| `qp_phrase_position` | int | prev/next/select, material load (→0), bounds-clamp | target lookup, nav guards | current index into the queue |
| `{prefix}_last_result` / `quick_last_result` | dict \| None | Check (`practice_word_from_audio`), Remove (→None) | results display, vocab-capture guard | the evaluation of the latest attempt |
| `current_sessions[language]["practices"]` | list | `_persist_result` (on each Check) | History/Statistics (other components) | accumulated attempts this session |
| `session_saved` | bool | `_persist_result`(False), `save_current_session`(True) | save flow | whether the session is persisted |

### Framework bookkeeping (discarded — encoding it re-imports the contamination; H2 evidence)
| Variable | Why it exists (Streamlit rerun model) |
|---|---|
| `{prefix}_audio_input_key`, `audio_input_key` | integer bumped only to **remount** `st.audio_input` and drop a stale blob — pure widget-reset hack |
| `{prefix}_audio_input_{N}` | the audio widget value, keyed by the counter above |
| `last_phrase_index` | remembers previous index *only* to detect a change and remount the recorder |
| `phrase_selector_widget` | mirror of `qp_phrase_position` kept in sync because the selectbox owns its own key (dual-management) |
| `last_sound_played` | one result-id so the success chime fires once per result (UI effect, see ports) |
| `state_change_log`, `last_state_snapshot` | debug-only tracing |
| `pending_active_tab`, `active_tab`, `material_source_tab`, `pending_*` | tab navigation; deferred-mutation workaround for Streamlit's "can't mutate a drawn widget key" rule |
| `whisper_model(_name)`, `wav2vec2_*` | cached ASR models — perf caching, internal to the scoring stub |
| `qp_materials_expanded`, `qp_builtin_category/file`, `{upload}_*`, `mp_max_pairs` | material-*picker* widget state (the load sub-flow); only the resulting `phrase_list` is domain |

**Discard ratio (Quick Practice):** ~5 domain variables vs ~15+ framework-bookkeeping variables — the interaction's "real" state is a small fraction of `session_state`. This is the H2 evidence the protocol asks to record, not silently drop.

*Cross-cutting/context (owned elsewhere, not this agent's state):* `language`, `source_language`, `target_language`, `settings`, `authenticated`, `user` — set by the sidebar/auth; the session operates *within* them.

---

## (2) Interaction triggers → candidate input ports (port boundary criterion)

A port exists only where crossing it is *semantically observable*. Keystrokes, the audio-recording field, and text fields are **not** ports.

| Trigger (Streamlit) | Input port | System-side transition on sync |
|---|---|---|
| recording captured by `st.audio_input` (a blob now exists) | `recording_made(audio)` | attach the recording; Check/Remove become afforded |
| "✅ Check Pronunciation" (`{prefix}_submit_btn`) | `attempt_made` | score the recording vs target → store result |
| "🗑️ Remove Recording" (`{prefix}_clear_btn`) | `clear_recording` | drop recording **and** result; remount recorder |
| "➡️ Next" (`_on_next`) | `next_item_requested` | `position += 1`; clear recording/result |
| "⬅️ Previous" (`_on_prev`) | `prev_item_requested` | `position -= 1`; clear recording/result |
| phrase selectbox (`phrase_selector_widget`) | `select_item(i)` | jump `position := i`; clear recording/result |
| "📂 Load This File" / "✅ Use This File" / vocab & minimal-pairs loaders | `load_material(phrases)` | set queue, `position := 0` |
| "🗑️ Clear Material" | `clear_material` | empty the queue |
| "➕ Add" (vocab capture, multi-word result) | `capture_vocab(word)` | **cross-component** → `VocabStore.add`; loops here |
| "💾 Save" (`save_current_session`) | `save_session` | persist; reset current-session accumulator |

*Borderline / deferred:* `edit_mode` toggle (opens phrase editing; disables nav while open) is a sub-mode, recorded but not in the core loop. Free-text target/source entry is an alternate material source feeding `load_material`.

---

## (3) Displays → candidate output ports (projections, never raw state)

Each is output-only, carrying `view!(f state)`.

| Display (Streamlit) | Output port / projection `f` |
|---|---|
| target text + IPA + target TTS audio ("🎯 Target pronunciation") | `view!` while no result — **the prompt**: `f = targetView(phrase_list, position)` (text, `formatIPA(correctIPA)`, `generateTargetAudio`) |
| recording playback ("▶️ Your recording") | part of the recorded-state view: `f = recordedView` |
| Results block (score / PERFECT / Excellent / Score%, target-vs-user IPA, coloured diff) | `view!` while a result exists: `f = resultView(result)` |
| "Word i / N" position / selectbox label | `f = progressView(position, len phrase_list)` |
| success / excellent chime (`components.html` beep, gated by `last_sound_played`) | **one-shot** output effect `chime!(grade)` on first render of a perfect/excellent result — distinct from the steady `view!` |
| "🔍 Show detailed phoneme analysis" (checkbox-gated) | a **reflective/richer** projection `detailView(result)` — a *distinct* port from `view!`, per the runtime-vs-reflective rule |

---

## (4) Afforded-port (ready-set) table per mode

Recovered from the conditional rendering. `view!` and `afforded!` (the discipline ports) are present in **every** mode and omitted from the rows below for brevity.

| Mode (state) | Domain ports afforded | Recovered from |
|---|---|---|
| **NoMaterial** (`phrase_list` empty / no text) | `load_material` | `render_practice_interface` early-returns on `not text`; material loaders in the picker |
| **Prompting** (item shown, no recording) | `recording_made`, `next`†, `prev`‡, `select`, `clear_material`, `load_material` | target rendered; recorder shown; nav row |
| **Recorded** (recording exists, no result) | `attempt_made`, `clear_recording`, `next`†, `prev`‡, `select`, … | `if audio_data:` → Check + Remove buttons |
| **Evaluated** (result exists) | `clear_recording`, `capture_vocab`§, `next`†, `prev`‡, `select`, … | `render_practice_results`; vocab input |

Guards (state-dependent enablement, the headline):
- † `next` afforded iff `position < len(phrase_list) − 1` **and** not `edit_mode` (`disabled=...`).
- ‡ `prev` afforded iff `position > 0` **and** not `edit_mode`.
- § `capture_vocab` afforded iff the result's target is **multi-word** and the user is authenticated (`_render_practice_vocab_capture` returns early otherwise; single-word perfect matches are auto-captured in `_persist_result`).
- `attempt_made` / `clear_recording` afforded iff a recording exists (`if audio_data:`).

---

## (5) Wiring diagram (plain text — the draft link graph)

```
                   load_material(phrases) ─┐
                   clear_material ─────────┤
   user ──recording_made(audio)──►         │
        ──attempt_made────────────►   ┌───────────────────────────┐
        ──clear_recording─────────►   │  PracticeSession           │
        ──next/prev/select────────►   │  state: (phrase_list,      │
                                       │          position,         │
        ◄──view!(f state)──────────    │          recording,        │
        ◄──chime!(grade)───────────    │          result)           │
        ◄──afforded!(ready set)────    └───────────────────────────┘
                                              │            │
                            evaluate(target,──┘            └──capture_vocab(word)──► VocabStore.add
                            recording)  [stub]                (cross-component port)
                                              │
                                      save_session ──► (History/Statistics persistence; other components)
```

Restriction/composition note: `capture_vocab` is the one link to another agent (`VocabStore`); everything else is a port between the user and this agent. `save_session`, History and Statistics are downstream consumers of the accumulated `practices` projection (separate components).

---

## (6) Stub list (named, no bodies — recovered in a later pass from `src/scoring/`, `src/audio/`)

`targetOf(phrase_list, position)`, `generateTargetAudio(text, settings)`, `formatIPA(ipa)`,
`evaluate(target, recording, settings, language)` → result *(the `practice_word_from_audio` core)*,
`isMultiWord(target)`, `atStart(position)`, `atEnd(phrase_list, position)`,
`nextPos`/`prevPos`/`selectPos`, `capture(word, …)`, `persist(result)`.

These are committed as *signatures only*. Their bodies survive framework-independently in `src/scoring/practice.py`, `src/scoring/phonemes.py`, `src/audio/`, and `src/vocab.py`, and are recovered mechanically later — not invented now (§4, §6).
