// JSON export/import — the portability story for browser-owned data (and the
// landing pad for the one-off MySQL export, web/oracle/scripts/export_mysql.py,
// which emits exactly this shape). Ids are never exported or imported: vocab
// identity is [lang+word]; log rows are append-only.

import { db, type PracticeLogRow, type VocabRow } from './db.js';

type PortableVocab = Omit<VocabRow, 'id'>;
type PortableLog = Omit<PracticeLogRow, 'id'>;

export interface ExportFile {
  miolingo_export: 1;
  exportedAt: string;
  vocab: PortableVocab[];
  practiceLog: PortableLog[];
  settings: Record<string, unknown>;
}

const stripId = <T extends { id?: unknown }>(row: T): Omit<T, 'id'> => {
  const { id: _id, ...rest } = row;
  return rest;
};

export async function exportAll(): Promise<ExportFile> {
  const [vocab, practiceLog, settings] = await Promise.all([
    db.vocab.toArray(),
    db.practiceLog.toArray(),
    db.settings.toArray(),
  ]);
  return {
    miolingo_export: 1,
    exportedAt: new Date().toISOString(),
    vocab: vocab.map(stripId),
    practiceLog: practiceLog.map(stripId),
    settings: Object.fromEntries(settings.map((s) => [s.key, s.value])),
  };
}

/** Merge one incoming vocab row into an existing one: fill-never-overwrite
 * (addEntry semantics), sum timesSeen, widen the seen window. */
function mergeVocab(existing: VocabRow, incoming: PortableVocab): VocabRow {
  const fill = (old: string | null, next: string | null): string | null =>
    old == null || old === '' ? next : old;
  return {
    ...existing,
    translation: fill(existing.translation, incoming.translation),
    ipa: fill(existing.ipa, incoming.ipa),
    sourceName: fill(existing.sourceName, incoming.sourceName),
    url: fill(existing.url, incoming.url),
    contextBefore: fill(existing.contextBefore, incoming.contextBefore),
    contextLine: fill(existing.contextLine, incoming.contextLine),
    contextAfter: fill(existing.contextAfter, incoming.contextAfter),
    notes: fill(existing.notes, incoming.notes),
    timesSeen: existing.timesSeen + incoming.timesSeen,
    firstSeenAt:
      incoming.firstSeenAt < existing.firstSeenAt ? incoming.firstSeenAt : existing.firstSeenAt,
    lastSeenAt:
      incoming.lastSeenAt > existing.lastSeenAt ? incoming.lastSeenAt : existing.lastSeenAt,
  };
}

export interface ImportSummary {
  vocabAdded: number;
  vocabMerged: number;
  logAdded: number;
  settingsApplied: boolean;
}

/** Import an export file: vocab deduped on [lang+word], log rows appended,
 * settings applied only where absent (never clobber the local Helm). */
export async function importAll(
  data: ExportFile,
  opts: { applySettings?: boolean } = {},
): Promise<ImportSummary> {
  if (data.miolingo_export !== 1) throw new Error('not a miolingo export file');
  let vocabAdded = 0;
  let vocabMerged = 0;

  await db.transaction('rw', db.vocab, db.practiceLog, db.settings, async () => {
    for (const row of data.vocab) {
      const existing = await db.vocab.where('[lang+word]').equals([row.lang, row.word]).first();
      if (existing === undefined) {
        // clone: Dexie writes the assigned id back INTO the object it is
        // given, which would silently mutate the caller's import data
        await db.vocab.add({ ...row } as VocabRow);
        vocabAdded++;
      } else {
        await db.vocab.put(mergeVocab(existing, row));
        vocabMerged++;
      }
    }
    await db.practiceLog.bulkAdd(data.practiceLog.map((r) => ({ ...r }) as PracticeLogRow));
    if (opts.applySettings === true) {
      for (const [key, value] of Object.entries(data.settings)) {
        const existing = await db.settings.get(key);
        if (existing === undefined) await db.settings.put({ key, value });
      }
    }
  });

  return {
    vocabAdded,
    vocabMerged,
    logAdded: data.practiceLog.length,
    settingsApplied: opts.applySettings === true,
  };
}
