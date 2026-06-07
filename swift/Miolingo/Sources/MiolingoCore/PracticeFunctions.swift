import Foundation

// =====================================================================
// PracticeFunctions — ported from spec/PracticeSessionFunctions.wl
// (recovered from src/scoring/comparison.py). The ASR step (audio →
// phonemes) is the uninterpreted oracle; the spec is parametric in it, so
// here `evaluate` is split: the pure comparison (ported verbatim) takes the
// already-recognised phoneme string, which the app's SpeechScorer produces.
// =====================================================================

// --- levenshtein (comparison.py:9) — pure edit distance ---------------
public func levenshtein(_ s1: String, _ s2: String) -> Int {
    let a = Array(s1), b = Array(s2)
    if a.isEmpty { return b.count }
    if b.isEmpty { return a.count }
    var prev = Array(0...b.count)
    var cur = [Int](repeating: 0, count: b.count + 1)
    for i in 1...a.count {
        cur[0] = i
        for j in 1...b.count {
            let cost = a[i - 1] == b[j - 1] ? 0 : 1
            cur[j] = Swift.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
        }
        swap(&prev, &cur)
    }
    return prev[b.count]
}

// --- compare_phonemes_edit_distance (comparison.py:83) ----------------
public func comparePhonemes(user: String, correct: String) -> Score {
    if correct.isEmpty {
        return Score(exactMatch: user == correct, similarity: 0.0, distance: user.count)
    }
    let dist = levenshtein(user, correct)
    let maxLen = Swift.max(user.count, correct.count)
    return Score(exactMatch: user == correct,
                 similarity: 1.0 - Double(dist) / Double(maxLen),
                 distance: dist)
}

// --- targetOf / selectPos (PracticeSessionFunctions.wl) ----------------
public func targetOf(_ phrases: [Phrase], _ pos: Int) -> Phrase {
    (0 <= pos && pos < phrases.count) ? phrases[pos] : .empty
}

/// select_item guard: an out-of-range index is a no-op (pos stays put).
public func selectPos(_ phrases: [Phrase], _ i: Int, _ cur: Int) -> Int {
    (0 <= i && i < phrases.count) ? i : cur
}

func correctPhonemesOf(_ target: Phrase) -> String { target.ipa }

// --- normalisePhonemes (phonemes.py normalize_for_phoneme_scoring) -----
/// Strip word-boundary whitespace so scoring is on pronunciation phonemes only
/// (we feed clean --ipa, never espeak -x codes).
public func normalisePhonemes(_ ipa: String) -> String {
    ipa.components(separatedBy: .whitespacesAndNewlines).joined()
}

// --- alignPhonemes (comparison.py get_edit_operations) ----------------
/// Levenshtein backtrace aligning the target (correct) against the user's
/// phonemes → segments {op, target, user}, oriented target-vs-user (as
/// practice_tab _colorize_diff renders). The matched/unmatched structure.
public func alignPhonemes(user: String, correct: String) -> [AlignSeg] {
    let a = Array(correct), b = Array(user)        // a = target, b = user
    let m = a.count, n = b.count
    var dp = Array(repeating: Array(repeating: 0, count: n + 1), count: m + 1)
    for i in 0...m { dp[i][0] = i }
    for j in 0...n { dp[0][j] = j }
    if m > 0 && n > 0 {
        for i in 1...m { for j in 1...n {
            dp[i][j] = a[i-1] == b[j-1] ? dp[i-1][j-1]
                : 1 + Swift.min(dp[i-1][j], dp[i][j-1], dp[i-1][j-1])
        } }
    }
    var ops: [AlignSeg] = []
    var i = m, j = n
    while i > 0 || j > 0 {
        if i > 0 && j > 0 && a[i-1] == b[j-1] {
            ops.append(AlignSeg(op: .equal, target: String(a[i-1]), user: String(b[j-1]))); i -= 1; j -= 1
        } else if i > 0 && j > 0 && dp[i][j] == dp[i-1][j-1] + 1 {
            ops.append(AlignSeg(op: .sub, target: String(a[i-1]), user: String(b[j-1]))); i -= 1; j -= 1
        } else if j > 0 && dp[i][j] == dp[i][j-1] + 1 {
            ops.append(AlignSeg(op: .ins, target: "", user: String(b[j-1]))); j -= 1
        } else {
            ops.append(AlignSeg(op: .del, target: String(a[i-1]), user: "")); i -= 1
        }
    }
    return ops.reversed()
}

// --- scoreDetail / evaluate -------------------------------------------
/// The full scored result: comparePhonemes numbers + phoneme strings + alignment.
public func scoreDetail(user: String, correct: String) -> Score {
    var s = comparePhonemes(user: user, correct: correct)
    s.user = user; s.target = correct
    s.alignment = alignPhonemes(user: user, correct: correct)
    return s
}

/// evaluate, pure half: normalise both sides, then score + align. (The ASR —
/// recognisePhonemes — is the oracle, performed by SpeechScorer.)
public func evaluate(target: Phrase, recognisedPhonemes: String) -> Score {
    scoreDetail(user: normalisePhonemes(recognisedPhonemes),
                correct: normalisePhonemes(correctPhonemesOf(target)))
}

// --- sessionView (read-only projection) -------------------------------
public struct SessionView: Equatable, Sendable {
    public var total: Int
    public var pos: Int
    public var item: Phrase?
    public var hasRecording: Bool
    public var score: Score?
}

public func sessionView(phrases: [Phrase], pos: Int,
                        rec: Recording?, res: Score?) -> SessionView {
    SessionView(total: phrases.count, pos: pos,
                item: phrases.isEmpty ? nil : targetOf(phrases, pos),
                hasRecording: rec != nil, score: res)
}
