<script lang="ts">
  // Renders one channel's per-phone ops VERBATIM from the oracle (the ops
  // always come from the same scorer that produced the number — the UI never
  // recomputes a diff). Substitutions the fold-map tolerates render as
  // accent (soft), significant ones as error (hard).
  import type { AttemptOp } from '../../oracle/types.js';

  const { ops }: { ops: AttemptOp[] } = $props();

  function cls(op: AttemptOp): string {
    if (op.kind === 'match') return 'match';
    if (op.kind === 'substitute') return op.significant ? 'sub-hard' : 'sub-soft';
    return op.significant ? `${op.kind} hard` : op.kind;
  }

  function label(op: AttemptOp): string {
    switch (op.kind) {
      case 'match':
        return op.target;
      case 'substitute':
        return `${op.target}→${op.user}`;
      case 'delete':
        return op.target;
      case 'insert':
        return `+${op.user}`;
    }
  }

  function title(op: AttemptOp): string {
    switch (op.kind) {
      case 'match':
        return `${op.target} — matched`;
      case 'substitute':
        return op.significant
          ? `said ${op.user} for ${op.target} — error`
          : `said ${op.user} for ${op.target} — tolerated accent variation`;
      case 'delete':
        return `${op.target} — missing`;
      case 'insert':
        return `${op.user} — extra`;
    }
  }
</script>

<span class="diff">
  {#each ops as op, i (i)}
    <span class="seg {cls(op)}" title={title(op)}>{label(op)}</span>
  {/each}
</span>

<style>
  .diff {
    display: inline-flex;
    flex-wrap: wrap;
    gap: 0.15rem;
    font-size: 1.15rem;
    line-height: 1.8;
  }

  .seg {
    padding: 0 0.2rem;
    border-radius: 4px;
  }

  .seg.match {
    color: var(--ok);
  }

  .seg.sub-soft {
    color: var(--warn);
  }

  .seg.sub-hard {
    color: var(--err);
    background: color-mix(in srgb, var(--err) 14%, transparent);
  }

  .seg.delete {
    color: var(--err);
    text-decoration: line-through;
  }

  .seg.insert {
    color: var(--warn);
    font-style: italic;
  }
</style>
