#!/usr/bin/env python3
"""Generate one sample clip per bundled Piper voice for quality spot-checks.

For each locale in the registry, synthesizes a short phrase and writes a WAV to
``desktop/packaging/voice_samples/``. Matthew listens through these and flags any
weak voice in ``QUESTIONS.md`` for replacement (see the Piper-voice question).

Run after fetching voices:

    python desktop/packaging/fetch_piper_voices.py
    python desktop/packaging/generate_voice_samples.py
"""

from __future__ import annotations

import sys
from pathlib import Path

_PKG_ROOT = Path(__file__).resolve().parent.parent
if str(_PKG_ROOT) not in sys.path:
    sys.path.insert(0, str(_PKG_ROOT))

from miolingo_desktop.core import piper_voices  # noqa: E402

# A natural sample phrase per locale.
SAMPLE_PHRASES: dict[str, str] = {
    "en-US": "The quick brown fox jumps over the lazy dog.",
    "en-GB": "The quick brown fox jumps over the lazy dog.",
    "pt-BR": "O rato roeu a roupa do rei de Roma.",
    "pt-PT": "O rato roeu a roupa do rei de Roma.",
    "fr-FR": "Le vif renard brun saute par-dessus le chien paresseux.",
    "de-DE": "Der schnelle braune Fuchs springt über den faulen Hund.",
    "es-ES": "El veloz zorro marrón salta sobre el perro perezoso.",
    "it-IT": "La rapida volpe marrone salta sopra il cane pigro.",
    "nl-NL": "De snelle bruine vos springt over de luie hond.",
    "nl-BE": "De snelle bruine vos springt over de luie hond.",
}


def generate(out_dir: Path | None = None) -> list[Path]:
    out_dir = out_dir or (_PKG_ROOT / "packaging" / "voice_samples")
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for locale, voice_id in sorted(piper_voices.PIPER_VOICE_IDS.items()):
        phrase = SAMPLE_PHRASES.get(locale, "Hello, world.")
        try:
            audio = piper_voices.synthesize(phrase, locale)
        except piper_voices.PiperUnavailable as e:
            print(f"skip {locale} ({voice_id}): {e}", file=sys.stderr)
            continue
        dest = out_dir / f"{locale}_{voice_id}.wav"
        dest.write_bytes(audio)
        written.append(dest)
        print(f"wrote {dest.name}")
    return written


if __name__ == "__main__":
    out = generate()
    print(f"Done. {len(out)} sample clip(s).")
