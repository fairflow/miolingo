// Vitest setup: in-memory IndexedDB so the Dexie store works in node
// (must load before any module imports store/db.ts). Materials tests read
// the real shipped language_materials from disk (astro convention).
import 'fake-indexeddb/auto';
