#!/usr/bin/env python3
"""Download the bundled Piper voices into the resources voices directory.

Voices are large binaries and are NOT committed to git. This script fetches
each voice listed in ``core.piper_voices.PIPER_VOICE_IDS`` (the ``.onnx`` model
+ its ``.onnx.json`` config) from the official rhasspy/piper-voices release on
Hugging Face, into ``miolingo_desktop/resources/piper_voices/`` (override with
``$MIOLINGO_PIPER_VOICES_DIR``).

Run once before packaging (Milestone 8 bundles whatever is present here):

    python desktop/packaging/fetch_piper_voices.py

Requires network access. Idempotent: skips files already present.
"""

from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

# Make the package importable when run from anywhere in the repo.
_PKG_ROOT = Path(__file__).resolve().parent.parent
if str(_PKG_ROOT) not in sys.path:
    sys.path.insert(0, str(_PKG_ROOT))

from miolingo_desktop.core.piper_voices import PIPER_VOICE_IDS, voices_dir  # noqa: E402

# Hugging Face base for the rhasspy/piper-voices repo. Voice files live at
# <base>/<lang>/<LANG_REGION>/<name>/<quality>/<voice_id>.onnx[.json]
HF_BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0"


def _voice_url(voice_id: str, suffix: str) -> str:
    # voice_id like "pt_BR-faber-medium" -> lang=pt, region=pt_BR, name=faber, quality=medium
    lang_region, name, quality = voice_id.split("-", 2)
    lang = lang_region.split("_")[0]
    return f"{HF_BASE}/{lang}/{lang_region}/{name}/{quality}/{voice_id}.onnx{suffix}"


def fetch_all(target: Path | None = None) -> list[Path]:
    target = target or voices_dir()
    target.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for voice_id in sorted(set(PIPER_VOICE_IDS.values())):
        for suffix in ("", ".json"):
            dest = target / f"{voice_id}.onnx{suffix}"
            if dest.exists():
                print(f"skip (present): {dest.name}")
                continue
            url = _voice_url(voice_id, suffix)
            print(f"fetch: {url}")
            try:
                urllib.request.urlretrieve(url, dest)  # noqa: S310 - trusted host
                written.append(dest)
            except Exception as e:  # noqa: BLE001
                print(f"  ! failed: {e}", file=sys.stderr)
    return written


if __name__ == "__main__":
    out = fetch_all()
    print(f"Done. {len(out)} new file(s) in {voices_dir()}.")
