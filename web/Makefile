# Miolingo web port — local dev/serve/test entry points.
# Run from web/. The repo venv (../venv) supplies the Python ML stack.

.PHONY: dev app oracle serve test

dev:  ## run oracle + vite dev together (Ctrl-C stops both)
	$(MAKE) -j2 oracle app

app:  ## vite dev server on :8330 (proxies /api,/materials to :8331)
	cd app && npm run dev

oracle:  ## FastAPI sidecar on :8331
	cd oracle && ../../venv/bin/uvicorn main:app --port 8331 --reload

serve:  ## prod-local: build the SPA, then serve app+api from one process
	cd app && npm run build
	cd oracle && ../../venv/bin/uvicorn main:app --port 8331

test:  ## all gates: vitest, tsc, pytest
	cd app && npm test && npm run typecheck
	cd .. && venv/bin/python -m pytest web/oracle/tests -q
