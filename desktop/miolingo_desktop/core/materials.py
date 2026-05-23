"""Language materials discovery and loading.

Ported from ``src/app_language_materials.py`` with ``@st.cache_data`` replaced
by ``functools.lru_cache`` (in-process). Logic is otherwise preserved so the
desktop app reads the exact same bundled ``language_materials/`` content.

The content directory is resolved by ``get_data_dir()``:
1. the ``MIOLINGO_MATERIALS_DIR`` environment variable, if set (packaging/M8
   points this at the bundled resources);
2. otherwise the repo-root ``language_materials/`` (dev mode), located by
   walking up from this file.
"""

from __future__ import annotations

import functools
import json
import os
from pathlib import Path

from .import_header import is_header_line

CACHE_VERSION = "1.10.1"


@functools.lru_cache(maxsize=1)
def get_data_dir() -> Path:
    """Resolve the bundled language-materials directory."""
    env = os.environ.get("MIOLINGO_MATERIALS_DIR")
    if env:
        return Path(env)
    # Walk up to the repo root (contains a top-level ``language_materials/``).
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "language_materials"
        if candidate.is_dir():
            return candidate
    # Fallback: repo-root guess two levels above desktop/.
    return here.parents[3] / "language_materials"


def _unified_dir() -> Path:
    return get_data_dir() / "unified"


@functools.lru_cache(maxsize=1)
def get_available_languages(_cache_version: str = CACHE_VERSION) -> list[str]:
    """Languages with materials, from per-language dirs plus unified files."""
    data_dir = get_data_dir()
    if not data_dir.exists():
        return []

    per_lang = {
        d.name
        for d in data_dir.iterdir()
        if d.is_dir() and not d.name.startswith(".") and d.name != "unified"
    }

    unified_langs: set[str] = set()
    unified = _unified_dir()
    for subdir_name in ("phrases", "phrasebook", "stories"):
        subdir = unified / subdir_name
        if subdir.is_dir():
            candidates = sorted(subdir.glob("*.json"))
            if candidates:
                try:
                    with open(candidates[0], encoding="utf-8") as f:
                        meta = json.load(f).get("meta", {})
                    unified_langs.update(meta.get("languages", []))
                    break
                except Exception:
                    pass

    return sorted(per_lang | unified_langs)


@functools.lru_cache(maxsize=64)
def get_language_structure(
    language: str, _cache_version: str = CACHE_VERSION
) -> dict[str, list[str]]:
    """Aggregate a language's files into ``phrases``/``words`` (+ unified cats)."""
    data_dir = get_data_dir()
    lang_dir = data_dir / language
    aggregated: dict[str, list[str]] = {"phrases": [], "words": []}
    excluded_dirs = {"phrases-original", "story-scenes"}

    iterdir = sorted(lang_dir.iterdir()) if lang_dir.exists() else []
    for category_dir in iterdir:
        if not category_dir.is_dir() or category_dir.name.startswith("."):
            continue
        if (
            category_dir.name in excluded_dirs
            or "-original" in category_dir.name
            or "backup" in category_dir.name
        ):
            continue

        txt_files = sorted(f.name for f in category_dir.glob("*.txt"))
        json_files = sorted(f.name for f in category_dir.glob("*.json"))
        files = txt_files + json_files
        if not files:
            continue

        if category_dir.name == "phrases" or category_dir.name.startswith("phrases-"):
            aggregated["phrases"].extend(files)
        elif category_dir.name == "words" or category_dir.name.startswith("words-"):
            aggregated["words"].extend(files)
        else:
            aggregated[category_dir.name] = files

    result = {k: v for k, v in aggregated.items() if v}

    unified_category_map = {
        "stories": "unified-stories",
        "phrases": "unified-phrases",
        "phrasebook": "unified-phrasebook",
    }
    unified = _unified_dir()
    for subdir, category_name in unified_category_map.items():
        unified_subdir = unified / subdir
        if unified_subdir.is_dir():
            files = sorted(f.name for f in unified_subdir.glob("*.json"))
            if files:
                try:
                    with open(unified_subdir / files[0], encoding="utf-8") as f:
                        meta = json.load(f).get("meta", {})
                    if language in meta.get("languages", []):
                        result[category_name] = files
                except Exception:
                    pass

    return result


def get_file_metadata(
    language: str, category: str, filename: str, source_language: str = "en"
) -> dict:
    """Return metadata (path, line_count, has_translations, has_ipa, preview)."""
    if category.startswith("unified-"):
        subdir = category.replace("unified-", "", 1)
        file_path = _unified_dir() / subdir / filename
    else:
        file_path = get_data_dir() / language / category / filename

    if not file_path.exists():
        return {}

    try:
        if file_path.suffix == ".json":
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)

            if isinstance(data, dict) and "meta" in data and "phrases" in data:
                meta = data["meta"]
                phrases = data["phrases"]
                preview = []
                for phrase in phrases[:3]:
                    text = phrase.get("text", {}).get(language, "")
                    if not text:
                        continue
                    trans = phrase.get("text", {}).get(source_language) or phrase.get(
                        "text", {}
                    ).get("en", "")
                    if trans == text:
                        trans = ""
                    ipa = phrase.get("ipa", {}).get(language, "")
                    if trans and ipa:
                        preview.append(f"{text} | {trans} | {ipa}")
                    elif trans:
                        preview.append(f"{text} | {trans}")
                    else:
                        preview.append(text)
                return {
                    "path": file_path,
                    "line_count": meta.get("phrase_count", len(phrases)),
                    "has_translations": True,
                    "has_ipa": any(p.get("ipa", {}).get(language) for p in phrases[:5]),
                    "preview": preview,
                }

            if isinstance(data, dict):
                lang_keys = [k for k in data if k not in ("scene_number", "scene_title")]
                if not lang_keys:
                    return _empty_meta(file_path)
                lang_key = lang_keys[0]
                phrases = data[lang_key]
                preview = []
                for phrase in phrases[:3]:
                    text = phrase.get(lang_key, "")
                    translation = phrase.get("english", "")
                    ipa = phrase.get("ipa", "")
                    if translation and ipa:
                        preview.append(f"{text} | {translation} | {ipa}")
                    elif translation:
                        preview.append(f"{text} | {translation}")
                    else:
                        preview.append(text)
                return {
                    "path": file_path,
                    "line_count": len(phrases),
                    "has_translations": bool(phrases and phrases[0].get("english")),
                    "has_ipa": bool(phrases and phrases[0].get("ipa")),
                    "preview": preview,
                }
            return _empty_meta(file_path)

        with open(file_path, encoding="utf-8") as f:
            all_lines = f.readlines()

        content_lines = [
            s
            for line in all_lines
            if (s := line.strip())
            and not s.startswith("#")
            and not is_header_line(line)
        ]
        if not content_lines:
            return _empty_meta(file_path)

        sample = content_lines[0]
        return {
            "path": file_path,
            "line_count": len(content_lines),
            "has_translations": "|" in sample,
            "has_ipa": "[" in sample and "]" in sample,
            "preview": content_lines[:3],
        }
    except Exception as e:  # noqa: BLE001 - mirror source's broad guard
        meta = _empty_meta(file_path)
        meta["error"] = str(e)
        return meta


def _empty_meta(file_path: Path) -> dict:
    return {
        "path": file_path,
        "line_count": 0,
        "has_translations": False,
        "has_ipa": False,
        "preview": [],
    }


@functools.lru_cache(maxsize=128)
def load_unified_phrase_file(
    file_path_str: str, target_lang: str, source_lang: str
) -> tuple[dict, ...]:
    """Load a unified multi-language JSON file, projecting one language pair.

    Returns a tuple (hashable, so it's lru_cache-friendly) of
    ``{text, translation, ipa}`` dicts. Callers can ``list(...)`` it.
    """
    with open(file_path_str, encoding="utf-8") as f:
        doc = json.load(f)

    phrases: list[dict] = []
    for entry in doc.get("phrases", []):
        target_text = entry.get("text", {}).get(target_lang)
        if not target_text:
            continue
        source_text = entry.get("text", {}).get(source_lang) or entry.get("text", {}).get(
            "en", ""
        )
        ipa_text = entry.get("ipa", {}).get(target_lang, "")
        phrases.append(
            {"text": target_text, "translation": source_text, "ipa": ipa_text or None}
        )
    return tuple(phrases)


def load_phrase_file(file_path_str: str) -> list[dict]:
    """Load and parse a phrase/word file (TXT or JSON) within the data dir."""
    file_path = Path(file_path_str)

    try:
        file_path_resolved = file_path.resolve()
        data_dir_resolved = get_data_dir().resolve()
        if not file_path_resolved.is_relative_to(data_dir_resolved):
            raise ValueError("Invalid file path: outside language materials directory")
    except Exception as e:
        raise ValueError(f"Invalid file path: {e}") from e

    unified_resolved = _unified_dir().resolve()
    if str(file_path_resolved).startswith(str(unified_resolved)):
        raise ValueError(
            "Unified files must be loaded via load_unified_phrase_file() with "
            "explicit target/source language parameters"
        )

    if file_path.suffix == ".json":
        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)

        lang_code = None
        phrases_data = None
        for key in ("fr", "pt", "es", "de", "nl", "it"):
            if key in data and isinstance(data[key], list):
                lang_code = key
                phrases_data = data[key]
                break
        if phrases_data is None:
            if isinstance(data, list):
                phrases_data = data
            else:
                raise ValueError("Could not find phrase list in JSON file")

        phrases = []
        for item in phrases_data:
            text = item.get(lang_code) if lang_code else item.get("french", item.get("text", ""))
            phrases.append(
                {
                    "text": text,
                    "translation": item.get("english", item.get("translation")),
                    "ipa": item.get("ipa"),
                }
            )
        return phrases

    with open(file_path, encoding="utf-8") as f:
        content = f.read()

    phrases = []
    for raw in content.split("\n"):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#") or is_header_line(stripped):
            continue
        line = stripped
        if "|" in line:
            parts = [p.strip() for p in line.split("|")]
            phrases.append(
                {
                    "text": parts[0],
                    "translation": parts[1] if len(parts) > 1 else None,
                    "ipa": parts[2] if len(parts) > 2 else None,
                }
            )
        else:
            phrases.append({"text": line, "translation": None, "ipa": None})
    return phrases


def format_language_name(lang_code: str) -> str:
    """Format a language code for display (kept pure; no emoji-free requirement)."""
    language_map = {
        "en": "English",
        "fr": "French",
        "pt": "Portuguese",
        "nl": "Dutch",
        "de": "German",
        "it": "Italian",
        "es": "Spanish",
    }
    return language_map.get(lang_code, lang_code.upper())
