# miolingo — Architectural Record

## Governing Principle

miolingo's behaviour is specified in value-passing CCS as a network of agents, each visible only through named, typed ports. The port signature is the contract; everything else is subordinate. All UI implementations are derived from, or verified against, this spec. The spec is the authority.

## The Agent / Port Model

- Each component is an agent with hidden internal state.
- An agent exposes input and output ports, each carrying a typed value.
- Output: on synchronisation, a value computed from current state is delivered; state may change as the agent's own definition dictates.
- Input: on synchronisation, a value is received and incorporated, directly or via a derived state change.
- The partner across any port may be another agent or an external client (UI, test harness, user) — symmetric, unprivileged.
- The agent is visible only at its ports. No other channel exists.

**Sort vs ready set.** The *sort* is an agent's full port alphabet — every presentation L2/L3 must be able to produce. The *ready set* is the subset offered in the current state, fixed by guarding. Control enablement is therefore L1-derived: the skin renders the ready set, it does not decide it. Because guards are state-dependent, the ready set cannot be precomputed in general; the live agent encoding must compute its afforded ports on the fly from current state, and the skin queries and renders them.

**Read-only views.** A state display is an output-only port carrying a published projection, `view!(f state)` — never raw state. The projection `f` is an L1 decision; its rendering is L2/L3. Reflective views (showing the agent's own definition) are a distinct projection and a distinct port.

## The Three Levels

### L1 — Semantic Specification

- Language: value-passing CCS
- Location: `/spec/*.ccs` (i.e. sibling of this `docs/` directory)
- Executor: Wolfram/RCA (existing codebase), via WolframScript bridge at `/spec/wolfram/`
- Defines: agents, ports, value types, guard structure (hence ready sets), published projections
- Governed by: human architect (agent-assisted drafting permitted; human reviews and owns)

### L2 — Abstract Interaction Form

How each port is presented, in framework-independent vocabulary derived from L1:

| Port shape | Example realisations |
|---|---|
| Finite-choice input | tabs, radio buttons, dropdown |
| Sequential input | wizard, paged flow |
| Free-form input | text field, IPA input |
| Confirmation input | dialog, inline confirm |
| Scalar projection (output) | progress bar, score display |
| Collection projection (output) | scrollable list, table |
| Non-ready port rendering | greyed-and-inert, or hidden |

Location: `/spec/interaction-forms.md`. Governed by: human designer.

### L3 — Skin

- Framework-specific widget implementation and styling
- Swappable without modifying L1 or L2
- Location: `/spec/skins/{skin-name}/`
- Agent-executable under the L2 contract
- Multiple skins may coexist against the same spec

## Component Inventory (preliminary)

Two tiers: **interactive agents** (UI-facing) and **store agents** (the data tier — one per DB table; see Naming note below).

| Component | CCS agent family | Kind | Priority |
|---|---|---|---|
| Practice Session | `PracticeSession` (PS) | Interactive — tight interaction loop | High — **recovered** |
| Vocabulary tab | `Vocab` | Interactive — the gated viewer/editor (holds no data) | High — **recovered** |
| Session / language | `Helm` | Interactive — finite-choice settings; **owns the (source, target) language pair** | **recovered + composed** ‡ |
| Vocab store | `VocabTable` | **Store** — the persisted vocab collection (DB `vocab_entries`) | **recovered + composed** |
| Story Reader | `StoryReader` | Interactive — narrative nav + 3 modes; practice mode reuses the factored `PracticeLoop` | Next |
| Stats / History † | (read projections over a `Ledger` store) | view ports backed by store queries — **not** standalone interactive agents | Medium |
| Mode Navigation | ~~`ModeSelector`~~ **eliminated** | each mode carries its own *visible* entry instead | — |

Correction from the previous draft: the read-only "displays" are most likely *view ports on* the stateful agents (a published `view!` projection rendered by a skin), not agents in their own right. Promote one to a standalone agent only if it genuinely owns state; otherwise it is a presentation of another agent's projection. Decide this deliberately per component.

### Naming (2026-06-03 rename)

Store agents are named after their **table**, not generically, because table-faithfulness documents which component touches which table and pays off when rigging to the real DB. The interactive vocab agent is the **tab** (it stores nothing); the store is the **table**:

| Old | New | Why |
|---|---|---|
| `VocabStore` / `VS` (the *tab*) | `Vocab` | it's a viewer/editor — stored nothing after the (i) migration; the old name was the misnomer |
| `CargoHold` (the *store*) | `VocabTable` | per-table store, instance of the `Store[table, rows]` pattern |
| `chRead`/`chUpsert`/`chImport`/`chRemove`/`chAmend`, `vAdd` | `vocabRead`/`vocabUpsert`/`vocabImport`/`vocabRemove`/`vocabAmend` | table-scoped channels (multiple stores can't share generic `ch*` — a reader couldn't route). `vAdd` (PS capture) collapsed into `vocabUpsert` (same upsert, two writers) |
| `vSView` (view port) | `vocabView` | follows the `decap[name]<>"View"` rule |

`Helm` keeps its nautical name (it's a controller, not a store). Future store tables follow the same scheme (`Ledger`/`AttemptTable`… for stats/history).

**‡ Helm and how the language reaches its consumers.** Helm is composed into
`mioCore` as a **pure parallel** agent (no restricted sync): it *owns* the
`(source, target, tts, speed)` tuple and *publishes* it as `helmView`, exactly
mirroring `language_state.py` (the sidebar is the sole owner; everyone else
reads via `read_source_lang` / `read_target_code` / `read_training_lang`). That
owner→reader split **is** the `view!` discipline.

Crucially, Vocab and PS do **not** receive the language through any port. No
**control guard** in Vocab/PS branches on it (logical-clock precedent: a value no
guard reads is *data*, not control), so it is not threaded as a sync. It
reaches the vocab/practice sides **indirectly, through the oracle boundary**:
the g2p/IPA, translation/enrich and TTS oracles (live oracles, not modelled
agents) read `helmView` for the `(source, target)` pair, and the *result* of
that — an IPA string, a translation, audio — enters Vocab/PS baked into the value
of an ordinary input port (`add` already carries an `ipa`; `load_material`
already carries translations). The language selects *which* oracle output,
upstream of the port.

Today that oracle→`helmView` read is still **implicit** (test data carries
pre-baked `ipa`/`translation` values, correct by fiat). Making it explicit — the
oracle call reading `(source, target)` from `helmView` — is now a **decided**
matter: see **Borrowed vs owned data** below. In short, the consuming action
*pulls* the language fresh through an internal port at the point of use; it is
**not** pushed into a Vocab/PS cache. The one place a setting already gates a port
is `set_speed` (`if[tts === espeak, …]`) — a genuine **control** dependency, but
on Helm's *own* state, so internal. The day a Vocab/PS port's *readiness* comes to
depend on the language, **that** edge must enter the model as a restricted sync —
and, being a guard over *borrowed* data, is the one case that may force a
calculus extension (see below).

**† Stats / History and the external store (a rigging issue).** Treating these as *view ports* is correct only under the current modelling assumption that each component stores its own domain data in-process. In any sensible implementation, stats and history are retrieved from an **external store**, not held by the component. Rigging that external store into the system — where the data lives, who reads/writes it, how a view port is backed by a *query* rather than in-process state — is a key **rig** concern, and the question of *how* it is done may itself need to enter the model (an external-store agent / port), not be left wholly to L3. Flagged for when stats/history (and persistence generally) are recovered.

## Borrowed vs Owned Data (decision)

When one component needs data another component owns — Vocab/PS needing Helm's
`(source, target)` to enrich/score — the rule is:

> **Own it → store it. Borrow it → fetch it fresh, at the point of use.**

A component keeps the data it *owns* in its own state (Vocab's entries, sort,
filter; PS's position). It **never caches data another component owns**; it reads
that through a port, as a prefix of the action that needs it.

**Why not push-to-cache.** The tempting model — Helm pushes each change into a
Vocab/PS replica, which then reads locally — is **not faithfully expressible in
pure CCS**. CCS has no priority: an offered synchronisation is declinable while
the agent has any other transition. So with a cache, the run

```
set_target(pt) · Vocab.autofill[reads stale "fr"] · langToVS(pt)
```

is a legal trace — the refresh is not forced before the stale read. The very
asynchrony that makes CCS clean removes the "write is immediately visible"
guarantee a shared-memory framework (Streamlit) gives for free. A cache of
borrowed data cannot be kept coherent without leaving the calculus.

**The mechanism: pull-on-use, forced by prefix.** Instead, the read sits on the
*critical path* of the consuming action:

```
Helm:  … + langRead!(source, target) · Helm        (* persistent internal read port, a self-loop *)
Vocab:    autofill?(id) · langRead?(s,t) · ⟨enrichOracle[word, s, t]⟩ · Vocab′
PS:    attempt_made  · langRead?(_,t) · ⟨recognisePhonemes[audio, t]⟩ · …
```

`langRead` is **restricted** in `mioCore` (an internal τ, like `vocabUpsert`/`vocabRead`).
The consumer cannot complete the enrich/score without first taking it, and what
it reads is necessarily Helm's *current* value — there is no local copy to be
stale. This is **forced by sequencing, not by priority**: it is the same idiom
`vocabUpsert`/`vocabRead` already use (a sync that is the only way for the agent to make
progress). Helm remains the **sole owner**; oracles stay boundary functions
(decision-A) but are now called *with* the language the read delivered.
`espeakG2P[word, voice]` already has this shape (`voice` = the target read).

*Status:* implemented for **both** borrowers, by the identical prefix-read, with
Helm's `langRead!` restricted in `mioCore`:
- **Vocab `autofill`** → `autofillIn[entries, id, lang]` → `enrichOracle[word, source, target]`;
- **PS scoring** (`attempt_made`) → `evaluate[target, rec, lang]` → `recognisePhonemes[audio, targetCode]`.

**External store (VocabTable) — the persistence counterpart, now modelled.** The
vocab collection is owned by the **VocabTable** agent (the DB), not held in Vocab.
Vocab is the **Vocabulary *tab*** — a *gated viewer/editor*: a VISIBLE entry
`open_vocab` (the user selecting the tab), then a `vocabRead` of the store, then the
view/edit actions; writes route to VocabTable (`vocabUpsert`/`vocabImport`/`vocabRemove`/
`vocabAmend`, all restricted → τ). Capture from practice writes the store **directly**
(`PS.capture_vocab → vocabUpsert → VocabTable`), not through the tab — matching the app
(`capture_vocab_entry` is a direct DB write).

**PS reads the store too — practise is a pull, not a push (2026-06-03).** PracticeSession
no longer receives a *pushed snapshot*. It reads VocabTable itself, by two visibly-guarded
entries that mirror `open_vocab`:
- **Pull** — `open_practice` (the visible quick-practice entry) → `vocabRead` → `PSBrowse`
  offers `load_vocab` (all) / `load_filtered(q)`, shaping the collection into the practice
  queue (`quick_practice_tab.py`'s "Load vocabulary"/"Load filtered").
- **Signal** — the vocab-tab "Practise these" (`Vocab.practise_vocab`) now emits
  `goPractice!(filter)` — the **filter only, not the entries** — and PS pulls the
  collection *fresh* (`vocabRead`) and shapes it. No snapshot crosses the boundary. Vocab, having
  navigated away, returns to its un-opened `open_vocab` entry (it does **not** re-read), which
  also leaves PS's pull as the unique enabled τ so the hand-off settles deterministically.
This replaced the old `pLoad` data-push: borrowed data (the collection) is pulled-on-use,
consistent with the rule below. The loaded queue PS then holds is a deliberate *session*
snapshot the user practices through — not a cache of borrowed data. Two design points this
settled:
- **Visible-guarding for congruence.** A *prefix-read* (Vocab's first action a `vocabRead`
  τ) put an **initial τ** in the composition, and `≈` fails to be a congruence over
  `+` exactly because of initial τ. Guarding the tab behind the **visible**
  `open_vocab` (no initial τ) keeps the system *initially stable* / visibly-guarded,
  so weak bisimilarity stays a congruence. (The `ModeSelector` idea was eliminated:
  each mode carries its own visible entry; no relay agent needed.)
- **Store vs tab.** Separating *the store* (VocabTable, always accepting writes) from
  *the tab* (Vocab, gated) is both faithful and what makes capture mode-independent.
  This is the persistence half of the `†` Stats/History note: when stats/history
  are recovered they read/write a store the same way.

**The one escape hatch.** Pull-on-use covers a *data* dependency (the value is
needed when an action runs). It does **not** cover a *control* dependency over
borrowed data — a guard whose ready set must change the instant Helm changes,
with no action in flight. That genuinely needs push, i.e. a calculus extension:
**priority / maximal progress** (Cleaveland & Hennessy; timed-process-algebra
maximal progress) or **broadcast** (Prasad's CBS, broadcast-π). We adopt none of
these now; they are reserved for the first borrowed-data *guard*. (`set_speed`'s
guard reads Helm's *own* state, so it is internal, not a borrowed-data guard.)

**Simulator note (a strategy, not a semantics).** The harness offers a
**maximal-progress toggle** (`autoTau`, `walk.wl`): between the user's actions it
auto-fires the unique enabled internal τ until the state is τ-stable (and stops,
handing back, if ≥2 τ are ready — a real choice is never silently resolved). This
is a *scheduling strategy over the existing LTS*, leaving the spec's transition
relation untouched; it does not introduce priority into the language. It embodies
the meta-agent split: the user plays the **user** (external inputs) and the
**world** (oracle return values); the simulator plays the **system** (internal
syncs). Every auto-fired τ is recorded in the trace and is Back-steppable.

**The "data cloud".** Any datum a component reads but that is owned by *nothing
yet modelled* (DB persistence, an oracle's internal knowledge) is, until given an
owning agent, shown in the simulator as an explicit **incompleteness inventory** —
a standing reminder that the simulated agents are not complete in themselves.
Pull-on-use removes the *language* from that cloud (it now flows through a real
port); what remains is the genuinely-external world, and it shrinks as each owner
is modelled (the DB becoming an agent being the large remaining one — it unifies
with the external-store note † above).

## Execution Model

- Single-user, single-threaded (current version).
- Qt direct signal/slot connections throughout; direct connections preserve CCS synchronisation semantics.
- Validation path: execute the CCS spec on the RCA executor and/or run CCS-derived test processes.
- Product path: a PyQt skin realises the port contract. Whether core logic is reimplemented natively or bridged to Wolfram at runtime is an open decision; the spec governs either way.
- Multi-user game variant: future work — concurrency (and possibly bigraph place-structure) introduced at L1 only when locality/mobility becomes load-bearing, not before.

## Framework Selection Criterion (hypothesis)

Prefer frameworks whose execution model is compatible with the port/ready-set model. The sharp form: a view port emitting on state-change *is* a Qt signal, and a ready set *is* the set of currently connected/enabled slots; Streamlit's whole-script rerun only simulates both. Qt is therefore preferred not on taste but because it has native constructs for the view port and the ready set, whereas Streamlit fakes them. Under empirical investigation, not yet confirmed.

## Port Boundary Criterion

A port exists where the agent deliberately exposes a typed data exchange — an input it accepts, or a projection of state it publishes — that advances the protocol or is observable by a partner. Not every widget signal; only exchanges the agent chooses to make part of its contract.

Example for Practice Session: `attempt_made` (in), `evaluation` (out, a projection), `next_item_requested` (in) — not individual keystrokes or field updates.

## What Agents May and May Not Do

### Permitted

- Implement L3 skin code given L2 interaction-form declarations.
- Generate Qt bindings for declared ports, including ready-set rendering (enablement) and view-port projections.
- Write WolframScript bridge code for specified port types.
- Generate test-harness code from spec-derived traces and ready sets.
- Assist in *drafting* CCS under explicit human review (the human owns and signs off L1).

### Not Permitted

- Treat old Streamlit code as a source of semantic truth.
- Infer component dependencies from existing code rather than from ports.
- Refactor across architectural layers in a single session.
- Invent control enablement instead of rendering the ready set.
- Expose agent state other than through a declared port/projection.
- Proceed without a declared L2 interaction form for each port in scope.

## Open Problems

- Formal definition of the binding-layer protocol, including the mandatory afforded-ports operation each encoding must compute on the fly, and how to verify it matches `init(P)` at every reachable state.
- Precise vocabulary and grammar of L2 interaction forms, including non-ready-port rendering.
- Handling framework constructs with no clean CCS analogue.
- Automated verification of L3 against L1 via ready-set / testing equivalence.
- The point at which the multi-user variant forces locality into L1 (bigraph adoption threshold).
