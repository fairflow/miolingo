import Foundation

// =====================================================================
// Phrase import — the SAME bulk-ingest shape as vocab import, but the payload
// parses to [Phrase] (a practice queue) instead of vocab entries. Reuses the
// (target, source) header, the #-comment / blank-line rules, the 250-row cap.
// Rows: `text | translation | ipa`  (IPA may be […]-wrapped). The first three
// columns mirror vocab's word|translation|ipa, so the format is shared.
// =====================================================================

public enum PhraseImportResult: Equatable, Sendable {
    case ok(count: Int)
    case noHeader
    case targetMismatch(fileTarget: String, expected: String)
    case tooMany(Int)
}

public func importPhrases(_ f: ImportRequest) -> (phrases: [Phrase], result: PhraseImportResult) {
    guard let hdr = parseImportHeader(f.contents) else { return ([], .noHeader) }
    if let exp = f.expectedTarget, hdr.target != exp.lowercased() {
        return ([], .targetMismatch(fileTarget: hdr.target, expected: exp.lowercased()))
    }
    let dataLines = f.contents.components(separatedBy: "\n").filter(isImportDataLine)
    if dataLines.count > importLineLimit { return ([], .tooMany(dataLines.count)) }
    let phrases: [Phrase] = dataLines.compactMap { raw in
        let parts = raw.components(separatedBy: "|").map { $0.trimmingCharacters(in: .whitespaces) }
        let text = parts.first ?? ""
        if text.isEmpty { return nil }
        func col(_ i: Int) -> String { parts.count >= i ? parts[i - 1] : "" }
        var ipa = col(3)
        if ipa.count >= 2, ipa.hasPrefix("["), ipa.hasSuffix("]") { ipa = String(ipa.dropFirst().dropLast()) }
        return Phrase(text: text, translation: col(2), ipa: ipa)
    }
    return (phrases, .ok(count: phrases.count))
}
