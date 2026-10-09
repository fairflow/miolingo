// Behavioural assertions transcribed from the spec test suites
// (spec/tests/*.wls), mirroring swift/Miolingo TEST_PLAN.md's core table —
// the TS port must match the .wl behaviour. Row 15 (storeRoundTrip) lives in
// db.spec.ts (M5): the web store is Dexie, tested with fake-indexeddb.

import { describe, expect, it } from 'vitest';
import {
  addEntry,
  applyFilter,
  autofillFields,
  deleteFrom,
  practiseList,
  sortEntries,
  updateEntry,
  validateWord,
} from '../src/domain/vocabFunctions.js';
import { exportCsv, importInto, importOutcome, importPhrases } from '../src/domain/vocabImportExport.js';
import {
  alignPhonemes,
  comparePhonemes,
  evaluate,
  levenshtein,
  normalisePhonemes,
  selectPos,
  targetOf,
} from '../src/domain/practiceFunctions.js';
import * as ps from '../src/domain/practiceSession.js';
import * as story from '../src/domain/storyReader.js';
import * as helm from '../src/domain/helm.js';
import { phrase } from '../src/domain/types.js';

const bytes = (...xs: number[]) => new Uint8Array(xs);

describe('vocab value functions (VocabFunctions.wl)', () => {
  it('validateWord', () => {
    expect(validateWord('   ')).toBeNull();
    expect(validateWord('....')).toBeNull(); // only punctuation
    expect(validateWord('two words')).toBeNull(); // not single word
    expect(validateWord('Chat!')?.display).toBe('Chat');
    expect(validateWord('Chat!')?.key).toBe('chat');
    expect(validateWord('«bonjour»')?.key).toBe('bonjour');
  });

  it('addEntry dedups on key and bumps timesSeen', () => {
    let es = addEntry([], 'souris');
    expect(es).toHaveLength(1);
    expect(es[0]!.timesSeen).toBe(1);
    expect(es[0]!.displayWord).toBe('souris');
    es = addEntry(es, 'Souris'); // same key, different case
    expect(es).toHaveLength(1);
    expect(es[0]!.timesSeen).toBe(2);
    expect(es[0]!.displayWord).toBe('souris'); // original display kept
  });

  it('addEntry coalesces: fill, never overwrite', () => {
    let es = addEntry([], { word: 'chat', translation: 'cat' });
    es = addEntry(es, { word: 'chat', translation: 'feline', ipa: 'ʃa' });
    expect(es[0]!.translation).toBe('cat'); // not overwritten
    expect(es[0]!.ipa).toBe('ʃa'); // filled
  });

  it('delete and update', () => {
    let es = addEntry(addEntry([], 'chat'), 'chien');
    const chatId = es.find((e) => e.word === 'chat')!.id;
    es = deleteFrom(es, chatId);
    expect(es.map((e) => e.word)).toEqual(['chien']);
    const id = es[0]!.id;
    es = updateEntry(es, id, { translation: 'dog' });
    expect(es[0]!.translation).toBe('dog');
    es = updateEntry(es, id, { bogus: 'x' }); // unknown field rejected
    expect(es[0]!.translation).toBe('dog');
    es = updateEntry(es, id, { display_word: 'cat' }); // key change rejected
    expect(es[0]!.displayWord).toBe('chien');
  });

  it('sort and filter', () => {
    let es = addEntry([], 'banana'); // seq 1
    es = addEntry(es, 'apple'); // seq 2
    es = addEntry(es, 'banana'); // re-capture bumps lastSeq -> 3
    expect(sortEntries(es, 'alpha').map((e) => e.word)).toEqual(['apple', 'banana']);
    expect(sortEntries(es, 'recent')[0]!.word).toBe('banana'); // bumped
    expect(sortEntries(es, 'oldest')[0]!.word).toBe('banana'); // first captured
    expect(applyFilter(es, 'app').map((e) => e.word)).toEqual(['apple']);
  });

  it('import round-trip and target guard', () => {
    const es = importInto([], {
      contents: '(fr,en)\nsouris|mouse|[suʁi]\nchat|cat',
      expectedTarget: 'fr',
    });
    expect(new Set(es.map((e) => e.word))).toEqual(new Set(['souris', 'chat']));
    expect(es.find((e) => e.word === 'souris')?.ipa).toBe('suʁi'); // []-stripped
    // wrong target -> no capture (file target en ≠ fr)
    expect(importInto([], { contents: '(en,fr)\nx|y', expectedTarget: 'fr' })).toHaveLength(0);
    // no header -> no capture
    expect(importInto([], { contents: 'x|y' })).toHaveLength(0);
  });

  it('importOutcome reports reasons', () => {
    expect(importOutcome([], { contents: '(fr,en)\nchat|cat', expectedTarget: 'fr' }).result).toEqual({
      kind: 'ok',
      added: 1,
    });
    expect(importOutcome([], { contents: '(en,fr)\nx|y', expectedTarget: 'fr' }).result).toEqual({
      kind: 'targetMismatch',
      fileTarget: 'en',
      expected: 'fr',
    });
    expect(importOutcome([], { contents: 'x|y', expectedTarget: 'fr' }).result).toEqual({
      kind: 'noHeader',
    });
  });

  it('exportCsv header and quoting', () => {
    const es = addEntry([], { word: 'chat', translation: 'a, cat' });
    const lines = exportCsv(es).split('\n');
    expect(lines[0]!.startsWith('word,translation,ipa,source_language,source,')).toBe(true);
    expect(lines[1]!).toContain('"a, cat"'); // comma -> quoted
  });

  it('practiseList shape', () => {
    const es = addEntry([], { word: 'chat', translation: 'cat', ipa: 'ʃa' });
    expect(practiseList(es, null)).toEqual([phrase('chat', 'cat', 'ʃa')]);
  });
});

describe('practice scoring (PracticeSessionFunctions.wl)', () => {
  it('levenshtein and comparePhonemes', () => {
    expect(levenshtein('kitten', 'sitting')).toBe(3);
    const exact = comparePhonemes('ʃa', 'ʃa');
    expect(exact.exactMatch).toBe(true);
    expect(exact.similarity).toBeCloseTo(1.0, 9);
    const empty = comparePhonemes('abc', '');
    expect(empty.similarity).toBe(0.0);
    expect(empty.distance).toBe(3);
  });

  it('targetOf and selectPos guards', () => {
    const ph = [phrase('a'), phrase('b')];
    expect(targetOf(ph, 1).text).toBe('b');
    expect(targetOf(ph, 9).text).toBe(''); // out of range -> empty
    expect(selectPos(ph, 1, 0)).toBe(1);
    expect(selectPos(ph, 5, 0)).toBe(0); // out of range -> keep current
  });

  it('alignPhonemes and evaluate detail', () => {
    expect(normalisePhonemes('k o m')).toBe('kom');
    const sub = alignPhonemes('kat', 'kit');
    expect(sub.map((s) => s.op)).toEqual(['equal', 'sub', 'equal']);
    expect(sub[1]!.target).toBe('i');
    expect(sub[1]!.user).toBe('a');
    const del = alignPhonemes('ka', 'kat'); // target longer → del
    expect(del.map((s) => s.op)).toEqual(['equal', 'equal', 'del']);
    expect(del[2]!.target).toBe('t');
    expect(del[2]!.user).toBe('');
    const ins = alignPhonemes('kat', 'ka'); // user longer → ins
    expect(ins.map((s) => s.op)).toEqual(['equal', 'equal', 'ins']);
    expect(ins[2]!.user).toBe('t');
    expect(ins[2]!.target).toBe('');
    expect(alignPhonemes('', '')).toEqual([]);
    // evaluate normalises both sides and carries the detail
    const s = evaluate(phrase('x', '', 'a b c'), 'a b d');
    expect(s.distance).toBe(1);
    expect(s.user).toBe('abd');
    expect(s.target).toBe('abc');
    expect(s.alignment.at(-1)?.op).toBe('sub');
    expect(s.alignment.at(-1)?.target).toBe('c');
    expect(s.alignment.at(-1)?.user).toBe('d');
  });

  it('scoring methods: strict vs lenient', () => {
    const p = phrase('x', '', 'ABC');
    expect(evaluate(p, 'abc', 'editDistance').exactMatch).toBe(false); // case differs
    expect(evaluate(p, 'abc', 'lenient').exactMatch).toBe(true); // lenient folds
  });
});

describe('component behaviour (the agents)', () => {
  it('practice session flow', () => {
    let s = ps.initialPS;
    expect(ps.isEmpty(s)).toBe(true);
    s = ps.load(s, [phrase('chat', '', 'ʃa'), phrase('chien', '', 'ʃjɛ̃')]);
    expect(s.pos).toBe(0);
    s = ps.select(s, 5); // out-of-range select is a no-op (interleaving guard)
    expect(s.pos).toBe(0);
    s = ps.recordingMade(s, bytes(1, 2, 3));
    expect(s.rec).not.toBeNull();
    s = ps.score(s, 'ʃa');
    expect(s.res?.exactMatch).toBe(true);
    expect(ps.captureWord(s)).toBe('chat');
    s = ps.next(s);
    expect(s.pos).toBe(1);
    expect(s.rec).toBeNull(); // next clears rec/res
  });

  it('re-record requires clear (the constant-result bug guard)', () => {
    let s = ps.load(ps.initialPS, [phrase('x', '', 'a')]);
    const first = bytes(1);
    const second = bytes(2);
    s = ps.recordingMade(s, first);
    expect(s.rec).toBe(first);
    s = ps.recordingMade(s, second); // guarded no-op — keeps the first take
    expect(s.rec).toBe(first);
    s = ps.recordingMade(ps.clearRecording(s), second); // clear-then-record idiom
    expect(s.rec).toBe(second);
  });

  it('story mode-switch preserves position', () => {
    const lib = story.fixtureStoryLibrary;
    let s = story.initialStoryReader; // scene 0, pos 0, browse
    s = story.next(s, lib); // pos 1
    expect(s.pos).toBe(1);
    s = story.setMode(s, 'practice'); // PRESERVES (scene, pos)
    expect(s.scene).toBe(0);
    expect(s.pos).toBe(1);
    expect(s.mode).toBe('practice');
    s = story.selectScene(s, 1); // new scene -> pos resets
    expect(s.scene).toBe(1);
    expect(s.pos).toBe(0);
  });

  it('story practice capture word', () => {
    const lib = story.fixtureStoryLibrary;
    let s = story.setMode(story.initialStoryReader, 'practice');
    s = story.recordingMade(s, bytes(9));
    s = story.score(s, lib, 'bɔ̃ʒuʁ');
    expect(story.captureWord(s, lib)).toBe('Bonjour');
    expect(s.res?.exactMatch).toBe(true);
  });

  it('helm view and speed guard', () => {
    let h = helm.defaultHelm;
    expect(helm.helmView(h).language).toBe('French');
    h = helm.setSpeed(h, 180); // non-espeak tts -> guard blocks
    expect(h.speed).toBe(250);
    h = helm.setSpeed(helm.setTTS(h, 'espeak'), 180);
    expect(h.speed).toBe(180);
  });
});

describe('phrase import + autofill (sequence-adjacent rows)', () => {
  it('phrase import: same ingest format → a practice queue', () => {
    const { phrases, result } = importPhrases({
      contents: '(fr,en)\nbonjour|hello|[bɔ̃ʒuʁ]\nchat|cat',
      expectedTarget: 'fr',
    });
    expect(result).toEqual({ kind: 'ok', added: 2 });
    expect(phrases[0]).toEqual(phrase('bonjour', 'hello', 'bɔ̃ʒuʁ'));
    expect(
      importPhrases({ contents: '(en,fr)\nx|y', expectedTarget: 'fr' }).result.kind,
    ).toBe('targetMismatch');
  });

  it('autofill fills only empty, never overwrites', () => {
    const es = addEntry([], 'chat');
    const id = es[0]!.id;
    expect(autofillFields(es, id, { translation: 'cat' })).toEqual({ translation: 'cat' });
    const es2 = updateEntry(es, id, { translation: 'feline' });
    expect(autofillFields(es2, id, { translation: 'cat' })).toEqual({});
    expect(autofillFields(es, id, null)).toEqual({}); // oracle miss → no fields
  });
});
