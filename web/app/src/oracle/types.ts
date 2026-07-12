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
