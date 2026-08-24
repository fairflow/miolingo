<script lang="ts">
  // Statistics over the Dexie practice log for the current language —
  // computed client-side by pure domain functions (the SQL queries the
  // Streamlit app ran server-side, replaced).
  import { model } from '../../app/model.svelte.js';
  import { db, type PracticeLogRow } from '../../store/db.js';
  import {
    histogram,
    summarize,
    trendPoints,
    volumeByDay,
    weakestPhrases,
  } from '../../domain/statsFunctions.js';
  import TrendChart from './TrendChart.svelte';
  import BarChart from './BarChart.svelte';

  let rows = $state<PracticeLogRow[]>([]);

  $effect(() => {
    void db.practiceLog
      .where('lang')
      .equals(model.helm.target)
      .toArray()
      .then((r) => (rows = r));
  });

  const summary = $derived(summarize(rows));
  const trend = $derived(trendPoints(rows));
  const volume = $derived(volumeByDay(rows));
  const hist = $derived(histogram(rows));
  const weakest = $derived(weakestPhrases(rows));
  const histLabels = $derived(hist.map((_, i) => `${i * 5}–${(i + 1) * 5}%`));

  const pct = (x: number | null): string => (x === null ? '—' : `${Math.round(x * 100)}%`);
</script>

<section>
  <h2>📊 Statistics — {model.helm.target}</h2>
  {#if rows.length === 0}
    <p class="muted">No practice attempts logged for this language yet.</p>
  {:else}
    <div class="tiles">
      <div class="card tile"><strong>{summary.attempts}</strong><span>attempts</span></div>
      <div class="card tile"><strong>{pct(summary.meanSimilarity)}</strong><span>mean score</span></div>
      <div class="card tile"><strong>{summary.perfectCount}</strong><span>perfect</span></div>
      <div class="card tile"><strong>{summary.distinctPhrases}</strong><span>phrases</span></div>
    </div>

    <div class="card chart">
      <h3>Accuracy trend <span class="muted">(dots = attempts, line = rolling 10)</span></h3>
      <TrendChart points={trend} />
    </div>

    <div class="card chart">
      <h3>Practice volume <span class="muted">(attempts per day)</span></h3>
      <BarChart
        values={volume.map((v) => v.count)}
        labels={volume.map((v) => v.day)}
        ariaLabel="attempts per day"
      />
    </div>

    <div class="card chart">
      <h3>Score distribution</h3>
      <BarChart values={hist} labels={histLabels} ariaLabel="score distribution" />
    </div>

    {#if weakest.length > 0}
      <div class="card">
        <h3>Weakest phrases <span class="muted">(≥3 attempts)</span></h3>
        <table>
          <thead><tr><th>phrase</th><th>attempts</th><th>mean</th><th>last tried</th></tr></thead>
          <tbody>
            {#each weakest as w (w.target)}
              <tr>
                <td>{w.target}</td>
                <td class="num">{w.attempts}</td>
                <td class="num">{pct(w.mean)}</td>
                <td class="muted">{w.lastDate.slice(0, 10)}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {/if}
  {/if}
</section>

<style>
  .tiles {
    display: flex;
    gap: 0.6rem;
    flex-wrap: wrap;
    margin-bottom: 0.8rem;
  }

  .tile {
    display: flex;
    flex-direction: column;
    align-items: center;
    min-width: 6.5rem;
    padding: 0.6rem 1rem;
  }

  .tile strong {
    font-size: 1.4rem;
    color: var(--accent);
  }

  .tile span {
    font-size: 0.8rem;
    color: var(--fg-muted);
  }

  .chart {
    margin-bottom: 0.8rem;
  }

  .chart h3,
  .card h3 {
    margin: 0 0 0.5rem;
    font-size: 0.95rem;
  }

  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.92rem;
  }

  th,
  td {
    text-align: left;
    padding: 0.3rem 0.5rem;
    border-bottom: 1px solid var(--border);
  }

  .num {
    text-align: right;
  }
</style>
