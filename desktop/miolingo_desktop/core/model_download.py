"""First-run Whisper model availability + download (UI-free).

The default ``medium`` model (~1.5 GB) is not bundled (SPEC §8); openai-whisper
downloads it on first ``load_model`` and caches it under ``~/.cache/whisper``.
These helpers let the UI show a one-time "downloading model" state and check
whether a model is already cached (so it can warn before a long first run).
"""

from __future__ import annotations

import os
from pathlib import Path

# openai-whisper's published model filenames (per model name).
_WHISPER_FILENAMES: dict[str, str] = {
    "tiny": "tiny.pt",
    "base": "base.pt",
    "small": "small.pt",
    "medium": "medium.pt",
    "large": "large-v3.pt",
}


def whisper_cache_dir() -> Path:
    """The directory openai-whisper caches downloaded models in."""
    env = os.environ.get("XDG_CACHE_HOME")
    base = Path(env) if env else Path.home() / ".cache"
    return base / "whisper"


def is_model_cached(model_name: str) -> bool:
    """True if *model_name* is already downloaded (no network needed to load)."""
    filename = _WHISPER_FILENAMES.get(model_name)
    if filename is None:
        return False
    return (whisper_cache_dir() / filename).exists()


def ensure_model(model_name: str, *, progress_fn=None) -> object:
    """Load *model_name*, downloading on first use. Returns the loaded model.

    Reuses the cached model loader in ``asr`` so the model is cached in-process
    too. ``progress_fn(message)`` is called before a potentially slow load (the
    UI shows it once); the actual byte-progress is owned by whisper's downloader.
    """
    from .asr import get_whisper_model

    if progress_fn is not None and not is_model_cached(model_name):
        progress_fn(
            f"Downloading Whisper '{model_name}' model on first run "
            "(this can take a while)..."
        )
    return get_whisper_model(model_name, progress_fn=progress_fn)
