"""mfa_align_batch with a stub `mfa` (no MFA needed): corpus layout, output
mapping, caching, and utterances MFA drops."""

import json
import os
import stat
import sys

from realised_phone.align import mfa_align_batch

from conftest import FIXTURES

STUB = r'''#!{py}
import json, shutil, sys
from pathlib import Path
args = sys.argv[1:]
assert args[0] == "align", args
corpus, out = Path(args[1]), Path(args[4])
log = Path({log!r})
calls = int(log.read_text()) if log.exists() else 0
log.write_text(str(calls + 1))
for spk in sorted(corpus.iterdir()):
    utt = spk.name
    assert (spk / f"{{utt}}.wav").exists() and (spk / f"{{utt}}.lab").read_text().strip()
    if utt == "dropped":
        continue
    (out / utt).mkdir(parents=True, exist_ok=True)
    shutil.copy({fixture!r}, out / utt / f"{{utt}}.json")
'''


def _stub(tmp_path):
    log = tmp_path / "calls"
    exe = tmp_path / "mfa"
    exe.write_text(STUB.format(py=sys.executable, log=str(log),
                               fixture=str(FIXTURES / "mfa_es_correctamente.json")))
    exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    return exe, log


def test_batch_alignment_maps_caches_and_drops(tmp_path, monkeypatch):
    exe, log = _stub(tmp_path)
    monkeypatch.setenv("MIO_MFA_CMD", str(exe))
    monkeypatch.delenv("MIO_MFA_MODELS", raising=False)
    wav = tmp_path / "a.wav"
    wav.write_bytes(b"RIFF")
    items = [{"id": "u1", "wav": str(wav), "text": "La aplicación móvil."},
             {"id": "u2", "wav": str(wav), "text": "correctamente"},
             {"id": "dropped", "wav": str(wav), "text": "nada"}]
    cache = tmp_path / "cache"
    r = mfa_align_batch(items, "spanish_mfa", "spanish_mfa", cache_dir=str(cache), jobs=2)
    assert set(r) == {"u1", "u2"}                        # MFA-dropped utterance is absent
    assert r["u1"].words[-1].label == "correctamente"
    assert (cache / "spanish_mfa" / "u1.json").exists()
    assert log.read_text() == "1"
    # second call: everything cached except the dropped one -> MFA runs only for it
    r2 = mfa_align_batch(items[:2], "spanish_mfa", "spanish_mfa", cache_dir=str(cache))
    assert set(r2) == {"u1", "u2"} and log.read_text() == "1"
    assert json.loads((cache / "spanish_mfa" / "u2.json").read_text())["tiers"]


def test_batch_without_cache(tmp_path, monkeypatch):
    exe, _ = _stub(tmp_path)
    monkeypatch.setenv("MIO_MFA_CMD", str(exe))
    wav = tmp_path / "a.wav"
    wav.write_bytes(b"RIFF")
    r = mfa_align_batch([{"id": "u1", "wav": str(wav), "text": "correctamente"}],
                        "spanish_mfa", "spanish_mfa")
    assert r["u1"].oov == [] and os.path.exists(wav)
