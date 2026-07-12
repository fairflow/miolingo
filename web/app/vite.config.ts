import { defineConfig } from 'vitest/config';
import { svelte } from '@sveltejs/vite-plugin-svelte';

// Dev serving model: Vite serves the SPA on :8330 and proxies the oracle
// sidecar (uvicorn on :8331) so the browser sees ONE origin — no CORS in
// practice, and IndexedDB stays pinned to a single origin (see PITFALLS).
// Prod-local flips it around: the sidecar mounts dist/ and is the one origin.
export default defineConfig({
  // relative base so dist/ can be mounted under any prefix by the sidecar
  base: './',
  plugins: [svelte()],
  server: {
    port: 8330,
    strictPort: true,
    proxy: {
      '/api': 'http://localhost:8331',
      '/materials': 'http://localhost:8331',
    },
  },
  test: {
    setupFiles: ['./test/setup.ts'],
  },
});
