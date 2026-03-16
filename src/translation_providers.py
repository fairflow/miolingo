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


class OpenAITranslator(TranslationProvider):
    name = "openai"

    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self.api_key = api_key
        self.model = model

    def translate(self, text: str, source_lang: str, target_lang: str) -> TranslationResult:
        from openai import OpenAI

        client = OpenAI(api_key=self.api_key)
        prompt = f"Translate this {source_lang} text to {target_lang}. Only return the translation, nothing else:\n\n{text}"

        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": f"You are a professional translator. Translate {source_lang} to {target_lang} accurately and naturally."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=200,
        )

        translation = response.choices[0].message.content.strip()

        return TranslationResult(
            translated_text=translation,
            provider=self.name,
            raw=response,
        )


def get_translator(provider: str, api_key: str) -> TranslationProvider:
    provider = (provider or "google").lower()
    if provider == "google":
        return GoogleTranslator(api_key=api_key)
    if provider == "openai":
        return OpenAITranslator(api_key=api_key)
    raise ValueError(f"Unknown translation provider: {provider}")
