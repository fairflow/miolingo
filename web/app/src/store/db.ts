// Dexie / IndexedDB — the browser owns ALL user data (vocab, practice log,
// settings); the oracle sidecar is stateless. Store inputs, recompute derived
// values (astro pattern). ALWAYS pass values through $state.snapshot before
// writing — Svelte 5 proxies are not structured-cloneable (see PITFALLS).

import Dexie, { type EntityTable } from 'dexie';
import type { VocabEntry } from '../domain/types.js';
import type { Helm } from '../domain/helm.js';

/** vocab_entries row: the domain entry + language scope + wall-clock times
 * (the domain models a logical clock; wall-clock lives only here). */
export interface VocabRow extends VocabEntry {
  lang: string;
  firstSeenAt: string; // ISO
  lastSeenAt: string; // ISO
}

/** One practice attempt (superset of the app's user_progress + dual channel). */
export interface PracticeLogRow {
  id?: number; // Dexie auto-increment
  lang: string;
  date: string; // ISO
  target: string;
  recognized: string;
  targetIpa: string;
  algorithm: string;
  compIpa: string;
  compSimilarity: number | null;
  accIpa: string;
  accSimilarity: number | null;
  /** Primary-channel verdict (drives perfect_match compatibility). */
  perfect: boolean;
  similarity: number;
  origin: 'quick' | 'story' | 'vocab';
}

export interface SettingsRow {
  key: string;
  value: unknown;
}

export const db = new Dexie('miolingo') as Dexie & {
  vocab: EntityTable<VocabRow, 'id'>;
  practiceLog: EntityTable<PracticeLogRow, 'id'>;
  settings: EntityTable<SettingsRow, 'key'>;
};

db.version(1).stores({
  vocab: '++id, &[lang+word], lang, lastSeenAt',
  practiceLog: '++id, lang, date, [lang+target]',
  settings: '&key',
});

// --- settings helpers ---------------------------------------------------

export async function loadHelm(fallback: Helm): Promise<Helm> {
  try {
    const row = await db.settings.get('helm');
    if (row === undefined) return fallback;
    return { ...fallback, ...(row.value as Partial<Helm>) };
  } catch {
    return fallback;
  }
}

export async function saveHelm(helm: Helm): Promise<void> {
  await db.settings.put({ key: 'helm', value: helm });
}
