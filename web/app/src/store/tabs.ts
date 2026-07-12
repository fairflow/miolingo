// Pure tab-routing helpers — the whole "router" for this no-SvelteKit SPA.
// Kept framework-free so they're unit-testable without rune compilation
// (astro convention: runes stores are thin containers over pure helpers).

export const TABS = ['practice', 'story', 'vocab', 'stats', 'history', 'helm'] as const;
export type Tab = (typeof TABS)[number];

export const TAB_LABELS: Record<Tab, string> = {
  practice: '🎯 Practice',
  story: '📖 Story',
  vocab: '📚 Vocabulary',
  stats: '📊 Statistics',
  history: '📜 History',
  helm: '⚙️ Helm',
};

export const DEFAULT_TAB: Tab = 'practice';

/** Parse a location.hash ("#vocab", "vocab", "") into a Tab, defaulting safely. */
export function parseTab(hash: string): Tab {
  const name = hash.replace(/^#/, '');
  return (TABS as readonly string[]).includes(name) ? (name as Tab) : DEFAULT_TAB;
}
