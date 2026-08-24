// =====================================================================
// VocabTable — spec/VocabTableRecovered.wl: the external store that OWNS the
// persisted collection. The Vocab tab and PS read it fresh (vocabRead) and
// write through it (vocabUpsert/vocabImport/vocabRemove/vocabAmend) — no
// snapshots cross component boundaries. Persistence (Dexie) mirrors
// `entries` write-through in the AppModel.
// =====================================================================

import type { Capture, ImportRequest, VocabEntry } from './types.js';
import { addEntry, deleteFrom, updateEntry, updateNotesIn } from './vocabFunctions.js';
import { importInto } from './vocabImportExport.js';

export interface VocabTable {
  readonly entries: readonly VocabEntry[];
}

export const emptyVocabTable: VocabTable = { entries: [] };

/** vocabRead — the single source of truth, read fresh at point of use. */
export function read(t: VocabTable): readonly VocabEntry[] {
  return t.entries;
}

/** vocabUpsert (two writers: tab add + PS capture). */
export function upsert(t: VocabTable, w: Capture | string): VocabTable {
  return { entries: addEntry(t.entries, w) };
}

/** vocabImport */
export function importBulk(t: VocabTable, f: ImportRequest): VocabTable {
  return { entries: importInto(t.entries, f) };
}

/** vocabRemove */
export function remove(t: VocabTable, id: number): VocabTable {
  return { entries: deleteFrom(t.entries, id) };
}

/** vocabAmend */
export function amend(t: VocabTable, id: number, fields: Readonly<Record<string, string>>): VocabTable {
  return { entries: updateEntry(t.entries, id, fields) };
}

export function amendNotes(t: VocabTable, id: number, notes: string | null): VocabTable {
  return { entries: updateNotesIn(t.entries, id, notes) };
}
