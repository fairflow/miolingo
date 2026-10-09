# Miolingo — web port (TypeScript + Svelte 5)

Port of the Streamlit app to a local-first SPA, built **from the CCS spec**
(`../spec/*.wl`) the way the Swift port was, following the architecture
conventions of the astro app (Vite + Svelte 5 runes, no SvelteKit, pure-TS
domain core, Dexie persistence, plain-CSS theming).

Two processes, one origin:

- **`app/`** — the Svelte SPA. All state lives in the browser (Dexie/
  IndexedDB + localStorage). Pure framework-free domain code under
  `src/domain/` implements the spec's five agents.
- **`oracle/`** — a stateless FastAPI sidecar wrapping the repo's Python
  phonetics stack (espeak G2P, Whisper ASR, wav2vec2 A2P recognizers,
  panphon weighted scoring). The spec's oracle boundary, made literal.

## Run

```bash
cd web/app && npm install          # once
pip install -r web/oracle/requirements.txt   # once, into the repo venv

cd web && make dev                 # vite :8330 + oracle :8331 (browse :8330)
cd web && make serve               # prod-local: built SPA served by the oracle on :8331
cd web && make test                # vitest + tsc + pytest
```

## Layout

See `docs/DESIGN.md` for the architecture, `docs/DECISIONS.md` for the
decision log (append-only, with rationale), and `docs/PITFALLS.md` before
touching Svelte 5 state or Dexie writes.

Milestones are tracked as beads (`bd list | grep "web port"`): M1 scaffold →
M2 domain core → M3 attempt pipeline → M4 practice loop (first usable) →
M5 vocab → M6 story → M7 stats/history → M8 polish.
