"""Miolingo phonetics oracle — stateless FastAPI sidecar.

Wraps the repo's Python audio/ML stack (espeak G2P now; Whisper ASR + A2P
phone recognizers + weighted scoring arrive with /api/attempt in M3) so the
Svelte app stays pure TypeScript. The spec's oracle boundary made real: this
process computes, the browser owns all state (Dexie).

Run (dev):   cd web/oracle && ../../venv/bin/uvicorn main:app --port 8331
Prod-local:  same command after `npm run build` — dist/ is mounted at /.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

import schemas  # noqa: E402

MATERIALS_DIR = REPO / "language_materials"
DIST_DIR = REPO / "web" / "app" / "dist"

app = FastAPI(title="miolingo-oracle", version="0.1.0")

# Vite's dev proxy makes requests same-origin, but allow localhost dev tools
# (e.g. hitting :8331 directly) without fuss. Local deployment only.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_methods=["*"],
    allow_headers=["*"],
)


def _espeak_path() -> str | None:
    from scoring.phonemes import get_espeak_path

    path = get_espeak_path()
    return path if shutil.which(path) else None


@app.get("/api/health", response_model=schemas.Health)
def health() -> schemas.Health:
    from audio.phone_recognizer import _VOICE_TO_MODEL

    return schemas.Health(
        ok=True,
        espeak=_espeak_path(),
        whisper=schemas.WhisperStatus(),  # loads on first /api/attempt (M3)
        a2p_langs=sorted(_VOICE_TO_MODEL),
        translate_available=False,  # wired in M8
    )


@app.post("/api/g2p", response_model=schemas.G2pResponse)
def g2p(req: schemas.G2pRequest) -> schemas.G2pResponse:
    from scoring.phonemes import get_ipa, get_phonemes

    if _espeak_path() is None:
        raise HTTPException(503, "espeak binary not found")
    items = [
        schemas.G2pItem(
            text=text,
            ipa=get_ipa(text, req.lang),
            phonemes=get_phonemes(text, req.lang),
        )
        for text in req.texts
    ]
    return schemas.G2pResponse(lang=req.lang, items=items)


@app.get("/api/materials", response_model=schemas.MaterialsIndex)
def materials_index() -> schemas.MaterialsIndex:
    """Index of unified materials (one source of truth: language_materials/).

    Walks unified/{phrases,phrasebook,stories}/*.json and returns each file's
    meta block. (src/app_language_materials.py imports streamlit, so the
    walk is reimplemented here — ~20 lines against a stable layout.)
    """
    files: list[schemas.MaterialsFile] = []
    unified = MATERIALS_DIR / "unified"
    for kind in ("phrases", "phrasebook", "stories"):
        for path in sorted((unified / kind).glob("*.json")):
            try:
                meta = json.loads(path.read_text(encoding="utf-8")).get("meta", {})
            except (OSError, json.JSONDecodeError):
                continue  # unreadable file: omit from index rather than 500
            files.append(
                schemas.MaterialsFile(
                    path=str(path.relative_to(MATERIALS_DIR)), kind=kind, meta=meta
                )
            )
    return schemas.MaterialsIndex(files=files)


app.mount("/materials", StaticFiles(directory=MATERIALS_DIR), name="materials")

# Prod-local: serve the built SPA from this same process/origin (M8 verifies
# this path end-to-end; harmless no-op until dist/ exists).
if DIST_DIR.exists():
    app.mount("/", StaticFiles(directory=DIST_DIR, html=True), name="app")
