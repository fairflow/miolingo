#!/usr/bin/env python3
"""
Enrich material files by adding translations and IPA transcriptions.

This script:
1. Reads material files from a specified directory.
2. Adds missing translations using a language model.
3. Adds missing IPA transcriptions using eSpeak.
4. Saves the enriched files and logs statistics.

Usage:
    python3 enrich_materials.py --input-dir /path/to/materials --lang pt
"""

import os
import re
import json
import argparse
import subprocess
from pathlib import Path
from typing import Dict

# ============================================================================
# ESPEAK CONFIGURATION
# ============================================================================

def get_espeak_path():
    """
    Get espeak path (local build or system-wide)
    
    Platform differences:
    - macOS (MacPorts): Binary is "espeak" at /opt/local/bin/espeak
    - Debian/Ubuntu (Streamlit Cloud): Binary is "espeak-ng" from espeak-ng package
    """
    # Try macOS MacPorts path first
    local_path = "/opt/local/bin/espeak"
    if Path(local_path).exists():
        return local_path
    
    # Try espeak-ng (Streamlit Cloud / Ubuntu)
    try:
        subprocess.run(["espeak-ng", "--version"], capture_output=True, check=True)
        return "espeak-ng"
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    
    # Fallback to espeak (if available)
    return "espeak"


def get_ipa_from_espeak(text: str, lang_code: str) -> str:
    """
    Generate IPA transcription using espeak-ng.
    
    Args:
        text: Text to transcribe
        lang_code: Language code (pt, fr, nl, de, it, es)
    
    Returns:
        IPA transcription or '[error]' on failure
    """
    # Map language codes to espeak voices
    ESPEAK_LANG_MAP = {
        'pt': 'pt-br',
        'fr': 'fr-fr',
        'nl': 'nl',
        'de': 'de',
        'it': 'it',
        'es': 'es'
    }
    
    espeak_lang = ESPEAK_LANG_MAP.get(lang_code, lang_code)
    espeak_cmd = get_espeak_path()
    
    try:
        result = subprocess.run(
            [espeak_cmd, '-v', espeak_lang, '-q', '--ipa', text],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            ipa = result.stdout.strip()
            # Clean up spacing
            ipa = ' '.join(ipa.split())
            return ipa
        return '[error]'
    except subprocess.TimeoutExpired:
        return '[timeout]'
    except Exception as e:
        return f'[error: {str(e)}]'


# ============================================================================
# TRANSLATION CONFIGURATION
# ============================================================================

def get_openai_api_key() -> str:
    """
    Get OpenAI API key from environment or secrets file.
    
    Returns:
        API key or None if not found
    """
    # Try environment variable first
    api_key = os.environ.get("OPENAI_API_KEY")
    if api_key:
        return api_key
    
    # Try secrets.toml file (for Streamlit compatibility)
    secrets_path = Path(__file__).parent.parent.parent / '.streamlit' / 'secrets.toml'
    if secrets_path.exists():
        try:
            import toml
            secrets = toml.load(secrets_path)
            api_key = secrets.get("openai_api_key")
            if api_key and api_key != "your-openai-api-key-here":
                return api_key
        except Exception as e:
            print(f"⚠️ Warning: Could not load secrets.toml: {e}")
    
    return None


def get_translation_from_llm(text: str, source_lang: str, target_lang: str = "English") -> str:
    """
    Get translation using OpenAI API.
    
    Args:
        text: Text to translate
        source_lang: Source language name (e.g., "Portuguese", "French")
        target_lang: Target language (default: "English")
    
    Returns:
        Translation or error message
    """
    try:
        # Validate API key
        api_key = get_openai_api_key()
        if not api_key:
            return "[error: Valid OpenAI API key required for translations. Set OPENAI_API_KEY env var or configure in .streamlit/secrets.toml]"
        
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        
        # Simple, direct prompt for translation
        prompt = f"Translate this {source_lang} text to {target_lang}. Only return the translation, nothing else:\n\n{text}"
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Cost-effective model
            messages=[
                {"role": "system", "content": f"You are a professional translator. Translate {source_lang} to {target_lang} accurately and naturally."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,  # Low temperature for consistent translations
            max_tokens=200
        )
        
        translation = response.choices[0].message.content.strip()
        return translation
        
    except Exception as e:
        return f"[error: {str(e)}]"

def enrich_material_file(file_path: Path, lang_code: str) -> Dict:
    """Enrich a material file by adding translations and IPA."""
    LANG_NAMES = {
        'pt': 'Portuguese',
        'fr': 'French',
        'nl': 'Dutch',
        'de': 'German',
        'it': 'Italian',
        'es': 'Spanish'
    }
    source_lang_name = LANG_NAMES.get(lang_code, lang_code.upper())

    # Read file
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

    # Process lines
    enriched_lines = []
    stats = {
        'total_lines': 0,
        'translations_added': 0,
        'ipa_added': 0,
        'errors': []
    }

    for line in lines:
        # Skip comments and empty lines
        if line.strip().startswith('#') or not line.strip():
            enriched_lines.append(line)
            continue

        # Normalize: strip trailing pipes and whitespace
        normalized_line = line.strip()
        while normalized_line.endswith('|'):
            normalized_line = normalized_line[:-1].strip()

        # Parse the line by splitting on pipes
        if '|' in normalized_line:
            parts = [p.strip() for p in normalized_line.split('|')]
            phrase = parts[0] if len(parts) > 0 else ''
            translation = parts[1] if len(parts) > 1 else ''
            ipa = parts[2] if len(parts) > 2 else ''
        else:
            # Plain text format (no pipes) - treat entire line as phrase
            phrase = normalized_line
            translation = ''
            ipa = ''

        # Skip if no phrase
        if not phrase:
            enriched_lines.append(line)
            continue

        stats['total_lines'] += 1

        # Add translation if missing
        if not translation:
            new_translation = get_translation_from_llm(phrase, source_lang_name, "English")
            # Check if LLM returned IPA instead of translation
            if new_translation.startswith('[') and not new_translation.startswith('[error'):
                stats['errors'].append(f"LLM returned IPA instead of translation for '{phrase}': {new_translation}")
            elif not new_translation.startswith('[error'):
                translation = new_translation
                stats['translations_added'] += 1
            else:
                stats['errors'].append(f"Translation error for '{phrase}': {new_translation}")

        # Add IPA if missing
        # Consider IPA missing if empty or just placeholder markers
        ipa_empty = not ipa or ipa in ['[ipa]', '[]']
        if ipa_empty:
            new_ipa = get_ipa_from_espeak(phrase, lang_code)
            if not new_ipa.startswith('[error') and not new_ipa.startswith('[timeout') and new_ipa.strip():
                ipa = f"[{new_ipa}]"  # Wrap in brackets
                stats['ipa_added'] += 1
            else:
                if new_ipa.strip():
                    stats['errors'].append(f"IPA error for '{phrase}': {new_ipa}")
                else:
                    stats['errors'].append(f"IPA empty for '{phrase}'")

        # Reconstruct line with consistent format: always 3 fields
        enriched_line = f"{phrase} | {translation} | {ipa}\n"
        enriched_lines.append(enriched_line)

    # Write enriched content
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.writelines(enriched_lines)
    except Exception as e:
        # Restore from backup
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

def main():
    parser = argparse.ArgumentParser(
        description="Enrich material files by adding translations and IPA.",
        epilog="""
Examples:
  # Enrich Portuguese materials
  python3 enrich_materials.py --input-dir language_materials/pt --lang pt
  
  # Enrich French materials
  python3 enrich_materials.py --input-dir language_materials/fr --lang fr

Note: Set OPENAI_API_KEY environment variable for translations.
        """
    )
    parser.add_argument("--input-dir", required=True, help="Directory containing material files.")
    parser.add_argument("--lang", required=True, help="Language code (e.g., 'pt', 'fr').")
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    if not input_dir.exists():
        print(f"❌ Input directory does not exist: {input_dir}")
        return

    # Check for OpenAI API key
    api_key = get_openai_api_key()
    if not api_key:
        print("⚠️  Warning: No OpenAI API key found. Translations will not work.")
        print("   Set OPENAI_API_KEY environment variable or configure in .streamlit/secrets.toml")
    else:
        print(f"✅ OpenAI API key found")
    
    # Check for espeak
    espeak_cmd = get_espeak_path()
    print(f"🔧 Using eSpeak: {espeak_cmd}")
    
    print()
    
    # Process all .txt files
    total_files = 0
    total_translations = 0
    total_ipa = 0
    total_errors = 0
    
    for file_path in sorted(input_dir.glob("*.txt")):
        print(f"📄 Processing {file_path.name}...")
        result = enrich_material_file(file_path, args.lang)
        
        if result['success']:
            stats = result['stats']
            total_files += 1
            total_translations += stats.get('translations_added', 0)
            total_ipa += stats.get('ipa_added', 0)
            total_errors += len(stats.get('errors', []))
            
            print(f"   ✅ Lines: {stats.get('total_lines', 0)}, "
                  f"Translations: +{stats.get('translations_added', 0)}, "
                  f"IPA: +{stats.get('ipa_added', 0)}, "
                  f"Errors: {len(stats.get('errors', []))}")
            
            # Show first few errors
            if stats.get('errors'):
                for error in stats['errors'][:3]:
                    print(f"      ⚠️  {error}")
                if len(stats['errors']) > 3:
                    print(f"      ... and {len(stats['errors']) - 3} more errors")
        else:
            print(f"   ❌ Failed: {result['message']}")
        print()
    
    # Summary
    print("=" * 70)
    print(f"✅ Summary:")
    print(f"   Files processed: {total_files}")
    print(f"   Translations added: {total_translations}")
    print(f"   IPA added: {total_ipa}")
    print(f"   Total errors: {total_errors}")
    print(f"   💾 Original files backed up with .bak extension")
    print("=" * 70)

if __name__ == "__main__":
    main()