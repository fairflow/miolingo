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


class MaterialsFile(BaseModel):
    path: str  # under /materials/, e.g. "unified/phrases/common-phrases-001.json"
    kind: str  # phrases | phrasebook | stories
    meta: dict


class MaterialsIndex(BaseModel):
    files: list[MaterialsFile]
