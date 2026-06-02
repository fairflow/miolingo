# Spec Provenance — where every model element comes from, and why

This is the systematic record tying each element of the L1 spec back to the
**implementation it was recovered from**, at the line level, with the
justification for how it was extracted. It is the audit trail for the claim that
the spec is *recovered, not invented*.

It governs **every** extension: when the spec grows, add the inline tag(s) and
the table row(s) below, in the same pass.

---

## How it works — two layers

**Layer 1 — inline `@src` tags** in the `.wl` source, right at the element:

```wolfram
(* @src vocabulary_tab.py:556 ; quick_practice_tab.py:184 *)
precede[coLabel["practise_vocab"], …]
```

A grep-able marker (`grep -rn "@src" spec/*.wl`) so a reader at the spec sees the
origin without leaving the file. One tag per port / guard / value-function.

**Layer 2 — a provenance table** per component (in its `docs/<component>-recovery.md`,
indexed below). Columns:

| Spec element | Kind | Source `file:line (fn)` | App construct | Extraction note / justification |

---

## Conventions (so the record stays honest and re-findable)

- **Pin the source baseline.** Each table states the app-source commit it was read
  against. App source (`src/`) is currently frozen at **`504f8c8` (2026-04-26)** —
  stable, so line numbers hold. Re-pin only when `src/` changes under a row.
- **Cite `file:line (function_name)`** — the function name makes a row re-findable
  even if a few lines shift.
- **Kind** is one of: `agent` · `port` (in/out) · `guard` · `sync` (restricted τ) ·
  `value-fn` · `projection`.
- **Tag every row with one of three honesty marks** in the note:
  - **faithful** — a direct correspondence to a single app construct;
  - **simplified** — a deliberate collapse/abstraction (say what was merged or
    dropped, and why it is meaning-preserving);
  - **deferred / invented** — *flag explicitly*. `deferred` = a real app feature
    not yet modelled; `invented` = not in the app (should be rare and justified).
- **Verification.** Note the engine check that confirms the element behaves
  (a test name, or the ready-set/τ it produces), so provenance ties to evidence.

---

## Template (copy when extending the spec)

```markdown
### <Component> — provenance  (app src @ <sha>, <date>)

| Spec element | Kind | Source `file:line (fn)` | App construct | Note |
|---|---|---|---|---|
| `<name>` | <kind> | `file.py:NN (fn)` | <what it is in the UI/logic> | **faithful/simplified/deferred** — <justification>. Verified: <test/τ>. |
```

---

## Component index

| Component | Spec file | Recovery doc (provenance table) | Status |
|---|---|---|---|
| Practice Session | `PracticeSessionRecovered.wl` | `practice-session-recovery.md` | recovered (table: back-fill pending) |
| Vocabulary Store | `VocabStoreRecovered.wl` | `vocabstore-recovery.md` | recovered (table: back-fill pending) |
| Helm (session/language) | `HelmRecovered.wl` | `helm-recovery.md` | recovered (table: back-fill pending) |
| CargoHold (external store) | `CargoHoldRecovered.wl` | `cargohold-recovery.md` | **in design** |

Existing components get their tables back-filled as we next touch them; new ones
ship with the table from the start.

---

## Worked example — the `practise_vocab` extraction (app src @ `504f8c8`)

The first extraction recorded in this format (the vocab→practice channel, PR #161).

| Spec element | Kind | Source `file:line (fn)` | App construct | Note |
|---|---|---|---|---|
| `practise_vocab` | port (in, VS) | `quick_practice_tab.py:184 (_render_vocab_materials)`, `vocabulary_tab.py:556` | "📂 Load vocabulary" / "🎯 Load filtered" / "🎯 Practise these" buttons | **simplified** — the app exposes the same hand-off as three buttons; modelled as **one** ungated channel (available when non-empty). The filter shapes the *payload*, not availability. Meaning-preserving: each button sets the same `phrase_list`. Verified: `walk-tests` `practise-all` + `sync-pload` on both engines. |
| `pLoad` | sync (VS→PS τ) | `quick_practice_tab.py:170,190`; `vocabulary_tab.py:559-570` | sets `st.session_state.phrase_list`, `qp_phrase_position = 0` | **faithful** — the cross-component hand-off; PS loads at position 0. Restricted in `mioCore`. Verified: `internal_transitions_test`, `composition_test`. |
| `practiseList[entries, filter]` | value-fn | `vocab.py:644 (vocab_as_practice_phrases)` | maps rows → `{text, translation, ipa}` | **faithful** — `filter = none` ⇒ all (`filterMatch[_, none] = True`); `filterBy[q]` ⇒ subset. |
| `capture_vocab` | port (in, PS) | `vocabulary_tab.py:7` (capture hook), `vocab.py:106 (capture_vocab_entry)` | Story Reader / Quick Practice capture | **faithful** — the reverse direction; relays to VS via `vAdd`. Symmetric with `practise_vocab`. |
