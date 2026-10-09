<script lang="ts">
  // The Vocab TAB (spec Vocab agent): sort/filter/add/import/export chrome.
  // Renders ONLY vocabView(model.vocab, model.entries) — the collection is
  // read fresh from the table at view time (borrow, never cache).
  import { model } from '../../app/model.svelte.js';
  import { vocabView } from '../../domain/vocab.js';
  import type { VocabSort } from '../../domain/types.js';
  import VocabTableView from './VocabTableView.svelte';
  import ImportExportBar from './ImportExportBar.svelte';
  import { setTab } from '../../store/prefs.svelte.js';

  const view = $derived(vocabView(model.vocab, model.entries));

  let newWord = $state('');
  let addNote = $state<string | null>(null);

  function add(): void {
    const word = newWord.trim();
    if (word === '') return;
    const before = model.entries.length;
    model.captureVocab({ word, sourceName: 'manual' });
    addNote =
      model.entries.length > before
        ? `added “${word}”`
        : model.entries.some((e) => e.word === word.toLowerCase())
          ? `bumped “${word}” (already known)`
          : `“${word}” is not a single word`;
    newWord = '';
  }

  function practise(): void {
    model.practiseVocab(view.filter); // goPractice carries only the filter
    setTab('practice');
  }
</script>

<section>
  <div class="card controls">
    <h2>📚 Vocabulary — {model.helm.target} ({view.count})</h2>
    <div class="row">
      <input
        placeholder="add a word…"
        bind:value={newWord}
        onkeydown={(e) => e.key === 'Enter' && add()}
      />
      <button onclick={add}>＋ Add</button>
      {#if addNote !== null}<span class="muted">{addNote}</span>{/if}
    </div>
    <div class="row">
      <label
        >Sort
        <select
          value={view.sort}
          onchange={(e) => model.setVocabSort(e.currentTarget.value as VocabSort)}
        >
          <option value="alpha">A→Z</option>
          <option value="recent">recently seen</option>
          <option value="oldest">first captured</option>
        </select>
      </label>
      <input
        placeholder="filter…"
        value={view.filter ?? ''}
        oninput={(e) => model.setVocabFilter(e.currentTarget.value)}
      />
      <button onclick={practise} disabled={view.entries.length === 0}>
        🎯 Practise these ({view.entries.length})
      </button>
    </div>
    <ImportExportBar />
  </div>

  <VocabTableView entries={view.entries} editing={view.editing} />
</section>

<style>
  .controls .row {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    flex-wrap: wrap;
    margin: 0.5rem 0;
  }

  input,
  select {
    font: inherit;
    color: inherit;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 0.35rem 0.5rem;
  }

  label {
    display: flex;
    align-items: center;
    gap: 0.4rem;
  }
</style>
