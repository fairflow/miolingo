"""
ASR gate (HANDOFF "Settled"): Whisper confirms the learner attempted the target
words in the target language BEFORE analysis. Its transcript is never the error
signal -- a pass only means "worth aligning"; a fail means "don't analyse".
"""

from __future__ import annotations

import unicodedata
from collections import Counter
from typing import Callable, Optional

from realised_phone.align import words_of
from realised_phone.model import GateResult


def _fold(w: str) -> str:
    """Accent-insensitive compare: Whisper often drops/adds accents on learner speech."""
    return "".join(c for c in unicodedata.normalize("NFD", w) if unicodedata.category(c) != "Mn")


def word_recall(target_text: str, transcript: str) -> tuple[float, list[str]]:
    tgt = [_fold(w) for w in words_of(target_text)]
    have = Counter(_fold(w) for w in words_of(transcript))
    missing = []
    for w in tgt:
        if have[w] > 0:
            have[w] -= 1
        else:
            missing.append(w)
    return ((len(tgt) - len(missing)) / len(tgt) if tgt else 0.0), missing


def check(target_text: str, transcript: Optional[str], min_word_recall: float = 0.6) -> GateResult:
    if transcript is None:
        return GateResult(False, "", 0.0, words_of(target_text), "no transcript")
    r, missing = word_recall(target_text, transcript)
    ok = r >= min_word_recall
    return GateResult(ok, transcript, round(r, 3), missing,
                      "" if ok else f"only {r:.0%} of target words heard (< {min_word_recall:.0%})")


def whisper_transcriber(settings: dict, language: str) -> Callable[[str], str]:
    """Adapter over the app's ASR (audio.asr.transcribe_audio) for standalone use.
    In the practice flow, reuse result['recognized'] instead of transcribing twice."""
    def _t(wav_path: str) -> str:
        from audio.asr import transcribe_audio
        return transcribe_audio(wav_path, settings, language) or ""
    return _t
