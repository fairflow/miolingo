import Foundation

// =====================================================================
// Domain types — ported from the CCS spec data representations
// (VocabFunctions.wl entry schema, PracticeSessionFunctions.wl phrase shape,
//  HelmRecovered.wl settings, StoryReaderRecovered.wl modes).
// =====================================================================

/// A practice phrase — exactly practiseList's / load_material's shape
/// `<|"text","translation","ipa"|>`.
public struct Phrase: Equatable, Codable, Sendable {
    public var text: String
    public var translation: String
    public var ipa: String
    public init(text: String, translation: String = "", ipa: String = "") {
        self.text = text; self.translation = translation; self.ipa = ipa
    }
    public static let empty = Phrase(text: "", translation: "", ipa: "")
}

/// list_vocab ordering (an Enum SYMBOL in the spec, not a string).
public enum VocabSort: String, CaseIterable, Codable, Sendable {
    case alpha, recent, oldest
}

/// The TTS engine setting (Helm.tts).
public enum TTSKind: String, CaseIterable, Codable, Sendable {
    case google, espeak, system   // `system` = AVSpeechSynthesizer (native default)
}

/// The ASR engine setting (Helm.asr).
public enum ASRKind: String, CaseIterable, Codable, Sendable, Identifiable {
    case system, whisper
    public var id: String { rawValue }
    public var label: String { self == .system ? "System (SFSpeech)" : "Whisper" }
}

/// The Whisper model size (Helm.asrModel) — only meaningful when asr == .whisper.
public enum WhisperModel: String, CaseIterable, Codable, Sendable, Identifiable {
    case tiny, base, small, medium
    public var id: String { rawValue }
}

public enum ReadingMode: String, CaseIterable, Codable, Sendable {
    case full, browse, practice
}

/// The vocab_entries row. `Null` (Python NULL) is modelled as `nil`.
/// `word` is the lowercased lookup key; `displayWord` keeps original case.
public struct VocabEntry: Equatable, Codable, Sendable, Identifiable {
    public var id: Int
    public var word: String            // lookup key (lowercased)
    public var displayWord: String
    public var translation: String?
    public var ipa: String?
    public var sourceName: String?
    public var url: String?
    public var contextBefore: String?
    public var contextLine: String?
    public var contextAfter: String?
    public var timesSeen: Int
    public var firstSeq: Int
    public var lastSeq: Int
    public var notes: String?

    public init(id: Int, word: String, displayWord: String,
                translation: String? = nil, ipa: String? = nil,
                sourceName: String? = nil, url: String? = nil,
                contextBefore: String? = nil, contextLine: String? = nil,
                contextAfter: String? = nil, timesSeen: Int = 1,
                firstSeq: Int = 1, lastSeq: Int = 1, notes: String? = nil) {
        self.id = id; self.word = word; self.displayWord = displayWord
        self.translation = translation; self.ipa = ipa
        self.sourceName = sourceName; self.url = url
        self.contextBefore = contextBefore; self.contextLine = contextLine
        self.contextAfter = contextAfter; self.timesSeen = timesSeen
        self.firstSeq = firstSeq; self.lastSeq = lastSeq; self.notes = notes
    }
}

/// A captured-word payload (addEntry's `w`): at least a word, optionally fields.
/// A bare string lifts to `Capture(word:)`.
public struct Capture: Equatable, Sendable {
    public var word: String
    public var translation: String?
    public var ipa: String?
    public var sourceName: String?
    public var url: String?
    public var contextBefore: String?
    public var contextLine: String?
    public var contextAfter: String?
    public init(word: String, translation: String? = nil, ipa: String? = nil,
                sourceName: String? = nil, url: String? = nil,
                contextBefore: String? = nil, contextLine: String? = nil,
                contextAfter: String? = nil) {
        self.word = word; self.translation = translation; self.ipa = ipa
        self.sourceName = sourceName; self.url = url
        self.contextBefore = contextBefore; self.contextLine = contextLine
        self.contextAfter = contextAfter
    }
}

/// One aligned phoneme segment (alignPhonemes / get_edit_operations).
public enum AlignOp: String, Codable, Sendable { case equal, sub, ins, del }
public struct AlignSeg: Equatable, Codable, Sendable, Identifiable {
    public var op: AlignOp
    public var target: String
    public var user: String
    public var id = UUID()
    public init(op: AlignOp, target: String, user: String) {
        self.op = op; self.target = target; self.user = user
    }
    private enum CodingKeys: String, CodingKey { case op, target, user }
}

/// evaluate's result — scoreDetail (comparison.py + the alignment): the numbers
/// AND the phoneme strings + the matched/unmatched alignment the UI colours.
public struct Score: Equatable, Codable, Sendable {
    public var exactMatch: Bool
    public var similarity: Double
    public var distance: Int
    public var user: String              // normalised user phonemes
    public var target: String            // normalised target phonemes
    public var alignment: [AlignSeg]
    public init(exactMatch: Bool, similarity: Double, distance: Int,
                user: String = "", target: String = "", alignment: [AlignSeg] = []) {
        self.exactMatch = exactMatch; self.similarity = similarity; self.distance = distance
        self.user = user; self.target = target; self.alignment = alignment
    }
}

/// A held recording (rec : none | recorded[audio]).
public struct Recording: Equatable, Sendable {
    public var audio: Data
    public init(audio: Data) { self.audio = audio }
}

/// The language pair Helm lends out (langRead → {source, target}).
public struct LangPair: Equatable, Sendable {
    public var source: String   // native language NAME, e.g. "English"
    public var target: String   // target language CODE, e.g. "fr"
    public init(source: String, target: String) { self.source = source; self.target = target }
}

/// A bulk-import request (importInto's `f`).
public struct ImportRequest: Sendable {
    public var contents: String
    public var expectedTarget: String?
    public init(contents: String, expectedTarget: String? = nil) {
        self.contents = contents; self.expectedTarget = expectedTarget
    }
}
