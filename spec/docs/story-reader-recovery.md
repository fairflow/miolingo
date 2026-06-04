# Story Reader — recovery & design (plan A)

`StoryReader` is the narrative tab: read one story three ways and **practise
pronunciation from it without leaving the story**. Recovered from
`src/ui/story_tab.py` (app src @ `504f8c8`), composed into `mioCore` (2026-06-04).

## What the app does (and the two artifacts we fix)

`render_story_reader` is a `st.radio` mode selector over one story:
- **📄 Full Story** — the whole markdown.
- **🎬 Scene by Scene** — a scene with parallel translation.
- **🎙️ Practice Mode** — `render_scene_practice_mode`, which renders **the same**
  `render_practice_interface(…, key_prefix="story")` Quick Practice uses.

Two things "grew like Topsy" here, and the spec deliberately corrects both:

1. **A duplicated practice loop.** Story practice re-renders the practice interface
   with a `story` key-prefix and **separate** state (`story_practice_index`,
   `story_last_result`). Same logic, copied. There is **no "return to story" action**
   — practice never leaves the tab; the radio *is* the navigation.
2. **Independent positions per mode.** Practice Mode's scene+index is independent of
   the reading modes' position, so flipping modes doesn't keep your place in the
   narrative.

## The design (plan A)

`StoryReader[scene, pos, mode, rec, res]` owns **one narrative position**
`(scene, pos)`; the three modes are **affordances over it**:

| mode | ports | @src |
|---|---|---|
| `full` | `view!` (whole story); `set_mode`, `select_scene` only | `story_tab.py:360` |
| `browse` | `+ story_select_item / story_next / story_prev` (scroll the scene) | `story_tab.py:386` |
| `practice` | `+` the full record→score→capture loop (`StoryPractice`) | `story_tab.py:165` |

- **`set_mode` PRESERVES `(scene, pos)`** (and clears `rec,res`). So you read scene 5
  in browse, flip to practice, and you're practising scene 5 — the coherence the app
  loses. **This is a deliberate deviation from the app** (flagged in PROVENANCE).
- `select_scene` resets `pos` to 0 (new scene). `view!` publishes `storyView`.
- The mode-specific ports come from a sub-agent named in a guarded summand —
  `if[mode === browse, call["StoryBrowse", scene, pos]]` and
  `if[mode === practice, call["StoryPractice", scene, pos, rec, res]]` — so that
  sub-agent's transitions join StoryReader's choice only in that mode (the same idiom
  PS uses to bring in `PSActive` when its queue is non-empty).
- Capture from a scene → **`vocabUpsert` → VocabTable** (the SAME store channel Quick
  Practice capture uses). Scoring borrows the language from Helm on **`langRead`**.
  Both are existing restricted channels — StoryReader adds **no new** sync channels.
- User-facing loop ports are **`story_`-prefixed** (`story_recording_made`, …) so they
  are distinct controls from Quick Practice's (the app's `key_prefix="story"`); the
  `vocabUpsert`/`langRead` channels stay unprefixed (store/Helm channels, shared).

## Why the practice loop is written twice (not one shared definition)

The plan asked for ONE practice loop reused by both Quick Practice and the Story tab.
It was tried and backed out. Here is what was tried and exactly why it doesn't work —
a real property of the Wolfram engine, worth recording.

**What was attempted.** A plain Wolfram function returning *a fragment of an agent's
defining equation* (the loop's summands), to be dropped into both agents:

```wolfram
practiceLoopSummands[pfx_, phrases_, pos_, rec_, res_, ret_] := Sequence[
   ...,
   if[rec === none, recordSummand, ...],          (* a guard *)
   if[pos < Length[phrases] - 1, nextSummand], ... ]

defineAgent["PSActive", {phrases, pos, rec, res},
   choice[ clearSummand, practiceLoopSummands["", phrases, pos, rec, res, retToPS] ]]
```

That is *source-template* reuse — like a macro — one level **below** CCS, and that is
the level at which it collides with the engine.

**The collision, concretely.** `defineAgent` stores its body UNEVALUATED (it has the
`HoldRest` attribute). Two different transition functions read the spec, and they
handle a guard `if[cond, P]` in *opposite* ways:

- `transNamed` (steps `call[name, args]` directly) substitutes the **concrete**
  arguments into the stored body and only then evaluates — so `rec === none` becomes
  `none === none → True`. Its rule is `if[c_, p_] := If[c, …]`: it expects `c` to
  ALREADY be a Boolean. It needs **naked** conditions.
- `transVP` (steps a compiled mu-term) compiles the agent with its parameters still
  **symbolic**, so conditions can't be evaluated yet. A pass `prepBody` rescues this by
  *scanning the stored body for every `if[cond, …]` and wrapping the condition in
  `Hold`*, deferring evaluation to each simulation step.

The decisive word is **scanning**: `prepBody` finds conditions by pattern-matching the
literal `if[…]` syntax in the stored body. Hand-written, the `if[rec === none, …]` is
right there, so `prepBody` wraps it. With the builder, the stored body holds only
`practiceLoopSummands[…]` — an *unexpanded function call*; there is no `if[…]` for
`prepBody` to find. By the time the function expands (at read time) it is too late, and
the conditions are evaluated against the bare symbols, where they reduce **wrongly**:

```wolfram
Length[phrases]   (* phrases is a bare symbol ⇒ atomic ⇒ 0 ,  so "pos < -1" : always false *)
rec === none      (* two distinct symbols     ⇒ False    ,  so always the wrong branch    *)
```

Two repairs both fail: emitting `if[Hold[cond], …]` from the builder fixes `transVP`
but breaks `transNamed` (which never `ReleaseHold`s); expanding the builder at
definition time makes the conditions visible but re-triggers `Length[symbol] ⇒ 0` and
`=== ⇒ False`. Shape-gated predicates patch some cases and leave others stuck
mid-composition.

**Conclusion — and it is also a modelling point, not only an engine one.** The engine's
deferred-guard mechanism assumes guards are hand-written in each agent's stored body, so
the loop is written once per context (`PSActive` and `StoryPractice` — same shape,
~20 lines). The genuine reuse is at the value-function level — `targetOf`, `evaluate`,
`scored`/`recorded`, `selectPos`, which both call — which is where the actual logic
lives; only the summand scaffolding is repeated. And the loop is *not* a cleanly
separable agent: its state IS the context's state — the queue position `pos`. `next`
steps PS's own state in Quick Practice and StoryReader's own state in the Story tab. To
make it a standalone agent (then reused by restriction + relabelling) you would have to
externalise `pos` as a separate "cursor" agent talking over channels — more machinery
than ~20 lines is worth. Per-context is the faithful model. (A single shared definition
would need an engine change: `transNamed[if]` doing `ReleaseHold`, or a define-time
code-gen macro doing the `Hold` surgery by hand.)

## select_item is bounded — out-of-range is a no-op

`select_item?(i)` / `story_select_item?(i)` take the index from the open environment.
The app can only render a clickable row for an item that EXISTS, so an out-of-range
index never arises there — but at L1 nothing stopped one. Originally the index was
bound raw (`call["PS", phrases, i, none, none]`), so a stray `select_item 5` on a
one-item queue set `pos = 5`; `targetOf` then returned the empty item and a later
`attempt_made` scored a meaningless **zero** (found by an interleaved PS+Story trace,
2026-06-04). Both selects now route through the recovered guard `selectPos[phrases, i,
cur]` (`PracticeSessionFunctions.wl`): a valid index selects, an invalid one is a no-op
(keeps the current position). Regression-tested in `story_reader_test.wls` §5.

## The story-content boundary (`sceneOf`) — a deferred store

A scene's phrases come from per-language JSON files (`_extract_scene_phrases`), an
external read-only source. Properly this is a **`StoryLibrary` store agent** read
across a port — parallel to `VocabTable` (ARCHITECTURE.md store tier) — **deferred**
this round to keep the focus on the interaction + position design. `sceneOf` is a
small in-spec **fixture** standing in for it, shaped exactly as the app returns
(`{text, translation, ipa}`) so the loop runs over it unchanged. When the store lands,
StoryReader gains a visible **`open_story`** entry guarding a `storyRead` τ (the
`open_vocab`/`open_practice` pattern) and `sceneOf` becomes that pull. In the
cloud/incompleteness inventory until then.

## Provenance  (app src @ `504f8c8`)

| Spec element | Kind | Source `file:line (fn)` | App construct | Note |
|---|---|---|---|---|
| `StoryReader[scene,pos,mode,rec,res]` | agent | `story_tab.py:295 (render_story_reader)` | the Story Reader tab | **faithful** — one tab, one narrative position. |
| `set_mode` | port (in) | `story_tab.py:348 (st.radio)` | the mode selector | **faithful** — but PRESERVES position (app doesn't). **deviation**. |
| `select_scene` | port (in) | `story_tab.py:193 (scene selectbox)` | scene picker | **faithful** — new scene ⇒ pos 0. |
| `view! (storyView)` | port (out) | `render_full_story / render_scene_by_scene` | per-mode render | **faithful** — one projection, skin renders per mode. |
| `StoryBrowse` nav | ports (in) | `story_tab.py:386 (render_scene_by_scene)` | scene scroll | **faithful** — `story_`-prefixed. |
| `selectPos[phrases,i,cur]` | value-fn (guard) | `story_tab.py` scene selector / `render_practice_interface` | clicking an existing item | **faithful** — keeps pos valid; invalid index = no-op (the app can only offer existing items). Shared with PS. |
| `StoryPractice` loop | ports (in) | `story_tab.py:165 (render_scene_practice_mode)` → `render_practice_interface` | the practice pane | **simplified** — mirrors `PSActive`; one position, not a separate index. **deviation**. |
| `story_capture_vocab → vocabUpsert` | sync (→ VocabTable τ) | `story_tab.py:55 (capture_vocab_entry)` | scene capture | **faithful** — direct store write, same channel as PS capture. |
| `story_attempt_made → langRead` | sync (Helm τ) | scoring path | borrowed language | **faithful** — same borrow as PS scoring. |
| `sceneOf[scene]` | value-fn (boundary) | `story_tab.py:80 (_extract_scene_phrases)` | per-language scene JSON | **deferred** — fixture now; a `StoryLibrary` store later. |

### Verified
- `story_reader_test` — explicit assertions: a **PS regression guard** (PSActive's exact
  ready-sets at 5 states, proving PS is unchanged), per-mode port sets, the
  **mode-switch-preserves-position** property, end-to-end capture → VocabTable, and §5
  the **select_item bounds** regression (your interleaved trace now scores the real item).
- `composition_test` (StoryReader/StoryBrowse/StoryPractice registered; settled ready set),
  `merge_defined_test` (story ports in the parity set), `grouping_test` (StoryReader a clean
  group), `walk_sequences_test` (`story-browse`, `story-practice` complete on both engines).
