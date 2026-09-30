# Decisions — append-only, newest last. Record rejected alternatives.

## 2026-07-12 — Stack: Vite + Svelte 5 runes, no SvelteKit

Copied from the astro blueprint, which proved the shape at similar scale.
SvelteKit rejected: no SSR/routing needs (hash tabs suffice), and the domain
core must stay framework-free. React rejected: user preference + astro
precedent.

## 2026-07-12 — Python sidecar for the phonetics stack

espeak (subprocess), Whisper and the wav2vec2 A2P recognizers (torch) cannot
run in TS. Alternatives rejected: transformers.js/ONNX conversion of the five
benched specialist models is a research project with accuracy risk;
Web Speech API loses the accuracy channel entirely. The sidecar reuses
`src/audio` + `src/scoring` verbatim, so the app and the port score
identically. Matches the spec's oracle boundary.

## 2026-07-12 — Browser-owned persistence (Dexie), stateless sidecar

User choice (astro-pure). Vocab, practice log, and settings live in
IndexedDB; portability via JSON export/import; the existing MySQL data
arrives through a one-off export script (M5). Rejected: SQLite behind the
sidecar (server state complicates the "kill the sidecar, lose nothing"
property and the astro pattern).

## 2026-07-12 — Materials served from language_materials/, not copied

The oracle mounts the directory read-only at /materials and provides an
index endpoint. One source of truth; no build-time copy step to drift.
`src/app_language_materials.py` imports streamlit, so the sidecar walks the
unified layout itself (~20 lines) rather than importing it.

## 2026-07-13 — Persisted vocab rows drop domain ids

Identity is [lang+word]; Dexie auto-assigns row ids on write-through. The
domain's per-language id sequences would collide on the global primary key.
In-memory ids stay stable within a session; they are never exported.

## 2026-07-13 — Translation reuses src/translation.py, degradable

The provider chain (Google/OpenAI via secrets.toml or env) runs stateless
(no cache table). /api/translate 503s without a key; the UI hides free-text
and autofill on health.translate_available. Minimal pairs are computed
server-side by the app's own src/ipa/minimal_pairs.py over the learner's
vocabulary (espeak phonemes per word) rather than porting 300 lines to TS.

## 2026-07-12 — Displayed scores come from the oracle only

Every number/diff shown about an attempt is taken verbatim from the
/api/attempt response. TS ports of comparison/fold-map exist ONLY for the
spec's pure-function test table and cosmetic text diffs, and are pinned to
Python behaviour by committed golden files (regenerating goldens is the only
sanctioned way to change them).
