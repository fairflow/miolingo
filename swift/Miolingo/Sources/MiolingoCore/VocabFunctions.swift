import Foundation

// =====================================================================
// VocabFunctions — ported verbatim (in behaviour) from spec/VocabFunctions.wl
// (recovered from src/vocab.py). Pure; no IO except the enrich oracle, which
// is passed in.
// =====================================================================

// --- derived identity + logical clock ---------------------------------
func vsNewId(_ entries: [VocabEntry]) -> Int { 1 + (entries.map(\.id).max() ?? 0) }
func vsNextSeq(_ entries: [VocabEntry]) -> Int { 1 + (entries.map(\.lastSeq).max() ?? 0) }

func emptyToNull(_ x: String?) -> String? {
    guard let x, !x.isEmpty else { return nil }
    return x
}
func coalesce(_ old: String?, _ new: String?) -> String? {
    if old == nil || old == "" { return emptyToNull(new) }
    return old
}

// --- _normalise + validate_single_word (vocab.py:31, 50) --------------
// _TRIM_PUNCT: ASCII + curly quotes, guillemets, dashes, ellipsis.
private let vsTrimChars: Set<Character> = {
    var s = Set(".,;:!?\"'-")
    for cp in [0x201C, 0x201D, 0x2018, 0x2019, 0xAB, 0xBB, 0x2014, 0x2013, 0x2026] {
        s.insert(Character(UnicodeScalar(cp)!))
    }
    return s
}()

/// Strip surrounding (never inner) trim-punctuation. Returns (display, key).
func normalise(_ word: String) -> (display: String, key: String) {
    var t = Substring(word.trimmingCharacters(in: .whitespacesAndNewlines))
    while let f = t.first, vsTrimChars.contains(f) { t = t.dropFirst() }
    while let l = t.last, vsTrimChars.contains(l) { t = t.dropLast() }
    let display = String(t)
    return (display, display.lowercased())
}

/// validate_single_word: returns (display, key) or nil.
public func validateWord(_ word: String) -> (display: String, key: String)? {
    if word.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty { return nil }
    let (display, key) = normalise(word)
    if key.isEmpty { return nil }                                   // only punctuation
    if key.rangeOfCharacter(from: .whitespacesAndNewlines) != nil { return nil } // not single word
    if key.count > 100 { return nil }                              // too long
    return (display, key)
}

// --- addEntry[entries, w] : capture_vocab_entry upsert (vocab.py:106) --
public func addEntry(_ entries: [VocabEntry], _ w: Capture) -> [VocabEntry] {
    guard let (display, key) = validateWord(w.word) else { return entries }
    if let idx = entries.firstIndex(where: { $0.word == key }) {
        var out = entries
        var m = out[idx]
        m.timesSeen += 1
        m.lastSeq = vsNextSeq(entries)                              // advance logical clock
        m.translation   = coalesce(m.translation, w.translation)
        m.ipa           = coalesce(m.ipa, w.ipa)
        m.sourceName    = coalesce(m.sourceName, w.sourceName)
        m.url           = coalesce(m.url, w.url)
        m.contextBefore = coalesce(m.contextBefore, w.contextBefore)
        m.contextLine   = coalesce(m.contextLine, w.contextLine)
        m.contextAfter  = coalesce(m.contextAfter, w.contextAfter)
        out[idx] = m
        return out
    } else {
        let seq = vsNextSeq(entries)
        let e = VocabEntry(
            id: vsNewId(entries), word: key, displayWord: display,
            translation: emptyToNull(w.translation), ipa: emptyToNull(w.ipa),
            sourceName: emptyToNull(w.sourceName), url: emptyToNull(w.url),
            contextBefore: emptyToNull(w.contextBefore),
            contextLine: emptyToNull(w.contextLine),
            contextAfter: emptyToNull(w.contextAfter),
            timesSeen: 1, firstSeq: seq, lastSeq: seq, notes: nil)
        return entries + [e]
    }
}

public func addEntry(_ entries: [VocabEntry], _ word: String) -> [VocabEntry] {
    addEntry(entries, Capture(word: word))
}

// --- deleteFrom[entries, id] : delete_vocab_entry (vocab.py:301) -------
public func deleteFrom(_ entries: [VocabEntry], _ id: Int) -> [VocabEntry] {
    entries.filter { $0.id != id }
}

// --- updateNotesIn (vocab.py:314) -------------------------------------
public func updateNotesIn(_ entries: [VocabEntry], id: Int, notes: String?) -> [VocabEntry] {
    entries.map { e in
        guard e.id == id else { return e }
        var m = e; m.notes = emptyToNull(notes); return m
    }
}

// --- updateEntry[entries, editingRow[id], fields] (vocab.py:343) -------
public let vsEditableFields: Set<String> = [
    "display_word", "translation", "ipa", "source_name",
    "url", "context_before", "context_line", "context_after"]

/// Apply an edit. Rejects unknown keys; rejects a display_word whose key would
/// change; "" → nil. On any rejection returns the list unchanged.
public func updateEntry(_ entries: [VocabEntry], id: Int, fields: [String: String]) -> [VocabEntry] {
    if !Set(fields.keys).isSubset(of: vsEditableFields) { return entries }
    guard let idx = entries.firstIndex(where: { $0.id == id }) else { return entries }
    let row = entries[idx]
    if let dw = fields["display_word"], normalise(dw).key != row.word { return entries }
    var out = entries
    var m = out[idx]
    for (k, v) in fields {
        let nv = emptyToNull(v)
        switch k {
        case "display_word":   if let nv { m.displayWord = nv }   // display kept; key unchanged
        case "translation":    m.translation = nv
        case "ipa":            m.ipa = nv
        case "source_name":    m.sourceName = nv
        case "url":            m.url = nv
        case "context_before": m.contextBefore = nv
        case "context_line":   m.contextLine = nv
        case "context_after":  m.contextAfter = nv
        default: break
        }
    }
    out[idx] = m
    return out
}

// --- autofillFields (vocab.py:411) — only-empty / never-overwrite -----
/// Compute the fill fields (translation/ipa) for entry `id` using the enrich
/// oracle and the borrowed language pair. Returns the fields to set (maybe empty).
public func autofillFields(_ entries: [VocabEntry], id: Int, lang: LangPair,
                           oracle: EnrichOracle) -> [String: String] {
    guard let row = entries.first(where: { $0.id == id }) else { return [:] }
    guard let fill = oracle.enrich(word: row.displayWord, source: lang.source, target: lang.target)
    else { return [:] }
    var out: [String: String] = [:]
    if (row.translation == nil || row.translation == ""), let t = emptyToNull(fill.translation) {
        out["translation"] = t
    }
    if (row.ipa == nil || row.ipa == ""), let i = emptyToNull(fill.ipa) {
        out["ipa"] = i
    }
    return out
}

// --- sort + filter (list_vocab order map + search; vocab.py:195) ------
public func sortEntries(_ entries: [VocabEntry], _ order: VocabSort) -> [VocabEntry] {
    switch order {
    case .alpha:  return entries.sorted { $0.word < $1.word }
    case .recent: return entries.sorted { $0.lastSeq > $1.lastSeq }
    case .oldest: return entries.sorted { $0.firstSeq < $1.firstSeq }
    }
}

func filterMatch(_ e: VocabEntry, _ filter: String?) -> Bool {
    guard let q = filter else { return true }
    let needle = q.lowercased()
    if needle.isEmpty { return true }
    if e.displayWord.lowercased().contains(needle) { return true }
    if (e.translation ?? "").lowercased().contains(needle) { return true }
    return false
}

public func applyFilter(_ entries: [VocabEntry], _ filter: String?) -> [VocabEntry] {
    entries.filter { filterMatch($0, filter) }
}

// --- practiseList (vocab.py:644) — shape to practice phrases -----------
public func practiseList(_ entries: [VocabEntry], filter: String?) -> [Phrase] {
    applyFilter(entries, filter).map {
        Phrase(text: $0.displayWord,
               translation: $0.translation ?? "",
               ipa: $0.ipa ?? "")
    }
}
