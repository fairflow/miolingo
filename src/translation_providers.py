"""Pluggable translation providers for Miolingo."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
import html
import json
import os
from urllib.parse import urlencode
from urllib.request import Request, urlopen


@dataclass
class TranslationResult:
    translated_text: str
    provider: str
    detected_source: Optional[str] = None
    confidence: Optional[float] = None
    raw: Optional[dict] = None


class TranslationProvider:
    name = "base"

    def translate(self, text: str, source_lang: str, target_lang: str) -> TranslationResult:
        raise NotImplementedError


class GoogleTranslator(TranslationProvider):
    name = "google"

    def __init__(self, api_key: str):
        self.api_key = api_key

    def translate(self, text: str, source_lang: str, target_lang: str) -> TranslationResult:
        url = "https://translation.googleapis.com/language/translate/v2"
        params = {
            "q": text,
            "source": source_lang,
            "target": target_lang,
            "format": "text",
            "key": self.api_key,
        }

        data = urlencode(params).encode("utf-8")
        req = Request(url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})

        with urlopen(req) as resp:
            payload = resp.read().decode("utf-8")

        raw = json.loads(payload)
        translations = raw.get("data", {}).get("translations", [])
        if not translations:
            raise RuntimeError(f"No translations returned: {raw}")

        first = translations[0]
        translated_text = html.unescape(first.get("translatedText", ""))
        detected = first.get("detectedSourceLanguage")

        return TranslationResult(
            translated_text=translated_text,
            provider=self.name,
            detected_source=detected,
            raw=raw,
        )


def get_translator(provider: str, api_key: str) -> TranslationProvider:
    provider = (provider or "google").lower()
    if provider == "google":
        return GoogleTranslator(api_key=api_key)
    raise ValueError(f"Unknown translation provider: {provider}")
