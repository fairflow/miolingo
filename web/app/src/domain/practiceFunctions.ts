// =====================================================================
// PracticeFunctions — ported from spec/PracticeSessionFunctions.wl
// (recovered from src/scoring/comparison.py). The ASR step (audio →
// phonemes) is the uninterpreted oracle; the spec is parametric in it, so
// `evaluate` takes the already-recognised phoneme string (which the oracle
// tier produces).
//
// String semantics: all lengths/edits are over Unicode CODE POINTS
// (Array.from), matching Python's str — the golden-parity source. (Swift
// counts grapheme clusters, which differs on combining marks like ɛ̃;
// Python/TS agree with each other, which is what the shipped scorer uses.)
// =====================================================================

import type { AlignSeg, Phrase, Score, ScoringMethod } from './types.js';
import { EMPTY_PHRASE } from './types.js';

// --- levenshtein (comparison.py:9) — pure edit distance ---------------
export function levenshtein(s1: string, s2: string): number {
  const a = Array.from(s1);
  const b = Array.from(s2);
  if (a.length === 0) return b.length;
  if (b.length === 0) return a.length;
  let prev = Array.from({ length: b.length + 1 }, (_, j) => j);
  let cur = new Array<number>(b.length + 1).fill(0);
  for (let i = 1; i <= a.length; i++) {
    cur[0] = i;
    for (let j = 1; j <= b.length; j++) {
      const cost = a[i - 1] === b[j - 1] ? 0 : 1;
      cur[j] = Math.min(prev[j]! + 1, cur[j - 1]! + 1, prev[j - 1]! + cost);
    }
    [prev, cur] = [cur, prev];
  }
  return prev[b.length]!;
}

// --- compare_phonemes_edit_distance (comparison.py:83) ----------------
export function comparePhonemes(user: string, correct: string): Score {
  if (correct.length === 0) {
    return {
      exactMatch: user === correct,
      similarity: 0.0,
      distance: Array.from(user).length,
      user: '',
      target: '',
      alignment: [],
    };
  }
  const dist = levenshtein(user, correct);
  const maxLen = Math.max(Array.from(user).length, Array.from(correct).length);
  return {
    exactMatch: user === correct,
    similarity: 1.0 - dist / maxLen,
    distance: dist,
    user: '',
    target: '',
    alignment: [],
  };
}

// --- targetOf / selectPos (PracticeSessionFunctions.wl) ----------------
export function targetOf(phrases: readonly Phrase[], pos: number): Phrase {
  const p = phrases[pos];
  return pos >= 0 && p !== undefined ? p : EMPTY_PHRASE;
}

/** select_item guard: an out-of-range index is a no-op (pos stays put). */
export function selectPos(phrases: readonly Phrase[], i: number, cur: number): number {
  return i >= 0 && i < phrases.length ? i : cur;
}

// --- normalisePhonemes (phonemes.py normalize_for_phoneme_scoring) -----
/** Strip word-boundary whitespace so scoring is on pronunciation only. */
export function normalisePhonemes(ipa: string): string {
  return ipa.split(/\s+/).join('');
}

// --- alignPhonemes (comparison.py get_edit_operations) ----------------
/**
 * Levenshtein backtrace aligning the target (correct) against the user's
 * phonemes → segments {op, target, user}, oriented target-vs-user. The
 * matched/unmatched structure the diff renderer colours.
 */
export function alignPhonemes(user: string, correct: string): AlignSeg[] {
  const a = Array.from(correct); // target
  const b = Array.from(user);
  const m = a.length;
  const n = b.length;
  const dp: number[][] = Array.from({ length: m + 1 }, () => new Array<number>(n + 1).fill(0));
  for (let i = 0; i <= m; i++) dp[i]![0] = i;
  for (let j = 0; j <= n; j++) dp[0]![j] = j;
  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      dp[i]![j] =
        a[i - 1] === b[j - 1]
          ? dp[i - 1]![j - 1]!
          : 1 + Math.min(dp[i - 1]![j]!, dp[i]![j - 1]!, dp[i - 1]![j - 1]!);
    }
  }
  const ops: AlignSeg[] = [];
  let i = m;
  let j = n;
  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && a[i - 1] === b[j - 1]) {
      ops.push({ op: 'equal', target: a[i - 1]!, user: b[j - 1]! });
      i--;
      j--;
    } else if (i > 0 && j > 0 && dp[i]![j] === dp[i - 1]![j - 1]! + 1) {
      ops.push({ op: 'sub', target: a[i - 1]!, user: b[j - 1]! });
      i--;
      j--;
    } else if (j > 0 && dp[i]![j] === dp[i]![j - 1]! + 1) {
      ops.push({ op: 'ins', target: '', user: b[j - 1]! });
      j--;
    } else {
      ops.push({ op: 'del', target: a[i - 1]!, user: '' });
      i--;
    }
  }
  return ops.reverse();
}

// --- scoreDetail / evaluate -------------------------------------------
/** Full scored result: comparePhonemes numbers + strings + alignment. */
export function scoreDetail(user: string, correct: string): Score {
  const s = comparePhonemes(user, correct);
  return { ...s, user, target: correct, alignment: alignPhonemes(user, correct) };
}

/** Lenient fold: strip combining marks + length mark, lowercase. */
export function lenientNormalise(s: string): string {
  return s
    .normalize('NFD')
    .replace(/\p{M}/gu, '')
    .replaceAll('ː', '')
    .toLowerCase();
}

/**
 * evaluate, pure half: normalise both sides (per method), then score + align.
 * (The ASR — recognisePhonemes — is the oracle, performed server-side.)
 */
export function evaluate(
  target: Phrase,
  recognisedPhonemes: string,
  method: ScoringMethod = 'editDistance',
): Score {
  let u = normalisePhonemes(recognisedPhonemes);
  let c = normalisePhonemes(target.ipa);
  if (method === 'lenient') {
    u = lenientNormalise(u);
    c = lenientNormalise(c);
  }
  return scoreDetail(u, c);
}

// --- sessionView (read-only projection) -------------------------------
export interface SessionView {
  readonly total: number;
  readonly pos: number;
  readonly item: Phrase | null;
  readonly hasRecording: boolean;
  readonly score: Score | null;
}

export function sessionView(
  phrases: readonly Phrase[],
  pos: number,
  rec: unknown,
  res: Score | null,
): SessionView {
  return {
    total: phrases.length,
    pos,
    item: phrases.length === 0 ? null : targetOf(phrases, pos),
    hasRecording: rec != null,
    score: res,
  };
}
