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
- The mode-specific ports are spliced via a bare `call[…]` summand gated by the mode
  guard — the same idiom PS uses to splice `PSActive`.
- Capture from a scene → **`vocabUpsert` → VocabTable** (the SAME store channel Quick
  Practice capture uses). Scoring borrows the language from Helm on **`langRead`**.
  Both are existing restricted channels — StoryReader adds **no new** sync channels.
- User-facing loop ports are **`story_`-prefixed** (`story_recording_made`, …) so they
  are distinct controls from Quick Practice's (the app's `key_prefix="story"`); the
  `vocabUpsert`/`langRead` channels stay unprefixed (store/Helm channels, shared).

## Why the loop isn't a single shared definition

The plan asked to *factor* the practice loop into ONE definition reused by PS and
StoryReader. It was attempted (a `practiceLoopSummands` builder splicing a `Sequence`
of guarded summands into both bodies) and **abandoned** — a genuine
framework-boundary case (`docs/CLAUDE.md`: framework difficulty is research data):

- `defineAgent` is `HoldRest`; the engine's two readers treat guard conditions
  **oppositely**. `transNamed[if[c_,p_]] := If[c,…]` needs a NAKED, already-evaluated
  Boolean (it reads the raw body, ReleaseHold'd with **concrete** params).
  `buildSystem`/`transVP` build a **parametric** mu-term with params **symbolic**, and
  rely on `prepBody` to `Hold`-wrap the conditions that are **syntactically present in
  the stored body**.
- A runtime/builder-produced body defeats this: `prepBody` runs **before** the builder
  expands, so it cannot wrap the conditions. Expanding the builder at define-time
  instead makes conditions visible — but then they evaluate against the bare param
  **symbols**, and several reduce **wrongly**: `Length[phrases] ⇒ 0` (a symbol is
  atomic), `rec === none ⇒ False`. Shape-gated predicates (`hasNext[_List,_]`,
  `recEmpty`) dodge those, but other intermediate states then leave the guard
  *stuck* (`If[unevaluated,…]`) under composition.

Net: the engine's guard mechanism assumes conditions are **hand-written in the stored
body**. So the loop is written per context (`PSActive`, `StoryPractice`), and reuse is
at the **value-function** level (`targetOf`, `evaluate`, `scored`/`recorded`) — which
is where the real logic lives. A single-definition factoring would need an engine
change (e.g. `transNamed[if]` doing `ReleaseHold`, or a define-time code-gen macro
with `Hold`-surgery). Recorded as a finding, not worked around silently.

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
| `StoryPractice` loop | ports (in) | `story_tab.py:165 (render_scene_practice_mode)` → `render_practice_interface` | the practice pane | **simplified** — mirrors `PSActive`; one position, not a separate index. **deviation**. |
| `story_capture_vocab → vocabUpsert` | sync (→ VocabTable τ) | `story_tab.py:55 (capture_vocab_entry)` | scene capture | **faithful** — direct store write, same channel as PS capture. |
| `story_attempt_made → langRead` | sync (Helm τ) | scoring path | borrowed language | **faithful** — same borrow as PS scoring. |
| `sceneOf[scene]` | value-fn (boundary) | `story_tab.py:80 (_extract_scene_phrases)` | per-language scene JSON | **deferred** — fixture now; a `StoryLibrary` store later. |

### Verified
`composition_test` (StoryReader/StoryBrowse/StoryPractice registered; settled ready
set), `merge_defined_test` (story ports in the parity set), `grouping_test` (StoryReader
a clean group), `walk_sequences_test` (`story-browse`, `story-practice` complete on both
engines — the latter drives the `langRead` + `vocabUpsert` τs and position preservation).
