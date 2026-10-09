// Parses the REAL shipped language materials (astro convention: tests
// validate production data, not fixtures) plus the fold-map data file.

import { readdirSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { languagesOf, phrasesFor, stripIpaBrackets, type UnifiedDoc } from '../src/domain/materials.js';
import { foldMapKey, isTolerated, languages as foldLanguages } from '../src/domain/foldMap.js';

const MATERIALS = fileURLToPath(new URL('../../../language_materials/unified/', import.meta.url));

function loadDoc(rel: string): UnifiedDoc {
  return JSON.parse(readFileSync(MATERIALS + rel, 'utf-8')) as UnifiedDoc;
}

describe('unified materials', () => {
  it('every shipped unified file parses and has phrases for its languages', () => {
    for (const kind of ['phrases', 'phrasebook', 'stories'] as const) {
      for (const file of readdirSync(MATERIALS + kind).filter((f) => f.endsWith('.json'))) {
        const doc = loadDoc(`${kind}/${file}`);
        expect(doc.phrases.length, `${kind}/${file} has phrases`).toBeGreaterThan(0);
        expect(languagesOf(doc).length, `${kind}/${file} has languages`).toBeGreaterThan(0);
      }
    }
  });

  it('phrasesFor shapes a practice queue with bare-IPA and translations', () => {
    const doc = loadDoc('phrases/common-phrases-001.json');
    const ph = phrasesFor(doc, 'fr', 'en');
    expect(ph.length).toBeGreaterThan(0);
    const first = ph[0]!;
    expect(first.text.length).toBeGreaterThan(0);
    expect(first.ipa.startsWith('[')).toBe(false); // brackets stripped
  });

  it('regional voice codes fall back to the bare material language', () => {
    const doc = loadDoc('phrases/common-phrases-001.json');
    const br = phrasesFor(doc, 'pt-br', 'en'); // materials ship bare "pt"
    const pt = phrasesFor(doc, 'pt', 'en');
    expect(br).toEqual(pt);
    expect(br.length).toBeGreaterThan(0);
  });

  it('stripIpaBrackets', () => {
    expect(stripIpaBrackets('[wi]')).toBe('wi');
    expect(stripIpaBrackets('wi')).toBe('wi');
    expect(stripIpaBrackets('')).toBe('');
  });
});

describe('fold-map (same data file as the app)', () => {
  it('loads the shipped languages and aliases pt → pt-br', () => {
    expect(foldLanguages()).toContain('pt-br');
    expect(foldMapKey('pt')).toBe('pt-br');
    expect(foldMapKey('nl-be')).toBe('nl');
    expect(foldMapKey('xx')).toBeNull();
  });

  it('tolerance is reflexive, symmetric, and closed over the data', () => {
    for (const lang of foldLanguages()) {
      expect(isTolerated(lang, 'a', 'a')).toBe(true); // reflexive always
    }
    // symmetric on a real pair from the data (data-driven, not hardcoded)
    const raw = JSON.parse(
      readFileSync(
        fileURLToPath(new URL('../../../src/ipa/data/espeak_fold_map.json', import.meta.url)),
        'utf-8',
      ),
    ) as Record<string, { tolerated_pairs?: { pair: string[] }[] }>;
    for (const lang of foldLanguages()) {
      const pairs = raw[lang]?.tolerated_pairs ?? [];
      for (const { pair } of pairs.slice(0, 5)) {
        const [a, b] = pair as [string, string];
        expect(isTolerated(lang, a, b), `${lang}: ${a}~${b}`).toBe(true);
        expect(isTolerated(lang, b, a), `${lang}: ${b}~${a} (symmetric)`).toBe(true);
      }
    }
    expect(isTolerated('fr', 'a', 'ʁ')).toBe(false); // absurd pair stays error
  });
});
