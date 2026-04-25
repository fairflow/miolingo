"""
Minimal pairs extraction for pronunciation practice.

Minimal pairs are word pairs that differ by exactly one phoneme — the gold
standard for ear training in pronunciation pedagogy. This module finds them
automatically from the user's existing vocabulary.

Design (from docs/dev-docs/IPA_LEARNING_DESIGN.md § 4.3):
    1. Take the user's personal vocab for the current language.
    2. Compute eSpeak phoneme strings (cached via get_phonemes).
    3. Use difflib.SequenceMatcher to find pairs whose phoneme strings differ
       by exactly one symbol.
    4. Surface those pairs as an optional drill in Quick Practice.

The clever part: zero new data authoring — the user's own word list is the
curriculum.
"""

import random
import re
from difflib import SequenceMatcher
from typing import List, Tuple, Optional


def _tokenize_espeak_phonemes(phonemes: str) -> List[str]:
    """
    Split espeak phoneme string into individual phoneme tokens.
    
    Espeak phonemes are not space-separated. We need to tokenize them properly
    for minimal pair detection. This handles multi-character phonemes and
    special symbols.
    
    Args:
        phonemes: Espeak phoneme string (e.g. ",akoljed'or")
    
    Returns:
        List of phoneme tokens (e.g. [",", "a", "k", "o", "l", "j", "e", "d", "'", "o", "r"])
    
    Examples:
        >>> _tokenize_espeak_phonemes(",akoljed'or")
        [',', 'a', 'k', 'o', 'l', 'j', 'e', 'd', "'", 'o', 'r']
        >>> _tokenize_espeak_phonemes("tS'igUs")
        ['tS', "'", 'i', 'g', 'U', 's']
    """
    if not phonemes:
        return []
    
    tokens = []
    i = 0
    while i < len(phonemes):
        # Multi-character phonemes: tS, dZ, @-, etc.
        if i + 1 < len(phonemes):
            two_char = phonemes[i:i+2]
            if two_char in ('tS', 'dZ', 'dz', 'ts', '@-', '~N', '~n'):
                tokens.append(two_char)
                i += 2
                continue
        
        # Single character phoneme
        tokens.append(phonemes[i])
        i += 1
    
    return tokens


def _highlight_ipa_difference(ipa1: str, ipa2: str) -> Tuple[str, str]:
    """
    Highlight the differing phoneme in two IPA strings.
    
    Args:
        ipa1: First IPA string (stripped of brackets)
        ipa2: Second IPA string (stripped of brackets)
    
    Returns:
        Tuple of (highlighted_ipa1, highlighted_ipa2) with **bold** markers
        around the differing phoneme(s)
    
    Example:
        >>> _highlight_ipa_difference('ˌakoljedˈoɾ', 'ˌakoŋsˈeljæ')
        ('ˌak**o**ljedˈoɾ', 'ˌak**oŋ**sˈeljæ')
    """
    # Simple character-level diff to find where they diverge
    matcher = SequenceMatcher(None, ipa1, ipa2)
    opcodes = matcher.get_opcodes()
    
    highlighted1 = []
    highlighted2 = []
    
    for tag, i1, i2, j1, j2 in opcodes:
        if tag == 'equal':
            highlighted1.append(ipa1[i1:i2])
            highlighted2.append(ipa2[j1:j2])
        elif tag == 'replace':
            # Highlight the differing parts
            highlighted1.append(f"**{ipa1[i1:i2]}**")
            highlighted2.append(f"**{ipa2[j1:j2]}**")
        elif tag == 'delete':
            highlighted1.append(f"**{ipa1[i1:i2]}**")
        elif tag == 'insert':
            highlighted2.append(f"**{ipa2[j1:j2]}**")
    
    return ''.join(highlighted1), ''.join(highlighted2)


def find_minimal_pairs(
    vocab_list: List[dict],
    max_pairs: int = 50,
    phoneme_key: str = 'phonemes'
) -> List[Tuple[dict, dict, str]]:
    """
    Find minimal pairs (word pairs differing by exactly one phoneme).

    Args:
        vocab_list: List of vocabulary dictionaries. Each dict must have:
            - 'text': the word/phrase
            - phoneme_key: eSpeak phoneme string (defaults to 'phonemes')
        max_pairs: Maximum number of pairs to return
        phoneme_key: Key name for phoneme data in vocab dicts

    Returns:
        List of (word1_dict, word2_dict, difference_description) tuples.
        difference_description explains which phoneme differs.

    Example:
        >>> vocab = [
        ...     {'text': 'casa', 'phonemes': 'k a z a'},
        ...     {'text': 'cama', 'phonemes': 'k a m a'},
        ... ]
        >>> pairs = find_minimal_pairs(vocab)
        >>> pairs[0]
        ({'text': 'casa', ...}, {'text': 'cama', ...}, 'z→m at position 3')
    """
    pairs = []
    seen_pair_signatures = set()  # Avoid duplicates (A, B) and (B, A)

    # Pre-filter: skip entries without phonemes, and require a minimum number
    # of real phonemes (excluding stress/boundary markers ' , -) so that
    # single-vowel words like 'a', 'i', 'o' never form a pair.
    # 4 real phonemes ≈ 2 syllables (CV-CV), which Whisper can recognise.
    MIN_REAL_PHONEMES = 4
    PROSODIC = set("',- ")

    def _real_phoneme_count(phoneme_str: str) -> int:
        return sum(1 for t in _tokenize_espeak_phonemes(phoneme_str) if t not in PROSODIC)

    valid_vocab = [
        v for v in vocab_list
        if v.get(phoneme_key) and _real_phoneme_count(v[phoneme_key]) >= MIN_REAL_PHONEMES
    ]

    # Shuffle so each session surfaces a different random subset of pairs
    valid_vocab = list(valid_vocab)
    random.shuffle(valid_vocab)

    for i, word1 in enumerate(valid_vocab):
        if len(pairs) >= max_pairs:
            break

        phonemes1 = word1[phoneme_key].strip()
        if not phonemes1:
            continue

        for word2 in valid_vocab[i+1:]:
            phonemes2 = word2[phoneme_key].strip()
            if not phonemes2:
                continue

            # Create canonical signature (sorted tuple) to avoid duplicates
            sig = tuple(sorted([word1['text'], word2['text']]))
            if sig in seen_pair_signatures:
                continue

            diff_desc = _is_minimal_pair(phonemes1, phonemes2)
            if diff_desc:
                pairs.append((word1, word2, diff_desc))
                seen_pair_signatures.add(sig)

                if len(pairs) >= max_pairs:
                    break

    return pairs


def _is_minimal_pair(phonemes1: str, phonemes2: str) -> Optional[str]:
    """
    Check if two phoneme strings form a minimal pair (differ by exactly one phoneme).

    Args:
        phonemes1: First espeak phoneme string (e.g. ",akoljed'or")
        phonemes2: Second espeak phoneme string (e.g. ",akoljed'ur")

    Returns:
        Description of the difference if it's a minimal pair, None otherwise.

    Examples:
        >>> _is_minimal_pair(",akoljed'or", ",akoljed'ur")
        'o→u at position 9'
        >>> _is_minimal_pair(",akoljed'or", ",a'iNd&")
        None  # Length differs by more than 1
    """
    # Tokenize espeak phoneme strings into individual phonemes
    p1 = _tokenize_espeak_phonemes(phonemes1)
    p2 = _tokenize_espeak_phonemes(phonemes2)

    # Quick length check: must differ by at most 1 phoneme
    if abs(len(p1) - len(p2)) > 1:
        return None

    matcher = SequenceMatcher(None, p1, p2)
    opcodes = matcher.get_opcodes()

    # Count non-equal operations
    non_equal_ops = [op for op in opcodes if op[0] != 'equal']

    # Minimal pair: exactly one operation that's not 'equal'
    if len(non_equal_ops) != 1:
        return None

    tag, i1, i2, j1, j2 = non_equal_ops[0]

    # Ensure it's a single-phoneme difference
    if tag == 'replace':
        # Must be single phoneme → single phoneme
        if (i2 - i1) == 1 and (j2 - j1) == 1:
            old_phoneme = p1[i1]
            new_phoneme = p2[j1]
            position = i1 + 1  # 1-indexed for humans
            return f"{old_phoneme}→{new_phoneme} at position {position}"
    elif tag == 'insert':
        # One phoneme inserted
        if (j2 - j1) == 1:
            inserted = p2[j1]
            position = j1 + 1
            return f"inserted {inserted} at position {position}"
    elif tag == 'delete':
        # One phoneme deleted
        if (i2 - i1) == 1:
            deleted = p1[i1]
            position = i1 + 1
            return f"deleted {deleted} at position {position}"

    return None


def format_minimal_pair_for_practice(pair: Tuple[dict, dict, str], lang_code: str = 'pt') -> dict:
    """
    Format a minimal pair for the practice interface.

    Args:
        pair: (word1_dict, word2_dict, difference_description) tuple
        lang_code: Language code for selecting appropriate 'or' word

    Returns:
        Dictionary suitable for Quick Practice phrase list format:
        {
            'text': combined prompt (words separated by language-specific 'or'),
            'translation': explanation with actual phoneme difference,
            'ipa': combined IPA (if available),
            'pair': (word1_text, word2_text) for specialized scoring,
            'minimal_pair': True flag to signal special handling
        }
    """
    word1, word2, diff_desc = pair

    # Language-specific 'or' words for natural separation
    or_words = {
        'pt': 'ou',
        'fr': 'ou',
        'de': 'oder',
        'es': 'o',
        'it': 'o',
        'nl': 'of',
        'en': 'or',
    }
    separator = or_words.get(lang_code, 'ou')

    # Build practice prompt — use language-appropriate 'or' for natural pausing
    text = f"{word1['text']} {separator} {word2['text']}"

    # Build translation/explanation with highlighted IPA difference
    trans_parts = []
    if word1.get('translation'):
        trans_parts.append(f"{word1['text']} = {word1['translation']}")
    if word2.get('translation'):
        trans_parts.append(f"{word2['text']} = {word2['translation']}")
    
    # Use proper IPA with highlighting instead of espeak phonemes
    if word1.get('ipa') and word2.get('ipa'):
        ipa1_clean = word1['ipa'].strip('[]')
        ipa2_clean = word2['ipa'].strip('[]')
        ipa1_highlighted, ipa2_highlighted = _highlight_ipa_difference(ipa1_clean, ipa2_clean)
        trans_parts.append(f"🎯 Sound difference: [{ipa1_highlighted}] → [{ipa2_highlighted}]")
    else:
        # Fallback to espeak phoneme description if no IPA available
        phoneme_diff = diff_desc.split(' at position ')[0] if ' at position ' in diff_desc else diff_desc
        trans_parts.append(f"🎯 Sound difference: {phoneme_diff}")
    
    translation = " · ".join(trans_parts)

    # Combine IPA if available — no separator, just space between brackets
    ipa_parts = []
    if word1.get('ipa'):
        ipa_parts.append(word1['ipa'].strip('[]'))
    if word2.get('ipa'):
        ipa_parts.append(word2['ipa'].strip('[]'))
    ipa = f"[{ipa_parts[0]}] / [{ipa_parts[1]}]" if len(ipa_parts) == 2 else None

    return {
        'text': text,
        'translation': translation,
        'ipa': ipa,
        'pair': (word1['text'], word2['text']),
        'minimal_pair': True,
    }


def generate_minimal_pair_practice_list(vocab_list: List[dict], max_pairs: int = 20, lang_code: str = 'pt') -> List[dict]:
    """
    Generate a ready-to-use practice list from minimal pairs.

    This is the top-level function for Quick Practice integration.

    Args:
        vocab_list: User's vocabulary (each entry must have 'text' and 'phonemes')
        max_pairs: Maximum number of pairs to include
        lang_code: Language code for selecting appropriate 'or' word

    Returns:
        List of dicts in Quick Practice phrase format
    """
    pairs = find_minimal_pairs(vocab_list, max_pairs=max_pairs)
    return [format_minimal_pair_for_practice(pair, lang_code=lang_code) for pair in pairs]
