"""Attempt-pipeline smoke tests — the closed loop the Swift harness proved:
espeak GENERATES audio of the target → the pipeline scores it. Slow-ish on
first run (whisper 'tiny' + the French A2P specialist load once per session).

Run: venv/bin/python -m pytest web/oracle/tests -q
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from main import app  # noqa: E402

client = TestClient(app)

TARGET = "bonjour"
VOICE = "fr"


def _espeak_wav(text: str, voice: str) -> bytes:
    from scoring.phonemes import get_espeak_path

    return subprocess.run(
        [get_espeak_path(), "-v", voice, "--stdout", text],
        capture_output=True, check=True,
    ).stdout


def _post_attempt(audio: bytes, filename: str, **form: str) -> object:
    data = {"target": TARGET, "lang": VOICE, "whisper_model": "tiny",
            "algorithm": "weighted_phone", **form}
    return client.post(
        "/api/attempt",
        files={"audio": (filename, audio, "application/octet-stream")},
        data=data,
    )


def test_attempt_fixture_wav_closed_loop():
    r = _post_attempt(_espeak_wav(TARGET, VOICE), "take.wav")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["target"] == TARGET
    assert body["target_ipa"].strip()
    # accuracy channel reads the waveform directly — must be populated
    assert body["accuracy"]["ipa"].strip()
    assert body["accuracy"]["similarity"] is not None
    assert body["accuracy"]["ops"], "per-phone ops must accompany the score"
    # espeak-generated audio of the exact target should score well acoustically
    assert body["accuracy"]["similarity"] > 0.5
    assert body["timings_ms"]["total"] > 0


def test_attempt_accepts_webm():
    wav = _espeak_wav(TARGET, VOICE)
    proc = subprocess.run(
        ["ffmpeg", "-i", "pipe:0", "-c:a", "libopus", "-f", "webm", "pipe:1"],
        input=wav, capture_output=True,
    )
    if proc.returncode != 0:
        pytest.skip("ffmpeg lacks libopus; webm path untestable here")
    r = _post_attempt(proc.stdout, "take.webm")
    assert r.status_code == 200, r.text
    assert r.json()["accuracy"]["ipa"].strip()


def test_attempt_rejects_unknown_algorithm_and_empty_audio():
    r = _post_attempt(_espeak_wav(TARGET, VOICE), "t.wav", algorithm="bogus")
    assert r.status_code == 422
    r = _post_attempt(b"", "t.wav")
    assert r.status_code == 422


def test_tts_espeak_returns_wav():
    r = client.post("/api/tts", json={"text": "bonjour", "lang": "fr", "engine": "espeak"})
    assert r.status_code == 200
    assert r.headers["x-tts-engine"] == "espeak"
    assert r.content[:4] == b"RIFF"


def test_health_reports_whisper_after_attempt():
    body = client.get("/api/health").json()
    assert body["whisper"]["loaded"] is True
    assert body["whisper"]["model"] == "tiny"
