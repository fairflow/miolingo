<script lang="ts">
  import { health } from '../../oracle/client.js';
  import type { OracleHealth } from '../../oracle/types.js';

  let status = $state<'checking' | 'ok' | 'offline'>('checking');
  let info = $state<OracleHealth | null>(null);

  async function check(): Promise<void> {
    try {
      info = await health();
      status = info.ok ? 'ok' : 'offline';
    } catch {
      info = null;
      status = 'offline';
    }
  }

  $effect(() => {
    void check();
    const id = setInterval(check, 15_000);
    return () => clearInterval(id);
  });

  const title = $derived(
    info
      ? `espeak: ${info.espeak ?? 'missing'} · A2P: ${info.a2p_langs.join(', ')}`
      : 'Phonetics oracle unreachable — scoring and materials are unavailable',
  );
</script>

<span class="badge {status}" {title}>
  ● {status === 'ok' ? 'oracle' : status}
</span>

<style>
  .badge {
    font-size: 0.8rem;
    color: var(--fg-muted);
  }

  .badge.ok {
    color: var(--ok);
  }

  .badge.offline {
    color: var(--err);
  }
</style>
