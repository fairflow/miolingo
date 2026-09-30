"""Golden clips (tests/golden/realised_phone/manifest.yaml). Needs MFA + the clips,
which live outside the repo; skipped otherwise. Full runner:
scripts/realised_phone/run_golden.py."""

import importlib.util
import os
import shutil
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "tests" / "golden" / "realised_phone" / "manifest.yaml"


def _runner():
    spec = importlib.util.spec_from_file_location("run_golden", ROOT / "scripts" / "realised_phone" / "run_golden.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _mfa_available():
    cmd = os.environ.get("MIO_MFA_CMD", "mfa").split()[0]
    return shutil.which(cmd) is not None or Path(cmd).exists()


CLIPS = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))["clips"]


def test_manifest_is_well_formed():
    ids = [c["id"] for c in CLIPS]
    assert len(ids) == len(set(ids))
    for c in CLIPS:
        assert c["level"] in ("detector", "combined", "pipeline")
        if c["level"] in ("detector", "combined"):
            assert {"aligner", "phone", "class"} <= set(c)
        else:
            assert c["expect"]


@pytest.mark.parametrize("clip", CLIPS, ids=[c["id"] for c in CLIPS])
def test_golden_clip(clip):
    if not _mfa_available():
        pytest.skip("MFA not available (set MIO_MFA_CMD)")
    r = _runner().run_clip(clip, allow_candidates=True)
    if r["result"] == "skipped":
        pytest.skip(r["why"])
    assert r["result"] != "fail", r          # abstaining/uncertain is allowed; confident-wrong is not
