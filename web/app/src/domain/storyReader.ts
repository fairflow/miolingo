// =====================================================================
// StoryReader — spec/StoryReaderRecovered.wl: ONE narrative position
// (scene, pos) with three modes as affordances over it. Deliberate fix over
// the Streamlit app's two independent practice loops: set_mode PRESERVES the
// position; select_scene resets it.
//
// The story CONTENT boundary: the spec defers sceneOf to a fixture standing
// in for a StoryLibrary store. Here the library is a plain interface passed
// INTO the functions that need it (not held in state — keeps the state slice
// a snapshot-safe plain object; the real unified-materials library lands in
// M6 without touching these transitions).
// =====================================================================

import type { Audio, Phrase, ReadingMode, Score, ScoringMethod } from './types.js';
import { evaluate, selectPos, targetOf } from './practiceFunctions.js';

export interface StoryLibrary {
  scene(index: number): readonly Phrase[];
  readonly sceneCount: number;
}

/** The spec fixture (StoryFunctions.wl sceneOf), verbatim. */
export const fixtureStoryLibrary: StoryLibrary = {
  sceneCount: 2,
  scene(index: number): readonly Phrase[] {
    switch (index) {
      case 0:
        return [
          { text: 'Bonjour', translation: 'Hello', ipa: 'bɔ̃ʒuʁ' },
          { text: 'Comment ça va?', translation: 'How are you?', ipa: 'kɔmɑ̃ sa va' },
        ];
      case 1:
        return [{ text: 'Au revoir', translation: 'Goodbye', ipa: 'o ʁəvwaʁ' }];
      default:
        return [];
    }
  },
};

export interface StoryReader {
  readonly scene: number;
  readonly pos: number;
  readonly mode: ReadingMode;
  readonly rec: Audio | null;
  readonly res: Score | null;
}

export const initialStoryReader: StoryReader = {
  scene: 0,
  pos: 0,
  mode: 'browse',
  rec: null,
  res: null,
};

export function phrasesOf(s: StoryReader, lib: StoryLibrary): readonly Phrase[] {
  return lib.scene(s.scene);
}

// set_mode — PRESERVES (scene, pos), clears rec/res
export function setMode(s: StoryReader, m: ReadingMode): StoryReader {
  return { ...s, mode: m, rec: null, res: null };
}

// select_scene — new scene ⇒ pos resets to 0
export function selectScene(s: StoryReader, scene: number): StoryReader {
  return { ...s, scene, pos: 0, rec: null, res: null };
}

// story_select_item(i) — guarded no-op out of range
export function selectItem(s: StoryReader, lib: StoryLibrary, i: number): StoryReader {
  return { ...s, pos: selectPos(phrasesOf(s, lib), i, s.pos), rec: null, res: null };
}

export function canNext(s: StoryReader, lib: StoryLibrary): boolean {
  return s.pos < phrasesOf(s, lib).length - 1;
}

export function canPrev(s: StoryReader): boolean {
  return s.pos > 0;
}

export function next(s: StoryReader, lib: StoryLibrary): StoryReader {
  return canNext(s, lib) ? { ...s, pos: s.pos + 1, rec: null, res: null } : s;
}

export function prev(s: StoryReader): StoryReader {
  return canPrev(s) ? { ...s, pos: s.pos - 1, rec: null, res: null } : s;
}

// practice-mode loop (mirrors PSActive; only value functions are shared)
export function recordingMade(s: StoryReader, audio: Audio): StoryReader {
  if (s.mode !== 'practice' || s.rec !== null) return s;
  return { ...s, rec: audio, res: null };
}

export function clearRecording(s: StoryReader): StoryReader {
  return { ...s, rec: null, res: null };
}

export function score(
  s: StoryReader,
  lib: StoryLibrary,
  recognisedPhonemes: string,
  method: ScoringMethod = 'editDistance',
): StoryReader {
  if (s.rec === null) return s;
  return { ...s, res: evaluate(targetOf(phrasesOf(s, lib), s.pos), recognisedPhonemes, method) };
}

export function attemptMade(s: StoryReader, res: Score): StoryReader {
  if (s.rec === null) return s;
  return { ...s, res };
}

// story_capture_vocab — only when scored
export function captureWord(s: StoryReader, lib: StoryLibrary): string | null {
  return s.res !== null ? targetOf(phrasesOf(s, lib), s.pos).text : null;
}

// --- storyView (read-only projection) ----------------------------------
export interface StoryViewModel {
  readonly scene: number;
  readonly mode: ReadingMode;
  readonly pos: number;
  readonly count: number;
  readonly phrases: readonly Phrase[];
  readonly item: Phrase | null;
  readonly hasRecording: boolean;
  readonly score: Score | null;
}

export function storyView(s: StoryReader, lib: StoryLibrary): StoryViewModel {
  const phrases = phrasesOf(s, lib);
  return {
    scene: s.scene,
    mode: s.mode,
    pos: s.pos,
    count: phrases.length,
    phrases,
    item: phrases.length === 0 ? null : targetOf(phrases, s.pos),
    hasRecording: s.rec !== null,
    score: s.res,
  };
}
