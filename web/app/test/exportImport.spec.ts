// Export → wipe → import identity, merge semantics, and the MySQL-export
// shape (the script emits exactly this format).

import { beforeEach, describe, expect, it } from 'vitest';
import { db, type VocabRow } from '../src/store/db.js';
import { exportAll, importAll, type ExportFile } from '../src/store/exportImport.js';

const row = (over: Partial<VocabRow> = {}): Omit<VocabRow, 'id'> => ({
  lang: 'fr',
  word: 'chat',
  displayWord: 'chat',
  translation: 'cat',
  ipa: 'ʃa',
  sourceName: null,
  url: null,
  contextBefore: null,
  contextLine: null,
  contextAfter: null,
  timesSeen: 2,
  firstSeq: 1,
  lastSeq: 1,
  notes: null,
  firstSeenAt: '2026-01-01T00:00:00Z',
  lastSeenAt: '2026-06-01T00:00:00Z',
  ...over,
});

describe('JSON export/import', () => {
  beforeEach(async () => {
    await db.vocab.clear();
    await db.practiceLog.clear();
    await db.settings.clear();
  });

  it('export → wipe → import is identity (minus ids)', async () => {
    await db.vocab.bulkAdd([row(), row({ word: 'chien', displayWord: 'chien' })] as VocabRow[]);
    await db.practiceLog.add({
      lang: 'fr',
      date: '2026-07-12T10:00:00Z',
      target: 'chat',
      recognized: 'chat',
      targetIpa: 'ʃa',
      algorithm: 'weighted_phone',
      compIpa: 'ʃa',
      compSimilarity: 1,
      accIpa: '',
      accSimilarity: null,
      perfect: true,
      similarity: 1,
      origin: 'quick',
    });

    const exported = await exportAll();
    expect(exported.vocab).toHaveLength(2);
    expect(exported.vocab[0]).not.toHaveProperty('id');

    await db.vocab.clear();
    await db.practiceLog.clear();
    const summary = await importAll(exported);
    expect(summary).toMatchObject({ vocabAdded: 2, vocabMerged: 0, logAdded: 1 });

    const back = await exportAll();
    expect(back.vocab).toEqual(exported.vocab);
    expect(back.practiceLog).toEqual(exported.practiceLog);
  });

  it('merges duplicates: fill-never-overwrite, timesSeen summed, window widened', async () => {
    await db.vocab.add(row({ translation: 'cat', ipa: null, timesSeen: 2 }) as VocabRow);
    const incoming: ExportFile = {
      miolingo_export: 1,
      exportedAt: 'x',
      vocab: [
        row({
          translation: 'feline',
          ipa: 'ʃa',
          timesSeen: 3,
          firstSeenAt: '2025-01-01T00:00:00Z',
          lastSeenAt: '2026-07-01T00:00:00Z',
        }),
      ],
      practiceLog: [],
      settings: {},
    };
    const s = await importAll(incoming);
    expect(s).toMatchObject({ vocabAdded: 0, vocabMerged: 1 });
    const merged = (await db.vocab.toArray())[0]!;
    expect(merged.translation).toBe('cat'); // never overwritten
    expect(merged.ipa).toBe('ʃa'); // filled
    expect(merged.timesSeen).toBe(5); // summed
    expect(merged.firstSeenAt).toBe('2025-01-01T00:00:00Z'); // widened
    expect(merged.lastSeenAt).toBe('2026-07-01T00:00:00Z');
  });

  it('rejects non-export files and leaves local settings alone by default', async () => {
    await expect(importAll({ nope: true } as unknown as ExportFile)).rejects.toThrow();
    await db.settings.put({ key: 'helm', value: { target: 'fr' } });
    await importAll({
      miolingo_export: 1,
      exportedAt: 'x',
      vocab: [],
      practiceLog: [],
      settings: { helm: { target: 'ru' } },
    });
    const helm = await db.settings.get('helm');
    expect((helm?.value as { target: string }).target).toBe('fr'); // untouched
  });
});
