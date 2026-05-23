"""UI-framework-free business logic (ported from the Streamlit app).

Nothing in this package may import ``streamlit`` or ``PySide6`` (enforced by
``tests/unit/test_core_purity.py``). It takes plain arguments and returns plain
values so it stays headlessly testable.

Modules:
- ``config``       — language/voice tables + default settings.
- ``comparison``   — Levenshtein scoring (verbatim from source; parity-locked).
- ``phonemes``     — espeak IPA/phoneme extraction.
- ``import_header``— ``(source, target)`` header parsing.
- ``materials``    — bundled language-materials discovery/loading.
- ``asr``          — Whisper transcription (model load separated for off-thread).
- ``tts``          — TTS engines + Piper->GoogleCloud->espeak dispatcher.
- ``practice``     — the practice/scoring orchestration pipeline.
"""
