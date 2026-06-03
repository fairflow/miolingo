# VocabTable — recovery & provenance

`VocabTable` (the vocab-table store) is the agent that **owns the persisted collection** — recovered
from the app's MySQL layer (`src/vocab.py` over `src/app_mysql.py`), where every
vocab operation opens a connection and runs SQL against the `vocab_entries` table.
It is the model of the *external store* the `†` note (ARCHITECTURE.md) anticipated,
and the persistence counterpart of the "own it → store it" rule.

(`VocabTable`, not `Hold`: `Hold` is a Wolfram built-in. Nautical theme — `Helm`
steers, the cargo hold stores.)

**Status:** PR-1 defined it standalone. **PR-2 composes it into `mioCore`**
(restricted `vocabRead`/`vocabUpsert`/`vocabImport`/`vocabRemove`/`vocabAmend` + `vocabUpsert`) and
migrates Vocab to the (i) form: Vocab holds no entries; it is the **`open_vocab`-gated
tab** that reads/writes the store. **Two writers feed the store:** `vocabUpsert` (Vocab
tab type/paste) and **`vocabUpsert` (PS capture from practice, written DIRECTLY — not via
the tab)**. The first Vocab action is the *visible* `open_vocab`, not the `vocabRead` τ,
so the composition stays visibly-guarded (≈ a congruence — ARCHITECTURE.md).

**Now TWO readers (2026-06-03).** `vocabRead` serves both Vocab *and* PS — PS reads the
store directly to load practice material (pull-on-use), instead of receiving a pushed
snapshot. PS's two visibly-guarded entries: `open_practice` (the quick-practice picker)
→ `vocabRead` → `load_vocab`/`load_filtered`; and the vocab-tab signal
`practise_vocab → goPractice!(filter)`, after which PS pulls (`vocabRead`) and shapes with
that filter. The old `pLoad` data-push is gone (`goPractice` replaces it in the restricted
set). `vocabRead!` is a self-loop output, so it answers any number of readers as separate τ
syncs. See `practice-session-recovery.md` (PS pull/signal) and ARCHITECTURE.md.

---

## Provenance  (app src @ `504f8c8`, 2026-04-26)

| Spec element | Kind | Source `file:line (fn)` | App construct | Note |
|---|---|---|---|---|
| `VocabTable[entries]` | agent | `vocab.py` (all ops); `app_mysql.py:143 (get_connection)` | the `vocab_entries` table + its CRUD | **faithful** — the persisted collection, owned here. Single source of truth. |
| `vocabRead` | port (out, self-loop) | `vocab.py:195 (list_vocab)` | `SELECT * FROM vocab_entries WHERE …` | **faithful** — emits the current collection; a self-loop (read never mutates). The READ a client pulls. (Filter/sort applied by the *reader* — Vocab, or PS via practiseList — not in the store — kept minimal.) |
| `vocabUpsert` | port (in) | `vocab.py:106 (capture_vocab_entry)` | `INSERT … ON DUPLICATE KEY UPDATE` | **faithful** — `addEntry` *is* this upsert (dedup on word + `times_seen` bump). Verified: `cargohold_test` §2. |
| `vocabRemove` | port (in) | `vocab.py:301 (delete_vocab_entry)` | `DELETE … WHERE vocab_id=%s` | **faithful** — `deleteFrom`. Verified: `cargohold_test` §4. |
| `vocabAmend` | port (in) | `vocab.py:343 (update_vocab_entry)` | `UPDATE … WHERE vocab_id=%s` | **simplified** — one port for field updates; carries `<|"id"->_, "fields"->_|>` → `updateEntry`. `update_vocab_notes` (`vocab.py:314`) and autofill enrichment fold in at the migration. Verified: `cargohold_test` §3. |

### Functions used (already recovered; applied here now)
`addEntry`, `deleteFrom`, `updateEntry` (`VocabFunctions.wl`) — the collection
transforms move to being applied *in VocabTable*, where the data lives.

### Bug fixed in passing
`deleteFrom[entries_List, id_]` → `deleteFrom[entries_List, id_Integer]`
(`VocabFunctions.wl`). Without the `_Integer` gate it fired while `id` was
still a **free binder** (concrete entries, symbolic id): `DeleteCases` matched
nothing and collapsed to the unchanged list *before* the supplied value landed —
a **silent no-op delete**, latent in `Vocab.delete`, surfaced by `VocabTable.vocabRemove`
(which asserts the post-delete effect). Same held-until-concrete discipline as
`addEntry[w:(_String|_Association)]` / `updateEntry[fields_Association]`.

---

## Deferred (this round)
- `vocabImport` (bulk `importInto`) — bulk upsert.
- autofill's enrichment in the store (needs the oracle + borrowed language).
- Stats / history tables (`get_user_stats`, session/attempt reads) — VocabTable (or
  a sibling store agent) gains read ports for these when those views are recovered.
