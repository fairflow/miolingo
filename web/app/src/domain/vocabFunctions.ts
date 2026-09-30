// =====================================================================
// VocabFunctions — ported verbatim (in behaviour) from spec/VocabFunctions.wl
// (recovered from src/vocab.py). Pure; the enrich oracle's async fetch lives
// outside — only the fill policy (never-overwrite) is modelled here.
// =====================================================================

import type { Capture, Phrase, VocabEntry, VocabSort } from './types.js';

// --- derived identity + logical clock ---------------------------------
export function vsNewId(entries: readonly VocabEntry[]): number {
  return 1 + entries.reduce((m, e) => Math.max(m, e.id), 0);
}

export function vsNextSeq(entries: readonly VocabEntry[]): number {
  return 1 + entries.reduce((m, e) => Math.max(m, e.lastSeq), 0);
}

export function emptyToNull(x: string | null | undefined): string | null {
  return x != null && x !== '' ? x : null;
}

function coalesce(old: string | null, next: string | null | undefined): string | null {
  return old == null || old === '' ? emptyToNull(next) : old;
}

// --- _normalise + validate_single_word (vocab.py:31, 50) --------------
// _TRIM_PUNCT: ASCII + curly quotes, guillemets, dashes, ellipsis.
const TRIM_CHARS = new Set([
  ...'.,;:!?"\'-',
  '“',
  '”',
  '‘',
  '’',
  '«',
  '»',
  '—',
  '–',
  '…',
]);

/** Strip surrounding (never inner) trim-punctuation. Returns {display, key}. */
export function normaliseWord(word: string): { display: string; key: string } {
  let t = Array.from(word.trim());
  while (t.length > 0 && TRIM_CHARS.has(t[0]!)) t = t.slice(1);
  while (t.length > 0 && TRIM_CHARS.has(t[t.length - 1]!)) t = t.slice(0, -1);
  const display = t.join('');
  return { display, key: display.toLowerCase() };
}

/** validate_single_word: {display, key} or null. */
export function validateWord(word: string): { display: string; key: string } | null {
  if (word.trim() === '') return null;
  const { display, key } = normaliseWord(word);
  if (key === '') return null; // only punctuation
  if (/\s/.test(key)) return null; // not a single word
  if (Array.from(key).length > 100) return null; // too long
  return { display, key };
}

// --- addEntry[entries, w] : capture_vocab_entry upsert (vocab.py:106) --
export function addEntry(entries: readonly VocabEntry[], w: Capture | string): VocabEntry[] {
  const cap: Capture = typeof w === 'string' ? { word: w } : w;
  const valid = validateWord(cap.word);
  if (valid === null) return [...entries];
  const { display, key } = valid;
  const idx = entries.findIndex((e) => e.word === key);
  if (idx >= 0) {
    const m = entries[idx]!;
    const updated: VocabEntry = {
      ...m,
      timesSeen: m.timesSeen + 1,
      lastSeq: vsNextSeq(entries), // advance the logical clock
      translation: coalesce(m.translation, cap.translation),
      ipa: coalesce(m.ipa, cap.ipa),
      sourceName: coalesce(m.sourceName, cap.sourceName),
      url: coalesce(m.url, cap.url),
      contextBefore: coalesce(m.contextBefore, cap.contextBefore),
      contextLine: coalesce(m.contextLine, cap.contextLine),
      contextAfter: coalesce(m.contextAfter, cap.contextAfter),
    };
    return entries.map((e, i) => (i === idx ? updated : e));
  }
  const seq = vsNextSeq(entries);
  const entry: VocabEntry = {
    id: vsNewId(entries),
    word: key,
    displayWord: display,
    translation: emptyToNull(cap.translation),
    ipa: emptyToNull(cap.ipa),
    sourceName: emptyToNull(cap.sourceName),
    url: emptyToNull(cap.url),
    contextBefore: emptyToNull(cap.contextBefore),
    contextLine: emptyToNull(cap.contextLine),
    contextAfter: emptyToNull(cap.contextAfter),
    timesSeen: 1,
    firstSeq: seq,
    lastSeq: seq,
    notes: null,
  };
  return [...entries, entry];
}

// --- deleteFrom[entries, id] : delete_vocab_entry (vocab.py:301) -------
export function deleteFrom(entries: readonly VocabEntry[], id: number): VocabEntry[] {
  return entries.filter((e) => e.id !== id);
}

// --- updateNotesIn (vocab.py:314) -------------------------------------
export function updateNotesIn(
  entries: readonly VocabEntry[],
  id: number,
  notes: string | null,
): VocabEntry[] {
  return entries.map((e) => (e.id === id ? { ...e, notes: emptyToNull(notes) } : e));
}

// --- updateEntry[entries, editingRow[id], fields] (vocab.py:343) -------
export const EDITABLE_FIELDS: ReadonlySet<string> = new Set([
  'display_word',
  'translation',
  'ipa',
  'source_name',
  'url',
  'context_before',
  'context_line',
  'context_after',
]);

/**
 * Apply an edit. Rejects unknown keys; rejects a display_word whose key would
 * change; "" → null. On any rejection returns the list unchanged.
 */
export function updateEntry(
  entries: readonly VocabEntry[],
  id: number,
  fields: Readonly<Record<string, string>>,
): VocabEntry[] {
  if (!Object.keys(fields).every((k) => EDITABLE_FIELDS.has(k))) return [...entries];
  const idx = entries.findIndex((e) => e.id === id);
  if (idx < 0) return [...entries];
  const row = entries[idx]!;
  const dw = fields['display_word'];
  if (dw !== undefined && normaliseWord(dw).key !== row.word) return [...entries];
  let m = { ...row };
  for (const [k, v] of Object.entries(fields)) {
    const nv = emptyToNull(v);
    switch (k) {
      case 'display_word':
        if (nv !== null) m = { ...m, displayWord: nv }; // display kept; key unchanged
        break;
      case 'translation':
        m = { ...m, translation: nv };
        break;
      case 'ipa':
        m = { ...m, ipa: nv };
        break;
      case 'source_name':
        m = { ...m, sourceName: nv };
        break;
      case 'url':
        m = { ...m, url: nv };
        break;
      case 'context_before':
        m = { ...m, contextBefore: nv };
        break;
      case 'context_line':
        m = { ...m, contextLine: nv };
        break;
      case 'context_after':
        m = { ...m, contextAfter: nv };
        break;
    }
  }
  return entries.map((e, i) => (i === idx ? m : e));
}

// --- autofill (vocab.py:411) — only-empty / never-overwrite ------------
/** What an enrich oracle returns for a word (translation and/or IPA). */
export interface EnrichFill {
  readonly translation?: string | null;
  readonly ipa?: string | null;
}

/**
 * Pure autofill policy: given the oracle's fill for entry `id`, compute the
 * fields to set — only ones currently empty; never overwrite. (The async
 * oracle fetch itself happens in the AppModel, borrowing the language pair
 * fresh via langRead.)
 */
export function autofillFields(
  entries: readonly VocabEntry[],
  id: number,
  fill: EnrichFill | null,
): Record<string, string> {
  const row = entries.find((e) => e.id === id);
  if (row === undefined || fill === null) return {};
  const out: Record<string, string> = {};
  const t = emptyToNull(fill.translation);
  if ((row.translation == null || row.translation === '') && t !== null) out['translation'] = t;
  const i = emptyToNull(fill.ipa);
  if ((row.ipa == null || row.ipa === '') && i !== null) out['ipa'] = i;
  return out;
}

// --- sort + filter (list_vocab order map + search; vocab.py:195) ------
export function sortEntries(entries: readonly VocabEntry[], order: VocabSort): VocabEntry[] {
  const out = [...entries];
  switch (order) {
    case 'alpha':
      return out.sort((a, b) => (a.word < b.word ? -1 : a.word > b.word ? 1 : 0));
    case 'recent':
      return out.sort((a, b) => b.lastSeq - a.lastSeq);
    case 'oldest':
      return out.sort((a, b) => a.firstSeq - b.firstSeq);
  }
}

function filterMatch(e: VocabEntry, filter: string | null): boolean {
  if (filter == null) return true;
  const needle = filter.toLowerCase();
  if (needle === '') return true;
  if (e.displayWord.toLowerCase().includes(needle)) return true;
  return (e.translation ?? '').toLowerCase().includes(needle);
}

export function applyFilter(entries: readonly VocabEntry[], filter: string | null): VocabEntry[] {
  return entries.filter((e) => filterMatch(e, filter));
}

// --- practiseList (vocab.py:644) — shape to practice phrases -----------
export function practiseList(entries: readonly VocabEntry[], filter: string | null): Phrase[] {
  return applyFilter(entries, filter).map((e) => ({
    text: e.displayWord,
    translation: e.translation ?? '',
    ipa: e.ipa ?? '',
  }));
}
