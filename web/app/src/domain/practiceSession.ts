// =====================================================================
// PracticeSession (PS / PSActive) — spec/PracticeSessionRecovered.wl.
// Each exported function is a PORT: (state, args) → successor state,
// mirroring the .wl transitions one-for-one. The restricted cross-component
// channels (vocabUpsert / goPractice / langRead / vocabRead) are wired by
// the AppModel — they are the τ's the walk harness auto-fires.
// =====================================================================

import type { Audio, Phrase, Score, ScoringMethod } from './types.js';
import { evaluate, selectPos, sessionView, targetOf, type SessionView } from './practiceFunctions.js';

export interface PS {
  readonly phrases: readonly Phrase[];
  readonly pos: number;
  readonly rec: Audio | null;
  readonly res: Score | null;
}

export const initialPS: PS = { phrases: [], pos: 0, rec: null, res: null };

// load_material / load_vocab / load_filtered (queue := ph, pos 0, cleared)
export function load(_s: PS, phrases: readonly Phrase[]): PS {
  return { phrases, pos: 0, rec: null, res: null };
}

// clear_material
export function clearMaterial(_s: PS): PS {
  return initialPS;
}

// select_item(i) — guarded so an out-of-range index is a no-op
export function select(s: PS, i: number): PS {
  return { ...s, pos: selectPos(s.phrases, i, s.pos), rec: null, res: null };
}

// recording_made(audio) — only when no recording held (the re-record guard)
export function recordingMade(s: PS, audio: Audio): PS {
  if (s.rec !== null) return s;
  return { ...s, rec: audio, res: null };
}

// clear_recording
export function clearRecording(s: PS): PS {
  return { ...s, rec: null, res: null };
}

// attempt_made — score the held recording against the current target.
// Pure half: takes the recognised phonemes (ASR is the oracle, upstream).
export function score(s: PS, recognisedPhonemes: string, method: ScoringMethod = 'editDistance'): PS {
  if (s.rec === null) return s;
  return { ...s, res: evaluate(targetOf(s.phrases, s.pos), recognisedPhonemes, method) };
}

// attempt_made, oracle-supplied: the /api/attempt primary channel projected
// into the spec Score shape (M4 wiring).
export function attemptMade(s: PS, res: Score): PS {
  if (s.rec === null) return s;
  return { ...s, res };
}

// next_item_requested / prev_item_requested
export function next(s: PS): PS {
  return canNext(s) ? { ...s, pos: s.pos + 1, rec: null, res: null } : s;
}

export function prev(s: PS): PS {
  return canPrev(s) ? { ...s, pos: s.pos - 1, rec: null, res: null } : s;
}

// capture_vocab — only when scored; payload defaults to the current item text
export function captureWord(s: PS): string | null {
  return s.res !== null ? targetOf(s.phrases, s.pos).text : null;
}

/** The current target's text ('' when the queue is empty). */
export function targetText(s: PS): string {
  return targetOf(s.phrases, s.pos).text;
}

/** The current item, or null on an empty queue. */
export function currentItem(s: PS): Phrase | null {
  return s.phrases.length === 0 ? null : targetOf(s.phrases, s.pos);
}

export function isEmpty(s: PS): boolean {
  return s.phrases.length === 0;
}

export function canNext(s: PS): boolean {
  return s.pos < s.phrases.length - 1;
}

export function canPrev(s: PS): boolean {
  return s.pos > 0;
}

/** The ready set — the ONLY source of control enablement (spec invariant). */
export interface PSReady {
  readonly canRecord: boolean;
  readonly canClearRecording: boolean;
  readonly canScore: boolean;
  readonly canNext: boolean;
  readonly canPrev: boolean;
  readonly canCapture: boolean;
}

export function psReady(s: PS): PSReady {
  return {
    canRecord: !isEmpty(s) && s.rec === null,
    canClearRecording: s.rec !== null,
    canScore: s.rec !== null && s.res === null,
    canNext: canNext(s),
    canPrev: canPrev(s),
    canCapture: s.res !== null,
  };
}

/** pSView — the projection the practice pane renders (never raw state). */
export function psView(s: PS): SessionView {
  return sessionView(s.phrases, s.pos, s.rec, s.res);
}
