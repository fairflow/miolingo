# ProgressTable Recovery — the attempt store (stats / history)

**Status: recovered + composed (2026-07-06).** This resolves the `†`
Stats/History incompleteness flagged in `ARCHITECTURE.md` and carried in the
walk cloud as "not yet recovered". Files: `ProgressTableRecovered.wl` (agent),
`ProgressFunctions.wl` (function pass), writers wired in
`PracticeSessionRecovered.wl` / `StoryReaderRecovered.wl`, composed in
`MioCore.wl`, pinned by `spec/tests/progress_flow_test.wls`.

## What was recovered, from where

The app persists **every scored attempt immediately**: scoring runs
`_persist_result` (`src/ui/practice_tab.py:44`) which calls `save_practice`
(`src/app_mysql.py:1628`) — a plain `INSERT INTO user_progress`. Both practice
loops go through the same interface (`render_practice_interface`:
`story_tab.py:279`, `quick_practice_tab.py:1030`), so story practice persists
identically. Reads are queries over the same table:

| App read | Source | Spec recovery |
|---|---|---|
| Statistics tab numbers | `get_user_stats` (`app_mysql.py:1736`): total, perfect_count, avg_score, recent_avg (last 10 by date) | `statsView!(statsOf records)` |
| History tab sessions | `load_history` (`history_tab.py:20`) over `get_user_progress` (newest first) | `historyView!(historyOf records)` |
| Raw rows | `get_user_progress` (`app_mysql.py:1700`) | `progressRead!(records)` — the SELECT surface |

## The shape (VocabTable pattern, per-table naming)

`ProgressTable[records]` — a leaf store agent named after its table
(`user_progress`), resolving the older `Ledger`/`AttemptTable` placeholder.
Channels are table-scoped: `progressRead` / `progressAppend`. The append is
**append-only** (every attempt is a new row) — deliberately *not* an upsert,
unlike `vocabUpsert`'s dedup.

**The write is part of scoring, not a user action.** Both scoring chains
extend by one action:

```
attempt_made        · langRead?(lp) · progressAppend!(attemptRecord …) · PS′
story_attempt_made  · langRead?(lp) · progressAppend!(attemptRecord …) · StoryReader′
```

- `progressAppend` is **restricted** in `mioCore` (an internal τ): only the
  scoring chains write, matching the app (the insert lives inside
  `_persist_result`, behind no user-facing surface). One port, **two
  writers** — the `vocabUpsert` precedent.
- The mid-handoff NB from `capture_vocab` extends: the chain holds PS/
  StoryReader between `attempt_made` and the second τ, so L3 must treat
  score-and-log as **atomic** (no view flicker).
- Stats and History are **query projections on the store** — the Component
  Inventory's "view ports backed by store queries, not standalone interactive
  agents", made literal.

## Decisions a reviewer should check

1. **Naming.** `ProgressTable`, not `Ledger`/`AttemptTable`: the naming rule
   ("store agents are named after their table") post-dates the placeholder
   and wins. Rename is a one-file-set mechanical change if rejected.
2. **Record shape.** `save_practice`'s INSERT columns minus `user_id`
   (single-user L1) and `practice_date` (the clock is the DB's — insertion
   order stands in for date order; both are cloud items now). The app's
   `recognized_phrase` is the ASR transcript *text* — an oracle detail below
   the L1 boundary — so the recognised *phoneme string* stands in.
3. **Language at read time.** `get_user_stats`/`get_user_progress` filter by
   the *current* language; a view self-loop cannot borrow (`langRead`) as a
   projection prefix. Records instead **carry** `language_code` (baked in
   from the write-time borrow), so filtering is presentation over the
   published projection. If a filtered-at-source read is ever wanted, it
   enters as a value-carrying **query port** — the remaining rig option.
4. **Held-until-concrete.** With the ASR oracle uninterpreted, the appended
   row stays a symbolic `attemptRow[…]` term (the append τ still fires — the
   app always inserts). `statsOf`/`historyOf` aggregate the *concrete* rows
   and surface symbolic ones as a `pending` count, so the views stay honest
   Associations instead of warning-panel stubs. Consistent with "hold the
   score symbolic when the ASR oracle is uninterpreted".
5. **`progressRead` external.** No composed component pulls the raw rows yet,
   so it is not restricted (a dead restricted port would be unfireable). The
   first internal borrower — e.g. a practise-weakest-phrases route — restricts
   it exactly as `vocabRead` was.

## ProgressTable — provenance  (app src @ `504f8c8`, 2026-04-26)

| Spec element | Kind | Source `file:line (fn)` | App construct | Note |
|---|---|---|---|---|
| `ProgressTable` | agent | `app_mysql.py:1628 (save_practice)` + the `user_progress` table | per-user per-language practice log | **faithful** — the store agent for the table, VocabTable pattern. Verified: `progress_flow_test`. |
| `progressAppend` | sync (PS/StoryReader→ProgressTable τ) | `practice_tab.py:44 (_persist_result)` → `app_mysql.py:1628 (save_practice)` | INSERT on every scored attempt, inside the scoring path | **faithful** — restricted; ONE port, TWO writers (both loops share `render_practice_interface`: `story_tab.py:279`, `quick_practice_tab.py:1030`). Append-only (no upsert). Verified: `progress_flow_test` §2/§4, `maxprog_test`. |
| `progressRead` | port (out) | `app_mysql.py:1700 (get_user_progress)` | SELECT of the rows | **faithful** — the raw read surface; external until the first internal borrower. Verified: `progress_flow_test` §1. |
| `statsView` | projection | `app_mysql.py:1736 (get_user_stats)`, rendered `statistics_tab.py:49` | Statistics tab: total / perfect_count / avg_score / recent_avg | **simplified** — per-language *filtering* dropped at source (rows carry `language_code`; filtering is presentation). `pending` added for oracle-held rows (no app analogue — the app always has concrete scores). Verified: `progress_flow_test` §3/§5. |
| `historyView` | projection | `history_tab.py:20 (load_history)` over `get_user_progress` | History tab: newest-first sessions | **simplified** — group-by-date and LIMIT 100 dropped (the date is the external clock's stamp, below L1); newest-first kept via insertion order. Verified: `progress_flow_test` §3/§5. |
| `attemptRecord` / `attemptRow` | value-fn | `practice_tab.py:52-67 (_persist_result)` | the kwargs passed to `save_practice` | **simplified** — `user_id`/`practice_date` out of the model (single-user; external clock); `recognized_phrase` stands in as the recognised *phoneme* string (the transcript text is an oracle detail). Held until the score is concrete. Verified: `progress_flow_test` §5. |
| `appendAttempt` | value-fn | `app_mysql.py:1660` (the INSERT) | plain INSERT | **faithful** — `Append`, no dedup. Verified: `progress_flow_test` §2. |
| `statsOf` / `historyOf` | value-fn | `app_mysql.py:1736` / `history_tab.py:27-41` | the two queries | **simplified** — aggregates over concrete rows only, `None` (not `0.0`) when empty; last-10 by insertion order. Verified: `progress_flow_test` §3/§5. |

## What it pins (progress_flow_test.wls)

On **both** compositions (`mioCore`/`transVP`, `mioCoreD`/`transNamed`):
boundary (append restricted, query surface external); the write (one
`progressAppend` τ per scored attempt, store total grows); the held
discipline (pending count, `None` averages, the symbolic row carries the
borrowed target code); two writers (story path appends via the same
channel); and — with a test ASR downvalue — the concrete numeric pipeline
(perfect_count / averages / tabulated row with `language_code`).
