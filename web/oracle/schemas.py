"""Pydantic models — the sidecar's API contract.

Mirrored by web/app/src/oracle/types.ts; change them together.
"""
from __future__ import annotations

from pydantic import BaseModel


class WhisperStatus(BaseModel):
    model: str | None = None
    loaded: bool = False


class Health(BaseModel):
    ok: bool
    espeak: str | None
    whisper: WhisperStatus
    a2p_langs: list[str]
    translate_available: bool


class G2pRequest(BaseModel):
    texts: list[str]
    lang: str


class G2pItem(BaseModel):
    text: str
    ipa: str
    phonemes: str


class G2pResponse(BaseModel):
    lang: str
    items: list[G2pItem]


class AttemptOp(BaseModel):
    """One aligned phone/char operation, target-oriented (the diff the UI
    renders verbatim — always from the same scorer that produced the numbers)."""

    kind: str  # match | substitute | insert | delete
    target: str  # '' for insert
    user: str  # '' for delete
    significant: bool  # costly enough to flag as a real error


class AttemptChannel(BaseModel):
    ipa: str
    similarity: float | None  # None when the channel produced nothing
    exact: bool
    distance: float | None
    ops: list[AttemptOp]


class AttemptTimings(BaseModel):
    asr: int
    a2p: int
    total: int


class AttemptResponse(BaseModel):
    target: str
    recognized_text: str
    target_ipa: str
    algorithm: str
    comprehensibility: AttemptChannel
    accuracy: AttemptChannel
    timings_ms: AttemptTimings


class TtsRequest(BaseModel):
    text: str
    lang: str  # espeak voice code, e.g. "fr", "pt-br"
    engine: str | None = None  # google_cloud | gtts | espeak; None = chain
    speed: int = 140  # espeak wpm
    slow: bool = False  # gtts/google slow mode


class TranslateRequest(BaseModel):
    text: str
    source_lang: str  # language NAME, e.g. "English" (the provider convention)
    target_lang: str  # language NAME, e.g. "French"


class TranslateResponse(BaseModel):
    translation: str


class MinimalPairItem(BaseModel):
    text: str
    translation: str | None = None
    ipa: str | None = None


class MinimalPairsRequest(BaseModel):
    items: list[MinimalPairItem]
    lang: str  # espeak voice code
    max_pairs: int = 20


class PracticePhrase(BaseModel):
    text: str
    translation: str = ""
    ipa: str = ""


class MinimalPairsResponse(BaseModel):
    phrases: list[PracticePhrase]


class MaterialsFile(BaseModel):
    path: str  # under /materials/, e.g. "unified/phrases/common-phrases-001.json"
    kind: str  # phrases | phrasebook | stories
    meta: dict


class MaterialsIndex(BaseModel):
    files: list[MaterialsFile]
