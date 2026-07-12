import { describe, expect, it } from 'vitest';
import { DEFAULT_TAB, parseTab, TAB_LABELS, TABS } from '../src/store/tabs.js';

describe('hash-tab routing', () => {
  it('parses every known tab with and without the # prefix', () => {
    for (const tab of TABS) {
      expect(parseTab(`#${tab}`)).toBe(tab);
      expect(parseTab(tab)).toBe(tab);
    }
  });

  it('falls back to the default tab on unknown or empty hashes', () => {
    expect(parseTab('')).toBe(DEFAULT_TAB);
    expect(parseTab('#')).toBe(DEFAULT_TAB);
    expect(parseTab('#nonsense')).toBe(DEFAULT_TAB);
  });

  it('has a label for every tab', () => {
    for (const tab of TABS) {
      expect(TAB_LABELS[tab]).toBeTruthy();
    }
  });
});
