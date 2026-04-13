"""
Phoneme comparison and scoring algorithms.

Extracted from app.py (Phase 1.4 of refactor).
Pure functions with no external dependencies.
"""


def levenshtein_distance(s1: str, s2: str) -> int:
    """
    Calculate Levenshtein (edit) distance between two strings.
    Returns the minimum number of single-character edits
    (insertions, deletions, substitutions).
    """
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)

    if len(s2) == 0:
        return len(s1)

    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]


def get_edit_operations(s1: str, s2: str):
    """
    Get the actual edit operations needed to transform s1 into s2.
    Returns a list of tuples: (operation, position, char1, char2)
    where operation is 'match', 'substitute', 'insert', or 'delete'.
    """
    m, n = len(s1), len(s2)
    dp = [[0] * (n + 1) for _ in range(m + 1)]

    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j

    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if s1[i-1] == s2[j-1]:
                dp[i][j] = dp[i-1][j-1]
            else:
                dp[i][j] = 1 + min(
                    dp[i-1][j],    # delete
                    dp[i][j-1],    # insert
                    dp[i-1][j-1]   # substitute
                )

    # Backtrack to find operations
    operations = []
    i, j = m, n
    while i > 0 or j > 0:
        if i > 0 and j > 0 and s1[i-1] == s2[j-1]:
            operations.append(('match', i-1, s1[i-1], s2[j-1]))
            i -= 1
            j -= 1
        elif i > 0 and j > 0 and dp[i][j] == dp[i-1][j-1] + 1:
            operations.append(('substitute', i-1, s1[i-1], s2[j-1]))
            i -= 1
            j -= 1
        elif j > 0 and dp[i][j] == dp[i][j-1] + 1:
            operations.append(('insert', i, '-', s2[j-1]))
            j -= 1
        elif i > 0 and dp[i][j] == dp[i-1][j] + 1:
            operations.append(('delete', i-1, s1[i-1], '-'))
            i -= 1

    operations.reverse()
    return operations



def compare_phonemes_edit_distance(user_phonemes: str, correct_phonemes: str):
    """
    Compare phonemes using edit distance (Levenshtein).

    Returns:
        exact_match: bool - True if strings are identical
        similarity: float - 0.0 to 1.0, where 1.0 is perfect match
        distance: int - Number of edits needed
    """
    exact_match = user_phonemes == correct_phonemes

    if len(correct_phonemes) == 0:
        return exact_match, 0.0, len(user_phonemes)

    distance = levenshtein_distance(user_phonemes, correct_phonemes)
    max_length = max(len(user_phonemes), len(correct_phonemes))
    similarity = 1.0 - (distance / max_length)

    return exact_match, similarity, distance


def compare_phonemes(user_phonemes: str, correct_phonemes: str,
                     algorithm: str = "edit_distance"):
    """
    Modular phoneme comparison with selectable algorithms.

    Args:
        user_phonemes: Phonemes from user's speech
        correct_phonemes: Target phonemes
        algorithm: "edit_distance" (default) or "positional"

    Returns:
        exact_match: bool
        similarity: float (0.0 to 1.0)
        distance: int (only for edit_distance, None otherwise)
    """
    if algorithm == "edit_distance":
        return compare_phonemes_edit_distance(user_phonemes, correct_phonemes)
    else:
        raise ValueError(f"Unknown algorithm: {algorithm}")
