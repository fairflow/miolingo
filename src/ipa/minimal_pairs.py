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

from difflib import SequenceMatcher
from typing import List, Tuple, Optional
import functools


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

    # Pre-filter: skip entries without phonemes
    valid_vocab = [v for v in vocab_list if v.get(phoneme_key)]

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
        phonemes1: First phoneme string (whitespace-separated)
        phonemes2: Second phoneme string (whitespace-separated)

    Returns:
        Description of the difference if it's a minimal pair, None otherwise.

    Examples:
        >>> _is_minimal_pair('k a z a', 'k a m a')
        'z→m at position 3'
        >>> _is_minimal_pair('k a z a', 'k a m')
        None  # Length differs by more than 1
    """
    # Split into phoneme tokens
    p1 = phonemes1.split()
    p2 = phonemes2.split()

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


def format_minimal_pair_for_practice(pair: Tuple[dict, dict, str]) -> dict:
    """
    Format a minimal pair for the practice interface.

    Args:
        pair: (word1_dict, word2_dict, difference_description) tuple

    Returns:
        Dictionary suitable for Quick Practice phrase list format:
        {
            'text': combined prompt,
            'translation': explanation,
            'ipa': combined IPA (if available),
            'pair': (word1_text, word2_text) for specialized scoring
        }
    """
    word1, word2, diff_desc = pair

    # Build practice prompt
    text = f"{word1['text']} vs {word2['text']}"

    # Build translation/explanation
    trans_parts = []
    if word1.get('translation'):
        trans_parts.append(f"{word1['text']} = {word1['translation']}")
    if word2.get('translation'):
        trans_parts.append(f"{word2['text']} = {word2['translation']}")
    trans_parts.append(f"Difference: {diff_desc}")
    translation = " · ".join(trans_parts)

    # Combine IPA if available
    ipa_parts = []
    if word1.get('ipa'):
        ipa_parts.append(word1['ipa'].strip('[]'))
    if word2.get('ipa'):
        ipa_parts.append(word2['ipa'].strip('[]'))
    ipa = f"[{' vs '.join(ipa_parts)}]" if ipa_parts else None

    return {
        'text': text,
        'translation': translation,
        'ipa': ipa,
        'pair': (word1['text'], word2['text']),
        'minimal_pair': True,  # Flag for specialized rendering
    }


def generate_minimal_pair_practice_list(vocab_list: List[dict], max_pairs: int = 20) -> List[dict]:
    """
    Generate a ready-to-use practice list from minimal pairs.

    This is the top-level function for Quick Practice integration.

    Args:
        vocab_list: User's vocabulary (each entry must have 'text' and 'phonemes')
        max_pairs: Maximum number of pairs to include

    Returns:
        List of dicts in Quick Practice phrase format
    """
    pairs = find_minimal_pairs(vocab_list, max_pairs=max_pairs)
    return [format_minimal_pair_for_practice(pair) for pair in pairs]
