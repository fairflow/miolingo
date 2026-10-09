<script lang="ts">
  // Practice history: the last 100 attempts for the current language,
  // grouped by day, newest first — straight from the Dexie log.
  import { model } from '../../app/model.svelte.js';
  import { db, type PracticeLogRow } from '../../store/db.js';
  import { historyByDate } from '../../domain/statsFunctions.js';

  let rows = $state<PracticeLogRow[]>([]);

  $effect(() => {
    void db.practiceLog
      .where('lang')
      .equals(model.helm.target)
      .toArray()
      .then((r) => (rows = r));
  });

  const groups = $derived(historyByDate(rows));
  const pct = (x: number | null): string => (x === null ? '—' : `${Math.round(x * 100)}%`);
</script>

<section>
  <h2>📜 History — {model.helm.target}</h2>
  {#if groups.length === 0}
    <p class="muted">No practice attempts logged for this language yet.</p>
  {/if}
  {#each groups as g (g.day)}
    <div class="card day">
      <h3>{g.day} <span class="muted">({g.attempts.length} attempts)</span></h3>
      <table>
        <tbody>
          {#each g.attempts as a, i (i)}
            <tr>
              <td class="time muted">{a.date.slice(11, 16)}</td>
              <td class="target">{a.target}</td>
              <td class="muted">{a.recognized}</td>
              <td class="num" class:good={a.similarity >= 0.8} class:bad={a.similarity < 0.5}>
                {pct(a.similarity)}
              </td>
              <td>{a.perfect === true ? '✅' : ''}</td>
              <td class="muted">{a.origin}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/each}
</section>

<style>
  .day {
    margin-bottom: 0.8rem;
  }

  .day h3 {
    margin: 0 0 0.4rem;
    font-size: 0.95rem;
  }

  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.9rem;
  }

  td {
    padding: 0.25rem 0.5rem;
    border-bottom: 1px solid var(--border);
  }

  .time {
    white-space: nowrap;
  }

  .target {
    font-weight: 600;
  }

  .num {
    text-align: right;
  }

  .num.good {
    color: var(--ok);
  }

  .num.bad {
    color: var(--err);
  }
</style>
