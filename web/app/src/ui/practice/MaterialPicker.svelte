<script lang="ts">
  // Material sources for the practice queue (M4: unified files + vocab;
  // minimal pairs and free-text translate arrive in M8). Lists only the
  // files that cover the current target language (borrowed fresh from Helm).
  import { model } from '../../app/model.svelte.js';
  import { health, materialsIndex } from '../../oracle/client.js';
  import type { MaterialsFile } from '../../oracle/types.js';

  let files = $state<MaterialsFile[]>([]);
  let loadError = $state<string | null>(null);
  let loading = $state<string | null>(null);
  let translateAvailable = $state(false);
  let freeText = $state('');

  $effect(() => {
    materialsIndex().then(
      (idx) => (files = idx.files),
      (e: unknown) => (loadError = String(e)),
    );
    health().then(
      (h) => (translateAvailable = h.translate_available),
      () => (translateAvailable = false),
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

  async function run(label: string, fn: () => Promise<void>): Promise<void> {
    loading = label;
    loadError = null;
    try {
      await fn();
    } catch (e: unknown) {
      loadError = String(e);
    } finally {
      loading = null;
    }
  }

  const pick = (path: string): Promise<void> => run(path, () => model.loadMaterialFile(path));
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
    <button
      onclick={() => run('pairs', () => model.minimalPairsPractise())}
      disabled={model.entries.length < 2 || loading !== null}
      title="word pairs from your vocabulary differing by exactly one sound"
    >
      {loading === 'pairs' ? '…' : '👂 Minimal pairs'}
    </button>
  </div>
  {#if translateAvailable}
    <div class="freetext">
      <textarea
        rows="2"
        placeholder="Free text: type {model.helm.source} lines here to translate & practise…"
        bind:value={freeText}
      ></textarea>
      <button
        onclick={() => run('freetext', () => model.freeTextPractise(freeText))}
        disabled={freeText.trim() === '' || loading !== null}
      >
        {loading === 'freetext' ? '…' : '🔁 Translate & practise'}
      </button>
    </div>
  {/if}
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

  .freetext {
    display: flex;
    gap: 0.5rem;
    align-items: flex-end;
    margin-top: 0.6rem;
  }

  .freetext textarea {
    flex: 1;
    font: inherit;
    color: inherit;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 0.4rem 0.5rem;
    resize: vertical;
  }
</style>
