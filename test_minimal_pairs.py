#!/usr/bin/env python3
"""
Quick test script for minimal pairs logic.

Run from the worktree root:
    cd /Users/matthew/Software/working/miolingo/.claude/worktrees/ipa-integration-1777111546
    python3 test_minimal_pairs.py
"""

import sys
sys.path.insert(0, 'src')

from ipa.minimal_pairs import (
    find_minimal_pairs,
    _is_minimal_pair,
    format_minimal_pair_for_practice,
    generate_minimal_pair_practice_list
)

print("=" * 60)
print("Minimal Pairs Logic — Unit Tests")
print("=" * 60)

# Test 1: Basic minimal pair detection
print("\n[Test 1] Basic minimal pair detection")
print("-" * 60)

test_cases = [
    ("k a z a", "k a m a", "z→m at position 3"),  # casa vs cama
    ("k a z a", "k a z a s", "inserted s at position 5"),  # casa vs casas
    ("b o", "b o m", "inserted m at position 3"),  # bom (short form)
    ("k a z a", "b o m", None),  # casa vs bom (not minimal)
    ("f a l a", "f a l a s", "inserted s at position 5"),  # fala vs falas
    ("p e", "p ɛ", "e→ɛ at position 2"),  # pé vs pê (different e)
]

for phonemes1, phonemes2, expected in test_cases:
    result = _is_minimal_pair(phonemes1, phonemes2)
    status = "✓" if result == expected else "✗"
    print(f"{status} '{phonemes1}' vs '{phonemes2}'")
    print(f"  Expected: {expected}")
    print(f"  Got:      {result}")
    if result != expected:
        print("  ❌ FAILED!")
    print()

# Test 2: Find minimal pairs from sample vocab
print("\n[Test 2] Find minimal pairs from sample vocabulary")
print("-" * 60)

sample_vocab = [
    {'text': 'casa', 'phonemes': 'k a z a', 'translation': 'house'},
    {'text': 'cama', 'phonemes': 'k a m a', 'translation': 'bed'},
    {'text': 'amor', 'phonemes': 'a m o r', 'translation': 'love'},
    {'text': 'fala', 'phonemes': 'f a l a', 'translation': 'speech'},
    {'text': 'fala', 'phonemes': 'f a l a s', 'translation': 'speeches'},  # Duplicate text intentional
    {'text': 'bom', 'phonemes': 'b õ', 'translation': 'good'},
    {'text': 'tom', 'phonemes': 't õ', 'translation': 'tone'},
]

pairs = find_minimal_pairs(sample_vocab, max_pairs=10)
print(f"Found {len(pairs)} minimal pair(s):\n")

for i, (word1, word2, diff_desc) in enumerate(pairs, 1):
    print(f"{i}. {word1['text']} [{word1['phonemes']}] vs {word2['text']} [{word2['phonemes']}]")
    print(f"   Difference: {diff_desc}")
    print()

# Test 3: Format for practice interface
print("\n[Test 3] Format minimal pair for practice interface")
print("-" * 60)

if pairs:
    first_pair = pairs[0]
    formatted = format_minimal_pair_for_practice(first_pair)
    
    print("Formatted practice phrase:")
    print(f"  Text:        {formatted['text']}")
    print(f"  Translation: {formatted['translation']}")
    print(f"  IPA:         {formatted.get('ipa', 'N/A')}")
    print(f"  Pair:        {formatted['pair']}")
    print(f"  Is minimal:  {formatted.get('minimal_pair', False)}")
else:
    print("No pairs found to format!")

# Test 4: Generate full practice list
print("\n[Test 4] Generate full practice list")
print("-" * 60)

practice_list = generate_minimal_pair_practice_list(sample_vocab, max_pairs=5)
print(f"Generated {len(practice_list)} practice phrase(s):\n")

for i, phrase in enumerate(practice_list, 1):
    print(f"{i}. {phrase['text']}")
    print(f"   {phrase['translation'][:80]}...")
    print()

# Test 5: Edge cases
print("\n[Test 5] Edge cases")
print("-" * 60)

edge_cases = [
    ("Empty vocab", []),
    ("Single word vocab", [{'text': 'casa', 'phonemes': 'k a z a'}]),
    ("Vocab with no phonemes", [{'text': 'casa'}, {'text': 'cama'}]),
    ("Vocab with empty phonemes", [
        {'text': 'casa', 'phonemes': ''},
        {'text': 'cama', 'phonemes': 'k a m a'}
    ]),
]

for name, vocab in edge_cases:
    pairs = find_minimal_pairs(vocab, max_pairs=10)
    print(f"{name}: {len(pairs)} pair(s) found")

# Test 6: Portuguese phonemes with nasal vowels
print("\n[Test 6] Portuguese phonemes with nasal vowels and diacritics")
print("-" * 60)

portuguese_vocab = [
    {'text': 'bem', 'phonemes': 'b ẽ j̃', 'translation': 'well'},
    {'text': 'bom', 'phonemes': 'b õ', 'translation': 'good'},
    {'text': 'pé', 'phonemes': 'p ɛ', 'translation': 'foot'},
    {'text': 'pês', 'phonemes': 'p e s', 'translation': 'feet'},
    {'text': 'carro', 'phonemes': 'k a ʁ u', 'translation': 'car'},
    {'text': 'caro', 'phonemes': 'k a ɾ u', 'translation': 'expensive'},
]

pt_pairs = find_minimal_pairs(portuguese_vocab, max_pairs=10)
print(f"Found {len(pt_pairs)} Portuguese minimal pair(s):\n")

for word1, word2, diff_desc in pt_pairs:
    print(f"• {word1['text']} vs {word2['text']}")
    print(f"  {word1['translation']} vs {word2['translation']}")
    print(f"  Difference: {diff_desc}")
    print()

print("=" * 60)
print("All tests complete!")
print("=" * 60)
