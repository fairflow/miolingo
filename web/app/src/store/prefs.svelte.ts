// UI state runes store — thin $state container; logic lives in pure modules
// (store/tabs.ts). Hash-tab sync makes reload/back/forward work with no
// router dependency.

import { parseTab, type Tab } from './tabs.js';

export const ui = $state({
  tab: 'practice' as Tab,
});

export function setTab(tab: Tab): void {
  ui.tab = tab;
  if (typeof window !== 'undefined' && window.location.hash !== `#${tab}`) {
    window.location.hash = tab;
  }
}

/** Adopt the URL hash on startup and follow hashchange (back/forward). */
export function initTabSync(): void {
  if (typeof window === 'undefined') return;
  ui.tab = parseTab(window.location.hash);
  window.addEventListener('hashchange', () => {
    ui.tab = parseTab(window.location.hash);
  });
}

// --- theme (dark default; .light class on <html> flips the CSS vars) -----
export type Theme = 'dark' | 'light';

export const theme = $state<{ value: Theme }>({ value: 'dark' });

export function setTheme(t: Theme): void {
  theme.value = t;
  if (typeof document !== 'undefined') {
    document.documentElement.classList.toggle('light', t === 'light');
  }
  try {
    localStorage.setItem('miolingo.theme', t);
  } catch {
    /* private mode etc. — theme just won't persist */
  }
}

export function initTheme(): void {
  try {
    const saved = localStorage.getItem('miolingo.theme');
    setTheme(saved === 'light' ? 'light' : 'dark');
  } catch {
    /* defaults stand */
  }
}
