# CargoHold — recovery & provenance

`CargoHold` (`CH`) is the agent that **owns the persisted collection** — recovered
from the app's MySQL layer (`src/vocab.py` over `src/app_mysql.py`), where every
vocab operation opens a connection and runs SQL against the `vocab_entries` table.
It is the model of the *external store* the `†` note (ARCHITECTURE.md) anticipated,
and the persistence counterpart of the "own it → store it" rule.

(`CargoHold`, not `Hold`: `Hold` is a Wolfram built-in. Nautical theme — `Helm`
steers, the cargo hold stores.)

**Status:** PR-1 defined it standalone. **PR-2 composes it into `mioCore`**
(restricted `chRead`/`chUpsert`/`chImport`/`chRemove`/`chAmend` + `vAdd`) and
migrates VS to the (i) form: VS holds no entries; it is the **`open_vocab`-gated
tab** that reads/writes the store. **Two writers feed the store:** `chUpsert` (VS
tab type/paste) and **`vAdd` (PS capture from practice, written DIRECTLY — not via
the tab)**. The first VS action is the *visible* `open_vocab`, not the `chRead` τ,
so the composition stays visibly-guarded (≈ a congruence — ARCHITECTURE.md).

---

## Provenance  (app src @ `504f8c8`, 2026-04-26)

| Spec element | Kind | Source `file:line (fn)` | App construct | Note |
|---|---|---|---|---|
| `CargoHold[entries]` | agent | `vocab.py` (all ops); `app_mysql.py:143 (get_connection)` | the `vocab_entries` table + its CRUD | **faithful** — the persisted collection, owned here. Single source of truth. |
| `chRead` | port (out, self-loop) | `vocab.py:195 (list_vocab)` | `SELECT * FROM vocab_entries WHERE …` | **faithful** — emits the current collection; a self-loop (read never mutates). The READ a client pulls. (Filter/sort applied by the *reader*, VS, not in the store — kept minimal.) |
| `chUpsert` | port (in) | `vocab.py:106 (capture_vocab_entry)` | `INSERT … ON DUPLICATE KEY UPDATE` | **faithful** — `addEntry` *is* this upsert (dedup on word + `times_seen` bump). Verified: `cargohold_test` §2. |
| `chRemove` | port (in) | `vocab.py:301 (delete_vocab_entry)` | `DELETE … WHERE vocab_id=%s` | **faithful** — `deleteFrom`. Verified: `cargohold_test` §4. |
| `chAmend` | port (in) | `vocab.py:343 (update_vocab_entry)` | `UPDATE … WHERE vocab_id=%s` | **simplified** — one port for field updates; carries `<|"id"->_, "fields"->_|>` → `updateEntry`. `update_vocab_notes` (`vocab.py:314`) and autofill enrichment fold in at the migration. Verified: `cargohold_test` §3. |

### Functions used (already recovered; applied here now)
`addEntry`, `deleteFrom`, `updateEntry` (`VocabStoreFunctions.wl`) — the collection
transforms move to being applied *in CargoHold*, where the data lives.

### Bug fixed in passing
`deleteFrom[entries_List, id_]` → `deleteFrom[entries_List, id_Integer]`
(`VocabStoreFunctions.wl`). Without the `_Integer` gate it fired while `id` was
still a **free binder** (concrete entries, symbolic id): `DeleteCases` matched
nothing and collapsed to the unchanged list *before* the supplied value landed —
a **silent no-op delete**, latent in `VS.delete`, surfaced by `CargoHold.chRemove`
(which asserts the post-delete effect). Same held-until-concrete discipline as
`addEntry[w:(_String|_Association)]` / `updateEntry[fields_Association]`.

---

## Deferred (this round)
- `chImport` (bulk `importInto`) — bulk upsert.
- autofill's enrichment in the store (needs the oracle + borrowed language).
- Stats / history tables (`get_user_stats`, session/attempt reads) — CargoHold (or
  a sibling store agent) gains read ports for these when those views are recovered.
