// =====================================================================
// Import / export — ported from spec/VocabFunctions.wl (vocab.py:453, 486,
// 545, vocabulary_tab.py:222).
// =====================================================================

import type { Capture, ImportRequest, ImportResult, Phrase, VocabEntry } from './types.js';
import { addEntry } from './vocabFunctions.js';

export function parseImportLine(line: string): Capture | null {
  const parts = line.split('|').map((p) => p.trim());
  const word = parts[0] ?? '';
  if (word === '') return null;
  const get = (i: number): string => (parts.length >= i ? parts[i - 1]! : '');
  let ipa = get(3);
  if (ipa.length >= 2 && ipa.startsWith('[') && ipa.endsWith(']')) {
    ipa = ipa.slice(1, -1);
  }
  return {
    word,
    translation: get(2) === '' ? null : get(2),
    ipa: ipa === '' ? null : ipa,
    sourceName: get(4) === '' ? null : get(4),
    url: get(5) === '' ? null : get(5),
  };
}

/**
 * `(target, source)` header — matches the COLUMN order (word is target, the
 * translation is source). Lowercased codes; #-comment lines skipped. null if
 * no header before the first data line.
 */
export function parseImportHeader(contents: string): { target: string; source: string } | null {
  for (const raw of contents.split('\n')) {
    const line = raw.trim();
    if (line === '') continue;
    if (line.startsWith('(') && line.includes(',')) {
      const close = line.indexOf(')');
      if (close >= 0) {
        const inner = line.slice(1, close);
        const comma = inner.indexOf(',');
        if (comma >= 0) {
          const target = inner.slice(0, comma).trim().toLowerCase();
          const source = inner.slice(comma + 1).trim().toLowerCase();
          return { target, source };
        }
      }
    }
    if (line.startsWith('#')) continue;
    return null; // first data line, no header -> reject
  }
  return null;
}

function isImportDataLine(raw: string): boolean {
  const line = raw.trim();
  return line !== '' && !line.startsWith('#') && !line.startsWith('(');
}

export const IMPORT_LINE_LIMIT = 250;

/** importInto + the reason. The header's TARGET must equal the expected one. */
export function importOutcome(
  entries: readonly VocabEntry[],
  f: ImportRequest,
): { entries: VocabEntry[]; result: ImportResult } {
  const hdr = parseImportHeader(f.contents);
  if (hdr === null) return { entries: [...entries], result: { kind: 'noHeader' } };
  if (f.expectedTarget !== undefined && hdr.target !== f.expectedTarget.toLowerCase()) {
    return {
      entries: [...entries],
      result: {
        kind: 'targetMismatch',
        fileTarget: hdr.target,
        expected: f.expectedTarget.toLowerCase(),
      },
    };
  }
  const dataLines = f.contents.split('\n').filter(isImportDataLine);
  if (dataLines.length > IMPORT_LINE_LIMIT) {
    return { entries: [...entries], result: { kind: 'tooMany', count: dataLines.length } };
  }
  let out = [...entries];
  for (const raw of dataLines) {
    const p = parseImportLine(raw.trim());
    if (p !== null) out = addEntry(out, p);
  }
  return { entries: out, result: { kind: 'ok', added: out.length - entries.length } };
}

export function importInto(entries: readonly VocabEntry[], f: ImportRequest): VocabEntry[] {
  return importOutcome(entries, f).entries;
}

// --- importPhrases (PhraseImport.swift) — same ingest format → a queue --
export function importPhrases(f: ImportRequest): { phrases: Phrase[]; result: ImportResult } {
  const { entries, result } = importOutcome([], f);
  return {
    phrases: entries.map((e) => ({
      text: e.displayWord,
      translation: e.translation ?? '',
      ipa: e.ipa ?? '',
    })),
    result,
  };
}

// --- exportCsv (vocabulary_tab.py:222) — 13-column header + rows -------
export const EXPORT_CSV_HEADER = [
  'word',
  'translation',
  'ipa',
  'source_language',
  'source',
  'context_before',
  'context_line',
  'context_after',
  'times_seen',
  'first_seen_at',
  'last_seen_at',
  'notes',
  'url',
] as const;

/** RFC-4180 minimal quoting: quote only on comma/quote/newline; double quotes. */
function csvField(x: string | null): string {
  const s = x ?? '';
  if (s.includes(',') || s.includes('"') || s.includes('\n') || s.includes('\r')) {
    return '"' + s.replaceAll('"', '""') + '"';
  }
  return s;
}

function csvRow(cells: readonly (string | null)[]): string {
  return cells.map(csvField).join(',');
}

export function exportCsv(entries: readonly VocabEntry[]): string {
  const rows = [csvRow(EXPORT_CSV_HEADER)];
  for (const r of entries) {
    rows.push(
      csvRow([
        r.displayWord === '' ? r.word : r.displayWord,
        r.translation,
        r.ipa,
        null, // source_language_code — unmodelled at L1
        r.sourceName,
        r.contextBefore,
        r.contextLine,
        r.contextAfter,
        String(r.timesSeen),
        '', // first_seen_at — wall-clock unmodelled at L1
        '', // last_seen_at
        r.notes,
        r.url,
      ]),
    );
  }
  return rows.join('\n');
}
