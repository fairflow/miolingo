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
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from fastapi import FastAPI, File, Form, HTTPException, Response, UploadFile  # noqa: E402
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
    import engines
    from audio.phone_recognizer import _VOICE_TO_MODEL

    model, loaded = engines.whisper_status()
    return schemas.Health(
        ok=True,
        espeak=_espeak_path(),
        whisper=schemas.WhisperStatus(model=model, loaded=loaded),
        a2p_langs=sorted(_VOICE_TO_MODEL),
        translate_available=engines.translate_available(),
    )


@app.post("/api/translate", response_model=schemas.TranslateResponse)
def translate(req: schemas.TranslateRequest) -> schemas.TranslateResponse:
    """Provider-chain translation (src/translation.py, stateless). 503 when no
    provider key is configured — the UI hides translate features on that."""
    import engines

    if not engines.translate_available():
        raise HTTPException(503, "no translation provider configured")
    try:
        return schemas.TranslateResponse(
            translation=engines.translate(req.text, req.source_lang, req.target_lang)
        )
    except RuntimeError as e:
        raise HTTPException(502, str(e)) from e


@app.post("/api/minimal-pairs", response_model=schemas.MinimalPairsResponse)
def minimal_pairs(req: schemas.MinimalPairsRequest) -> schemas.MinimalPairsResponse:
    """Minimal-pair practice items from the caller's word list (usually the
    learner's vocabulary): espeak phonemes per word, then the app's pair
    finder + practice formatting (src/ipa/minimal_pairs.py, verbatim)."""
    from ipa.minimal_pairs import generate_minimal_pair_practice_list
    from scoring.phonemes import get_phonemes

    if _espeak_path() is None:
        raise HTTPException(503, "espeak binary not found")
    vocab = [
        {
            "text": it.text,
            "translation": it.translation or "",
            "ipa": it.ipa or "",
            "phonemes": get_phonemes(it.text, req.lang),
        }
        for it in req.items
    ]
    pairs = generate_minimal_pair_practice_list(
        vocab, max_pairs=req.max_pairs, lang_code=req.lang.split("-")[0]
    )
    return schemas.MinimalPairsResponse(
        phrases=[
            schemas.PracticePhrase(
                text=p.get("text", ""),
                translation=p.get("translation", ""),
                ipa=(p.get("ipa") or "").strip("[]"),
            )
            for p in pairs
        ]
    )


@app.post("/api/attempt", response_model=schemas.AttemptResponse)
async def attempt(
    audio: UploadFile = File(...),
    target: str = Form(...),
    lang: str = Form(...),
    algorithm: str = Form("weighted_phone"),
    whisper_model: str = Form("base"),
    silence_threshold: float = Form(0.01),
) -> schemas.AttemptResponse:
    """THE one round-trip: audio + target in → ASR text, both IPA channels,
    both scores, per-phone ops out (src/scoring/practice.py, streamlit-free)."""
    import pipeline

    if algorithm not in ("weighted_phone", "edit_distance"):
        raise HTTPException(422, f"unknown algorithm {algorithm!r}")
    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(422, "empty audio upload")
    try:
        return pipeline.score_attempt(
            audio_bytes,
            target=target,
            voice=lang,
            algorithm=algorithm,
            whisper_model=whisper_model,
            silence_threshold=silence_threshold,
        )
    except subprocess.CalledProcessError as e:
        raise HTTPException(422, f"audio decode failed (ffmpeg): {e}") from e


@app.post("/api/tts")
def tts(req: schemas.TtsRequest) -> Response:
    """Target-pronunciation audio; X-Tts-Engine reports the engine used
    (fallback chain google_cloud → gtts → espeak, per src/audio/tts.py)."""
    import engines

    try:
        audio_bytes, media_type, engine = engines.generate_tts(
            req.text, req.lang, engine=req.engine, speed=req.speed, slow=req.slow
        )
    except RuntimeError as e:
        raise HTTPException(503, str(e)) from e
    return Response(content=audio_bytes, media_type=media_type,
                    headers={"X-Tts-Engine": engine})


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
