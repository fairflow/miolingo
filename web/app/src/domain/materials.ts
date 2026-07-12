// =====================================================================
// Unified language-materials parsing — pure functions over the JSON the
// oracle serves from language_materials/unified/ (phrases, phrasebook, and
// story scenes all share one shape: {meta, phrases:[{id, text:{lang},
// ipa:{lang:"[…]"}}]}). Fetching lives in the oracle client tier; tests
// parse the real shipped files from disk.
// =====================================================================

import type { Phrase } from './types.js';

export interface UnifiedEntry {
  readonly id: string | number;
  readonly text: Readonly<Record<string, string>>;
  readonly ipa?: Readonly<Record<string, string>>;
}

export interface UnifiedDoc {
  readonly meta: { readonly languages?: readonly string[] } & Readonly<Record<string, unknown>>;
  readonly phrases: readonly UnifiedEntry[];
}

/** The unified files wrap IPA in brackets ("[wi]"); phrases carry it bare. */
export function stripIpaBrackets(ipa: string): string {
  const s = ipa.trim();
  return s.length >= 2 && s.startsWith('[') && s.endsWith(']') ? s.slice(1, -1) : s;
}

/** Languages a unified doc claims to cover (meta.languages, else text keys). */
export function languagesOf(doc: UnifiedDoc): string[] {
  if (doc.meta.languages !== undefined) return [...doc.meta.languages];
  const langs = new Set<string>();
  for (const e of doc.phrases) for (const l of Object.keys(e.text)) langs.add(l);
  return [...langs].sort();
}

/**
 * Shape a unified doc into a practice queue for (target, source). The
 * material language codes are bare ("pt"); voice codes may carry a region
 * ("pt-br") — fall back to the bare prefix so pt-br practises pt materials.
 * Entries lacking target text are skipped (never practise an empty phrase).
 */
export function phrasesFor(doc: UnifiedDoc, target: string, source: string): Phrase[] {
  const pick = (rec: Readonly<Record<string, string>> | undefined, lang: string): string => {
    if (rec === undefined) return '';
    return rec[lang] ?? rec[lang.split('-')[0] ?? lang] ?? '';
  };
  const out: Phrase[] = [];
  for (const e of doc.phrases) {
    const text = pick(e.text, target);
    if (text === '') continue;
    out.push({
      text,
      translation: pick(e.text, source),
      ipa: stripIpaBrackets(pick(e.ipa, target)),
    });
  }
  return out;
}
