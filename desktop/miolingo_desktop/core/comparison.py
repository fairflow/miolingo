"""Phoneme comparison and scoring algorithms.

Ported verbatim from the Streamlit app's ``src/scoring/comparison.py`` — these
were already pure functions with no UI coupling, so the desktop port is a
straight copy. Keeping them byte-identical guarantees scoring parity with the
source app (see ``tests/unit/test_scoring_parity.py``).
"""

from __future__ import annotations


def levenshtein_distance(s1: str, s2: str) -> int:
    """Minimum single-character edits (insert/delete/substitute) between strings."""
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)

    if len(s2) == 0:
        return len(s1)

    previous_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]


def get_edit_operations(s1: str, s2: str) -> list[tuple[str, int, str, str]]:
    """Return the edit operations transforming s1 into s2.

    Each tuple is ``(operation, position, char1, char2)`` where operation is
    'match', 'substitute', 'insert', or 'delete'.
    """
    m, n = len(s1), len(s2)
    dp = [[0] * (n + 1) for _ in range(m + 1)]

    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j

    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if s1[i - 1] == s2[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]
            else:
                dp[i][j] = 1 + min(
                    dp[i - 1][j],  # delete
                    dp[i][j - 1],  # insert
                    dp[i - 1][j - 1],  # substitute
                )

    operations: list[tuple[str, int, str, str]] = []
    i, j = m, n
    while i > 0 or j > 0:
        if i > 0 and j > 0 and s1[i - 1] == s2[j - 1]:
            operations.append(("match", i - 1, s1[i - 1], s2[j - 1]))
            i -= 1
            j -= 1
        elif i > 0 and j > 0 and dp[i][j] == dp[i - 1][j - 1] + 1:
            operations.append(("substitute", i - 1, s1[i - 1], s2[j - 1]))
            i -= 1
            j -= 1
        elif j > 0 and dp[i][j] == dp[i][j - 1] + 1:
            operations.append(("insert", i, "-", s2[j - 1]))
            j -= 1
        elif i > 0 and dp[i][j] == dp[i - 1][j] + 1:
            operations.append(("delete", i - 1, s1[i - 1], "-"))
            i -= 1

    operations.reverse()
    return operations


def compare_phonemes_edit_distance(
    user_phonemes: str, correct_phonemes: str
) -> tuple[bool, float, int]:
    """Compare phonemes via Levenshtein.

    Returns ``(exact_match, similarity[0..1], distance)``.
    """
    exact_match = user_phonemes == correct_phonemes

    if len(correct_phonemes) == 0:
        return exact_match, 0.0, len(user_phonemes)

    distance = levenshtein_distance(user_phonemes, correct_phonemes)
    max_length = max(len(user_phonemes), len(correct_phonemes))
    similarity = 1.0 - (distance / max_length)

    return exact_match, similarity, distance


def compare_phonemes(
    user_phonemes: str,
    correct_phonemes: str,
    algorithm: str = "edit_distance",
) -> tuple[bool, float, int]:
    """Modular phoneme comparison.

    The legacy "positional" algorithm was removed upstream; any unknown
    ``algorithm`` value falls back to edit distance (matches source behaviour).
    """
    return compare_phonemes_edit_distance(user_phonemes, correct_phonemes)
