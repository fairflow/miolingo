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

/// evaluate, pure half: compare a recognised phoneme string to the target's IPA.
/// (The ASR — recognisePhonemes — is the oracle, performed by SpeechScorer.)
public func evaluate(target: Phrase, recognisedPhonemes: String) -> Score {
    comparePhonemes(user: recognisedPhonemes, correct: correctPhonemesOf(target))
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
