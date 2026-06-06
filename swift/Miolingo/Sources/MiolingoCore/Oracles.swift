import Foundation

// =====================================================================
// Oracle seams — the "outside the model" services. The spec is parametric in
// these (uninterpreted stubs); promoting a stub to a live service keeps the
// port signature invariant (spec/docs/co-development.md). Native macOS
// implementations (AVSpeechSynthesizer / SFSpeechRecognizer) live in the app
// target; espeak (a subprocess) and the null stubs live here.
// =====================================================================

/// enrichOracle: word + (source,target) → translation + IPA. Either may be nil.
public protocol EnrichOracle: Sendable {
    func enrich(word: String, source: String, target: String) -> (translation: String?, ipa: String?)?
}

/// TTS: speak `text` in the target language.
public protocol TTSEngine: Sendable {
    func speak(_ text: String, languageCode: String, rate: Double)
    func stop()
}

/// recognisePhonemes: audio + target language → recognised phoneme/text string.
public protocol SpeechScorer: Sendable {
    func recognise(audio: Data, languageCode: String) async -> String
}

// --- espeak grapheme→phoneme (spec/g2p.wl) ----------------------------
public enum Espeak {
    public static let binary: String = {
        for p in ["/opt/local/bin/espeak", "/usr/bin/espeak", "/usr/local/bin/espeak"]
        where FileManager.default.isExecutableFile(atPath: p) { return p }
        return "espeak"
    }()

    public static var available: Bool {
        run(["--version"]) != nil
    }

    static func run(_ args: [String]) -> String? {
        let proc = Process()
        proc.executableURL = URL(fileURLWithPath: binary)
        proc.arguments = args
        let out = Pipe(); proc.standardOutput = out
        proc.standardError = Pipe()
        do { try proc.run() } catch { return nil }
        let data = out.fileHandleForReading.readDataToEndOfFile()
        proc.waitUntilExit()
        if proc.terminationStatus != 0 { return nil }
        return String(data: data, encoding: .utf8)?
            .trimmingCharacters(in: .whitespacesAndNewlines)
    }

    /// IPA transcription with stress marks stripped (matches the spec ipa style).
    public static func ipa(_ word: String, voice: String = "en") -> String? {
        guard let raw = run(["-q", "--ipa", "-v", voice, word]) else { return nil }
        return raw.replacingOccurrences(of: "ˈ", with: "")
                  .replacingOccurrences(of: "ˌ", with: "")
                  .trimmingCharacters(in: .whitespacesAndNewlines)
    }
}

/// enrichOracle backed by espeak for IPA (translation deferred — see PORTING.md).
public struct EspeakEnrichOracle: EnrichOracle {
    public init() {}
    public func enrich(word: String, source: String, target: String)
        -> (translation: String?, ipa: String?)? {
        let ipa = Espeak.ipa(word, voice: target)
        return (translation: nil, ipa: ipa)
    }
}

/// A no-op enrich oracle (used when no provider is available).
public struct NullEnrichOracle: EnrichOracle {
    public init() {}
    public func enrich(word: String, source: String, target: String)
        -> (translation: String?, ipa: String?)? { nil }
}

/// enrichOracle backed by an offline lexicon for translation (target word →
/// native meaning) + espeak for IPA. The lexicon is a bundled seed (lexicon.json);
/// swapping in the Apple Translation framework or an API keeps this signature.
/// `table` is keyed [targetCode: [lowercasedWord: translation]].
public struct DictionaryEnrichOracle: EnrichOracle {
    public let table: [String: [String: String]]
    public let useEspeakIPA: Bool
    public init(table: [String: [String: String]], useEspeakIPA: Bool = true) {
        self.table = table; self.useEspeakIPA = useEspeakIPA
    }
    public func enrich(word: String, source: String, target: String)
        -> (translation: String?, ipa: String?)? {
        let tr = table[target]?[word.lowercased()]
        let ipa = useEspeakIPA ? Espeak.ipa(word, voice: target) : nil
        if tr == nil && ipa == nil { return nil }
        return (tr, ipa)
    }
}
