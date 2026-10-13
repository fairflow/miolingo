"""Locate and import Miolingo's own scoring/audio code, without Streamlit.

Miolingo's modules use top-level imports (`from audio.phone_recognizer import
...`, `from ipa import fold_map`), so its `src/` directory must be on
`sys.path`.  We APPEND it (never prepend), so nothing of ours is shadowed.

Which `src/`?  The first of:
  1. the environment variable NEOLINGO_MIOLINGO_SRC;
  2. the parent checkout `~/Software/working/miolingo/src` (the branch that
     has `audio/`, `scoring/`, `ipa/`);
  3. a `src/` found by walking up from this file, if it has `audio/`.
The `main` snapshot in the locus-overseer worktree does NOT have these
directories (it predates them), so it is not used.

Offline guarantee: HF_HUB_OFFLINE / TRANSFORMERS_OFFLINE are set so that no
call can reach the network; a model that is not already in the local cache
raises instead of downloading.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")


def _candidates():
    env = os.environ.get("NEOLINGO_MIOLINGO_SRC")
    if env:
        yield Path(env)
    yield Path.home() / "Software" / "working" / "miolingo" / "src"
    for parent in Path(__file__).resolve().parents:
        yield parent / "src"


def miolingo_src() -> Path:
    for p in _candidates():
        if (p / "audio" / "phone_recognizer.py").exists():
            return p
    raise RuntimeError(
        "Miolingo src/ (with audio/phone_recognizer.py) not found; "
        "set NEOLINGO_MIOLINGO_SRC")


_SRC = miolingo_src()
if str(_SRC) not in sys.path:
    sys.path.append(str(_SRC))

# Imported here so that failures are loud and early.  None of these modules
# imports streamlit.  (audio.asr does, so it is NOT imported: see hearing.py.)
from scoring import phonemes as phonemes            # noqa: E402
from scoring import phone_distance as phone_distance  # noqa: E402
from audio import phone_recognizer as phone_recognizer  # noqa: E402
from scoring import sound_check as sound_check      # noqa: E402
from ipa import fold_map as fold_map                # noqa: E402
import config as mio_config                         # noqa: E402

assert "streamlit" not in sys.modules, "a Miolingo module pulled in streamlit"
