import SwiftUI
import MiolingoCore

// =====================================================================
// Skin — the L3 styling layer as a swappable token set (Phase 5). One accent,
// system fonts (rounded for warmth), system materials, and the colour meanings
// (score scale + phoneme-diff palette). `.miolingo` is the new calm, native,
// pronunciation-forward design; `.system` preserves the plain earlier look.
// Delivered via the environment so any view reads the same tokens.
// =====================================================================
struct Skin: Sendable {
    var name: String
    var accent: Color
    var rounded: Bool          // rounded design for the word/headings (warmth)
    var cornerRadius: CGFloat

    // score scale (green → amber → red) — correctness
    var scoreGood: Color
    var scoreMid: Color
    var scoreBad: Color
    func scoreColor(_ similarity: Double) -> Color {
        similarity >= 0.8 ? scoreGood : (similarity >= 0.5 ? scoreMid : scoreBad)
    }

    // phoneme-diff palette — in `.miolingo` it's CORRECTNESS-oriented
    // (matched = faint green, substituted = red, missing = amber, extra = grey),
    // so colour means the same thing everywhere.
    var diffMatch: Color
    var diffSub: Color
    var diffDel: Color
    var diffIns: Color
    func diff(_ op: AlignOp) -> Color {
        switch op {
        case .equal: return diffMatch
        case .sub:   return diffSub
        case .del:   return diffDel
        case .ins:   return diffIns
        }
    }

    var wordFont: Font    { .system(.largeTitle, design: rounded ? .rounded : .default).weight(.bold) }
    var titleFont: Font   { .system(.title2, design: rounded ? .rounded : .default).weight(.bold) }
    var headingFont: Font { .system(.headline, design: rounded ? .rounded : .default) }
    var ipaFont: Font     { .system(.title3, design: .monospaced) }

    static let miolingo = Skin(
        name: "Miolingo",
        accent: Color(red: 0.173, green: 0.478, blue: 0.482),   // teal #2C7A7B
        rounded: true, cornerRadius: 12,
        scoreGood: .green, scoreMid: .orange, scoreBad: .red,
        diffMatch: Color.green.opacity(0.16),
        diffSub: Color(red: 0.98, green: 0.74, blue: 0.74),     // red-ish (wrong sound)
        diffDel: Color(red: 1.00, green: 0.88, blue: 0.66),     // amber (missing)
        diffIns: Color.gray.opacity(0.28))                      // grey (extra)

    // The earlier look: system accent, no rounded fonts, op-type diff colours.
    static let system = Skin(
        name: "System",
        accent: .accentColor, rounded: false, cornerRadius: 8,
        scoreGood: .green, scoreMid: .orange, scoreBad: .red,
        diffMatch: .clear,
        diffSub: Color(red: 0.68, green: 0.85, blue: 0.90),     // blue
        diffDel: Color(red: 1.00, green: 0.71, blue: 0.78),     // pink
        diffIns: Color(red: 0.56, green: 0.93, blue: 0.56))     // green

    static let all: [Skin] = [.miolingo, .system]
}

private struct SkinKey: EnvironmentKey { static let defaultValue = Skin.miolingo }
extension EnvironmentValues {
    var skin: Skin {
        get { self[SkinKey.self] }
        set { self[SkinKey.self] = newValue }
    }
}
