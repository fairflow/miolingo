<script lang="ts">
  // Dual-channel results — the GAP between comprehensibility and accuracy is
  // the diagnostic. Prop-driven (Quick Practice and Story Practice share it);
  // everything shown comes verbatim from the oracle response.
  import type { AttemptResponse } from '../../oracle/types.js';
  import IpaDiff from '../practice/IpaDiff.svelte';

  const {
    res,
    error,
  }: { res: AttemptResponse | null; error: string | null } = $props();

  const pct = (x: number | null): string => (x === null ? '—' : `${Math.round(x * 100)}%`);
</script>

{#if res !== null}
  <div class="card score">
    <p class="heard muted">
      Heard: <em>{res.recognized_text || '(nothing)'}</em>
      <span class="timing">({res.timings_ms.asr} ms ASR · {res.timings_ms.a2p} ms A2P)</span>
    </p>
    <p class="ref">Target IPA: <span class="ipa">[{res.target_ipa}]</span></p>

    <div class="channel">
      <h3>🗨️ Comprehensibility <strong>{pct(res.comprehensibility.similarity)}</strong></h3>
      <p class="muted small">espeak IPA of what Whisper understood</p>
      <IpaDiff ops={res.comprehensibility.ops} />
    </div>

    <div class="channel">
      <h3>🎯 Accuracy <strong>{pct(res.accuracy.similarity)}</strong></h3>
      <p class="muted small">phones read directly from your recording</p>
      {#if res.accuracy.similarity === null}
        <p class="muted">acoustic channel unavailable for this language</p>
      {:else}
        <IpaDiff ops={res.accuracy.ops} />
      {/if}
    </div>
  </div>
{:else if error !== null}
  <div class="card">
    <p class="errline">⚠️ {error}</p>
    <p class="muted">Is the oracle running? Re-record to try again.</p>
  </div>
{/if}

<style>
  .score {
    margin: 1rem 0;
  }

  .channel {
    margin-top: 0.9rem;
  }

  .channel h3 {
    margin: 0 0 0.15rem;
    font-size: 1rem;
  }

  .channel strong {
    margin-left: 0.4rem;
    color: var(--accent);
  }

  .small {
    font-size: 0.8rem;
    margin: 0 0 0.3rem;
  }

  .ipa {
    color: var(--accent);
  }

  .timing {
    font-size: 0.75rem;
  }

  .errline {
    color: var(--err);
  }
</style>
