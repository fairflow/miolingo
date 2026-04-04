"""
Translation providers and material enrichment.

Extracted from app.py (Phase 1.2 of refactor).
"""

import os
from pathlib import Path
from typing import Dict, Optional

from config import get_language_code, get_language_for_provider
from scoring.phonemes import get_ipa_from_espeak


def get_translation_provider(secrets=None) -> str:
    """
    Get the configured translation provider name.

    Args:
        secrets: Streamlit secrets object (or dict-like). If None, checks
                 only environment variables.
    """
    provider = None
    if secrets:
        provider = secrets.get("translation_provider")
    return (
        provider
        or os.environ.get("TRANSLATION_PROVIDER")
        or "google"
    ).lower()


def validate_translation_api_key(provider: str, secrets=None) -> tuple:
    """
    Validate translation API key for the selected provider.

    Returns:
        (is_valid: bool, api_key_or_error: str)
    """
    provider = (provider or "google").lower()

    if provider == "google":
        api_key = None
        if secrets:
            api_key = secrets.get("google_cloud_translate_api_key")
        api_key = api_key or os.environ.get("GOOGLE_TRANSLATE_API_KEY")
        if not api_key or api_key == "your-google-translate-api-key-here":
            return False, ("Valid Google Translate API key required. "
                           "Configure google_cloud_translate_api_key in "
                           "secrets.toml or set GOOGLE_TRANSLATE_API_KEY.")
        return True, api_key

    if provider == "openai":
        api_key = None
        if secrets:
            api_key = secrets.get("openai_api_key")
        api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not api_key or api_key == "your-openai-api-key-here":
            return False, ("Valid OpenAI API key required. "
                           "Configure openai_api_key in secrets.toml "
                           "or set OPENAI_API_KEY.")
        return True, api_key

    return False, f"Unknown translation provider: {provider}"


def get_translation_from_llm(text: str, source_lang: str,
                             target_lang: str = "English",
                             secrets=None, db_module=None,
                             log_fn=None) -> str:
    """
    Get translation using a pluggable provider (default: Google Translate).

    Args:
        text:       Text to translate.
        source_lang: Source language name (e.g. "French").
        target_lang: Target language name (default "English").
        secrets:    Streamlit secrets object for API key lookup.
        db_module:  Database module for translation cache (get/set).
        log_fn:     Optional function(api_name, model, operation, ...) for cost logging.
    """
    try:
        provider = get_translation_provider(secrets)

        is_valid, api_key_or_error = validate_translation_api_key(provider, secrets)
        if not is_valid:
            return f"[error: {api_key_or_error}]"

        from translation_providers import get_translator

        source_lang_for_provider = get_language_for_provider(provider, source_lang)
        target_lang_for_provider = get_language_for_provider(provider, target_lang)

        # Cache lookup
        if db_module:
            cached = db_module.get_translation_cache(
                source_lang=source_lang_for_provider,
                target_lang=target_lang_for_provider,
                source_text=text,
                provider=provider,
            )
            if cached and cached.get("translated_text"):
                return cached["translated_text"]

        translator = get_translator(provider, api_key=api_key_or_error)
        result = translator.translate(text, source_lang_for_provider,
                                      target_lang_for_provider)

        # Cache store
        if db_module:
            db_module.set_translation_cache(
                source_lang=source_lang_for_provider,
                target_lang=target_lang_for_provider,
                source_text=text,
                translated_text=result.translated_text,
                provider=provider,
                detected_source=result.detected_source,
                confidence=result.confidence,
            )

        # Log API usage for cost tracking
        if log_fn:
            try:
                if provider == "openai" and getattr(result.raw, "usage", None):
                    log_fn(
                        api_name='openai',
                        model=getattr(result.raw, "model", "gpt-4o-mini"),
                        operation='translation',
                        input_tokens=result.raw.usage.prompt_tokens,
                        output_tokens=result.raw.usage.completion_tokens,
                        metadata={'source_lang': source_lang,
                                  'target_lang': target_lang}
                    )
                else:
                    log_fn(
                        api_name=provider,
                        model='google-translate',
                        operation='translation',
                        input_tokens=0,
                        output_tokens=0,
                        metadata={'source_lang': source_lang,
                                  'target_lang': target_lang}
                    )
            except Exception:
                pass

        return result.translated_text

    except Exception as e:
        return f"[error: {str(e)}]"


def enrich_material_file(
    file_path: Path,
    lang_code: str,
    add_translations: bool = True,
    add_ipa: bool = True,
    progress_callback=None,
    secrets=None,
    db_module=None,
    log_fn=None,
) -> Dict:
    """
    Enrich a material file by adding missing translations and/or IPA.

    Args:
        file_path:         Path to the material file.
        lang_code:         Language code (pt, fr, nl, etc.).
        add_translations:  Whether to add missing translations.
        add_ipa:           Whether to add missing IPA.
        progress_callback: Optional callback(current, total, message).
        secrets:           Streamlit secrets for API keys.
        db_module:         Database module for translation cache.
        log_fn:            API usage logging function.

    Returns:
        Dict with keys: success (bool), message (str), stats (dict)
    """
    provider = get_translation_provider(secrets)

    if add_translations:
        is_valid, error_message = validate_translation_api_key(provider, secrets)
        if not is_valid:
            return {
                'success': False,
                'message': error_message,
                'stats': {}
            }

    LANG_NAMES = {
        'pt': 'Portuguese',
        'fr': 'French',
        'nl': 'Dutch',
        'de': 'German',
        'it': 'Italian',
        'es': 'Spanish'
    }
    source_lang_name = LANG_NAMES.get(lang_code, lang_code.upper())

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except Exception as e:
        return {
            'success': False,
            'message': f'Could not read file: {e}',
            'stats': {}
        }

    # Create backup
    backup_path = file_path.with_suffix('.bak')
    try:
        with open(backup_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)
    except Exception as e:
        return {
            'success': False,
            'message': f'Could not create backup: {e}',
            'stats': {}
        }

    enriched_lines = []
    stats = {
        'total_lines': 0,
        'translations_added': 0,
        'ipa_added': 0,
        'errors': []
    }

    for i, line in enumerate(lines):
        if line.strip().startswith('#') or not line.strip():
            enriched_lines.append(line)
            continue

        normalized_line = line.strip()
        while normalized_line.endswith('|'):
            normalized_line = normalized_line[:-1].strip()

        if '|' in normalized_line:
            parts = [p.strip() for p in normalized_line.split('|')]
            phrase = parts[0] if len(parts) > 0 else ''
            translation_text = parts[1] if len(parts) > 1 else ''
            ipa = parts[2] if len(parts) > 2 else ''
        else:
            phrase = normalized_line
            translation_text = ''
            ipa = ''

        if not phrase:
            enriched_lines.append(line)
            continue

        stats['total_lines'] += 1

        if progress_callback:
            progress_callback(i + 1, len(lines), f"Processing: {phrase[:30]}...")

        if add_translations and not translation_text:
            if progress_callback:
                progress_callback(i + 1, len(lines),
                                  f"Translating: {phrase[:30]}...")

            new_translation = get_translation_from_llm(
                phrase, source_lang_name, secrets=secrets,
                db_module=db_module, log_fn=log_fn)

            if new_translation.startswith('[') and not new_translation.startswith('[error'):
                stats['errors'].append(
                    f"LLM returned IPA instead of translation for "
                    f"'{phrase}': {new_translation}")
            elif not new_translation.startswith('[error'):
                translation_text = new_translation
                stats['translations_added'] += 1
            else:
                stats['errors'].append(
                    f"Translation error for '{phrase}': {new_translation}")

        ipa_empty = not ipa or ipa in ['[ipa]', '[]']
        if add_ipa and ipa_empty:
            new_ipa = get_ipa_from_espeak(phrase, lang_code)
            if (not new_ipa.startswith('[error')
                    and not new_ipa.startswith('[timeout')
                    and new_ipa.strip()):
                ipa = f"[{new_ipa}]"
                stats['ipa_added'] += 1
            else:
                if new_ipa.strip():
                    stats['errors'].append(
                        f"IPA error for '{phrase}': {new_ipa}")
                else:
                    stats['errors'].append(f"IPA empty for '{phrase}'")

        enriched_line = f"{phrase} | {translation_text} | {ipa}\n"
        enriched_lines.append(enriched_line)

    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.writelines(enriched_lines)
    except Exception as e:
        try:
            with open(backup_path, 'r', encoding='utf-8') as f:
                backup_content = f.read()
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(backup_content)
        except Exception:
            pass
        return {
            'success': False,
            'message': f'Could not write enriched file: {e}',
            'stats': stats
        }

    return {
        'success': True,
        'message': 'File enriched successfully',
        'stats': stats
    }
