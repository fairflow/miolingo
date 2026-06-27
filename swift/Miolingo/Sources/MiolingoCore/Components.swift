import Foundation

// =====================================================================
// Components — the CCS agents (spec/*Recovered.wl) as pure value types.
// Each method is a PORT; it returns/produces the successor state, mirroring
// the .wl transitions one-for-one. The restricted cross-component channels
// (vocabUpsert / goPractice / langRead / vocabRead) are wired by AppModel —
// they are the τ's the walk harness auto-fires.
// =====================================================================

// --- PracticeSession (PS / PSActive) — PracticeSessionRecovered.wl -----
public struct PracticeSession: Sendable {
    public var phrases: [Phrase]
    public var pos: Int
    public var rec: Recording?
    public var res: Score?

    public init(phrases: [Phrase] = [], pos: Int = 0,
                rec: Recording? = nil, res: Score? = nil) {
        self.phrases = phrases; self.pos = pos; self.rec = rec; self.res = res
    }

    public var isEmpty: Bool { phrases.isEmpty }
    public var canNext: Bool { pos < phrases.count - 1 }
    public var canPrev: Bool { pos > 0 }
    public var view: SessionView { sessionView(phrases: phrases, pos: pos, rec: rec, res: res) }

    // load_material / load_vocab / load_filtered (queue := ph, pos 0, cleared)
    public mutating func load(_ ph: [Phrase]) { phrases = ph; pos = 0; rec = nil; res = nil }
    // clear_material
    public mutating func clearMaterial() { phrases = []; pos = 0; rec = nil; res = nil }
    // select_item(i) — guarded so an out-of-range index is a no-op
    public mutating func select(_ i: Int) { pos = selectPos(phrases, i, pos); rec = nil; res = nil }
    // recording_made(audio) — only when no recording held
    public mutating func recordingMade(_ audio: Data) {
        guard rec == nil else { return }
        rec = Recording(audio: audio); res = nil
    }
    // clear_recording
    public mutating func clearRecording() { rec = nil; res = nil }
    // attempt_made — score the held recording against the current target (needs ASR result)
    public mutating func score(recognisedPhonemes: String, method: ScoringMethod = .editDistance) {
        guard rec != nil else { return }
        res = evaluate(target: targetOf(phrases, pos), recognisedPhonemes: recognisedPhonemes, method: method)
    }
    // next_item_requested / prev_item_requested
    public mutating func next() { if canNext { pos += 1; rec = nil; res = nil } }
    public mutating func prev() { if canPrev { pos -= 1; rec = nil; res = nil } }
    // capture_vocab — only when scored; payload defaults to the current item text
    public var captureWord: String? { res != nil ? targetOf(phrases, pos).text : nil }
}

// --- Helm (session / language settings) — HelmRecovered.wl ------------
public struct Helm: Sendable {
    public var source: String
    public var target: String
    public var tts: TTSKind
    public var speed: Int
    public var asr: ASRKind
    public var asrModel: WhisperModel

    public init(source: String = "English", target: String = "fr",
                tts: TTSKind = .system, speed: Int = 250,
                asr: ASRKind = .system, asrModel: WhisperModel = .base) {
        self.source = source; self.target = target; self.tts = tts; self.speed = speed
        self.asr = asr; self.asrModel = asrModel
    }

    public var view: HelmView {
        helmView(source: source, target: target, tts: tts, speed: speed, asr: asr, asrModel: asrModel)
    }
    public var langPair: LangPair { LangPair(source: source, target: target) }  // langRead
    public var showsSpeed: Bool { tts == .espeak }      // the wpm slider guard
    public var showsAsrModel: Bool { asr == .whisper }  // model size only for whisper

    public mutating func setSource(_ s: String) { source = s }
    public mutating func setTarget(_ t: String) { target = t }
    public mutating func setTTS(_ e: TTSKind) { tts = e }
    public mutating func setSpeed(_ w: Int) { if tts == .espeak { speed = w } }
    public mutating func setAsr(_ a: ASRKind) { asr = a }
    public mutating func setAsrModel(_ m: WhisperModel) { if asr == .whisper { asrModel = m } }
}

// --- VocabTable (the external store) — VocabTableRecovered.wl ----------
// Owns the persisted collection. The SQLite store mirrors `entries`.
public struct VocabTable: Sendable {
    public var entries: [VocabEntry]
    public init(entries: [VocabEntry] = []) { self.entries = entries }

    public func read() -> [VocabEntry] { entries }                 // vocabRead
    public mutating func upsert(_ w: Capture) { entries = addEntry(entries, w) }     // vocabUpsert
    public mutating func upsert(_ word: String) { entries = addEntry(entries, word) }
    public mutating func importBulk(_ f: ImportRequest) { entries = importInto(entries, f) } // vocabImport
    public mutating func remove(_ id: Int) { entries = deleteFrom(entries, id) }     // vocabRemove
    public mutating func amend(id: Int, fields: [String: String]) {                  // vocabAmend
        entries = updateEntry(entries, id: id, fields: fields)
    }
    public mutating func amendNotes(id: Int, notes: String?) {
        entries = updateNotesIn(entries, id: id, notes: notes)
    }
}

// --- Vocab (the vocabulary tab UI params) — VocabRecovered.wl ----------
// Holds ONLY the UI params; the collection lives in VocabTable, read fresh.
public struct Vocab: Sendable {
    public var signedIn: Bool
    public var sort: VocabSort
    public var filter: String?         // none | filterBy[q]
    public var editing: Int?           // none | editingRow[id]
    public var opened: Bool            // open_vocab taken (in the tab)

    public init(signedIn: Bool = true, sort: VocabSort = .alpha,
                filter: String? = nil, editing: Int? = nil, opened: Bool = false) {
        self.signedIn = signedIn; self.sort = sort
        self.filter = filter; self.editing = editing; self.opened = opened
    }

    public mutating func openVocab() { opened = true }
    public mutating func setSort(_ s: VocabSort) { sort = s }
    public mutating func setFilter(_ q: String?) { filter = (q?.isEmpty ?? true) ? nil : q }
    public mutating func beginEdit(_ id: Int) { editing = id }
    public mutating func cancelEdit() { editing = nil }
    public mutating func endEdit() { editing = nil }

    public func view(entries: [VocabEntry]) -> VocabViewModel {
        vocabView(signedIn: signedIn, entries: entries, sort: sort, filter: filter, editing: editing)
    }
}

// --- StoryReader — StoryReaderRecovered.wl ----------------------------
public struct StoryReader: Sendable {
    public var scene: Int
    public var pos: Int
    public var mode: ReadingMode
    public var rec: Recording?
    public var res: Score?
    public let library: StoryLibrary

    public init(scene: Int = 0, pos: Int = 0, mode: ReadingMode = .browse,
                rec: Recording? = nil, res: Score? = nil,
                library: StoryLibrary = FixtureStoryLibrary()) {
        self.scene = scene; self.pos = pos; self.mode = mode
        self.rec = rec; self.res = res; self.library = library
    }

    public var phrases: [Phrase] { library.scene(scene) }
    public var canNext: Bool { pos < phrases.count - 1 }
    public var canPrev: Bool { pos > 0 }
    public var view: StoryView {
        storyView(scene: scene, pos: pos, mode: mode, rec: rec, res: res, library: library)
    }

    // set_mode — PRESERVES (scene,pos), clears rec/res
    public mutating func setMode(_ m: ReadingMode) { mode = m; rec = nil; res = nil }
    // select_scene — new scene ⇒ pos resets to 0
    public mutating func selectScene(_ s: Int) { scene = s; pos = 0; rec = nil; res = nil }
    // story_select_item(i) — guarded no-op out of range
    public mutating func selectItem(_ i: Int) { pos = selectPos(phrases, i, pos); rec = nil; res = nil }
    public mutating func next() { if canNext { pos += 1; rec = nil; res = nil } }
    public mutating func prev() { if canPrev { pos -= 1; rec = nil; res = nil } }
    // practice-mode loop
    public mutating func recordingMade(_ audio: Data) {
        guard mode == .practice, rec == nil else { return }
        rec = Recording(audio: audio); res = nil
    }
    public mutating func clearRecording() { rec = nil; res = nil }
    public mutating func score(recognisedPhonemes: String, method: ScoringMethod = .editDistance) {
        guard rec != nil else { return }
        res = evaluate(target: targetOf(phrases, pos), recognisedPhonemes: recognisedPhonemes, method: method)
    }
    public var captureWord: String? { res != nil ? targetOf(phrases, pos).text : nil }
}
