# Pitfalls — symptom → cause → fix. Seeded from astro's hard-won entries.

## Svelte 5 runes

- **`DataCloneError` on Dexie/IndexedDB writes** — `$state` values are
  proxies and not structured-cloneable → always `$state.snapshot(value)`
  before persisting.
- **`state_unsafe_mutation` thrown during render** — lazily creating/mutating
  $state inside a component render (e.g. memoizing into a store) → move the
  mutation into an event handler or `$effect`.
- **Mutating a reactive `{@const}` mid-loop** — reads stale values →
  restructure so derived values come from `$derived` at the top level.
- **`tsc --noEmit` does NOT typecheck `.svelte` files** — only `.ts` is
  gated. Keep logic in pure `.ts` modules (which is the architecture anyway);
  verify components in the browser.

## Storage

- **IndexedDB is per-origin** — changing the dev port silently "loses" all
  data. Ports are pinned (8330/8331, strictPort). Export/import JSON is the
  recovery path; call `navigator.storage.persist()` once at startup (M4).

## Audio (anticipated, M3/M4)

- **MediaRecorder containers vary by browser** (webm/opus vs Safari mp4) —
  never assume WAV client-side; the sidecar ffmpeg-normalizes everything to
  16 kHz mono WAV before Whisper/A2P.
- **Whisper cold start is tens of seconds** — surface `timings_ms` from
  /api/attempt and the health endpoint's `whisper.loaded`; optionally preload
  via `MIO_PRELOAD_WHISPER`.

## espeak

- **espeak vs espeak-ng output differs** — the fold-map and goldens were
  mined against the binary `config.get_espeak_path()` resolves
  (`/opt/local/bin/espeak` on this machine). The health endpoint reports the
  binary in use; a different binary shifts G2P output and goldens.
