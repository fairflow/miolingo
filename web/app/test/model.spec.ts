// AppModel τ-channel wiring, driven with a stubbed oracle client (the walk
// harness pattern: the model is exercised end-to-end, the oracle is a fake).

import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { AttemptResponse } from '../src/oracle/types.js';

vi.mock('../src/oracle/client.js', () => ({
  attempt: vi.fn(),
  tts: vi.fn(),
  fetchMaterial: vi.fn(),
  materialsIndex: vi.fn(),
  health: vi.fn(),
}));

import { attempt } from '../src/oracle/client.js';
import { AppModel, channelToScore } from '../src/app/model.svelte.js';
import { db } from '../src/store/db.js';
import { phrase } from '../src/domain/types.js';

function fakeResponse(overrides: Partial<AttemptResponse> = {}): AttemptResponse {
  return {
    target: 'chat',
    recognized_text: 'chat',
    target_ipa: 'ʃa',
    algorithm: 'weighted_phone',
    comprehensibility: {
      ipa: 'ʃa',
      similarity: 1.0,
      exact: true,
      distance: 0,
      ops: [{ kind: 'match', target: 'ʃ', user: 'ʃ', significant: false }],
    },
    accuracy: {
      ipa: 'ʃ a',
      similarity: 0.9,
      exact: false,
      distance: 0.3,
      ops: [{ kind: 'match', target: 'ʃ', user: 'ʃ', significant: false }],
    },
    timings_ms: { asr: 10, a2p: 5, total: 20 },
    ...overrides,
  };
}

const take = () => new Blob([new Uint8Array([1, 2, 3])], { type: 'audio/webm' });

describe('AppModel wiring (stubbed oracle)', () => {
  let model: AppModel;

  beforeEach(async () => {
    await db.vocab.clear();
    await db.practiceLog.clear();
    await db.settings.clear();
    vi.mocked(attempt).mockResolvedValue(fakeResponse());
    model = new AppModel();
  });

  it('recording_made → attempt_made: scores, logs, and auto-captures a perfect single word', async () => {
    model.loadMaterial([phrase('chat', 'cat', 'ʃa')]);
    await model.recordingMade(take());

    expect(model.ps.res?.exactMatch).toBe(true); // primary = comprehensibility
    expect(model.lastAttempt?.accuracy.similarity).toBe(0.9);
    expect(vi.mocked(attempt).mock.calls[0]![0].lang).toBe('fr'); // langRead borrowed fresh

    const log = await db.practiceLog.toArray();
    expect(log).toHaveLength(1);
    expect(log[0]!).toMatchObject({ target: 'chat', lang: 'fr', perfect: true, origin: 'quick' });

    // auto-capture: perfect single word landed in the table AND Dexie
    expect(model.entries.map((e) => e.word)).toEqual(['chat']);
    const rows = await db.vocab.toArray();
    expect(rows[0]!).toMatchObject({ word: 'chat', lang: 'fr', ipa: 'ʃa' });
  });

  it('does not auto-capture imperfect or multi-word attempts', async () => {
    vi.mocked(attempt).mockResolvedValue(
      fakeResponse({
        target: 'le chat noir',
        comprehensibility: { ipa: 'x', similarity: 0.4, exact: false, distance: 2, ops: [] },
      }),
    );
    model.loadMaterial([phrase('le chat noir', '', 'lə ʃa nwaʁ')]);
    await model.recordingMade(take());
    expect(model.entries).toHaveLength(0);
  });

  it('capture_vocab · vocabUpsert is atomic: the PS slice is untouched', async () => {
    model.loadMaterial([phrase('chat', '', 'ʃa')]);
    await model.recordingMade(take());
    const psBefore = model.ps;
    model.captureVocab('chien');
    expect(model.ps).toBe(psBefore); // zero PS transitions during capture
    expect(model.ps.res).not.toBeNull(); // score still displayed
    expect(model.entries.map((e) => e.word)).toContain('chien');
  });

  it('lastAttempt lifecycle is slaved to ps.res (clears on nav)', async () => {
    model.loadMaterial([phrase('chat', '', 'ʃa'), phrase('chien', '', 'ʃjɛ̃')]);
    await model.recordingMade(take());
    expect(model.lastAttempt).not.toBeNull();
    model.next();
    expect(model.ps.res).toBeNull();
    expect(model.lastAttempt).toBeNull();
  });

  it('a failed attempt clears the take so re-record works', async () => {
    vi.mocked(attempt).mockRejectedValue(new Error('oracle down'));
    model.loadMaterial([phrase('chat', '', 'ʃa')]);
    await model.recordingMade(take());
    expect(model.error).toContain('oracle down');
    expect(model.ps.rec).toBeNull(); // ready to re-record
    expect(model.lastAttempt).toBeNull();
  });

  it('setHelm target switch clears the queue and rescopes the vocab table', async () => {
    model.loadMaterial([phrase('chat', '', 'ʃa')]);
    model.captureVocab('chat'); // fr row
    await model.setHelm({ ...model.helm, target: 'pt-br' });
    expect(model.ps.phrases).toHaveLength(0); // stale-language queue cleared
    expect(model.entries).toHaveLength(0); // pt-br table is empty
    const persisted = await db.settings.get('helm');
    expect((persisted?.value as { target: string }).target).toBe('pt-br');
  });

  it('goPractice: practiseVocab pulls the collection fresh (vocabRead)', () => {
    model.captureVocab({ word: 'chat', translation: 'cat', ipa: 'ʃa' });
    model.practiseVocab();
    expect(model.ps.phrases).toEqual([phrase('chat', 'cat', 'ʃa')]);
  });

  it('channelToScore maps oracle ops onto the spec alignment shape', () => {
    const res = fakeResponse({
      comprehensibility: {
        ipa: 'ʃo',
        similarity: 0.5,
        exact: false,
        distance: 1,
        ops: [
          { kind: 'match', target: 'ʃ', user: 'ʃ', significant: false },
          { kind: 'substitute', target: 'a', user: 'o', significant: true },
        ],
      },
    });
    const s = channelToScore(res, res.comprehensibility);
    expect(s.alignment).toEqual([
      { op: 'equal', target: 'ʃ', user: 'ʃ' },
      { op: 'sub', target: 'a', user: 'o' },
    ]);
    expect(s.target).toBe('ʃa');
  });
});
