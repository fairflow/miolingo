<script lang="ts">
  // Material sources for the practice queue (M4: unified files + vocab;
  // minimal pairs and free-text translate arrive in M8). Lists only the
  // files that cover the current target language (borrowed fresh from Helm).
  import { model } from '../../app/model.svelte.js';
  import { materialsIndex } from '../../oracle/client.js';
  import type { MaterialsFile } from '../../oracle/types.js';

  let files = $state<MaterialsFile[]>([]);
  let loadError = $state<string | null>(null);
  let loading = $state<string | null>(null);

  $effect(() => {
    materialsIndex().then(
      (idx) => (files = idx.files),
      (e: unknown) => (loadError = String(e)),
    );
  });

  const target = $derived(model.helm.target.split('-')[0] ?? model.helm.target);
  const covering = $derived(
    files.filter((f) => {
      const langs = f.meta['languages'];
      return Array.isArray(langs) ? langs.includes(target) : true;
    }),
  );

  function labelOf(f: MaterialsFile): string {
    const name = f.path.split('/').at(-1)?.replace('.json', '') ?? f.path;
    const count = f.meta['phrase_count'];
    return `${f.kind}: ${name}${typeof count === 'number' ? ` (${count})` : ''}`;
  }

  async function pick(path: string): Promise<void> {
    loading = path;
    loadError = null;
    try {
      await model.loadMaterialFile(path);
    } catch (e: unknown) {
      loadError = String(e);
    } finally {
      loading = null;
    }
  }
</script>

<details class="card" open={model.ps.phrases.length === 0}>
  <summary>📂 Load material ({covering.length} sets for {model.helm.target})</summary>
  <div class="sources">
    {#each covering as f (f.path)}
      <button onclick={() => pick(f.path)} disabled={loading !== null}>
        {loading === f.path ? '…' : labelOf(f)}
      </button>
    {/each}
    <button
      onclick={() => model.practiseVocab()}
      disabled={model.entries.length === 0}
      title={model.entries.length === 0 ? 'No vocabulary captured yet for this language' : ''}
    >
      📚 My vocabulary ({model.entries.length})
    </button>
  </div>
  {#if loadError !== null}
    <p class="muted">⚠️ {loadError}</p>
  {/if}
</details>

<style>
  .sources {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
    margin-top: 0.6rem;
  }
</style>
