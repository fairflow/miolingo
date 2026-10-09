<script lang="ts">
  // Accuracy trend: one dot per attempt + rolling-10 mean line. Hand-rolled
  // SVG (astro render/ style) — CSS-var theming, viewBox scaling.
  import type { TrendPoint } from '../../domain/statsFunctions.js';

  const { points }: { points: TrendPoint[] } = $props();

  const W = 640;
  const H = 160;
  const PAD = 8;

  const x = (i: number): number =>
    points.length <= 1 ? W / 2 : PAD + (i / (points.length - 1)) * (W - 2 * PAD);
  const y = (v: number): number => H - PAD - v * (H - 2 * PAD);

  const line = $derived(points.map((p) => `${x(p.i).toFixed(1)},${y(p.rolling).toFixed(1)}`).join(' '));
</script>

<svg viewBox="0 0 {W} {H}" role="img" aria-label="accuracy trend">
  {#each [0.5, 1.0] as g (g)}
    <line x1={PAD} x2={W - PAD} y1={y(g)} y2={y(g)} class="grid" />
    <text x={PAD} y={y(g) - 3} class="tick">{Math.round(g * 100)}%</text>
  {/each}
  {#each points as p (p.i)}
    <circle cx={x(p.i)} cy={y(p.similarity)} r="2.4" class="dot">
      <title>{p.date.slice(0, 16).replace('T', ' ')} — {Math.round(p.similarity * 100)}%</title>
    </circle>
  {/each}
  {#if points.length > 1}
    <polyline points={line} class="rolling" />
  {/if}
</svg>

<style>
  svg {
    width: 100%;
    height: auto;
  }

  .grid {
    stroke: var(--border);
    stroke-dasharray: 3 4;
  }

  .tick {
    fill: var(--fg-muted);
    font-size: 9px;
  }

  .dot {
    fill: var(--accent);
    opacity: 0.55;
  }

  .rolling {
    fill: none;
    stroke: var(--ok);
    stroke-width: 2;
  }
</style>
