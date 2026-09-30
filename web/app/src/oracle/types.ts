// Response shapes mirroring the sidecar's pydantic models (web/oracle/schemas.py).
// The oracle is the single source of truth for anything it computes; these
// types are the contract, kept deliberately in one file per tier.

export interface OracleHealth {
  ok: boolean;
  /** Path of the espeak binary the G2P shells out to, or null if missing. */
  espeak: string | null;
  whisper: { model: string | null; loaded: boolean };
  /** espeak voice codes with a wired A2P recognizer (specialist or fallback). */
  a2p_langs: string[];
  translate_available: boolean;
}

export interface G2pItem {
  text: string;
  ipa: string;
  phonemes: string;
}

export interface G2pResponse {
  lang: string;
  items: G2pItem[];
}

/** One aligned op from the oracle's scorer (target-oriented). */
export interface AttemptOp {
  kind: 'match' | 'substitute' | 'insert' | 'delete';
  target: string;
  user: string;
  significant: boolean;
}

export interface AttemptChannel {
  ipa: string;
  /** null when the channel produced nothing (e.g. A2P unavailable). */
  similarity: number | null;
  exact: boolean;
  distance: number | null;
  ops: AttemptOp[];
}

export interface AttemptTimings {
  asr: number;
  a2p: number;
  total: number;
}

/** POST /api/attempt — everything displayed about an attempt, verbatim. */
export interface AttemptResponse {
  target: string;
  recognized_text: string;
  target_ipa: string;
  algorithm: string;
  comprehensibility: AttemptChannel;
  accuracy: AttemptChannel;
  timings_ms: AttemptTimings;
}

export type Algorithm = 'weighted_phone' | 'edit_distance';

/** One unified-materials file as listed by GET /api/materials. */
export interface MaterialsFile {
  /** Path under /materials/, e.g. "unified/phrases/common-phrases-001.json". */
  path: string;
  kind: 'phrases' | 'phrasebook' | 'stories';
  /** The file's "meta" object, verbatim (id/languages/title/...). */
  meta: Record<string, unknown>;
}

export interface MaterialsIndex {
  files: MaterialsFile[];
}
