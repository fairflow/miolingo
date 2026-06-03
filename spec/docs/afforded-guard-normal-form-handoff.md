# Handoff: remove `afforded`, use guard-partitioned normal form

## Scope

This branch prepares handoff notes for continuing the recovered spec rewrite on top of `claude/spec`.

Target repository: `fairflow/miolingo`  
Target PR base: `claude/spec`  
Working branch: `remove-afforded-guard-normal-form-notes`

## Core decisions from the chat

### 1. Remove `afforded` from the object-level process model

`afforded` should not be represented as an explicit action/channel in the spec.

Reasoning:
- It is observational/UI-derived metadata, not a state transition.
- It duplicates information already present in guards.
- Any compilation from IO actions to code would also need to resolve `afforded`, which adds unnecessary complexity.
- Enabledness/readiness can be calculated on the fly from the current process state and guards.

Project principle:

> `portsOf` belongs to analysis, not operational semantics.

### 2. Prefer outer-guard / guard-partitioned normal form

Published specs should prefer outermost `if[...]` case splits over embedded degenerate conditionals.

Desired style:
- principal state predicates are hoisted outward
- branches contain only meaningful behaviors
- avoid inert `nil` branches in published specs

Suggested project-local term:
- **guard-partitioned normal form**
- or **outer-guard normal form**

### 3. Avoid degenerate conditionals in written specs

The user explicitly requested removal of forms like:
- `if[c, X, nil]`
- `if[c, nil, Y]`

These may exist as desugaring internally, but should not appear in the final handoff/public spec form.

### 4. Wolfram syntax correctness matters

A previous draft had mismatched `if[...]` brackets.

Any follow-up agent must ensure:
- all `if[...]`, `choice[...]`, `precede[...]`, `call[...]` forms are syntactically balanced
- bracket structure is valid Wolfram Language syntax
- comments remain outside syntax-critical forms unless deliberately placed

## Structural-congruence guidance discussed

Two rewrite laws were discussed as the motivating algebraic basis:

1. Choice identity:
   - `P + 0 = P = 0 + P`

2. Conditional distribution over choice:
   - `if[c, P, Q] + R = if[c, P + R, Q + R]`

These motivate hoisting guards outward until the written form is a case split over real branches, instead of sums containing `if[..., ..., nil]` fragments.

## Concrete rewrite intent for the recovered agents

### PracticeSessionRecovered.wl

Required rewrite goals:
- remove `afforded`
- preserve `view`
- preserve cross-component `pLoad` and `capture_vocab`/`vAdd`
- preserve the queue-empty split
- preserve the recording/no-recording split
- preserve bounds-sensitive `next` / `prev`
- preserve result-sensitive `capture_vocab`
- normalize into guard-partitioned form
- ensure fully correct Wolfram bracket matching

### VocabStoreRecovered.wl

Required rewrite goals:
- remove `afforded`
- preserve `view`
- preserve auth gate
- preserve empty/non-empty split
- preserve filter-sensitive `practise_filtered` (later renamed `practise_vocab` and made filter-INsensitive — the filter now parametrises the payload, not availability; see vocab-tab-recovery.md Amendment 2026-06-02)
- preserve edit-mode split
- preserve cross-component `vAdd` and `pLoad`
- normalize into guard-partitioned form
- ensure fully correct Wolfram bracket matching

## Header/comment changes requested by the chat

Comments should reflect that affordance is analysis-only, not an explicit channel.

Examples:
- replace phrases like `view!, afforded! in every mode`
- with wording like `analysis only; not explicit channels in the process`

## Literature-adjacent framing noted in the chat

Potentially relevant concepts:
- guarded choice
- normal forms for process algebra terms
- conditional process expressions
- symbolic operational semantics
- readiness/enabling as derived semantics rather than explicit action
- GSOS / structured operational semantics with premises as guards

No literature lookup was requested during this handoff; this is just conceptual framing captured from the discussion.

## Next step for the follow-up agent

1. Verify the committed rewrites parse as valid Wolfram Language.
2. If needed, simplify duplicated branches while preserving the no-degenerate-`if` presentation goal.
3. Open a PR from `remove-afforded-guard-normal-form-notes` to `claude/spec`.
4. In the PR description, summarize:
   - removed explicit `afforded`
   - adopted guard-partitioned normal form
   - updated comments to make readiness analysis-only
   - preserved recovered behavior and cross-component ports
