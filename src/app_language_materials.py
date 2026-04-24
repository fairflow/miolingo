"""
Language materials discovery and loading.

This module provides functionality to browse and load built-in language
learning materials (phrases and words) organized by language and difficulty level.
"""

from pathlib import Path
from typing import Dict, List
import streamlit as st
import json

from import_header import is_header_line

DATA_DIR = Path(__file__).parent.parent / "language_materials"
UNIFIED_DIR = DATA_DIR / "unified"

# Cache version - increment when language list or structure changes
CACHE_VERSION = "1.10.1"


@st.cache_data
def get_available_languages(_cache_version: str = CACHE_VERSION) -> List[str]:
    """Get list of languages with available materials.

    Includes languages from per-language directories AND languages declared
    in unified multi-language files (e.g. 'en', which has no separate
    directory but is fully present in language_materials/unified/).

    Args:
        _cache_version: Version string to bust cache (leading underscore
            prevents Streamlit from using it as a cache key argument)

    Returns:
        Sorted list of language codes (e.g., ['de', 'en', 'fr', 'pt', ...])
    """
    if not DATA_DIR.exists():
        return []

    per_lang = {
        d.name for d in DATA_DIR.iterdir()
        if d.is_dir() and not d.name.startswith('.') and d.name != 'unified'
    }

    # Also surface languages that only exist in unified files (e.g. 'en')
    unified_langs: set = set()
    for subdir_name in ('phrases', 'phrasebook', 'stories'):
        subdir = UNIFIED_DIR / subdir_name
        if subdir.is_dir():
            candidates = sorted(subdir.glob("*.json"))
            if candidates:
                try:
                    with open(candidates[0], 'r', encoding='utf-8') as f:
                        meta = json.load(f).get('meta', {})
                    unified_langs.update(meta.get('languages', []))
                    break  # one file is sufficient
                except Exception:
                    pass

    return sorted(per_lang | unified_langs)


@st.cache_data
def get_language_structure(language: str, _cache_version: str = CACHE_VERSION) -> Dict[str, List[str]]:
    """Get complete directory structure for a language.
    
    Aggregates phrases-A/B/C/D into 'phrases' and words-A/B/C/D into 'words'.
    Story scenes remain separate.
    
    Args:
        language: Language code (e.g., 'fr', 'pt')
        _cache_version: Version string to bust cache (leading underscore prevents it from being used)
    
    Returns:
        Dictionary mapping category names to lists of filenames:
        {
            'phrases': ['phr-01.txt', 'phr-02.txt', ...],  # aggregated from phrases-A/B/C/D
            'words': ['words-01.txt', ...],                 # aggregated from words-A/B/C/D
            'story-scenes-json': ['scene-01.json', ...]
        }
    """
    lang_dir = DATA_DIR / language

    # Aggregated structure
    aggregated = {
        'phrases': [],
        'words': [],
    }

    # Directories to exclude from category discovery (backup/deprecated)
    excluded_dirs = {'phrases-original', 'story-scenes'}

    # Scan per-language subdirectory (may not exist for unified-only languages like 'en')
    for category_dir in sorted(lang_dir.iterdir()) if lang_dir.exists() else []:
        if not category_dir.is_dir() or category_dir.name.startswith('.'):
            continue
        
        # Skip excluded directories
        if category_dir.name in excluded_dirs or '-original' in category_dir.name or 'backup' in category_dir.name:
            continue
        
        # Collect files
        txt_files = sorted([f.name for f in category_dir.glob("*.txt")])
        json_files = sorted([f.name for f in category_dir.glob("*.json")])
        files = txt_files + json_files
        
        if not files:
            continue
        
        # Handle different directory types
        if category_dir.name == 'phrases':
            # Direct phrases directory (new consolidated structure)
            aggregated['phrases'].extend(files)
        elif category_dir.name == 'words':
            # Direct words directory (new consolidated structure)
            aggregated['words'].extend(files)
        elif category_dir.name.startswith('phrases-'):
            # Legacy phrases-A/B/C/D structure
            aggregated['phrases'].extend(files)
        elif category_dir.name.startswith('words-'):
            # Legacy words-A/B/C/D structure
            aggregated['words'].extend(files)
        else:
            # Keep other categories as-is (story-scenes-json, etc.)
            aggregated[category_dir.name] = files
    
    # Remove empty aggregated categories
    result = {k: v for k, v in aggregated.items() if v}

    # Inject unified multi-language categories (preferred over per-language files)
    unified_category_map = {
        'stories': 'unified-stories',
        'phrases': 'unified-phrases',
        'phrasebook': 'unified-phrasebook',
    }
    for subdir, category_name in unified_category_map.items():
        unified_subdir = UNIFIED_DIR / subdir
        if unified_subdir.is_dir():
            files = sorted([f.name for f in unified_subdir.glob("*.json")])
            if files:
                # Only include if target language has data in these files
                # (check first file's meta.languages)
                try:
                    sample = unified_subdir / files[0]
                    with open(sample, 'r', encoding='utf-8') as f:
                        meta = json.load(f).get('meta', {})
                    if language in meta.get('languages', []):
                        result[category_name] = files
                except Exception:
                    pass  # Skip if file can't be read

    return result


@st.cache_data
def get_file_metadata(language: str, category: str, filename: str,
                      source_language: str = "en") -> Dict:
    """Get metadata about a phrase/word file.
    
    For aggregated categories ('phrases', 'words'), searches across all level subdirectories
    (phrases-A/B/C/D, words-A/B/C/D) to find the file.
    
    Args:
        language: Language code (e.g., 'fr', 'pt')
        category: Category name (e.g., 'phrases', 'words', 'story-scenes-json')
        filename: File name (e.g., 'phr-01.txt')
    
    Returns:
        Dictionary with file metadata:
        {
            'path': Path object,
            'line_count': 50,
            'has_translations': True,
            'has_ipa': True,
            'preview': ['first', 'few', 'lines']
        }
    """
    # Handle unified categories (e.g., 'unified-stories' → UNIFIED_DIR/stories/)
    if category.startswith('unified-'):
        subdir = category.replace('unified-', '', 1)
        file_path = UNIFIED_DIR / subdir / filename
    else:
        lang_dir = DATA_DIR / language
        file_path = lang_dir / category / filename

    if not file_path.exists():
        return {}
    
    try:
        # Handle JSON files (story scenes) - extract actual phrases, not JSON structure
        if file_path.suffix == '.json':
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Unified format: {"meta": {...}, "phrases": [{text: {lang: ...}, ...}]}
            if isinstance(data, dict) and 'meta' in data and 'phrases' in data:
                meta = data['meta']
                phrases = data['phrases']
                # Project preview using target (language) and source
                source_code = source_language
                preview = []
                for phrase in phrases[:3]:
                    text = phrase.get('text', {}).get(language, '')
                    if not text:
                        continue
                    # Translation: use source lang, fall back to English
                    trans = (phrase.get('text', {}).get(source_code)
                             or phrase.get('text', {}).get('en', ''))
                    # Avoid showing identical text and translation
                    if trans == text:
                        trans = ''
                    ipa = phrase.get('ipa', {}).get(language, '')
                    if trans and ipa:
                        preview.append(f"{text} | {trans} | {ipa}")
                    elif trans:
                        preview.append(f"{text} | {trans}")
                    else:
                        preview.append(text)
                return {
                    'path': file_path,
                    'line_count': meta.get('phrase_count', len(phrases)),
                    'has_translations': True,
                    'has_ipa': any(p.get('ipa', {}).get(language) for p in phrases[:5]),
                    'preview': preview,
                }

            # Legacy Format 2: {"lang": [...], "scene_number": 1, "scene_title": "..."}
            if isinstance(data, dict):
                # Get language key (pt, fr, de, etc.)
                lang_keys = [k for k in data.keys() if k not in ['scene_number', 'scene_title']]
                if not lang_keys:
                    return {
                        'path': file_path,
                        'line_count': 0,
                        'has_translations': False,
                        'has_ipa': False,
                        'preview': []
                    }
                
                lang_key = lang_keys[0]
                phrases = data[lang_key]
                
                # Extract preview (first 3 phrases as text)
                preview = []
                for phrase in phrases[:3]:
                    text = phrase.get(lang_key, '')
                    translation = phrase.get('english', '')
                    ipa = phrase.get('ipa', '')
                    
                    # Format like text files: text | translation | ipa
                    if translation and ipa:
                        preview.append(f"{text} | {translation} | {ipa}")
                    elif translation:
                        preview.append(f"{text} | {translation}")
                    else:
                        preview.append(text)
                
                return {
                    'path': file_path,
                    'line_count': len(phrases),
                    'has_translations': bool(phrases and phrases[0].get('english')),
                    'has_ipa': bool(phrases and phrases[0].get('ipa')),
                    'preview': preview
                }
            else:
                # Unknown JSON format
                return {
                    'path': file_path,
                    'line_count': 0,
                    'has_translations': False,
                    'has_ipa': False,
                    'preview': []
                }
        
        # Handle text files
        with open(file_path, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()
        
        # Filter out comments, empty lines, and the (source, target)
        # language-pair header line for analysis. The header is not a
        # data row — leaving it in inflates line_count by 1 and makes
        # `sample = content_lines[0]` inspect the header instead of a
        # real entry, breaking has_translations / has_ipa detection.
        content_lines = [
            s for line in all_lines
            if (s := line.strip())
            and not s.startswith('#')
            and not is_header_line(line)
        ]
        
        if not content_lines:
            return {
                'path': file_path,
                'line_count': 0,
                'has_translations': False,
                'has_ipa': False,
                'preview': []
            }
        
        # Analyze format from first content line
        sample = content_lines[0]
        has_translations = '|' in sample
        has_ipa = '[' in sample and ']' in sample
        
        # Get preview (first 3 content lines)
        preview = content_lines[:3]
        
        return {
            'path': file_path,
            'line_count': len(content_lines),
            'has_translations': has_translations,
            'has_ipa': has_ipa,
            'preview': preview
        }
    except Exception as e:
        return {
            'path': file_path,
            'line_count': 0,
            'has_translations': False,
            'has_ipa': False,
            'preview': [],
            'error': str(e)
        }


@st.cache_data
def load_unified_phrase_file(file_path_str: str, target_lang: str, source_lang: str) -> List[Dict]:
    """Load a unified multi-language JSON file, projecting a specific language pair.

    Args:
        file_path_str: Path to unified JSON file
        target_lang: Target language code (e.g. 'fr') — becomes 'text'
        source_lang: Source language code (e.g. 'de') — becomes 'translation'

    Returns:
        Same [{text, translation, ipa}] shape as load_phrase_file()
    """
    with open(file_path_str, 'r', encoding='utf-8') as f:
        doc = json.load(f)

    phrases = []
    for entry in doc.get('phrases', []):
        target_text = entry.get('text', {}).get(target_lang)
        if not target_text:
            continue  # Skip phrases missing the target language
        source_text = entry.get('text', {}).get(source_lang) or entry.get('text', {}).get('en', '')
        ipa_text = entry.get('ipa', {}).get(target_lang, '')
        phrases.append({
            'text': target_text,
            'translation': source_text,
            'ipa': ipa_text or None,
        })
    return phrases


@st.cache_data
def load_phrase_file(file_path_str: str) -> List[Dict]:
    """Load and parse a phrase/word file (TXT or JSON).

    Args:
        file_path_str: String representation of file path (for caching)

    Returns:
        List of phrase dictionaries:
        [
            {'text': 'bonjour', 'translation': 'hello', 'ipa': '[bɔ̃ʒuʁ]'},
            ...
        ]
    """
    file_path = Path(file_path_str)

    # Security: Ensure path is within DATA_DIR
    try:
        file_path_resolved = file_path.resolve()
        data_dir_resolved = DATA_DIR.resolve()

        if not file_path_resolved.is_relative_to(data_dir_resolved):
            raise ValueError("Invalid file path: outside language materials directory")
    except Exception as e:
        raise ValueError(f"Invalid file path: {e}")

    # Unified files should be loaded via load_unified_phrase_file() directly,
    # which is cached by (path, target_lang, source_lang). Do not load them
    # through this function as it only caches by path.
    unified_resolved = UNIFIED_DIR.resolve()
    if str(file_path_resolved).startswith(str(unified_resolved)):
        raise ValueError(
            "Unified files must be loaded via load_unified_phrase_file() "
            "with explicit target/source language parameters"
        )

    # Handle JSON files (story scenes)
    if file_path.suffix == '.json':
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Determine language code from file path or data
        # Story scenes have structure: {"es": [...], "scene_number": N, "scene_title": "..."}
        lang_code = None
        phrases_data = None
        
        # Try to find the language-specific phrase list
        for key in ['fr', 'pt', 'es', 'de', 'nl', 'it']:
            if key in data and isinstance(data[key], list):
                lang_code = key
                phrases_data = data[key]
                break
        
        # Fallback: if data is already a list, use it directly
        if phrases_data is None:
            if isinstance(data, list):
                phrases_data = data
            else:
                raise ValueError("Could not find phrase list in JSON file")
        
        # Convert JSON format to phrase dict format
        phrases = []
        for item in phrases_data:
            # Handle both old format (french/english) and new format (lang_code/english)
            text = item.get(lang_code) if lang_code else item.get('french', item.get('text', ''))
            phrases.append({
                'text': text,
                'translation': item.get('english', item.get('translation')),
                'ipa': item.get('ipa')
            })
        return phrases
    
    # Handle TXT files (original format)
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    phrases = []
    for line in content.split('\n'):
        line = line.strip()
        
        # Skip comments and empty lines
        if not line or line.startswith('#'):
            continue
        
        # Parse format: "phrase | translation | [ipa]"
        if '|' in line:
            parts = [p.strip() for p in line.split('|')]
            phrases.append({
                'text': parts[0],
                'translation': parts[1] if len(parts) > 1 else None,
                'ipa': parts[2] if len(parts) > 2 else None
            })
        else:
            # Simple format: just the text
            phrases.append({
                'text': line,
                'translation': None,
                'ipa': None
            })
    
    return phrases


def format_category_name(category: str) -> str:
    """Format category name for display.
    
    Args:
        category: Raw category name (e.g., 'words', 'phrases', 'story-scenes-json')
    
    Returns:
        Formatted display name with emoji (e.g., '📚 Words', '📖 Story Scenes')
    """
    category_map = {
        'words': '📚 Words',
        'phrases': '📝 Phrases',
        'story-scenes-json': '📖 Story Scenes (Sophie & Lucas)',
        # Legacy support for old structure (in case some languages haven't been migrated)
        'phrases-A': '📝 Phrases - Level A (Beginner)',
        'phrases-B': '📝 Phrases - Level B (Intermediate)',
        'phrases-C': '📝 Phrases - Level C (Advanced)',
        'phrases-D': '📝 Phrases - Level D (Expert)',
        'words-A': '📖 Words - Level A (Beginner)',
        'words-B': '📖 Words - Level B (Intermediate)',
        'words-C': '📖 Words - Level C (Advanced)',
        'words-D': '📖 Words - Level D (Expert)',
        'phrasebook-topics': '💬 Phrasebook by Topic',
        'unified-stories': '📖 Story Scenes (All Languages)',
        'unified-phrases': '📝 Phrases (All Languages)',
        'unified-phrasebook': '💬 Phrasebook (All Languages)',
    }
    
    return category_map.get(category, category)


def format_language_name(lang_code: str) -> str:
    """Format language code for display.
    
    Args:
        lang_code: Language code (e.g., 'fr', 'pt')
    
    Returns:
        Formatted display name with flag (e.g., '🇫🇷 French')
    """
    language_map = {
        'en': '🇬🇧 English',
        'fr': '🇫🇷 French',
        'pt': '🇵🇹 Portuguese',
        'nl': '🇳🇱 Dutch',
        'de': '🇩🇪 German',
        'it': '🇮🇹 Italian',
        'es': '🇪🇸 Spanish',
    }
    
    return language_map.get(lang_code, lang_code.upper())
