# Rig — a binding language for (more) automatic app generation

A design + working prototype for the **rig**: the L2→L3 layer the methodology
names but hasn't built — *"you rig a port to a control"*
(`spec/docs/METHODOLOGY.md`, `methodology-and-skill-suite.md`). This is written
against the Swift/macOS skin but the model is **platform-neutral on purpose**,
because the goal is multi-platform generation from one spec.

Status: prototype implemented and exercised on the **Helm** component — see
`Sources/MiolingoCore/Rig.swift` (the neutral model), `Sources/Miolingo/RigLoft.swift`
(the SwiftUI loft + Helm berth + driver), and the **Settings → "Rig preview"**
section in the running app (the Helm settings UI *generated* from a declaration).

---

## Where the rig sits (recap of what L1 already gives)
- **Sort** = the full static port alphabet a presentation must cover.
- **Ready set / afforded-ports** = the subset live in the current state, answered
  on the fly by the component (`readyPorts`). *Enablement is L1-derived; the skin
  renders the ready set, it does not decide it.*
- **Skin** = L2+L3, a separately deployable presentation artefact.

The rig is the missing middle: a **typed, declarative binding** from ports to
abstract controls, plus a per-platform renderer. It is **static (over the whole
sort)**; the ready set gates it **at runtime**. The two compose and stay distinct.

## Invented vocabulary (nautical, to match rig / walk / helm / hold)
| term | meaning |
|---|---|
| **Plimsoll** | the payload **type** language — the "load line": what a port may carry |
| **Cleat** | a **typed port**: `name + role + Plimsoll type`. The fixed point you rig a control onto. The sort is a set of Cleats. |
| **Fitting** | an abstract **control kind** (button, field, choice, …). Rigging maps Cleats → Fittings. |
| **Berth** | a component's surface: its group of Cleats. |
| **Loft** | a **per-platform renderer** of Fittings → native widgets (`SwiftUILoft`; a `ComposeLoft`/`WebLoft` would consume the same Berth+Rig). |
| **Rig** | the map `Cleat → Fitting` (+ options). One entry changes one control. |

## Plimsoll — the type language (precise, multi-platform)
| type | meaning | typical fitting |
|---|---|---|
| `unit` | no payload | (trigger) → button |
| `bool` | a flag | toggle |
| `int` | an integer | stepper / field |
| `bounded(lo,hi)` | an int in a closed range | slider / stepper |
| `text` | free text | text field |
| `word` | a single token (shape hint) | text field |
| `code(domain)` | a value from a closed set; `domain` = `fixed([Choice])` or `dynamic(source)` | choice (segmented/radio/menu/tabs/sidebar) |
| `index(of: cleat)` | a position into a list projection | selection over that collection |
| `record([field])` | an ordered field set | panel |
| `list(T)` | a collection | collection |
| `audio`, `blob` | opaque media | (custom) |

**Role** (from the port-boundary analysis): `trigger` (value-less input),
`input(Plimsoll)` (value-carrying input), `projection(Plimsoll)` (read-only view).
Internal/restricted channels (the τ's) are below the UI boundary and are never rigged.

The held-until-concrete gates in the spec (`target_String`, `id_Integer`,
`entries_List`, `_Association`) **are Plimsoll types in disguise** — promoting them
to first-class Cleat types is exactly what lets a loft derive the boundary.

## Fittings and the "one-line re-skin"
A `Fitting` is `button | textField | stepper | slider | toggle | choice(Style) |
panel | collection`, with `ChoiceStyle = segmented | radio | menu | tabs | sidebar`.
The **Rig** chooses the realization, so *radio vs tabs is one line*:
```swift
defaultHelmRig["set_tts"] = .choice(.segmented)   // → .radio → .menu → .tabs …
```
And because Cleats are typed, an **unrigged** berth still renders: the loft picks a
**default fitting from the type** (`code → menu`, `bounded → slider`, `text → field`).
So types alone give a usable UI; the rig only customises. *That* is the automation.

## The generation pipeline (what's automatic vs authored)
```
spec sort ─▶ Cleats (typed ports)          [derived from the port interfaces]
            + afforded-ports (L1, runtime) [the component answers readyPorts]
            ─▶ default Fittings from types [automatic]
            ─▶ Rig overrides               [authored, tiny]
            + Deck-plan (layout)           [authored — see limitation 1]
            ─▶ Loft renders per platform   [one loft per target]
```
Authored per app: a small Rig + a layout. Everything else derives from the typed
sort + the L1 ready set. One Berth+Rig → many lofts.

## What the prototype actually taught me (Helm)
- **It works and it informs coding.** Declaring 5 Cleats + a 5-line Rig generated
  the whole Settings pane, including the `view` projection rendered from
  `record([...])`. Writing the generic loft once was comparable effort to one
  hand-written tab, and the *second* component would be nearly free.
- **Afforded-ports dropped in cleanly.** `driver.afforded()` hides `set_speed`
  unless `tts == espeak` — the same L1 guard as the hand-written `showsSpeed`.
  Confirms "rig over the sort, ready set gates at runtime."
- **Typing pays its way immediately.** The default-fitting fallback meant I didn't
  even need a Rig entry per cleat to get something sensible.

## Limitations (honest, and what each implies)
1. **Layout is orthogonal and *not* captured.** A Rig says *what kind* of control,
   not *where*. The loft just stacks Cleats in declaration order; the hand-written
   `SettingsView` groups into Sections. → needs a separate **deck-plan** grammar
   (grouping, order, panes, responsive rules). This is the biggest missing piece.
2. **Semantic refinement isn't in the type.** `word` is a shape hint; `validateWord`
   (punct-only, length) is a value-function guard. Plimsoll is shape+domain, not
   refinement predicates. → either keep validation in L1 (current) or add refinements.
3. **Stateful sub-flows aren't a single Cleat.** `open_practice → PSBrowse`'s
   load-vocab/load-filtered choice is a transient sub-surface. → needs **berth
   nesting / wizards** (a Cleat whose activation reveals a child Berth).
4. **Cross-port references** (`index(of: phrases)` couples `select_item` to a list
   projection) are *typed* but not *enforced*; a checker should verify the referent.
5. **Projection sub-rigging.** A `panel` renders key/value fine, but a `collection`
   (the vocab table with per-row Autofill/Edit/Delete) needs **field-level rig +
   per-row trigger rig**. Prototype does flat rows only.
6. **Fitting applicability is context-sensitive.** `tabs`/`sidebar` suit the
   *component switcher* (a `choice` over components) but not an inline settings
   choice. → Fittings need **applicability constraints** per role/type/cardinality.
7. **Inputs are events, not two-way bindings.** SwiftUI wants `Binding`; CCS inputs
   *emit* (produce a successor), they don't mutate shared state. The prototype
   bridges with `Binding(get: driver.value, set: driver.emit)`, which works but the
   "set" is really an emit — for pure triggers like `select_item` the binding shape
   is awkward. The model keeps `emit` to stay faithful.
8. **Multi-platform value encoding.** `PlimValue` is the canonical wire form across
   the loft boundary; a non-Swift loft needs it serialized (JSON-ish). Codes,
   audio, locale strings need canonical representations.
9. **Actor isolation friction.** The driver crosses into the `@MainActor` model;
   the prototype uses `MainActor.assumeIsolated` (UI-thread only). A real codegen
   would emit main-actor-isolated drivers.

## Necessary affordances (minimal set to cover miolingo)
Roles: `trigger`, `input`, `projection`. Fittings: `button`, `textField`,
`stepper`/`slider` (for `bounded`), `toggle`, `choice` (segmented/radio/menu/tabs/
sidebar), `panel` (record), `collection` (list + per-row triggers), and the
**component switcher** (a `choice` over component ids → tabs | sidebar | radio).
That set renders every current miolingo surface.

## Toward a precise typing language for the multi-platform effort
The cleanest next step is to make **Plimsoll the single source of port types**,
authored alongside the spec (or extracted from the held-until-concrete gates), and
to add: (a) a **deck-plan** grammar for layout; (b) **refinements** on scalars
(`word`, ranges) so validators generate too; (c) **berth nesting** for sub-flows;
(d) **applicability constraints** on fittings. With those, `Berth + Rig + Deck-plan`
becomes a complete, platform-neutral UI declaration that any loft can realise —
app generation that is mostly mechanical, with the spec still governing behaviour.
