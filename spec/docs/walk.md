# walk.md
## The interactive `walk` harness — living with the spec as it evolves

`walk` lets a human drive the executable CCS spec: step through transitions,
**play the user** by feeding real values into input ports as they become ready,
watch each state through the data-compaction views, and record/replay traces.
It's built from Wolfram `Dynamic`, and it's how you *use* the spec rather than
just read it — the human is the open environment supplying the inputs that make
the value-functions compute.

Files: **`spec/walk.wl`** (substrate + Dynamic widgets, loads `walk-tests.wl`),
**`spec/walk-tests.wl`** (the test batch), tests in `spec/tests/walk_test.wls`
and `spec/tests/walk_sequences_test.wls`.

---

## Loading and running

In a notebook, from **your own checkout** (not a worktree):

```wolfram
Get[".../spec/MiolingoSpec.wl"];   (* engine + spec, in order *)
Get[".../spec/walk.wl"];           (* the harness + walkTests *)

walkUI[mioCore]                                       (* GROUPED by component (auto) *)
walkUI[mioCoreD, "TransitionFunction" -> transNamed]  (* grouped; compact call form *)
walkMio[]   walkMioD[]                                 (* shorthands for the two above *)
walkUI[call["Vocab", signedIn, {}, alpha, none, none], "TransitionFunction" -> transNamed]  (* bare agent: flat *)
```

Grouping is **automatic**: `walkUI[term]` groups by component whenever `term` is
a **registered composed system** (the registry maps a system term to its
decomposition; `mioCore`/`mioCoreD` register themselves). A bare/unregistered
agent falls back to one flat list. To group your own composed system, either
register it (`registerWalkComponents[term, components]`) or pass
`"Components" -> components` explicitly (the same `{name->call,...}` list `merge`
uses; `"Components" -> {}` forces a flat list).

`MiolingoSpec.wl` self-locates the rest (see `paths.wl`), so loading from any
checkout works; just point the entry `Get` at the checkout you want to test.

The panel shows, top to bottom:
- **Current state** — the CCS process term (`foldAgentDisplay`), *where you are*.
  **Collapsible** (an `OpenerView`, closed by default) so the term doesn't eat
  space; the open/closed state persists across steps.
- **Data view** — the published `view!` projections (`vocabView`/`pSView`, or the
  bare `view`), rendered as the *computed* data through `linearizeGrid`.
- **Outside the model** — a collapsible *incompleteness inventory* (`$walkCloud`):
  data the agents **read but don't own** because its owner isn't modelled yet
  (`enrichOracle` / `recognisePhonemes` knowledge, vocab persistence, stats /
  history). A standing reminder the agents aren't complete in themselves; it
  **shrinks** as owners are modelled (the language left it once `langRead`
  brought it in-model). Each item **lights up (●)** when a currently-ready action
  would consult it — so the cloud changes as you walk.
- **Transitions** — one clickable row each; hover shows *→ goes to:* the
  derivative. Value-carrying input ports get an inline field. Under `walkMio[]`
  (or any `"Components"`) they are **grouped into a frame per providing
  component** (Helm / PS / Vocab), **inputs before outputs** in each frame; internal
  syncs go in an *internal (τ)* frame. The port→component map is a pure syntactic
  scan of each agent's sort (`componentPortMap`), so it needs no execution and
  can't be fooled by guards; dual restricted actions (`vocabUpsert`/`goPractice`/`langRead`)
  only ever appear as τ, so they never split across frames.
- **Back / Forward / Reset**, a **`Test:` menu + `Run test`** (see below), and
  the **condensed trace** (with Copy). **Back** and **Forward** scrub a run: step
  back through the states you've visited and forward again — handy after
  `Run test` to watch what each step of a sequence reveals. (A fresh manual step
  or `Run test` clears the forward/redo line.)
- **Auto-advance internal syncs (maximal progress)** — a checkbox. When on, the
  harness fires the system's internal synchronisations (`vocabUpsert`, `goPractice`, and
  `langRead` — the borrowed-language pull on `autofill` and on `attempt_made`
  scoring) for you between your actions, until the state is τ-stable,
  so you only ever click *external* ports. It's a **simulation strategy, not a
  language change** (`autoTau` in `walk.wl`): it just chooses how to walk the
  existing transition system. The meta-agent split — you play the *user* (and the
  *world*, via input values); the simulator plays the *system*. Every auto-fired
  τ is still **recorded in the trace and is Back-steppable**, so nothing is
  hidden. If two internal syncs are ready at once (a real nondeterministic
  choice) it **stops and hands back to you** rather than pick silently. See
  ARCHITECTURE.md → *Borrowed vs owned data* for why this is sound.

---

## Supplying values by hand

Each value-carrying input port has an `Expression` input field. Type a Wolfram
value, **press Enter (or Tab out) to commit**, then click the row. Conventions:

| port kind | type this | note |
|---|---|---|
| word (`add`, `capture_vocab`, `set_filter`) | `"souris"` | **quote strings** — bare `souris` is a *symbol* and `validateWord` rejects it |
| capture payload (`add`, `vocabUpsert`) | `<|"word"->"souris", "translation"->"mouse"|>` | needs a `"word"` key (vocab shape, not the practice `"text"`) |
| sort (`set_sort`) | `alpha` / `recent` / `oldest` | the Enum **symbols**, unquoted |
| id (`delete`, `autofill`, `begin_edit`) | `1` | integer |
| import (`import_bulk`) | `<|"contents"->"(en,fr)\nsouris|mouse", "expectedTarget"->"fr"|>` | header `(src,tgt)` then `word\|translation\|ipa\|source\|url` rows; target must match |
| phrases (`load_material`) | `{<|"text"->"chat","translation"->"cat","ipa"->"ʃa"|>}` | the practice `"text"` shape |

An untouched field steps the port symbolically (binder left free).

---

## Test sequences — driving with no typing

`walk-tests.wl` defines **`walkTests`**, an `Association` of named *plans*. A
plan is a list of:

- `vis["port"]` — a visible action with no value;
- `vis["port", value]` — a value-carrying input, value supplied;
- `tau["chan"]` — an internal sync (`goPractice`, `vocabUpsert`).

Run one from the GUI: pick it in the **`Test:`** menu and click **`Run test`** —
it replays the whole plan from the initial state, setting the data view and the
condensed trace, **with no typing**. Or headless:

```wolfram
walkSteps[transVP,   mioCore,  walkTests["full-roundtrip"]]
walkSteps[transNamed, mioCoreD, walkTests["full-roundtrip"]]
```

### The batch (naming / classification)

Kebab-case keys, prefixed by scope:

| prefix | meaning | sequences |
|---|---|---|
| `vs-*`   | Vocab-only ports | `vs-capture`, `vs-import`, `vs-edit` |
| `ps-*`   | PracticeSession-only ports | `ps-navigate`, `ps-score` |
| `sync-*` | one cross-component sync (composed-only) | `sync-practise`, `sync-vadd` |
| `full-*` | end-to-end, both syncs | `full-roundtrip` |

Together they exercise **every** Vocab and PS port and both syncs.

### Adding a sequence

Add an entry to `walkTests` under the right prefix, ≤ ~10 actions, with embedded
values (quote strings, Enum symbols for sort, integers for ids, Associations for
payloads). **The standing rule:** it must run to completion on *both* `mioCore`
(`transVP`) and `mioCoreD` (`transNamed`). `tests/walk_sequences_test.wls`
enforces this for every sequence; run it after editing the batch.

### Typing your own trace (the `Trace:` field)

To run a one-off trace **without** adding it to `walkTests`, type a plan straight
into the **`Trace:`** field and click **`Run trace`**. It's the *same format* as a
`walkTests` entry — a Wolfram list of plan entries:

| entry | meaning | example |
|---|---|---|
| `vis["port"]` | a visible action, no value | `vis["story_attempt_made"]` |
| `vis["port", value]` | a value-carrying input | `vis["set_mode", practice]`, `vis["select_item", 0]` |
| `tau["chan"]` | force one internal sync (rarely needed) | `tau["vocabRead"]` |

**You normally do NOT type the τ's.** Run trace uses maximal progress (`AutoTau`):
the internal synchronisations (`vocabUpsert`, `goPractice`, `langRead`, `vocabRead`)
fire automatically *between* your visible actions. List only what a *user* would do.
(`tau["chan"]` is there only for the rare case where two internal syncs are both
enabled and you want to force a specific one.)

Values follow the data: strings in quotes (`"chat"`); the sort/mode **enum symbols**
bare (`practice`, `browse`, `alpha`); integers for indices/ids (`0`); Associations
for payloads (`<|"word" -> "chat"|>`); and a *list* of phrase Associations for
`load_material`. Example — load a word, practise it, capture it:

```wolfram
{vis["load_material", {<|"text" -> "chat", "translation" -> "cat", "ipa" -> "ʃa"|>}],
 vis["recording_made", "audio"],
 vis["attempt_made"],
 vis["capture_vocab", "chat"]}
```

The trace **runs from the initial state** (like `Run test`), so it's fresh and
repeatable. The status text beside the button shows the parsed action count, or warns
if what you typed isn't a list of `vis[…]`/`tau[…]`. The **Short trace** checkbox
truncates bulky values in the event log.

---

## The substrate (headless-testable)

- `supplyValue[trans, val]` — insert a value into an input transition's binder
  via the engine's scope-aware `substVv` (not `ReplaceAll`). No validation; the
  spec's own functions judge the value.
- `readyTransitions` / `inputBinderOf` / `valueInputQ` / `readyInputs`.
- `vis[nm, val]` — value-carrying plan entry (an additive `walkResolve`
  downvalue) so `walkSteps` runs value-driven plans.
- `viewProjections` / `dataView` / `stateDisplay` / `traceView` — the displays.
- Reused from `discipline.wl`: `walkSteps`, `eventLog`, `condense`,
  `eventLogForm`, `linearizeGrid`, `replayTrace`.

All have `::usage`, so `?walkUI`, `?supplyValue`, `?walkTests`, `?loadEngine`,
… resolve in a notebook.

---

## Notes / gotchas

- **Value-function ports need a real value.** `set_filter`/`set_sort`/`begin_edit`
  drop the binder into a slot/constructor, so they visibly change a field even
  with the binder *unsupplied* (showing `filterBy[q]`, `editingRow[id]`). `add`
  drops it into `addEntry`, which won't compute on a bare symbol — so `add` only
  shows a change once a valid value is supplied. (It's the honest one.)
- **`view` vs `View`.** `viewProjections` matches the view suffix
  case-insensitively, so both the bare agent's `view` and the relabelled
  `vocabView`/`pSView` are picked up.
- **Syncs are composed-only.** `goPractice`/`vocabUpsert` are restricted internal channels;
  the `sync-*`/`full-*` sequences run on `mioCore`/`mioCoreD`, not Vocab/PS alone.
- **Deferred.** A cleaner value-supply route — giving `transVP` a parameter that
  derives an input transition *with* the substitution inline (supply-then-derive)
  instead of precompute-then-`substVv` — is noted for the future.

## Verification

- `spec/tests/walk_test.wls` — the substrate (`supplyValue`, scope-correctness,
  `viewProjections` finds the bare `view`, the value-driven plan path).
- `spec/tests/walk_sequences_test.wls` — every `walkTests` sequence completes on
  both compositions, and the syncs move data.
- GUI rendering is notebook-side (it can't be exercised headlessly).
