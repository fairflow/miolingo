<script lang="ts">
  // Generic bar chart (volume per day, score histogram) — hand-rolled SVG.
  const {
    values,
    labels,
    ariaLabel,
  }: { values: number[]; labels: string[]; ariaLabel: string } = $props();

  const W = 640;
  const H = 140;
  const PAD = 6;

  const max = $derived(Math.max(1, ...values));
  const bw = $derived((W - 2 * PAD) / Math.max(1, values.length));
</script>

<svg viewBox="0 0 {W} {H}" role="img" aria-label={ariaLabel}>
  {#each values as v, i (i)}
    <rect
      x={PAD + i * bw + 1}
      y={H - PAD - (v / max) * (H - 2 * PAD)}
      width={Math.max(1, bw - 2)}
      height={(v / max) * (H - 2 * PAD)}
      class="bar"
    >
      <title>{labels[i]}: {v}</title>
    </rect>
  {/each}
</svg>

<style>
  svg {
    width: 100%;
    height: auto;
  }

  .bar {
    fill: var(--accent);
    opacity: 0.8;
  }

  .bar:hover {
    opacity: 1;
  }
</style>
