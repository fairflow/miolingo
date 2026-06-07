import Foundation

// =====================================================================
// Import / export — ported from spec/VocabFunctions.wl (vocab.py:453, 486,
// 545, vocabulary_tab.py:222).
// =====================================================================

func parseImportLine(_ line: String) -> Capture? {
    let parts = line.components(separatedBy: "|").map {
        $0.trimmingCharacters(in: .whitespaces)
    }
    let word = parts.first ?? ""
    if word.isEmpty { return nil }
    func get(_ i: Int) -> String { parts.count >= i ? parts[i - 1] : "" }
    var ipa = get(3)
    if ipa.count >= 2, ipa.hasPrefix("["), ipa.hasSuffix("]") {
        ipa = String(ipa.dropFirst().dropLast())
    }
    return Capture(word: word, translation: get(2).isEmpty ? nil : get(2),
                   ipa: ipa.isEmpty ? nil : ipa,
                   sourceName: get(4).isEmpty ? nil : get(4),
                   url: get(5).isEmpty ? nil : get(5))
}

/// `(target, source)` header — matches the COLUMN order (word is target, the
/// translation is source). Lowercased language codes; #-comment lines skipped.
/// nil if no header before the first data line.
func parseImportHeader(_ contents: String) -> (target: String, source: String)? {
    for raw in contents.components(separatedBy: "\n") {
        let line = raw.trimmingCharacters(in: .whitespaces)
        if line.isEmpty { continue }
        if line.hasPrefix("("), line.contains(","), let close = line.firstIndex(of: ")") {
            let inner = line[line.index(after: line.startIndex)..<close]
            let bits = inner.split(separator: ",", maxSplits: 1).map {
                $0.trimmingCharacters(in: .whitespaces).lowercased()
            }
            if bits.count == 2 { return (bits[0], bits[1]) }   // (target, source)
        }
        if line.hasPrefix("#") { continue }
        return nil   // first data line, no header -> reject
    }
    return nil
}

func isImportDataLine(_ raw: String) -> Bool {
    let line = raw.trimmingCharacters(in: .whitespaces)
    return !line.isEmpty && !line.hasPrefix("#") && !line.hasPrefix("(")
}

public let importLineLimit = 250

/// Why an import did/didn't happen — drives user feedback (no more silent no-op).
public enum ImportResult: Equatable, Sendable {
    case ok(added: Int)
    case noHeader
    case targetMismatch(fileTarget: String, expected: String)
    case tooMany(Int)
}

/// importInto + the reason. The header's TARGET must equal the expected target.
public func importOutcome(_ entries: [VocabEntry], _ f: ImportRequest)
    -> (entries: [VocabEntry], result: ImportResult) {
    guard let hdr = parseImportHeader(f.contents) else { return (entries, .noHeader) }
    if let exp = f.expectedTarget, hdr.target != exp.lowercased() {
        return (entries, .targetMismatch(fileTarget: hdr.target, expected: exp.lowercased()))
    }
    let dataLines = f.contents.components(separatedBy: "\n").filter(isImportDataLine)
    if dataLines.count > importLineLimit { return (entries, .tooMany(dataLines.count)) }
    let out = dataLines.reduce(entries) { acc, raw in
        if let p = parseImportLine(raw.trimmingCharacters(in: .whitespaces)) { return addEntry(acc, p) }
        return acc
    }
    return (out, .ok(added: out.count - entries.count))
}

public func importInto(_ entries: [VocabEntry], _ f: ImportRequest) -> [VocabEntry] {
    importOutcome(entries, f).entries
}

// --- exportCsv (vocabulary_tab.py:222) — 13-column header + rows -------
let exportCsvHeader = ["word", "translation", "ipa", "source_language", "source",
    "context_before", "context_line", "context_after",
    "times_seen", "first_seen_at", "last_seen_at", "notes", "url"]

private func csvCell(_ x: String?) -> String { x ?? "" }

/// RFC-4180 minimal quoting: quote only on comma/quote/newline; double quotes.
private func csvField(_ x: String?) -> String {
    let s = csvCell(x)
    if s.contains(",") || s.contains("\"") || s.contains("\n") || s.contains("\r") {
        return "\"" + s.replacingOccurrences(of: "\"", with: "\"\"") + "\""
    }
    return s
}

private func csvRow(_ cells: [String?]) -> String {
    cells.map(csvField).joined(separator: ",")
}

public func exportCsv(_ entries: [VocabEntry]) -> String {
    var rows = [csvRow(exportCsvHeader.map { $0 })]
    for r in entries {
        rows.append(csvRow([
            r.displayWord.isEmpty ? r.word : r.displayWord,
            r.translation, r.ipa,
            nil,                    // source_language_code — unmodelled at L1
            r.sourceName,
            r.contextBefore, r.contextLine, r.contextAfter,
            String(r.timesSeen),
            "", "",                 // first/last_seen_at — wall-clock unmodelled
            r.notes, r.url,
        ]))
    }
    return rows.joined(separator: "\n")
}
