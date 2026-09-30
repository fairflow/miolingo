// =====================================================================
// Vocab — spec/VocabRecovered.wl: the vocabulary TAB. Holds ONLY the UI
// params (sort/filter/editing); the collection lives in VocabTable and is
// read fresh at view time (the (i) store split — own it → store it,
// borrow it → fetch fresh).
// =====================================================================

import type { VocabEntry, VocabSort } from './types.js';
import { applyFilter, sortEntries } from './vocabFunctions.js';

export interface Vocab {
  readonly signedIn: boolean;
  readonly sort: VocabSort;
  readonly filter: string | null;
  readonly editing: number | null; // editingRow id, or null
  readonly opened: boolean; // open_vocab taken (in the tab)
}

export const initialVocab: Vocab = {
  signedIn: true,
  sort: 'alpha',
  filter: null,
  editing: null,
  opened: false,
};

export function openVocab(v: Vocab): Vocab {
  return { ...v, opened: true };
}

export function setSort(v: Vocab, s: VocabSort): Vocab {
  return { ...v, sort: s };
}

export function setFilter(v: Vocab, q: string | null): Vocab {
  return { ...v, filter: q == null || q === '' ? null : q };
}

export function beginEdit(v: Vocab, id: number): Vocab {
  return { ...v, editing: id };
}

export function cancelEdit(v: Vocab): Vocab {
  return { ...v, editing: null };
}

export function endEdit(v: Vocab): Vocab {
  return { ...v, editing: null };
}

// --- vocabView — the read-only projection (spec/VocabFunctions.wl) ------
export interface VocabViewModel {
  readonly signedIn: boolean;
  readonly count: number;
  readonly sort: VocabSort;
  readonly filter: string | null;
  readonly editing: number | null;
  readonly entries: readonly VocabEntry[]; // filtered + sorted
}

export function vocabView(v: Vocab, entries: readonly VocabEntry[]): VocabViewModel {
  return {
    signedIn: v.signedIn,
    count: entries.length,
    sort: v.sort,
    filter: v.filter,
    editing: v.editing,
    entries: sortEntries(applyFilter(entries, v.filter), v.sort),
  };
}
