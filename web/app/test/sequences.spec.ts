// Sequence tests — the analogue of spec/walk-tests.wl's `walkTests` (and
// swift ComponentSequenceTests). Each replays a named plan through the pure
// components with the restricted cross-component channels wired as direct
// calls (exactly what the AppModel does in M4), asserting the end state.

import { describe, expect, it } from 'vitest';
import * as ps from '../src/domain/practiceSession.js';
import * as story from '../src/domain/storyReader.js';
import * as table from '../src/domain/vocabTable.js';
import { practiseList } from '../src/domain/vocabFunctions.js';
import { phrase } from '../src/domain/types.js';

const bytes = (...xs: number[]) => new Uint8Array(xs);

describe('walk sequences', () => {
  it('vs_capture: add a word → it lands in the store', () => {
    const t = table.upsert(table.emptyVocabTable, 'souris'); // add → vocabUpsert
    expect(table.read(t).map((e) => e.word)).toEqual(['souris']);
  });

  it('vs_import: bulk import with a matching header', () => {
    const t = table.importBulk(table.emptyVocabTable, {
      contents: '(fr,en)\nchat|cat\nchien|dog',
      expectedTarget: 'fr',
    });
    expect(new Set(table.read(t).map((e) => e.word))).toEqual(new Set(['chat', 'chien']));
  });

  it('ps_score: load_material → recording_made → attempt_made', () => {
    let s = ps.load(ps.initialPS, [phrase('chat', '', 'ʃa')]);
    s = ps.recordingMade(s, bytes(1));
    s = ps.score(s, 'ʃa'); // attempt_made (langRead + ASR upstream)
    expect(s.res?.exactMatch).toBe(true);
  });

  it('sync_practise (goPractice): Vocab signals, PS pulls the collection fresh', () => {
    const t = table.upsert(table.emptyVocabTable, {
      word: 'chat',
      translation: 'cat',
      ipa: 'ʃa',
    });
    // goPractice carries only the filter; PS pulls via vocabRead:
    const s = ps.load(ps.initialPS, practiseList(table.read(t), null));
    expect(s.phrases).toEqual([phrase('chat', 'cat', 'ʃa')]);
  });

  it('full_roundtrip: practise → capture → reaches the store', () => {
    let t = table.emptyVocabTable;
    let s = ps.load(ps.initialPS, [phrase('chien', '', 'ʃjɛ̃')]);
    s = ps.recordingMade(s, bytes(2));
    s = ps.score(s, 'ʃjɛ̃');
    const w = ps.captureWord(s);
    if (w !== null) t = table.upsert(t, w); // capture_vocab → vocabUpsert
    expect(table.read(t).map((e) => e.word)).toEqual(['chien']);
  });

  it('story_capture_roundtrip: story practice capture; position preserved', () => {
    const lib = story.fixtureStoryLibrary;
    let t = table.emptyVocabTable;
    let s = story.setMode(story.initialStoryReader, 'practice'); // scene 0, pos 0
    s = story.recordingMade(s, bytes(3));
    s = story.score(s, lib, 'bɔ̃ʒuʁ');
    const w = story.captureWord(s, lib);
    if (w !== null) t = table.upsert(t, w); // story_capture_vocab → vocabUpsert
    expect(table.read(t)[0]?.displayWord).toBe('Bonjour');
    expect(s.pos).toBe(0); // capture does not move the position
  });

  it('capture_atomic_no_flicker: capture leaves PS untouched (res retained)', () => {
    // The spec notes capture·vocabUpsert! momentarily offers no view — a
    // modelling artifact. The port makes it structural: capture writes the
    // TABLE only; the PS slice is not part of the transition at all.
    let t = table.emptyVocabTable;
    let s = ps.load(ps.initialPS, [phrase('chat', '', 'ʃa')]);
    s = ps.recordingMade(s, bytes(1));
    s = ps.score(s, 'ʃa');
    const before = s;
    const w = ps.captureWord(s);
    if (w !== null) t = table.upsert(t, w);
    expect(s).toBe(before); // exactly zero PS transitions during capture
    expect(s.res).not.toBeNull(); // score still displayed after capture
    expect(table.read(t)).toHaveLength(1);
  });

  it('readySet gates the controls (enablement is never UI-decided)', () => {
    let s = ps.initialPS;
    expect(ps.psReady(s).canRecord).toBe(false); // empty queue
    s = ps.load(s, [phrase('a', '', 'a'), phrase('b', '', 'b')]);
    expect(ps.psReady(s)).toMatchObject({ canRecord: true, canScore: false, canCapture: false });
    s = ps.recordingMade(s, bytes(1));
    expect(ps.psReady(s)).toMatchObject({ canRecord: false, canScore: true });
    s = ps.score(s, 'a');
    expect(ps.psReady(s)).toMatchObject({ canScore: false, canCapture: true, canNext: true });
  });
});
