// Pure statistics aggregates (statistics_tab.py / history_tab.py semantics).

import { describe, expect, it } from 'vitest';
import {
  histogram,
  historyByDate,
  summarize,
  trendPoints,
  volumeByDay,
  weakestPhrases,
} from '../src/domain/statsFunctions.js';

const at = (day: string, target: string, similarity: number) => ({
  date: `${day}T10:00:00Z`,
  target,
  similarity,
});

describe('statsFunctions', () => {
  it('trendPoints sorts by date and rolls a 10-mean', () => {
    const rows = [at('2026-07-02', 'b', 1.0), at('2026-07-01', 'a', 0.5)];
    const t = trendPoints(rows);
    expect(t.map((p) => p.similarity)).toEqual([0.5, 1.0]); // date order
    expect(t[1]!.rolling).toBeCloseTo(0.75, 9);
  });

  it('volumeByDay counts per calendar day, ascending', () => {
    const rows = [at('2026-07-02', 'a', 1), at('2026-07-01', 'a', 1), at('2026-07-02', 'b', 1)];
    expect(volumeByDay(rows)).toEqual([
      { day: '2026-07-01', count: 1 },
      { day: '2026-07-02', count: 2 },
    ]);
  });

  it('histogram bins [0,1] with 1.0 in the top bin', () => {
    const h = histogram([at('d', 'a', 0), at('d', 'b', 0.5), at('d', 'c', 1.0)], 20);
    expect(h[0]).toBe(1);
    expect(h[10]).toBe(1);
    expect(h[19]).toBe(1);
    expect(h.reduce((s, x) => s + x, 0)).toBe(3);
  });

  it('weakestPhrases needs ≥3 attempts, ranks ascending by mean', () => {
    const rows = [
      ...[0.2, 0.4, 0.6].map((s) => at('2026-07-01', 'hard', s)),
      ...[0.9, 1.0, 0.95].map((s) => at('2026-07-02', 'easy', s)),
      at('2026-07-03', 'rare', 0.1), // only 1 attempt — excluded
    ];
    const w = weakestPhrases(rows);
    expect(w.map((x) => x.target)).toEqual(['hard', 'easy']);
    expect(w[0]!.mean).toBeCloseTo(0.4, 9);
    expect(w[0]!.attempts).toBe(3);
  });

  it('historyByDate groups newest-first and honours the limit', () => {
    const rows = [at('2026-07-01', 'a', 1), at('2026-07-02', 'b', 1), at('2026-07-02', 'c', 1)];
    const g = historyByDate(rows, 2);
    expect(g).toHaveLength(1); // limit 2 → only the newest day's two
    expect(g[0]!.day).toBe('2026-07-02');
    expect(g[0]!.attempts).toHaveLength(2);
  });

  it('summarize', () => {
    const s = summarize([
      { ...at('d', 'a', 1.0), perfect: true },
      { ...at('d', 'a', 0.5), perfect: false },
    ]);
    expect(s).toEqual({
      attempts: 2,
      meanSimilarity: 0.75,
      perfectCount: 1,
      distinctPhrases: 1,
    });
    expect(summarize([]).meanSimilarity).toBeNull();
  });
});
