<script lang="ts">
  // CSV export (the spec's exportCsv), bulk text import (header-guarded),
  // and whole-store JSON export/import (incl. the MySQL migration file).
  import { model } from '../../app/model.svelte.js';
  import { exportAll, importAll, type ExportFile } from '../../store/exportImport.js';

  let note = $state<string | null>(null);

  function download(name: string, text: string, type: string): void {
    const url = URL.createObjectURL(new Blob([text], { type }));
    const a = document.createElement('a');
    a.href = url;
    a.download = name;
    a.click();
    URL.revokeObjectURL(url);
  }

  function exportCsvFile(): void {
    download(`miolingo-vocab-${model.helm.target}.csv`, model.exportCsvString(), 'text/csv');
  }

  async function exportJsonFile(): Promise<void> {
    const data = await exportAll();
    download('miolingo-export.json', JSON.stringify(data, null, 1), 'application/json');
  }

  async function onBulkFile(e: Event): Promise<void> {
    const input = e.currentTarget as HTMLInputElement;
    const file = input.files?.[0];
    if (file === undefined) return;
    const result = model.importBulk(await file.text());
    note =
      result.kind === 'ok'
        ? `imported ${result.added} new entries`
        : result.kind === 'noHeader'
          ? 'no (target,source) header line — nothing imported'
          : result.kind === 'targetMismatch'
            ? `file is for “${result.fileTarget}”, current target is “${result.expected}”`
            : `too many lines (${result.count} > 250)`;
    input.value = '';
  }

  async function onJsonFile(e: Event): Promise<void> {
    const input = e.currentTarget as HTMLInputElement;
    const file = input.files?.[0];
    if (file === undefined) return;
    try {
      const data = JSON.parse(await file.text()) as ExportFile;
      const s = await importAll(data);
      await model.reloadEntries();
      note = `imported: ${s.vocabAdded} new + ${s.vocabMerged} merged vocab, ${s.logAdded} log rows`;
    } catch (err: unknown) {
      note = `import failed: ${String(err)}`;
    }
    input.value = '';
  }
</script>

<div class="row">
  <button onclick={exportCsvFile} disabled={model.entries.length === 0}>⬇ CSV</button>
  <button onclick={exportJsonFile}>⬇ Export JSON</button>
  <label class="filebtn">
    ⬆ Import JSON<input type="file" accept=".json" onchange={onJsonFile} />
  </label>
  <label class="filebtn">
    ⬆ Bulk text<input type="file" accept=".txt,.text" onchange={onBulkFile} />
  </label>
  {#if note !== null}<span class="muted">{note}</span>{/if}
</div>

<style>
  .row {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    flex-wrap: wrap;
  }

  .filebtn {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 0.4rem 0.9rem;
    cursor: pointer;
  }

  .filebtn input {
    display: none;
  }
</style>
