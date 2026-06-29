"""
Weighted phone-distance scorer (beads miolingo-8f0, research prototype).

Scores a learner's pronunciation (IPA string) against a target (IPA string) at
the *phone* level rather than the character level:

  - tokenize each IPA string into phones (panphon, handles multi-codepoint
    segments: affricates, length marks, diacritics);
  - substitution cost between two phones = normalized panphon articulatory
    *feature* distance (0 = identical features, 1 = maximally different), EXCEPT
    pairs the espeak-ng fold-map (miolingo-ark) marks as tolerated accent
    variation cost 0;
  - align with a weighted Levenshtein, returning a 0..1 similarity, the per-phone
    operations, and which substitutions are "significant" (real errors).

This replaces the character-level Levenshtein in src/scoring/comparison.py. It
scores ANY phone string (Whisper-derived IPA or phone-recognizer IPA) against the
espeak-ng target. Generated from the research prototype in
research/phonetics/phone_distance/ (beads miolingo-8f0).
"""
from __future__ import annotations

import math
import unicodedata
from dataclasses import dataclass
from functools import lru_cache

import panphon

from ipa import fold_map

_FT = panphon.FeatureTable()
_N_FEATURES = 24

# espeak/get_ipa decorations to drop before phone alignment.
_DROP = set("ˈˌˑ.|‖ ")          # stress, syllable, phrase marks, spaces
_INDEL_COST = 1.0               # insertion/deletion cost (a whole missing phone)
_SIGNIFICANT = 0.34             # substitution cost above this = flagged as error


def _clean(ipa: str) -> str:
    ipa = unicodedata.normalize("NFD", ipa)
    return "".join(c for c in ipa if c not in _DROP)


@lru_cache(maxsize=4096)
def _vector(seg: str):
    """panphon numeric feature vector for one segment, or None if unknown."""
    vecs = _FT.word_to_vector_list(seg, numeric=True)
    return tuple(vecs[0]) if len(vecs) == 1 else None


def _feature_distance(a: str, b: str) -> float:
    """Normalized articulatory distance in [0, 1] between two phones."""
    if a == b:
        return 0.0
    va, vb = _vector(a), _vector(b)
    if va is None or vb is None:        # unknown symbol: treat as fully distinct
        return 1.0
    # features are in {-1, 0, +1}; per-feature |diff| <= 2 -> normalize by 2N
    return sum(abs(x - y) for x, y in zip(va, vb)) / (2 * _N_FEATURES)


def segment(ipa: str) -> list[str]:
    """IPA string -> list of phone segments (stress/syllable marks removed)."""
    return _FT.ipa_segs(_clean(ipa))


@dataclass
class Op:
    kind: str          # 'match' | 'substitute' | 'insert' | 'delete'
    target: str        # phone on the target side ('' for insert)
    user: str          # phone on the user side ('' for delete)
    cost: float
    significant: bool  # a substitution costly enough to flag to the learner


@dataclass
class Result:
    exact_match: bool
    similarity: float        # 1.0 = perfect
    distance: float          # total weighted edit cost
    ops: list                # list[Op], target-order
    target_segs: list
    user_segs: list


def _sub_cost(target: str, user: str, lang: str | None) -> float:
    if target == user:
        return 0.0
    if lang is not None and fold_map_is_tolerated(lang, target, user):
        return 0.0
    return _feature_distance(target, user)


def fold_map_is_tolerated(lang: str, a: str, b: str) -> bool:
    try:
        return fold_map.is_tolerated(lang, a, b)
    except KeyError:
        return False            # no fold-map for this language -> nothing folded


def score(user_ipa: str, target_ipa: str, lang: str | None = None,
          gain: float = 1.0, exp: float = 1.0, sqrt_norm: bool = False) -> Result:
    """Weighted phone-distance score of user_ipa against target_ipa.

    lang is a fold-map key / voice code (pt, pt-pt, fr, nl, en, pt-br, ...). When
    given, tolerated accent substitutions cost 0; when None, every substitution
    is scored purely on feature distance.

    Accuracy curve (miolingo-7w3/h8q) — defaults are NO-OP so the legacy
    weighted_phone algorithm is unchanged:
      gain, exp : steepen each substitution cost -> min(1, (cost*gain)**exp).
                  panphon raw feature distances are compressed (ɛ→a≈0.12), so
                  without this even clear vowel errors barely register.
      sqrt_norm : divide total distance by 1.5*sqrt(len) instead of len, so a
                  single real error stays visible in a long phrase (else one
                  error / 11 phones ≈ 99%). For the ACCURACY channel only;
                  comprehensibility scoring stays lenient (defaults).
    """
    t = segment(target_ipa)
    u = segment(user_ipa)
    m, n = len(t), len(u)

    def _curve(c: float) -> float:
        if c <= 0.0:
            return 0.0
        return min(1.0, (c * gain) ** exp)

    # DP weighted Levenshtein; dp[i][j] = cost aligning t[:i] with u[:j].
    dp = [[0.0] * (n + 1) for _ in range(m + 1)]
    for i in range(1, m + 1):
        dp[i][0] = i * _INDEL_COST
    for j in range(1, n + 1):
        dp[0][j] = j * _INDEL_COST
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            sub = dp[i - 1][j - 1] + _curve(_sub_cost(t[i - 1], u[j - 1], lang))
            dele = dp[i - 1][j] + _INDEL_COST
            ins = dp[i][j - 1] + _INDEL_COST
            dp[i][j] = min(sub, dele, ins)

    # Backtrace for per-phone operations.
    ops: list[Op] = []
    i, j = m, n
    while i > 0 or j > 0:
        if i > 0 and j > 0:
            c = _curve(_sub_cost(t[i - 1], u[j - 1], lang))
            if abs(dp[i][j] - (dp[i - 1][j - 1] + c)) < 1e-9:
                if c == 0.0:
                    ops.append(Op("match", t[i - 1], u[j - 1], 0.0, False))
                else:
                    ops.append(Op("substitute", t[i - 1], u[j - 1], c,
                                  c >= _SIGNIFICANT))
                i -= 1
                j -= 1
                continue
        if i > 0 and abs(dp[i][j] - (dp[i - 1][j] + _INDEL_COST)) < 1e-9:
            ops.append(Op("delete", t[i - 1], "", _INDEL_COST, True))
            i -= 1
        else:
            ops.append(Op("insert", "", u[j - 1], _INDEL_COST, True))
            j -= 1
    ops.reverse()

    distance = dp[m][n]
    if sqrt_norm:
        denom = 1.5 * math.sqrt(max(m, n)) or 1
    else:
        denom = max(m, n) or 1
    similarity = max(0.0, 1.0 - distance / denom)
    return Result(
        exact_match=(t == u),
        similarity=similarity,
        distance=distance,
        ops=ops,
        target_segs=t,
        user_segs=u,
    )
