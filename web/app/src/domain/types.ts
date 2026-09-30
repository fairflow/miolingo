// =====================================================================
// Domain types — ported from the CCS spec data representations
// (spec/VocabFunctions.wl entry schema, PracticeSessionFunctions.wl phrase
// shape, HelmRecovered.wl settings, StoryReaderRecovered.wl modes), via the
// proven Swift mapping (swift/.../MiolingoCore/Model.swift).
//
// Everything here is a plain readonly object — no classes — so state slices
// sit cleanly in Svelte 5 $state proxies and $state.snapshot round-trips.
// =====================================================================

/** A practice phrase — exactly practiseList's / load_material's shape. */
export interface Phrase {
  readonly text: string;
  readonly translation: string;
  readonly ipa: string;
}

export const EMPTY_PHRASE: Phrase = { text: '', translation: '', ipa: '' };

export function phrase(text: string, translation = '', ipa = ''): Phrase {
  return { text, translation, ipa };
}

/** list_vocab ordering (an enum SYMBOL in the spec, not free text). */
export type VocabSort = 'alpha' | 'recent' | 'oldest';

/** TTS engine setting (Helm.tts) — the web app's engine chain. */
export type TTSKind = 'google_cloud' | 'gtts' | 'espeak';

/** ASR engine setting (Helm.asr). Whisper only on the web (via the oracle). */
export type ASRKind = 'whisper';

/** Whisper model size (Helm.asrModel) — meaningful only when asr is whisper. */
export type WhisperModel = 'tiny' | 'base' | 'small' | 'medium' | 'large';

export type ReadingMode = 'full' | 'browse' | 'practice';

/**
 * The vocab entry. Python NULL is modelled as null (not undefined) so JSON
 * round-trips are faithful. `word` is the lowercased lookup key; `displayWord`
 * keeps the original case. first/lastSeq are the spec's logical clock —
 * wall-clock timestamps live only in the persistence layer.
 */
export interface VocabEntry {
  readonly id: number;
  readonly word: string;
  readonly displayWord: string;
  readonly translation: string | null;
  readonly ipa: string | null;
  readonly sourceName: string | null;
  readonly url: string | null;
  readonly contextBefore: string | null;
  readonly contextLine: string | null;
  readonly contextAfter: string | null;
  readonly timesSeen: number;
  readonly firstSeq: number;
  readonly lastSeq: number;
  readonly notes: string | null;
}

/** A captured-word payload (addEntry's `w`): at least a word, maybe fields. */
export interface Capture {
  readonly word: string;
  readonly translation?: string | null;
  readonly ipa?: string | null;
  readonly sourceName?: string | null;
  readonly url?: string | null;
  readonly contextBefore?: string | null;
  readonly contextLine?: string | null;
  readonly contextAfter?: string | null;
}

/** One aligned phoneme segment (alignPhonemes / get_edit_operations). */
export type AlignOp = 'equal' | 'sub' | 'ins' | 'del';

export interface AlignSeg {
  readonly op: AlignOp;
  readonly target: string;
  readonly user: string;
}

/**
 * The pure scored result (comparison.py numbers + the alignment the UI
 * colours). This is the spec's `score[...]` payload. The oracle's dual-channel
 * /api/attempt response (M3) embeds two channel scores; the primary channel
 * is projected into this shape for the PS/StoryReader `res` slot.
 */
export interface Score {
  readonly exactMatch: boolean;
  readonly similarity: number;
  readonly distance: number;
  readonly user: string;
  readonly target: string;
  readonly alignment: readonly AlignSeg[];
}

/**
 * A held recording (spec: rec : none | recorded[audio]). Transitions never
 * inspect the payload, so tests may pass bytes where the browser passes a
 * Blob.
 */
export type Audio = Blob | Uint8Array;

/** The language pair Helm lends out (langRead → {source, target}). */
export interface LangPair {
  /** Native language NAME, e.g. "English" (authoring parameter). */
  readonly source: string;
  /** Target language CODE, e.g. "fr" (practice identity). */
  readonly target: string;
}

/** A bulk-import request (importInto's `f`). */
export interface ImportRequest {
  readonly contents: string;
  readonly expectedTarget?: string;
}

/** Why an import did/didn't happen — drives user feedback, never silent. */
export type ImportResult =
  | { readonly kind: 'ok'; readonly added: number }
  | { readonly kind: 'noHeader' }
  | { readonly kind: 'targetMismatch'; readonly fileTarget: string; readonly expected: string }
  | { readonly kind: 'tooMany'; readonly count: number };

/**
 * Pure phoneme scoring method for the domain evaluate (spec test surface and
 * offline/text diffs). The oracle's edit_distance/weighted_phone algorithms
 * are selected per attempt and computed server-side (single source of truth).
 */
export type ScoringMethod = 'editDistance' | 'lenient';
