import Foundation

// =====================================================================
// vocabView — the read-only projection (spec/VocabFunctions.wl). What the
// vocabulary pane renders: filtered + sorted entries plus the UI params.
// =====================================================================

public struct VocabViewModel: Equatable, Sendable {
    public var signedIn: Bool
    public var count: Int
    public var sort: VocabSort
    public var filter: String?
    public var editing: Int?          // editingRow id, or nil
    public var entries: [VocabEntry]  // filtered + sorted
}

public func vocabView(signedIn: Bool, entries: [VocabEntry],
                      sort: VocabSort, filter: String?, editing: Int?) -> VocabViewModel {
    VocabViewModel(signedIn: signedIn, count: entries.count,
                   sort: sort, filter: filter, editing: editing,
                   entries: sortEntries(applyFilter(entries, filter), sort))
}
