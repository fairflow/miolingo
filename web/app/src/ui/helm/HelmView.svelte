<script lang="ts">
  import { health } from '../../oracle/client.js';
  import type { OracleHealth } from '../../oracle/types.js';

  // M1: the Helm tab just surfaces what the oracle reports. The real Helm
  // agent (source/target/tts/speed guard/asr) lands with the domain core.
  let info = $state<OracleHealth | null>(null);
  let error = $state<string | null>(null);

  $effect(() => {
    health().then(
      (h) => (info = h),
      (e: unknown) => (error = String(e)),
    );
  });
</script>

<section class="card">
  <h2>⚙️ Helm</h2>
  <p class="muted">Language & engine settings arrive with the domain core (M2/M4).</p>
  {#if info}
    <dl>
      <dt>espeak</dt>
      <dd>{info.espeak ?? 'not found'}</dd>
      <dt>A2P recognizer languages</dt>
      <dd>{info.a2p_langs.join(', ')}</dd>
      <dt>Whisper</dt>
      <dd>{info.whisper.loaded ? `loaded (${info.whisper.model})` : 'loads on first attempt'}</dd>
      <dt>Translation</dt>
      <dd>{info.translate_available ? 'available' : 'not configured'}</dd>
    </dl>
  {:else if error}
    <p class="muted">Oracle unreachable: {error}</p>
  {/if}
</section>

<style>
  dt {
    font-weight: 600;
    margin-top: 0.5rem;
  }

  dd {
    margin: 0;
    color: var(--fg-muted);
  }
</style>
