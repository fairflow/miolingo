"""Piper neural-voice registry, resolution, and synthesis (offline TTS).

Maps each supported locale to a bundled Piper voice (a ``.onnx`` model +
``.onnx.json`` config). The voice files themselves are large binaries and are
NOT committed — ``packaging/fetch_piper_voices.py`` downloads them into the
voices directory and Milestone 8 bundles them into the app. This module locates
the voices dir, resolves a locale to a model path, and runs synthesis.

Voices dir resolution (``voices_dir()``):
1. ``$MIOLINGO_PIPER_VOICES_DIR`` if set (packaging points this at the bundle);
2. else ``miolingo_desktop/resources/piper_voices/`` next to the package.

Voice selection per language is a curated default (medium quality/size tier);
Matthew can spot-check the M7 sample clips and swap any weak voice (QUESTIONS.md).
"""

from __future__ import annotations

import os
import wave
from pathlib import Path

# Locale (BCP-47, as produced by config.VOICE_LOCALE_NORMALIZATION) -> Piper
# voice id. Voice ids follow the rhasspy/piper-voices naming
# (<lang>_<REGION>-<name>-<quality>). One vetted medium voice per language.
PIPER_VOICE_IDS: dict[str, str] = {
    "en-US": "en_US-amy-medium",
    "en-GB": "en_GB-alan-medium",
    "pt-BR": "pt_BR-faber-medium",
    "pt-PT": "pt_PT-tugão-medium",
    "fr-FR": "fr_FR-siwis-medium",
    "de-DE": "de_DE-thorsten-medium",
    "es-ES": "es_ES-davefx-medium",
    "it-IT": "it_IT-riccardo-x_low",
    "nl-NL": "nl_NL-mls-medium",
    "nl-BE": "nl_BE-rdh-medium",
}


class PiperUnavailable(RuntimeError):
    """Raised when a Piper voice for a locale can't be resolved/synthesized."""


def voices_dir() -> Path:
    """Resolve the directory holding the bundled Piper ``.onnx`` voice files."""
    env = os.environ.get("MIOLINGO_PIPER_VOICES_DIR")
    if env:
        return Path(env)
    return Path(__file__).resolve().parent.parent / "resources" / "piper_voices"


def voice_id_for_locale(locale: str, registry: dict[str, str] | None = None) -> str:
    """Return the Piper voice id for *locale*, or raise PiperUnavailable."""
    table = PIPER_VOICE_IDS if registry is None else registry
    voice_id = table.get(locale)
    if not voice_id:
        raise PiperUnavailable(f"No Piper voice configured for locale '{locale}'")
    return voice_id


def model_path_for_locale(
    locale: str,
    *,
    registry: dict[str, str] | None = None,
    directory: Path | None = None,
) -> Path:
    """Resolve the on-disk ``.onnx`` model path for *locale*.

    Raises PiperUnavailable if the locale is unknown or the model file is not
    present (i.e. voices haven't been fetched/bundled yet).
    """
    voice_id = voice_id_for_locale(locale, registry)
    base = directory if directory is not None else voices_dir()
    model = base / f"{voice_id}.onnx"
    if not model.exists():
        raise PiperUnavailable(
            f"Piper voice '{voice_id}' not found in {base} "
            "(run packaging/fetch_piper_voices.py)"
        )
    return model


def synthesize(
    text: str,
    locale: str = "pt-BR",
    *,
    registry: dict[str, str] | None = None,
    directory: Path | None = None,
) -> bytes:
    """Synthesize *text* to WAV bytes with the locale's bundled Piper voice.

    Uses the ``piper`` Python API (``piper.PiperVoice``) which loads the local
    ``.onnx`` model and runs fully offline. Raises PiperUnavailable if the voice
    or the piper package isn't available so the dispatcher can fall back.
    """
    model = model_path_for_locale(locale, registry=registry, directory=directory)

    try:
        from piper import PiperVoice  # type: ignore[import-not-found]
    except Exception as e:  # noqa: BLE001 - piper not installed
        raise PiperUnavailable(f"piper package unavailable: {e}") from e

    try:
        voice = PiperVoice.load(str(model))
        return _synthesize_to_wav_bytes(voice, text)
    except PiperUnavailable:
        raise
    except Exception as e:  # noqa: BLE001 - synthesis failure -> fall back
        raise PiperUnavailable(f"Piper synthesis failed: {e}") from e


def _synthesize_to_wav_bytes(voice: object, text: str) -> bytes:
    """Run a loaded PiperVoice over *text*, returning WAV bytes.

    Written defensively against piper API drift: prefer ``synthesize_wav`` if
    present, else fall back to streaming ``synthesize`` audio chunks into a WAV
    container using the voice's sample rate.
    """
    import io

    buf = io.BytesIO()

    if hasattr(voice, "synthesize_wav"):
        with wave.open(buf, "wb") as wav_file:
            voice.synthesize_wav(text, wav_file)  # type: ignore[attr-defined]
        return buf.getvalue()

    # Fallback: stream raw audio chunks.
    sample_rate = int(getattr(getattr(voice, "config", None), "sample_rate", 22050))
    with wave.open(buf, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        for chunk in voice.synthesize_stream_raw(text):  # type: ignore[attr-defined]
            wav_file.writeframes(chunk)
    return buf.getvalue()
