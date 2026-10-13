"""The variants on offer (English, French, German only)."""
from __future__ import annotations

from . import _miolingo as mio

# code -> (language, display name, espeak voice, Whisper language code)
# Codes and espeak voices follow Miolingo's LANGUAGE_CONFIG (config.py):
# English en-gb / en-us, French fr-fr, German de.
_VARIANTS = [
    ("en-gb", "en", "English (British)", "en-gb", "en"),
    ("en-us", "en", "English (American)", "en-us", "en"),
    ("fr-fr", "fr", "French (France)", "fr-fr", "fr"),
    ("de", "de", "German", "de", "de"),
]


def variants() -> list[dict]:
    """[{code, lang, name, espeak, whisper, phone_model}], in display order.

    `phone_model` is the Hugging Face id Miolingo's `model_for_voice` picks
    for the variant's espeak voice (per-language choice, one function)."""
    return [
        {"code": c, "lang": l, "name": n, "espeak": e, "whisper": w,
         "phone_model": phone_model(c)}
        for (c, l, n, e, w) in _VARIANTS
    ]


def variant(code: str) -> dict:
    for v in variants():
        if v["code"] == code:
            return v
    raise KeyError(f"unknown variant {code!r}; on offer: "
                   f"{[v['code'] for v in variants()]}")


def phone_model(code: str) -> str:
    """The ONE place where the phone model is chosen for a variant."""
    espeak = next(e for (c, _l, _n, e, _w) in _VARIANTS if c == code)
    return mio.phone_recognizer.model_for_voice(espeak)
