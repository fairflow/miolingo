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

walkMio[]                                             (* RECOMMENDED: grouped by component *)
walkMioD[]                                             (* the transNamed/mioCoreD twin *)

walkUI[mioCore]                                       (* mu-term, transVP default; ungrouped *)
walkUI[mioCoreD, "TransitionFunction" -> transNamed]  (* compact call form *)
walkUI[call["VS", signedIn, {}, alpha, none, none], "TransitionFunction" -> transNamed]  (* a bare agent *)
walkUI[mioCore, "Components" -> mioComponents]         (* what walkMio[] expands to *)
```

`walkMio[]` is the usual entry point: it groups the transitions by component
(below). `walkUI[mioCore]` alone gives one flat list. The `"Components"` option
takes the same decomposition `merge` uses (`mioComponents` in `MioCore.wl`).

`MiolingoSpec.wl` self-locates the rest (see `paths.wl`), so loading from any
checkout works; just point the entry `Get` at the checkout you want to test.

The panel shows, top to bottom:
- **Current state** — the CCS process term (`foldAgentDisplay`), *where you are*.
  **Collapsible** (an `OpenerView`, closed by default) so the term doesn't eat
  space; the open/closed state persists across steps.
- **Data view** — the published `view!` projections (`vSView`/`pSView`, or the
  bare `view`), rendered as the *computed* data through `linearizeGrid`.
- **Transitions** — one clickable row each; hover shows *→ goes to:* the
  derivative. Value-carrying input ports get an inline field. Under `walkMio[]`
  (or any `"Components"`) they are **grouped into a frame per providing
  component** (Helm / PS / VS), **inputs before outputs** in each frame; internal
  syncs go in an *internal (τ)* frame. The port→component map is a pure syntactic
  scan of each agent's sort (`componentPortMap`), so it needs no execution and
  can't be fooled by guards; dual restricted actions (`vAdd`/`pLoad`/`langRead`)
  only ever appear as τ, so they never split across frames.
- **Back / Forward / Reset**, a **`Test:` menu + `Run test`** (see below), and
  the **condensed trace** (with Copy). **Back** and **Forward** scrub a run: step
  back through the states you've visited and forward again — handy after
  `Run test` to watch what each step of a sequence reveals. (A fresh manual step
  or `Run test` clears the forward/redo line.)
- **Auto-advance internal syncs (maximal progress)** — a checkbox. When on, the
  harness fires the system's internal synchronisations (`vAdd`, `pLoad`, and
  `langRead` — the borrowed-language pull on `autofill`) for you between your
  actions, until the state is τ-stable,
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
| capture payload (`add`, `vAdd`) | `<|"word"->"souris", "translation"->"mouse"|>` | needs a `"word"` key (vocab shape, not the practice `"text"`) |
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
- `tau["chan"]` — an internal sync (`pLoad`, `vAdd`).

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
| `vs-*`   | VocabStore-only ports | `vs-capture`, `vs-import`, `vs-edit` |
| `ps-*`   | PracticeSession-only ports | `ps-navigate`, `ps-score` |
| `sync-*` | one cross-component sync (composed-only) | `sync-pload`, `sync-vadd` |
| `full-*` | end-to-end, both syncs | `full-roundtrip` |

Together they exercise **every** VS and PS port and both syncs.

### Adding a sequence

Add an entry to `walkTests` under the right prefix, ≤ ~10 actions, with embedded
values (quote strings, Enum symbols for sort, integers for ids, Associations for
payloads). **The standing rule:** it must run to completion on *both* `mioCore`
(`transVP`) and `mioCoreD` (`transNamed`). `tests/walk_sequences_test.wls`
enforces this for every sequence; run it after editing the batch.

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
  `vSView`/`pSView` are picked up.
- **Syncs are composed-only.** `pLoad`/`vAdd` are restricted internal channels;
  the `sync-*`/`full-*` sequences run on `mioCore`/`mioCoreD`, not VS/PS alone.
- **Deferred.** A cleaner value-supply route — giving `transVP` a parameter that
  derives an input transition *with* the substitution inline (supply-then-derive)
  instead of precompute-then-`substVv` — is noted for the future.

## Verification

- `spec/tests/walk_test.wls` — the substrate (`supplyValue`, scope-correctness,
  `viewProjections` finds the bare `view`, the value-driven plan path).
- `spec/tests/walk_sequences_test.wls` — every `walkTests` sequence completes on
  both compositions, and the syncs move data.
- GUI rendering is notebook-side (it can't be exercised headlessly).
