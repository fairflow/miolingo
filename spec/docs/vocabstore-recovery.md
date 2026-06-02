# VocabStore — UI-first spec recovery (pre-draft analysis)

Per `SPEC-RECOVERY.md` §3. Component: **Vocabulary** tab (per-user, per-language personal dictionary). Recovered from the Streamlit source, not invented.

**Source files read:**
- `src/ui/vocabulary_tab.py` — the tab: list view, paste/upload capture, inline edit, per-entry actions.
- `src/vocab.py` — the CRUD operations (names recovered; bodies are stubbed, recovered later).

**Headline findings:**
- The entry collection lives in the **database**, not `session_state`. So the CCS process-local state is the collection itself (read via `list_vocab`); almost everything in `session_state` here is per-widget edit bookkeeping.
- **Auth gates the entire component** (`_require_auth()` early-returns) — a top-level ready-set guard.
- This confirms and refines the invented VocabStore strawman: CRUD over a collection with **non-empty gating** of per-entry operations — exactly the state-dependent enablement the strawman demonstrated. The recovery adds real guards the strawman lacked: auth, search-non-empty (for "Practise these"), missing-fields (autofill), and an edit-mode.
- **Bidirectional coupling with PracticeSession**: Practice's `capture_vocab` → `VocabStore.add`; VocabStore's "🎯 Practise these" → `PracticeSession.load_material`.

---

## (1) State inventory with read/write dependencies

### Domain state → CCS process-local
| State | Where it lives | Meaning |
|---|---|---|
| the entry collection | **database** (`list_vocab`, `capture/update/delete/import`) | the vocabulary store |
| `vocab_sort` | widget (`alpha`/`recent`/`oldest`) | view ordering parameter |
| `vocab_search` / `vocab_search_active` | widget + shadow | view filter parameter (and read cross-tab by Quick Practice) |
| `vocab_editing_{id}` | session_state bool | which entry (if any) is in inline-edit mode |

### Framework bookkeeping (discarded — H2 evidence)
| State | Why it exists |
|---|---|
| `vocab_edit_{field}_{id}` (×8 fields) | inline edit-form widget values, per entry |
| `vocab_notes_{id}`, `vocab_save_{id}` | notes textarea + button keys, per entry |
| `vocab_paste_passage/word/source/url`, `vocab_bulk_upload/enrich/btn`, `vocab_export_csv` | form/widget keys for the capture/import/export routes |
| **`_prune_stale_session_keys` + `_clear_edit_state`** | whole functions that garbage-collect orphan `vocab_edit_*` / `vocab_editing_*` keys after deletes/logout — pure rerun-model leak management. **Strong H2 evidence: code whose only job is to clean framework state.** |
| `pending_active_tab`, `pending_material_source_tab`, `qp_materials_expanded`, … | cross-tab navigation set by "Practise these" |

*Cross-cutting/context:* `authenticated`, `user`, `language`, `source_language`, `settings` — owned by auth/sidebar; the store operates within them (auth being a hard precondition, below).

---

## (2) Interaction triggers → candidate input ports

| Trigger | Input port | Transition |
|---|---|---|
| "➕ Add from passage" (`vocab_paste_btn`) | `add(word, ctx, source, url)` | `capture_vocab_entry` → insert/merge entry |
| "Import file" (`vocab_bulk_btn`) | `import_bulk(file)` | `import_from_file_contents` → bulk insert/update |
| "💾 Save" (edit form) | `update(id, fields)` | `update_vocab_entry` |
| "💾 Save notes" | `update_notes(id, notes)` | `update_vocab_notes` |
| "🗑️ Delete" | `delete(id)` | `delete_vocab_entry` |
| "✨ Auto-fill" (only if missing fields) | `autofill(id)` | `autofill_vocab_entry` (enrich) |
| "✏️ Edit" | `begin_edit(id)` | enter edit-mode for `id` |
| "✖ Cancel" | `cancel_edit(id)` | leave edit-mode |
| Sort selectbox | `set_sort(s)` | reparametrise the view |
| Search box | `set_filter(q)` | reparametrise the view |
| "🎯 Practise these" / QP "📂 Load vocabulary" / "🎯 Load filtered" | `practise_vocab` | **cross-component** → `PracticeSession.load_material`. ONE channel; payload `practiseList(entries, filter)` is all vocab when `filter=none`, the subset otherwise (see Amendment below) |
| (text fields, the upload widget) | — not ports — | |

*"🔊 Play"* is an output effect (TTS), not a store mutation.

---

## (3) Displays → candidate output ports (projections)

| Display | Output port / projection `f` |
|---|---|
| entry list (rows: word · translation · IPA · source · date, expanders) | `view!` — the collection projection `f = listVocab(entries, sort, filter)` (R of CRUD; there is no separate read port) |
| "**N** entries" count | part of the list projection |
| empty-state with source-pairing breakdown | a *reflective* projection `whyEmpty(entries, pairing)` when the filtered view is empty |
| inline edit form (pre-filled) | a projection of the entry under edit `editView(entry)` |
| "⬇️ Export CSV" | output projection `exportCsv(entries)` (downloadable) |

---

## (4) Afforded-port (ready-set) table per mode

`view!`/`afforded!` present in every mode (omitted below).

| Mode | Domain ports | Recovered from |
|---|---|---|
| **Anon** (not authenticated) | — (none) | `_require_auth()` early-returns the whole tab |
| **Empty** (signed in, no entries in this pairing) | `add`, `import_bulk`, `set_sort`, `set_filter` | no rows ⇒ no per-entry actions, no export, no practise |
| **NonEmpty** | `+ export`, `practise_vocab`, and per entry: `delete`, `update_notes`, `autofill`†, `begin_edit` | `for row in rows:` renders the action rows |
| **Editing(id)** (a row in edit-mode) | for that row: `update(id)`, `cancel_edit(id)` *instead of* the normal actions (`export`, `practise_vocab` stay) | `if editing: _render_entry_edit_form` |

Guards (state-dependent enablement):
- **auth** gates every domain port (Anon offers none).
- per-entry ops + export + `practise_vocab` gate on **non-empty** (the filter no longer gates practise — see Amendment).
- † `autofill` gates on the entry **missing translation or IPA** (`need_autofill`) — a per-entry stubbed-value guard.
- `begin_edit` vs `update`/`cancel_edit` switch on **edit-mode** for that entry.

---

## (5) Wiring diagram

```
   auth ──(precondition)──►┌──────────────────────────────┐
   user ──add/import──────►│  VocabStore                   │
        ──update/notes────►│  state: (entries, sort,       │
        ──delete──────────►│          filter, editing)     │
        ──autofill────────►│                               │
        ──set_sort/filter─►│                               │
        ──begin/cancel_edit►│                               │
        ◄──view!(listVocab)─                                │
        ◄──afforded!────────                                │
        ◄──export(csv)──────                                │
        ◄──whyEmpty(...)────└──────────────────────────────┘
                                 │                    ▲
              practise_vocab ────┘                    └── add ◄── capture_vocab
                  │                                          (from PracticeSession)
                  ▼
            PracticeSession.load_material      ⇒ VocabStore ⇄ PracticeSession (bidirectional)
```

---

## (6) Stub list (named, no bodies — recovered later from `src/vocab.py`)

`listVocab(entries, sort, filter)`, `addEntry(entries, word, ctx, source, url)`,
`importInto(entries, file)`, `updateEntry(entries, id, fields)`,
`updateNotesIn(entries, id, notes)`, `deleteFrom(entries, id)`,
`autofillIn(entries, id)`, `exportCsv(entries)`, `whyEmpty(entries, pairing)`,
`needsAutofill(entries, id)`, `vocabView(...)`.

Names recovered from `vocabulary_tab.py`'s calls into `vocab.py`; bodies survive framework-independently in `src/vocab.py` and are recovered mechanically later — not invented now.

---

## Amendment (2026-06-02) — the vocab→practice channel is `practise_vocab`, ungated

The original recovery extracted only the vocab tab's "🎯 Practise these" button, as `practise_filtered`, **gated on a filter** (`if rows and search.strip()`). That under-extracted the design: **`src/ui/quick_practice_tab.py`** exposes the same hand-off from the *Quick Practice* side with **two more routes** — **"📂 Load vocabulary (N)"** (the *whole, unfiltered* vocab, available whenever vocab is non-empty) and **"🎯 Load filtered (N)"** (the filtered subset) — plus a Minimal-Pairs route (a computed subset).

Per Matthew's decision (2026-06-02), these are unified into **one channel**, `practise_vocab`:
- available whenever the store is **non-empty** (the filter no longer *gates* it);
- it emits the **current view** to PracticeSession via `pLoad` (restricted → τ): `practiseList(entries, filter)` — **all** vocab when `filter = none`, the filtered subset when `filterBy[q]`. So the filter *parametrises the payload*, it does not enable/disable the route.
- Minimal Pairs is **not** modelled this round (a separate computed route, deferred).

The τ hand-off itself was verified faithful before this change: PS receives the list and all PS features become available, identical to `load_material`. See `MioCore.wl` (the `pLoad` link) and `VocabStoreRecovered.wl` (`VSNonEmpty`).
