# The miolingo CCS-recovery methodology, and a skill suite to generalise it

*A research/synthesis deliverable. Part 1 crystallises the methodology as actually practised (every claim cited to the records). Part 2 designs the Claude skill suite that would let one point the method at an arbitrary codebase and get out a CCS spec + test sequences + harnesses. Honest about limits.*

*Produced by a background trawl (2026-06-03) of `spec/docs/*`, the spec artefacts, the `claude/spec` git log + merged PR bodies (#132–#166), the memory files, and the design-dialogue transcript. Sources cited inline (file:line, PR #, commit sha, memory slug) so each claim is checkable.*

---

## Part 1 — The methodology as practised

### 1.1 The origin and the thesis

The project did not start as a formal-methods exercise. It started as a *failed migration*: an autonomous agent was asked to port miolingo from Streamlit to PyQt and produced something "syntactic, not semantic" — it moved the functions and rebuilt a UI but "quietly discarded the interaction layer," because in Streamlit "a large part of how the app actually works lives in `session_state` and the full-script rerun model" which "is not visible in a function signature" (`SPEC-RECOVERY.md:8-14`). The diagnosis is the whole thesis: *the source conflated behaviour with framework, and that conflation is the disease* (`SPEC-RECOVERY.md:14`). The counterintuitive resolution: **the long detour through a formal specification is the fastest way to recover**, because "the thing that was lost (interaction topology) is precisely what CCS makes explicit and primary" (`SPEC-RECOVERY.md:16-18`).

This generalises into **Specification-Governed Software Engineering (SGSE)**: LLM agents are "syntactically fluent but semantically shallow"; a port-signature contract "removes the thing agents are bad at … there is no implicit dependency to infer, because every dependency is a declared port" (`METHODOLOGY.md:19-21`; restated `PAPER-ABSTRACT.md:5`).

### 1.2 The one invariant everything hangs from

> Every component is an agent with hidden state, visible **only** through named, typed ports. The set of ports and their value types is the entire contract. "If you ever find yourself reasoning about a component's internals by any route other than its ports, stop — you have left the model." (`spec/docs/CLAUDE.md:5-8`; `METHODOLOGY.md:7,30`)

Everything else is a corollary of this single commitment. The disciplines below are not independent rules; each is "an instance of it" (`METHODOLOGY.md:45`).

### 1.3 The disciplines (each recurs across artefacts; each is load-bearing)

**Sort vs ready set.** The *sort* is the full static port alphabet — "every presentation L2/L3 must be able to produce." The *ready set* is the subset offered in the current state, "fixed by guarding." Therefore **control enablement is L1-derived, not invented at L2/L3** — "the skin renders the ready set; it does not decide it," dissolving "the notorious bug class: scattered, ad-hoc enable/disable logic that drifts out of step with the model" (`METHODOLOGY.md:32-39`; `ARCHITECTURE.md:16`).

**The afforded-ports obligation (where pure CCS is extended).** CCS synchronisation is a blocking rendezvous; a UI wants to render enablement *before* the user acts. The ready set "cannot be precomputed in general: with data-dependent guards it depends entirely on current state." So every faithful encoding must answer an on-the-fly *afforded-ports* query "from its own state by evaluating its guards" — "the single point where pure CCS … is extended with a non-blocking introspection the encoding is obliged to provide" (`METHODOLOGY.md:41`). In the artefacts this is `readyPorts[s] := portName /@ (First /@ transNamed[s])` (`discipline.wl:50`).

**`afforded` is analysis, not a channel.** Early drafts reified `afforded!` as an explicit port; it was *removed* (PRs #132/#134). Rationale: "It is observational/UI-derived metadata, not a state transition. It duplicates information already present in guards … Enabledness can be calculated on the fly" (`afforded-guard-normal-form-handoff.md:14-21`). Project principle: **"`portsOf` belongs to analysis, not operational semantics"** (`…handoff.md:26`).

**Guard-partitioned normal form.** Published specs "hoist principal state predicates outward," with "branches containing only meaningful behaviors" and "no inert `nil` branches" — no `if[c,P,nil]`/`if[c,nil,Q]` in the written form (`…handoff.md:28-46`). Motivated by two structural-congruence laws: `P+0=P` and `if[c,P,Q]+R = if[c,P+R,Q+R]` (`…handoff.md:60-67`). You can see it directly in `VocabStoreRecovered.wl`: an outer `if[auth===signedIn,…]` gate, then a `Length[entries]==0` split, then an `editing===none` split (`:64-162`).

**Read-only views are output ports (`view!`).** A display "must not breach encapsulation by exposing state directly." A read-only display is "an output-only port whose carried value is a *projection* the agent chooses to publish: `view!(f state)`." The projection `f` is an L1 decision; its rendering is L2/L3. Reflective views (showing the agent's own definition) are "a distinct projection and a distinct port" (`METHODOLOGY.md:43-50`). In code: every agent carries a `view` self-loop (`discipline.wl:6-24`; `VocabStoreRecovered.wl:67`).

**Single ownership / single source of truth.** Recovered from the app itself: `language_state.py` is "explicit that the sidebar is the sole owner of the language pair (a tripwire warns if any other module writes it; everyone else reads)" — "that's the spec's `view!` discipline exactly" (PR #149). Matthew confirms this is a first principle: single source of truth "was frequently violated in early versions of miolingo" and the pull model is "healthier" (transcript). Hence the data-sharing rule:

**Own it → store it. Borrow it → fetch it fresh, at the point of use.** (`ARCHITECTURE.md:99-108`). A component never caches data another owns; it reads through a port "as a prefix of the action that needs it."

**Pull-on-use, forced by prefix (not priority).** Why not push-to-cache? "Pure CCS has no priority: an offered synchronisation is declinable while the agent has any other transition." So with a cache, the stale-read trace `set_target(pt)·autofill[reads "fr"]·langToVS(pt)` "is a legal trace — the refresh is not forced before the stale read … A cache of borrowed data cannot be kept coherent without leaving the calculus" (`ARCHITECTURE.md:113-122`). The mechanism is a persistent `langRead!` self-loop on the owner, read as a *prefix* of the consuming action and restricted to a τ in the composition; "forced by sequencing, not by priority — the same idiom `vAdd`/`pLoad` already use" (`ARCHITECTURE.md:124-145`; implemented PRs #154/#155/#158). The one escape hatch — a *control* guard over borrowed data — "genuinely needs push, i.e. a calculus extension (priority/maximal-progress or broadcast)," explicitly reserved, none adopted now (`ARCHITECTURE.md:147-154`).

**The logical-clock precedent (don't model un-guarded data as machinery).** "No guard in the spec reads time: it is passive data." So rather than a wall clock (which "would force a request/block/receive/resume handshake and a train of τ's to fetch a value that only lands in a data field"), keep only the one temporal fact the app uses — happens-before of captures — as a pure logical clock `vsNextSeq = max(last_seq)+1` (`function-recovery.md:103-120`; PR #137). This turned out "more faithful AND cheaper than the wall clock." It is the *precedent* the language decision cites: "a value no guard reads is *data*, not control, so it is not threaded as a sync" (`ARCHITECTURE.md:77`).

**Oracles: quarantine residual IO behind named, uninterpreted stubs.** The pure core is recovered as a total function; "every residual side effect is quarantined behind a named, uninterpreted oracle the function is parametric in" (`function-recovery.md:33-40`). Inventing an oracle body "would re-import the contamination the project exists to remove"; leaving it a stub "records the recovered fact that the operation is IO-bound." A service's port signature is invariant under the stub→canned-agent→live choice, so it can be promoted later "without disturbing its consumers," and the choice is made **per service** (`co-development.md:71-75`). The espeak g2p bridge was the first oracle "made to run for real inside the spec" (commit 924020f).

**Recovery, not invention.** The hardest discipline to keep. The spec is "recovered, not invented" — the function pass recovers bodies "from the Python, mechanically, never invented" (`function-recovery.md:5-7`), and the governance rule is absolute: agents may "**not** treat old implementation code as a source of semantic truth" once the spec exists, but recovery *reads* that code under review (`ARCHITECTURE.md:204-206`; `CLAUDE.md:14-16`). The tension is real and deliberate: during recovery you read the code; once recovered, the spec — never the code — is the authority. Matthew polices under-extraction directly: "I'm not inventing this, it is part of the existing design … Please study the actual app code to see what should happen" (transcript → PR #161).

**Provenance / `@src` audit.** Every model element ties back to the implementation at line level. Two layers: grep-able inline `(* @src file.py:NN ; … *)` tags, and per-component tables `Spec element | Kind | Source file:line(fn) | App construct | Note` (`PROVENANCE.md:13-30`). Conventions that keep it honest: pin the app-source baseline SHA (`src/` frozen at `504f8c8`); cite the *function name* so a row survives line drift; mark each row **faithful / simplified / deferred-invented**; record the verifying test/τ (`PROVENANCE.md:32-48`).

**The "data cloud" / incompleteness inventory.** Any datum read but "owned by nothing yet modelled" is shown as an explicit standing inventory — "a standing reminder that the simulated agents are not complete in themselves" — and it *shrinks* as each owner is modelled (`ARCHITECTURE.md:166-173`; PR #159). It is "hand-maintained in lockstep with the spec," and each item "lights up when a currently-ready action would consult it" (`walk.md:50-54`).

### 1.4 The two-level testing (symbolic vs real data)

The same spec is tested at two altitudes:
- **Symbolic / structural** — ready sets per mode, τ-availability, trace round-trips, cross-engine parity (`transVP`/mu-term vs `transNamed`/call-form must agree: PR #135 check D; `merge_defined_test`).
- **Real-data / value-function** — concrete values flow through the synchronisations and the value-functions compute: "27 golden cases vs Python docstring behaviour" (`functions_test.wls`, PR #136), dedup really bumps a counter, ordering really is faithful (`co-development.md:43-46`).

The standing invariant for sequences: *every `walkTests` plan must run to completion on **both** compositions* (`walk.md:135-139`; `walk_sequences_test.wls`). Verification is "intrinsic, not bolted on … the agent can independently verify its own work … before asking for a human's time" (`co-development.md:40-46`).

### 1.5 The `walk` simulator — the human's live interface

`walk` "lets a human drive the executable CCS spec: step through transitions, play the user by feeding real values into input ports … record/replay traces" (`walk.md:3-9`). It embodies the project's sharpest conceptual move, the **meta-agent split**: rather than model the user as an agent inside the system, "the person drives the model's input ports from outside … They remain the unmodelled environment of an open system. 'User and system are symmetric processes' is not a slogan here; it is literally how the tool is used" (`co-development.md:58-64`). Sharpened in the transcript: "you play the *user* (external input ports) and the *world* (oracle return values); the simulator plays the *system* (internal syncs)" (`ARCHITECTURE.md:160-164`).

Notable harness features that *are themselves methodology*, generalisable to any spec:
- **Maximal-progress / auto-τ toggle** — auto-fires the unique enabled internal τ until τ-stable, *stops if ≥2 are ready* ("a real choice is never silently resolved"); "a scheduling strategy over the existing LTS … it does not introduce priority into the language" (`ARCHITECTURE.md:156-164`; PRs #154/#165). Every auto-fired τ stays recorded and Back-steppable.
- **Grouped transitions by providing component**, via a *pure syntactic scan* of each agent's sort (`componentPortMap`) — "needs no execution and can't be fooled by guards" (`walk.md:56-62`).
- **Computed-view warnings** — when a wrongly-shaped value leaves a `view!` projection un-reduced, the panel says so (PR #162 §1).
- **Git build stamp** — "am I running the latest?"; a stale notebook cell keeps its old stamp (PR #162 §2). Directly addresses the stale-load failure mode.

### 1.6 The process / division of labour

The loop (every change, large or small): **Discuss → Implement → Test → Spiral → Branch→PR → Human review/merge** (`co-development.md:21-39`). The split mirrors the governance:
- **Human-governed:** the spec, the architectural decisions, the merges. "The spec — never old implementation code — is the source of truth."
- **Agent-executed, human-bounded:** bounded tasks referenced to the spec, each producing a *verifiable artefact*; "anything touching multiple layers at once is rejected" (`co-development.md:50-58`; `ARCHITECTURE.md:206`).

**Measured pace** is an explicit working agreement, not a nicety: Matthew's review time is "the binding constraint." Therefore: *decouple use from build* (the Streamlit app stays usable in parallel); *trust the tests, review the decisions* (surface a short decision list, terse async answers, proceed on answered ones, park the rest); *batch, don't stream* (coherent one-component batches over many tiny PRs); *keep docs in lockstep* as part of "done" (`memory/feedback_measured_pace.md`). PRs stack and sequence (e.g. the CargoHold migration: standalone #164 → auto-τ prereq #165 → compose+migrate PR-2b), and genuine architectural choices are "surfaced and deferred to the human, not decided silently" (`co-development.md:25-27`).

The naming theme is nautical and deliberate: **`rig`** is the (not-yet-built) L2→L3 action↔widget binding language ("you rig a port to a control"); **`walk`** is the simulator; "`patch` was rejected — it connotes a small correction, not a wiring" (`memory/project_rig_naming.md`).

### 1.7 The pipeline a component travels (concretely)

1. **UI-first pre-draft analysis** (sign-off gate *before any CCS*): (1) state inventory split into **domain state** vs **framework bookkeeping** — only domain state becomes process-local; the discard ratio is recorded as H2 evidence ("~5 domain vs ~15+ bookkeeping" for Quick Practice, `practice-session-recovery.md:42`); (2) interaction triggers → candidate *input ports* filtered by the **port boundary criterion** ("not every widget signal; only exchanges the agent chooses to make part of its contract," `ARCHITECTURE.md:188`); (3) displays → *output projection* ports; (4) an **afforded-port table per mode**; (5) a plain-text **wiring diagram** (`SPEC-RECOVERY.md:39-59`).
2. **Stubbed CCS** in guard-partitioned form — real prefixes/choices/ports, value-functions as *named stubs with signatures, no bodies* (`SPEC-RECOVERY.md:61-64`).
3. **Compose** — parallel composition with cross-component channels restricted to τ; `view!` ports relabelled per-agent to avoid the name clash (`discipline.wl:75-120`; `merge`/`mergeDefined`).
4. **Function-recovery pass** — recover the pure core as total functions from the Python; quarantine IO behind oracles (`function-recovery.md`).
5. **Test** at both levels; **walk** it by hand; **provenance**-tag in the same pass.
6. **Refine** when a recovery gap is found (PR #161's under-extraction; re-pin the source SHA only when `src/` changes under a row).

### 1.8 Recurring failure modes and their fixes (the hard-won knowledge)

- **Premature evaluation on a free binder ("held-until-concrete").** A value-function fires while its argument is still the symbolic binder: e.g. `deleteFrom[entries_List, id_]` — `DeleteCases` matches nothing and "collapses to the unchanged list before the supplied value lands — a silent no-op delete, latent in `VS.delete`" (`cargohold-recovery.md:33-41`; PR #164). Fix: gate the pattern to the contract type (`id_Integer`, `addEntry[w:(_String|_Association)]`, `vocabView[entries_List]`, `helmView[…target_String…]`). This is a *whole class* — "same held-until-concrete discipline" recurs across `addEntry`, `updateEntry`, `sortEntries`, `helmView` (PR #152 bug; PR #140 known limit; `memory/project_walk_supply_redesign.md`). The deeper fix is deferred: *supply-then-derive* in the engine (compute the input derivative *with* the substitution inline) "would obviate the pattern-restriction patches" (`memory/project_walk_supply_redesign.md`).
- **Stale notebook loads.** A cell silently runs an old build; "the `practise_vocab`-in-'other' confusion was a stale snapshot." Fix: the git build stamp (PR #162). Plus: heavy scripts collided with the notebook kernel — a **license-seat contention** ("concurrent-kernel seat limit colliding with your notebook kernel," transcript) — managed by retrying short runs.
- **Engine/spec divergence across two repos.** The spec coupled to the RCA engine via "~14 hardcoded absolute paths across 7 files … no version check," so "a green test proved nothing durable" (PR #139). Fix: `paths.wl` as single source of truth (`Get` relative to `$InputFileName`) + an engine-SHA ancestry guard (`$minEngineSha`, the "shared coordinate between the two repos, bumped in the same spec PR that adopts new engine capability — no lockstep branching").
- **Ready-set churn when a contract changes.** Renaming/regating a port ripples into every test's expected ready set and every τ-bearing plan. Mitigations: the *standing dual-composition invariant*; auto-τ so "plans list only external actions and stay robust as new syncs are added — no plan edits" (PR #165); `walk_test` catching "a genuine regression, not a stale assertion" (transcript, PR #144 — "your tests pass but it doesn't work," the bare-`view` suffix-match gap).
- **Weak bisimulation non-congruence around τ.** `≈` "fails to be a congruence over `+` only because of an initial τ (`τ.P ≈ P` but `τ.P + R ≉ P + R`)." This bit the `ModeSelector` design. Matthew's resolution: "eliminate the mode selector completely. Each mode starts with an externally visible parameter-less input action that initiates any necessary data/oracle reads as the next action. WB is a congruence for visibly-guarded agents, isn't it?" — confirmed: observation congruence adds exactly the rootedness side-condition, so guarding each mode behind a *visible* action restores compositionality and removes the need for relay agents (transcript). This is a methodology rule in the making: **prefix internal/oracle reads behind a visible action so weak bisimilarity stays a congruence.**

### 1.9 What is hypothesis, not yet result

The methodology is explicit that empirical validation is "the research programme ahead" (`PAPER-ABSTRACT.md:23`). H1 (port contract removes the inference step), H2 (view-port = Qt signal; Streamlit fakes it; the discard ratio is the evidence), H3 (constrained rendering beats unconstrained migration), H4 (ready set = ready/refusal set of testing semantics, so conformance = ready-set agreement at each reachable state) are listed as *requiring validation* (`METHODOLOGY.md:104-110`). Open problems remain: formalising the binding-layer protocol and verifying it matches `init(P)` everywhere; the L2 grammar; framework constructs with no clean CCS analogue (`ARCHITECTURE.md:212-218`). The skill suite below should *carry these forward as flags*, not pretend they are solved.

---

## Part 2 — The skill suite / scaffolding

### 2.1 Design stance

The goal: point the method at an arbitrary codebase, supply some initial configuration, interact at the genuine decision points, and get out a CCS spec + test sequences + harnesses. The honest framing (from `co-development.md:101`): **not "the AI builds the spec"** but "a person and a tool, in a loop where every step is checked against an executable specification." So the suite is designed around *human decision points*, not around full automation. Each skill names where it *must* stop and ask.

A guiding split, inherited from the project: the **mechanical** parts (pure value-function recovery, provenance tagging, harness generation, conformance checks) are AI-suited and safe; the **judgement** parts (port boundary, what is domain vs bookkeeping, oracle vs agent vs live, whether a dependency is control or data, normal-form factoring) are where the human is the binding constraint and where premature automation will under-extract or invent.

### 2.2 Initial configuration the user must supply (once per target)

A `sgse.config` (or skill arguments):

| Key | What it is | Why it can't be inferred |
|---|---|---|
| `source_root`, `source_baseline_sha` | the code being recovered + a pinned commit | provenance needs a frozen baseline (`PROVENANCE.md:32-34`) |
| `framework` | Streamlit / React / Qt / … | drives the bookkeeping-vs-domain heuristics and the H2 discard story |
| `engine` | path/SHA of the CCS executor (RCA) + `$minEngineSha` | the divergence guard (`paths.wl`, PR #139) |
| `spec_dir`, `naming_theme` | where artefacts land; lexical conventions (lc symbols, nautical) | project taste, must be consistent (commit 05b41b2) |
| `target_skin` (optional) | the framework being migrated *to* | only needed at the rig stage |
| oracle policy defaults | stub / canned / live, overridable per service | the per-service decision is human, but a default speeds the loop |

### 2.3 The skills

Eleven skills, in pipeline order. Naming follows the nautical theme where it fits. Each: **trigger · inputs · outputs · discipline enforced · human interaction**.

---

**1. `survey` — component inventory**
- *Trigger:* "recover a spec from this codebase" / start of a new target.
- *Inputs:* `source_root`, `framework`.
- *Outputs:* a draft Component Inventory table (component → candidate agent family → kind → priority), ordered by interaction complexity, plus a first guess at which "displays" are *view ports on* stateful agents vs standalone agents, and which data lives in an external store.
- *Discipline:* the agent/port model; the warning that read-only displays are "most likely view ports, not agents" and external stores are a *rig* concern (`ARCHITECTURE.md:54-97`).
- *Human:* **must** confirm the inventory, the recovery order, and the standalone-vs-projection call per display. Genuinely judgement; do not auto-promote.

**2. `lift` — UI-first pre-draft analysis (per component)**
- *Trigger:* a component selected from the inventory.
- *Inputs:* the component's source files; `framework`.
- *Outputs:* the five-part pre-draft doc (state inventory split domain vs **framework bookkeeping** *with the discard ratio recorded as H2 evidence*; triggers → candidate input ports filtered by the **port boundary criterion**; displays → projection ports; **afforded-port table per mode**; plain-text wiring diagram) — exactly `SPEC-RECOVERY.md §3` (and see `practice-session-recovery.md`, `vocabstore-recovery.md` for the shape).
- *Discipline:* domain/bookkeeping separation; port-boundary criterion; ready-sets-not-skipped; displays-as-projections.
- *Human:* **sign-off gate** — the five `SPEC-RECOVERY.md §5` criteria before any CCS is written. This is the most important human review in the pipeline: it is where under-extraction and invention are caught. AI-suited to *draft*, must not proceed unreviewed.

**3. `stub` — stubbed CCS in guard-partitioned normal form**
- *Trigger:* a signed-off `lift` doc.
- *Inputs:* the pre-draft analysis.
- *Outputs:* a `{Component}Recovered.wl` — agents with real prefixes / choices / guards, value-functions as *named stubs (signatures, no bodies)*, `view` self-loop per the discipline, in guard-partitioned form (no degenerate `if`).
- *Discipline:* stubbed-means-no-bodies (`SPEC-RECOVERY.md:61-64`); guard-partitioned normal form (`…handoff.md`); `afforded` stays analysis-only; Wolfram bracket balance (a real past bug, PR #132 chat).
- *Human:* review the guard structure and the normal-form factoring (the congruence laws give freedom here). Mechanical-ish given a good `lift`, but the factoring choices are reviewable.

**4. `compose` — parallel composition with restriction**
- *Trigger:* ≥2 recovered agents that interact.
- *Inputs:* the recovered agents; the cross-component channel list.
- *Outputs:* a composed system (`mioCore`-shape) via `merge`/`mergeDefined`, cross-component channels restricted to τ, `view!` relabelled per agent; a self-registering walk-grouping registry.
- *Discipline:* cross-component links are *restricted syncs*, not shared state; per-agent `view!` disambiguation (`discipline.wl:75-120`).
- *Human:* confirm which channels are internal (τ) vs external. Decide **borrowed-vs-owned** for any cross-component data: own→store, borrow→pull-on-use via a prefixed `langRead`-shaped read (`ARCHITECTURE.md:99-145`). This is a decision skill; surface it, don't decide silently.

**5. `recover-fn` — function recovery (the pure core)**
- *Trigger:* a stubbed component that needs denotations.
- *Inputs:* the named stubs; the Python (or other) source; the data schema.
- *Outputs:* a `{Component}Functions.wl` (loaded *after* the recovered agent — *additive*, removing the `Get` returns the fully-stubbed spec) giving each stub a total, deterministic body; a provenance table (each stub ← `file:line(fn)`, pure-core vs oracle split); golden unit tests vs the docstring behaviour.
- *Discipline:* recover-don't-invent; **quarantine IO behind named oracles**; fix data representation from the schema, not taste; the additivity rule (`function-recovery.md:1-148`).
- *Human:* decide the **logical-clock-style abstractions** (does any guard read this value? if not, it's data — don't model machinery for it, `ARCHITECTURE.md:77`, PR #137) and the **oracle policy per service** (stub / canned-agent / live; invariant under the choice, so deferrable, `co-development.md:71-75`). The *pure* recovery is the genuinely mechanical, AI-strong part; the IO classification is judgement.

**6. `provenance` — the audit trail**
- *Trigger:* runs *in the same pass* as `stub`/`recover-fn`/any extension (`PROVENANCE.md:8-10`).
- *Inputs:* the new spec elements; the pinned source baseline.
- *Outputs:* inline `@src` tags + per-component table rows, each marked **faithful / simplified / deferred-invented** with a verifying test/τ.
- *Discipline:* every element ties to a line; honesty marks; re-pin baseline only on `src/` change.
- *Human:* spot-check the honesty marks (especially any `invented`, "should be rare and justified"). Mostly mechanical; cheap to keep in lockstep, expensive to back-fill — so enforce *in-pass*.

**7. `cloud` — incompleteness inventory**
- *Trigger:* after composition, whenever an agent reads data it doesn't own.
- *Inputs:* the spec; the set of modelled owners.
- *Outputs:* the "Outside the model" inventory (DB persistence, oracle knowledge, stats/history), each item flagged by which ports consult it; shrinks as owners are modelled.
- *Discipline:* "the simulated agents are not complete in themselves" (`ARCHITECTURE.md:166-173`; `walk.md:50-54`).
- *Human:* hand-maintained in lockstep (like the ARCHITECTURE notes). Light judgement; mostly bookkeeping.

**8. `walk` — the interactive simulator (generated/configured)**
- *Trigger:* a composed system the human wants to drive.
- *Inputs:* the system term; the component registry.
- *Outputs:* a `walk.wl`-shaped harness: clickable ready transitions grouped by providing component, inline value fields on input ports, computed `view!` panels with wrong-shape warnings, Back/Forward/Reset, trace record/replay, the maximal-progress toggle, the git build stamp, the cloud panel.
- *Discipline:* the **meta-agent split** (human plays user+world, simulator plays system); maximal-progress is *a strategy over the LTS, not a language change*, and stops on a real choice; every τ recorded and Back-steppable (`walk.md`; `ARCHITECTURE.md:156-164`).
- *Human:* this *is* the human's live interface; not automatable and not meant to be. The skill generates the substrate; the human walks it.

**9. `sequence` — test-sequence generation**
- *Trigger:* a composed, function-recovered system.
- *Inputs:* the sorts and ready sets; the value contracts per port.
- *Outputs:* a `walkTests`-shaped batch of named value-carrying plans (`vis["port", value]` / auto-τ), kebab-cased by scope (`vs-*`, `ps-*`, `sync-*`, `full-*`), collectively exercising **every** port and sync; the standing dual-composition invariant test (`walk_sequences_test`).
- *Discipline:* plans carry real values matching each port's contract; *must run on both compositions*; auto-τ so plans list only external actions and survive new syncs (`walk.md:103-139`; PR #165).
- *Human:* confirm coverage intent; supply non-obvious payload values where the contract is subtle (e.g. vocab `"word"` shape vs practice `"text"` shape, `function-recovery.md:91-100`). AI-suited to enumerate; human sanity-checks the values.

**10. `conform` — ready-set / testing-equivalence harness (H4)**
- *Trigger:* a skin (L3) exists, or two encodings must be compared.
- *Inputs:* the spec; the skin's afforded-ports query.
- *Outputs:* a conformance harness checking **ready-set agreement at each reachable state** (testing equivalence, not trace inclusion alone), plus the cross-engine parity check (`transVP` vs `transNamed`).
- *Discipline:* H4 — "verifying a skin against the spec means checking ready-set agreement at each reachable state" (`METHODOLOGY.md:109`); the afforded-ports obligation each encoding must compute on the fly.
- *Human:* this is partly **open research** (`ARCHITECTURE.md:214`); the skill should generate what it can and *flag* the unverified `init(P)`-conformance gap rather than claim it solved.

**11. `rig` — the L2→L3 binding (port → widget)** *(future; named, not built)*
- *Trigger:* migrating a recovered spec to a real skin.
- *Inputs:* the L1 ports; an L2 interaction-form choice per port; `target_skin`.
- *Outputs:* skin bindings — input port → control of the L2 form; output port → rendering of its projection; **ready set → enablement** (query the afforded-ports op, never tabulate); non-ready rendering per L2.
- *Discipline:* the whole `CLAUDE.md` "How to render the contract" list; never invent enablement; never expose raw state; one layer per session.
- *Human:* choose the L2 interaction form per port (finite-choice → tabs/radio/dropdown, etc.); decide how external stores are rigged (a `view!` backed by a *query* — "may itself need to enter the model," `memory/project_external_store_rigging.md`). Genuinely a design layer.

### 2.4 Cross-cutting scaffolding (not skills, but the rails skills run on)

- **`paths`-style single-source load + engine-divergence guard** — generated per target so "a green test proves something durable" (PR #139). The `$minEngineSha` shared-coordinate idiom generalises to any spec/engine repo split.
- **Two-level test runner** — symbolic (ready-sets/τ/parity) and real-data (value-function goldens). The dual-composition invariant baked in.
- **The decision ledger** — every surfaced decision lands as a PR with a written rationale, so "the design history is self-documenting" (`co-development.md:67`). A skill-suite analogue: each human decision point emits a short, citable rationale stub the human edits, not a silent default.
- **Measured-pace governor** — batch the decision list, proceed on answered, park the rest; keep docs (`::usage` + `.md`) in lockstep as part of "done" (`memory/feedback_measured_pace.md`). This should be a *mode* of the suite, not an afterthought — it is the actual binding constraint.

### 2.5 What is genuinely AI-suited vs mechanical vs irreducibly human

- **AI-strong, low-risk:** `recover-fn` pure core; `provenance` tagging; `sequence` enumeration; `walk`/`conform` harness *generation*; the load-path/divergence scaffolding; bracket-balance and normal-form *mechanics*. These are "the verifiable parts" the project says the acceleration actually comes from (`co-development.md:108-111`).
- **AI-drafts, human-must-review:** `survey` inventory; `lift` domain/bookkeeping split and port-boundary calls; `stub` guard factoring. High value, high under-extraction risk — the sign-off gate exists precisely here.
- **Irreducibly human (the suite surfaces, never decides):** standalone-vs-projection; oracle stub/canned/live per service; borrowed-vs-owned and control-vs-data (the logical-clock test); whether a feature is *deferred* vs *out of scope*; the L2 interaction form; when a calculus extension is finally forced (priority/broadcast for a borrowed-data *guard*); when locality becomes load-bearing enough for bigraphs (`METHODOLOGY.md:52-58`).

### 2.6 Honest limits

- **Recovery still requires reading the source.** The discipline forbids treating old code as *semantic truth once a spec exists*, but recovery itself reads it under review — the tension (`CLAUDE.md:14-16` vs `function-recovery.md`) is managed by the sign-off gate, not eliminated. A skill cannot remove the human from `lift`.
- **The free-binder / held-until-concrete class is a standing hazard**, currently patched per-function; the principled fix (supply-then-derive in the engine) is *deferred* (`memory/project_walk_supply_redesign.md`). A generated harness will reproduce the hazard until the engine changes — `walk` must keep the wrong-shape warning (PR #162).
- **H4 conformance (`init(P)` agreement at every reachable state) is open research** (`ARCHITECTURE.md:214`). `conform` can check parity and finite-reachable ready-sets; it cannot yet *prove* full conformance.
- **Engine dependency.** The whole thing presumes an executable value-passing CCS engine (RCA) co-evolving in a second repo, with native guard/choice, scope-aware `substVv`, transition-time relabelling, and `walk`/`replayTrace` (`co-development.md:93-95`). The suite must own the *coordination* (the SHA guard) but cannot abstract the engine away.
- **License-seat / runtime friction** is real for the Wolfram backend (concurrent-kernel collisions, transcript) — operational, not conceptual, but it shapes how the loop is run (short verifications, retries).
- **Empirical validation has barely begun** (`PAPER-ABSTRACT.md:23`; `METHODOLOGY.md:111-120`). The suite would *be* a vehicle for that validation (the discard ratios, the Streamlit-vs-Qt comparison, the test-process substitution) — but it should report H1–H4 as hypotheses under test, not as settled foundations.

---

*Synthesis only — no spec artefacts were changed by its production. This document is itself subject to human review and correction; treat its skill design as a proposal, not a settled plan.*
