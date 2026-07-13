"""Oracle smoke tests. Run: venv/bin/python -m pytest web/oracle/tests -q"""
from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from main import app  # noqa: E402

client = TestClient(app)


def test_health_ok():
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["espeak"], "espeak binary must be present for the oracle to be useful"
    assert "fr" in body["a2p_langs"]


def test_g2p_french_word():
    r = client.post("/api/g2p", json={"texts": ["bonjour"], "lang": "fr"})
    assert r.status_code == 200
    item = r.json()["items"][0]
    assert item["text"] == "bonjour"
    assert item["ipa"].strip(), "espeak must produce IPA for a known word"


def test_materials_index_lists_unified_files():
    r = client.get("/api/materials")
    assert r.status_code == 200
    files = r.json()["files"]
    assert files, "unified materials should be present in this repo"
    kinds = {f["kind"] for f in files}
    assert "phrases" in kinds


def test_materials_static_serves_indexed_file():
    files = client.get("/api/materials").json()["files"]
    first = files[0]["path"]
    r = client.get(f"/materials/{first}")
    assert r.status_code == 200
    assert "phrases" in r.json()


def test_translate_degrades_when_unconfigured_or_works():
    r = client.post("/api/translate", json={
        "text": "hello", "source_lang": "English", "target_lang": "French"})
    # Either a real provider is configured (200 + text) or it must 503 —
    # never a silent wrong answer.
    assert r.status_code in (200, 502, 503)
    if r.status_code == 200:
        assert r.json()["translation"].strip()


def test_minimal_pairs_from_word_list():
    words = [{"text": w} for w in ("casa", "cama", "cassa", "gato", "pato")]
    r = client.post("/api/minimal-pairs", json={"items": words, "lang": "it"})
    assert r.status_code == 200
    phrases = r.json()["phrases"]
    assert phrases, "expected at least one minimal pair from the fixture words"
    assert all(p["text"] for p in phrases)
