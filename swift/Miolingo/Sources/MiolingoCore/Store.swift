import Foundation
import SQLite3

// =====================================================================
// Store — the local-only SQLite database (decision 3/4 in PORTING.md).
// Holds the persisted vocab collection (VocabTable's `entries`), Helm's
// settings, and the seeded `languages` reference table. Created on first
// launch at ~/Library/Application Support/Miolingo/miolingo.sqlite from the
// embedded schema/seed, so it ships WITH the app yet stays writable.
// =====================================================================

private let SQLITE_TRANSIENT = unsafeBitCast(-1, to: sqlite3_destructor_type.self)

public final class Database {
    private var db: OpaquePointer?
    public let path: String

    public init(path: String) throws {
        self.path = path
        try FileManager.default.createDirectory(
            atPath: (path as NSString).deletingLastPathComponent,
            withIntermediateDirectories: true)
        if sqlite3_open(path, &db) != SQLITE_OK {
            throw StoreError.open(String(cString: sqlite3_errmsg(db)))
        }
        try migrate()
        seedLanguages()
        seedDefaultSettings()
    }

    /// Default on-disk location, shared by the app.
    public static func defaultPath() -> String {
        let base = FileManager.default.urls(for: .applicationSupportDirectory,
                                            in: .userDomainMask).first!
        return base.appendingPathComponent("Miolingo/miolingo.sqlite").path
    }

    deinit { sqlite3_close(db) }

    public enum StoreError: Error { case open(String), exec(String), prepare(String) }

    private func exec(_ sql: String) throws {
        var err: UnsafeMutablePointer<CChar>?
        if sqlite3_exec(db, sql, nil, nil, &err) != SQLITE_OK {
            let msg = err.map { String(cString: $0) } ?? "unknown"
            sqlite3_free(err)
            throw StoreError.exec(msg)
        }
    }

    private func migrate() throws {
        try exec("""
        CREATE TABLE IF NOT EXISTS vocab_entries (
          id INTEGER PRIMARY KEY,
          word TEXT NOT NULL,
          display_word TEXT NOT NULL,
          translation TEXT, ipa TEXT, source_name TEXT, url TEXT,
          context_before TEXT, context_line TEXT, context_after TEXT,
          times_seen INTEGER NOT NULL DEFAULT 1,
          first_seq INTEGER NOT NULL DEFAULT 1,
          last_seq INTEGER NOT NULL DEFAULT 1,
          notes TEXT
        );
        CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE IF NOT EXISTS languages (code TEXT PRIMARY KEY, name TEXT);
        """)
    }

    private func seedLanguages() {
        for (code, name) in helmTrainingNames {
            try? run("INSERT OR IGNORE INTO languages(code,name) VALUES(?,?)",
                     [.text(code), .text(name)])
        }
    }

    private func seedDefaultSettings() {
        let defaults: [(String, String)] = [
            ("source", "English"), ("target", "fr"), ("tts", "system"), ("speed", "250")]
        for (k, v) in defaults {
            try? run("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)",
                     [.text(k), .text(v)])
        }
    }

    // --- a tiny bind/step helper -------------------------------------
    enum Bind { case text(String), int(Int), null, optText(String?) }

    func run(_ sql: String, _ binds: [Bind] = []) throws {
        var stmt: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &stmt, nil) == SQLITE_OK else {
            throw StoreError.prepare(String(cString: sqlite3_errmsg(db)))
        }
        defer { sqlite3_finalize(stmt) }
        bind(stmt, binds)
        if sqlite3_step(stmt) != SQLITE_DONE {
            throw StoreError.exec(String(cString: sqlite3_errmsg(db)))
        }
    }

    private func bind(_ stmt: OpaquePointer?, _ binds: [Bind]) {
        for (i, b) in binds.enumerated() {
            let idx = Int32(i + 1)
            switch b {
            case .text(let s): sqlite3_bind_text(stmt, idx, s, -1, SQLITE_TRANSIENT)
            case .int(let n):  sqlite3_bind_int64(stmt, idx, Int64(n))
            case .null:        sqlite3_bind_null(stmt, idx)
            case .optText(let s):
                if let s { sqlite3_bind_text(stmt, idx, s, -1, SQLITE_TRANSIENT) }
                else { sqlite3_bind_null(stmt, idx) }
            }
        }
    }

    private func col(_ stmt: OpaquePointer?, _ i: Int32) -> String? {
        guard let c = sqlite3_column_text(stmt, i) else { return nil }
        return String(cString: c)
    }

    // --- vocab_entries -----------------------------------------------
    public func loadEntries() -> [VocabEntry] {
        var stmt: OpaquePointer?
        let sql = """
        SELECT id, word, display_word, translation, ipa, source_name, url,
               context_before, context_line, context_after,
               times_seen, first_seq, last_seq, notes FROM vocab_entries
        """
        guard sqlite3_prepare_v2(db, sql, -1, &stmt, nil) == SQLITE_OK else { return [] }
        defer { sqlite3_finalize(stmt) }
        var out: [VocabEntry] = []
        while sqlite3_step(stmt) == SQLITE_ROW {
            out.append(VocabEntry(
                id: Int(sqlite3_column_int64(stmt, 0)),
                word: col(stmt, 1) ?? "", displayWord: col(stmt, 2) ?? "",
                translation: col(stmt, 3), ipa: col(stmt, 4),
                sourceName: col(stmt, 5), url: col(stmt, 6),
                contextBefore: col(stmt, 7), contextLine: col(stmt, 8),
                contextAfter: col(stmt, 9),
                timesSeen: Int(sqlite3_column_int64(stmt, 10)),
                firstSeq: Int(sqlite3_column_int64(stmt, 11)),
                lastSeq: Int(sqlite3_column_int64(stmt, 12)),
                notes: col(stmt, 13)))
        }
        return out
    }

    /// Persist the whole collection (replace-all — VocabTable is the source of truth).
    public func saveEntries(_ entries: [VocabEntry]) {
        try? exec("BEGIN")
        try? exec("DELETE FROM vocab_entries")
        for e in entries {
            try? run("""
            INSERT INTO vocab_entries
              (id, word, display_word, translation, ipa, source_name, url,
               context_before, context_line, context_after,
               times_seen, first_seq, last_seq, notes)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, [.int(e.id), .text(e.word), .text(e.displayWord),
                  .optText(e.translation), .optText(e.ipa), .optText(e.sourceName),
                  .optText(e.url), .optText(e.contextBefore), .optText(e.contextLine),
                  .optText(e.contextAfter), .int(e.timesSeen), .int(e.firstSeq),
                  .int(e.lastSeq), .optText(e.notes)])
        }
        try? exec("COMMIT")
    }

    // --- settings (Helm) ---------------------------------------------
    public func loadHelm() -> Helm {
        var s = "English", t = "fr", tts = "system", speed = "250"
        var stmt: OpaquePointer?
        if sqlite3_prepare_v2(db, "SELECT key, value FROM settings", -1, &stmt, nil) == SQLITE_OK {
            while sqlite3_step(stmt) == SQLITE_ROW {
                let k = col(stmt, 0) ?? "", v = col(stmt, 1) ?? ""
                switch k {
                case "source": s = v; case "target": t = v
                case "tts": tts = v; case "speed": speed = v
                default: break
                }
            }
        }
        sqlite3_finalize(stmt)
        return Helm(source: s, target: t,
                    tts: TTSKind(rawValue: tts) ?? .system, speed: Int(speed) ?? 250)
    }

    public func saveHelm(_ h: Helm) {
        let kv: [(String, String)] = [
            ("source", h.source), ("target", h.target),
            ("tts", h.tts.rawValue), ("speed", String(h.speed))]
        for (k, v) in kv {
            try? run("INSERT INTO settings(key,value) VALUES(?,?) " +
                     "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                     [.text(k), .text(v)])
        }
    }

    public func languages() -> [(code: String, name: String)] {
        var stmt: OpaquePointer?
        var out: [(String, String)] = []
        if sqlite3_prepare_v2(db, "SELECT code, name FROM languages ORDER BY name", -1, &stmt, nil) == SQLITE_OK {
            while sqlite3_step(stmt) == SQLITE_ROW {
                out.append((col(stmt, 0) ?? "", col(stmt, 1) ?? ""))
            }
        }
        sqlite3_finalize(stmt)
        return out
    }
}
