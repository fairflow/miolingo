// =====================================================================
// Statistics/History aggregates — pure functions over practice-log rows,
// matching the Streamlit statistics_tab.py/history_tab.py semantics:
// accuracy trend (+ rolling-10 mean), attempts per day, score distribution,
// weakest phrases (≥3 attempts, mean ascending), history grouped by date.
// Framework-free: takes a minimal row shape, not the Dexie type.
// =====================================================================

export interface AttemptLike {
  readonly date: string; // ISO
  readonly target: string;
  readonly similarity: number; // 0..1 primary-channel score
  readonly recognized?: string;
  readonly perfect?: boolean;
}

export interface TrendPoint {
  readonly i: number;
  readonly date: string;
  readonly similarity: number;
  /** Rolling mean over the last 10 attempts up to this point. */
  readonly rolling: number;
}

export function trendPoints(rows: readonly AttemptLike[], window = 10): TrendPoint[] {
  const sorted = [...rows].sort((a, b) => (a.date < b.date ? -1 : 1));
  return sorted.map((r, i) => {
    const from = Math.max(0, i - window + 1);
    const slice = sorted.slice(from, i + 1);
    const rolling = slice.reduce((s, x) => s + x.similarity, 0) / slice.length;
    return { i, date: r.date, similarity: r.similarity, rolling };
  });
}

export interface DayCount {
  readonly day: string; // YYYY-MM-DD
  readonly count: number;
}

export function volumeByDay(rows: readonly AttemptLike[]): DayCount[] {
  const counts = new Map<string, number>();
  for (const r of rows) {
    const day = r.date.slice(0, 10);
    counts.set(day, (counts.get(day) ?? 0) + 1);
  }
  return [...counts.entries()]
    .map(([day, count]) => ({ day, count }))
    .sort((a, b) => (a.day < b.day ? -1 : 1));
}

/** Similarity histogram over [0,1]; a perfect 1.0 lands in the top bin. */
export function histogram(rows: readonly AttemptLike[], bins = 20): number[] {
  const out = new Array<number>(bins).fill(0);
  for (const r of rows) {
    const idx = Math.min(bins - 1, Math.max(0, Math.floor(r.similarity * bins)));
    out[idx] = out[idx]! + 1;
  }
  return out;
}

export interface WeakPhrase {
  readonly target: string;
  readonly attempts: number;
  readonly mean: number;
  readonly lastDate: string;
}

export function weakestPhrases(
  rows: readonly AttemptLike[],
  minAttempts = 3,
  top = 10,
): WeakPhrase[] {
  const groups = new Map<string, AttemptLike[]>();
  for (const r of rows) {
    const g = groups.get(r.target);
    if (g === undefined) groups.set(r.target, [r]);
    else g.push(r);
  }
  const out: WeakPhrase[] = [];
  for (const [target, g] of groups) {
    if (g.length < minAttempts) continue;
    out.push({
      target,
      attempts: g.length,
      mean: g.reduce((s, x) => s + x.similarity, 0) / g.length,
      lastDate: g.reduce((m, x) => (x.date > m ? x.date : m), g[0]!.date),
    });
  }
  return out.sort((a, b) => a.mean - b.mean).slice(0, top);
}

export interface DayGroup<T extends AttemptLike> {
  readonly day: string;
  readonly attempts: T[];
}

/** Last `limit` attempts, grouped by day, newest day (and attempt) first. */
export function historyByDate<T extends AttemptLike>(rows: readonly T[], limit = 100): DayGroup<T>[] {
  const recent = [...rows].sort((a, b) => (a.date > b.date ? -1 : 1)).slice(0, limit);
  const groups: DayGroup<T>[] = [];
  for (const r of recent) {
    const day = r.date.slice(0, 10);
    const last = groups.at(-1);
    if (last !== undefined && last.day === day) last.attempts.push(r);
    else groups.push({ day, attempts: [r] });
  }
  return groups;
}

export interface Summary {
  readonly attempts: number;
  readonly meanSimilarity: number | null;
  readonly perfectCount: number;
  readonly distinctPhrases: number;
}

export function summarize(rows: readonly AttemptLike[]): Summary {
  return {
    attempts: rows.length,
    meanSimilarity:
      rows.length === 0 ? null : rows.reduce((s, x) => s + x.similarity, 0) / rows.length,
    perfectCount: rows.filter((r) => r.perfect === true).length,
    distinctPhrases: new Set(rows.map((r) => r.target)).size,
  };
}
