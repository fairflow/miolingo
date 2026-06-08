import SwiftUI
import MiolingoCore

// =====================================================================
// In-app Help — renders the bundled user-facing help.md in a Help window
// (opened from the Help menu / ⌘?). User-facing only; no methodology.
// A light block renderer: headings, bullets, code blocks, dividers, and
// paragraphs with inline markdown (**bold**, `code`).
// =====================================================================

enum HelpBlock {
    case h1(String), h2(String), h3(String)
    case para(AttributedString), bullet(AttributedString)
    case code(String), divider
}

enum HelpParser {
    static func load() -> String {
        BundledResource.url(forResource: "help", withExtension: "md")
            .flatMap { try? String(contentsOf: $0, encoding: .utf8) }
            ?? "# Miolingo Help\n\nHelp content is unavailable in this build."
    }
    static func inline(_ s: String) -> AttributedString {
        (try? AttributedString(markdown: s,
            options: .init(interpretedSyntax: .inlineOnlyPreservingWhitespace))) ?? AttributedString(s)
    }
    static func parse(_ md: String) -> [HelpBlock] {
        var blocks: [HelpBlock] = []
        var inCode = false, code: [String] = [], para: [String] = []
        func flush() { if !para.isEmpty { blocks.append(.para(inline(para.joined(separator: " ")))); para = [] } }
        for raw in md.components(separatedBy: "\n") {
            if raw.hasPrefix("```") {
                if inCode { blocks.append(.code(code.joined(separator: "\n"))); code = []; inCode = false }
                else { flush(); inCode = true }
                continue
            }
            if inCode { code.append(raw); continue }
            let t = raw.trimmingCharacters(in: .whitespaces)
            if t.isEmpty { flush() }
            else if t.hasPrefix("### ") { flush(); blocks.append(.h3(String(t.dropFirst(4)))) }
            else if t.hasPrefix("## ")  { flush(); blocks.append(.h2(String(t.dropFirst(3)))) }
            else if t.hasPrefix("# ")   { flush(); blocks.append(.h1(String(t.dropFirst(2)))) }
            else if t == "---"          { flush(); blocks.append(.divider) }
            else if t.hasPrefix("- ") || t.hasPrefix("* ") { flush(); blocks.append(.bullet(inline(String(t.dropFirst(2))))) }
            else if let m = t.range(of: #"^\d+\.\s+"#, options: .regularExpression) {
                flush(); blocks.append(.bullet(inline(String(t[m.upperBound...]))))
            }
            else { para.append(t) }
        }
        flush()
        return blocks
    }
}

struct HelpView: View {
    private let blocks = HelpParser.parse(HelpParser.load())

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 9) {
                ForEach(Array(blocks.enumerated()), id: \.offset) { _, b in block(b) }
            }
            .padding(26)
            .frame(maxWidth: 760, alignment: .leading)
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .frame(minWidth: 600, minHeight: 560)
    }

    @ViewBuilder private func block(_ b: HelpBlock) -> some View {
        switch b {
        case .h1(let t): Text(t).font(.largeTitle).bold().padding(.top, 4)
        case .h2(let t): Text(t).font(.title2).bold().padding(.top, 10)
        case .h3(let t): Text(t).font(.headline).padding(.top, 4)
        case .para(let a): Text(a)
        case .bullet(let a):
            HStack(alignment: .firstTextBaseline, spacing: 6) { Text("•"); Text(a) }
                .padding(.leading, 4)
        case .code(let s):
            Text(s).font(.system(.callout, design: .monospaced))
                .padding(10).frame(maxWidth: .infinity, alignment: .leading)
                .background(.quaternary, in: RoundedRectangle(cornerRadius: 6))
        case .divider: Divider().padding(.vertical, 4)
        }
    }
}
