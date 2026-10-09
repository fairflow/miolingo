<script lang="ts">
  // Inline row editor — writes go through vocabAmend (updateEntry), which
  // rejects unknown fields and display words that would change the key.
  import type { VocabEntry } from '../../domain/types.js';
  import { model } from '../../app/model.svelte.js';

  const { entry }: { entry: VocabEntry } = $props();

  let displayWord = $state(entry.displayWord);
  let translation = $state(entry.translation ?? '');
  let ipa = $state(entry.ipa ?? '');
  let notes = $state(entry.notes ?? '');

  function save(): void {
    model.amendEntry(entry.id, {
      display_word: displayWord,
      translation,
      ipa,
    });
    model.amendNotes(entry.id, notes === '' ? null : notes);
  }
</script>

<div class="edit">
  <label>word <input bind:value={displayWord} title="case only — the key cannot change" /></label>
  <label>translation <input bind:value={translation} /></label>
  <label>IPA <input bind:value={ipa} /></label>
  <label>notes <input bind:value={notes} /></label>
  <div class="buttons">
    <button onclick={save}>💾 Save</button>
    <button onclick={() => model.cancelEdit()}>Cancel</button>
  </div>
</div>

<style>
  .edit {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    align-items: end;
    padding: 0.3rem 0;
  }

  label {
    display: flex;
    flex-direction: column;
    font-size: 0.8rem;
    color: var(--fg-muted);
  }

  input {
    font: inherit;
    color: var(--fg);
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 0.3rem 0.45rem;
  }

  .buttons {
    display: flex;
    gap: 0.4rem;
  }
</style>
