// Dexie store roundtrip (the spec's storeRoundTrip row, web edition) —
// runs on fake-indexeddb. Export/import identity arrives with M5.

import { beforeEach, describe, expect, it } from 'vitest';
import { db, loadHelm, saveHelm } from '../src/store/db.js';
import { defaultHelm } from '../src/domain/helm.js';

describe('Dexie store roundtrip', () => {
  beforeEach(async () => {
    await db.vocab.clear();
    await db.practiceLog.clear();
    await db.settings.clear();
  });

  it('vocab rows round-trip and enforce the [lang+word] unique key', async () => {
    const base = {
      word: 'chat',
      displayWord: 'chat',
      translation: 'cat',
      ipa: 'ʃa',
      sourceName: null,
      url: null,
      contextBefore: null,
      contextLine: null,
      contextAfter: null,
      timesSeen: 1,
      firstSeq: 1,
      lastSeq: 1,
      notes: null,
      lang: 'fr',
      firstSeenAt: '2026-07-12T00:00:00Z',
      lastSeenAt: '2026-07-12T00:00:00Z',
    };
    await db.vocab.add({ ...base, id: 1 });
    await expect(db.vocab.add({ ...base, id: 2 })).rejects.toThrow(); // &[lang+word]
    await db.vocab.add({ ...base, id: 3, lang: 'pt-br' }); // same word, other lang: fine
    const fr = await db.vocab.where('lang').equals('fr').toArray();
    expect(fr).toHaveLength(1);
    expect(fr[0]!).toMatchObject({ word: 'chat', translation: 'cat', ipa: 'ʃa' });
  });

  it('helm settings round-trip with forward-compatible merge', async () => {
    await saveHelm({ ...defaultHelm, target: 'pt-br', tts: 'espeak', speed: 180 });
    const back = await loadHelm(defaultHelm);
    expect(back.target).toBe('pt-br');
    expect(back.speed).toBe(180);
    expect(back.asrModel).toBe(defaultHelm.asrModel); // absent fields → defaults
  });

  it('practice log rows accumulate per language', async () => {
    await db.practiceLog.add({
      lang: 'fr',
      date: '2026-07-12T10:00:00Z',
      target: 'chat',
      recognized: 'chat',
      targetIpa: 'ʃa',
      algorithm: 'weighted_phone',
      compIpa: 'ʃa',
      compSimilarity: 1,
      accIpa: 'ʃ a',
      accSimilarity: 0.9,
      perfect: true,
      similarity: 1,
      origin: 'quick',
    });
    expect(await db.practiceLog.where('lang').equals('fr').count()).toBe(1);
    expect(await db.practiceLog.where('lang').equals('pt-br').count()).toBe(0);
  });
});
