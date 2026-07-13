<script lang="ts">
  // The filtered+sorted collection (already projected by vocabView).
  import type { VocabEntry } from '../../domain/types.js';
  import { model } from '../../app/model.svelte.js';
  import VocabEditForm from './VocabEditForm.svelte';

  const {
    entries,
    editing,
  }: { entries: readonly VocabEntry[]; editing: number | null } = $props();
</script>

{#if entries.length === 0}
  <p class="muted">No entries yet — capture words by practising, add them above, or import.</p>
{:else}
  <div class="tablewrap card">
    <table>
      <thead>
        <tr><th>word</th><th>translation</th><th>IPA</th><th>seen</th><th>notes</th><th></th></tr>
      </thead>
      <tbody>
        {#each entries as e (e.id)}
          {#if editing === e.id}
            <tr><td colspan="6"><VocabEditForm entry={e} /></td></tr>
          {:else}
            <tr>
              <td class="word">{e.displayWord}</td>
              <td>{e.translation ?? ''}</td>
              <td class="ipa">{e.ipa !== null ? `[${e.ipa}]` : ''}</td>
              <td class="num">{e.timesSeen}</td>
              <td class="notes">{e.notes ?? ''}</td>
              <td class="actions">
                {#if e.translation === null || e.ipa === null}
                  <button
                    title="autofill missing translation/IPA (never overwrites)"
                    onclick={() => void model.autofillEntry(e.id)}>🪄</button
                  >
                {/if}
                <button title="edit" onclick={() => model.beginEdit(e.id)}>✏️</button>
                <button title="delete" onclick={() => model.removeEntry(e.id)}>🗑</button>
              </td>
            </tr>
          {/if}
        {/each}
      </tbody>
    </table>
  </div>
{/if}

<style>
  .tablewrap {
    overflow-x: auto;
    padding: 0.4rem;
  }

  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.92rem;
  }

  th,
  td {
    text-align: left;
    padding: 0.35rem 0.5rem;
    border-bottom: 1px solid var(--border);
  }

  .word {
    font-weight: 600;
  }

  .ipa {
    color: var(--accent);
  }

  .num {
    text-align: right;
  }

  .notes {
    color: var(--fg-muted);
    max-width: 14rem;
  }

  .actions button {
    padding: 0.1rem 0.35rem;
    margin-left: 0.2rem;
  }
</style>
