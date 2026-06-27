import Foundation
import MiolingoCore

#if WHISPERKIT
import WhisperKit

// =====================================================================
// WhisperScorer — an OPT-IN SpeechScorer backed by WhisperKit (Core ML
// Whisper). Same pipeline shape as SystemScorer: WAV → text → espeak IPA,
// so the pure scorer/alignment in MiolingoCore is unchanged.
//
// TRADE-OFF (see report + Package.swift): WhisperKit is an external SwiftPM
// dependency (network at `swift build` resolve) and downloads a Core ML model
// from Hugging Face on first use. This breaks the zero-dependency / offline
// build invariant, so the default engine stays SystemScorer (SFSpeech) and
// this is reachable only via Settings → Recognition → ASR engine = whisper.
//
// The whole type is gated on the WHISPERKIT compile flag: drop the WhisperKit
// dependency from Package.swift and the app still compiles (offline build),
// with `whisperAvailable == false` so the engine picker degrades gracefully.
// =====================================================================

/// Live status of the last Whisper recognise() call — mirrors ScorerDiagnostics
/// shape so Settings can surface either engine.
public struct WhisperDiagnostics: Sendable {
    public init() {}
    public var modelLoaded = false
    public var lastAudioBytes = 0
    public var lastAudioSeconds = 0.0
    public var lastHeardText = ""
    public var lastError = ""
}

public final class WhisperScorer: SpeechScorer, @unchecked Sendable {
    /// Whisper model name (Hugging Face short id). "base" is the small, fast,
    /// multilingual default; "small" is more accurate but a larger download.
    private let model: String

    private let lock = NSLock()
    private var pipe: WhisperKit?         // loaded lazily, kept warm across calls
    private var _diag = WhisperDiagnostics()

    public var diagnostics: WhisperDiagnostics {
        lock.lock(); defer { lock.unlock() }; return _diag
    }
    private func setDiag(_ mutate: (inout WhisperDiagnostics) -> Void) {
        lock.lock(); mutate(&_diag); lock.unlock()
    }

    public init(model: String = "base") { self.model = model }

    /// Whisper auto-detects from the audio, but we constrain it to the known
    /// target language for single short words (WhisperKit wants the 2-letter code).
    public func recognise(audio: Data, languageCode: String, hint: String) async -> String {
        setDiag {
            $0.lastAudioBytes = audio.count
            $0.lastAudioSeconds = wavDurationSeconds(bytes: audio.count)
            $0.lastError = ""
            $0.lastHeardText = ""
        }

        let url = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString + ".wav")
        guard (try? audio.write(to: url)) != nil else {
            setDiag { $0.lastError = "could not write temp WAV" }
            return ""
        }
        defer { try? FileManager.default.removeItem(at: url) }

        do {
            let kit = try await loadPipe()
            // NB: the `hint` (target text) is deliberately NOT used. An earlier
            // version's comment claimed it biased the decoder, but the wiring was
            // dead (promptTokens: nil) — and post-honesty-fix we don't WANT to
            // feed the grader the answer. Constrain only the language.
            let options = DecodingOptions(
                task: .transcribe,
                language: String(languageCode.prefix(2)).lowercased()
            )
            let results = try await kit.transcribe(audioPath: url.path, decodeOptions: options)
            let text = results.map(\.text).joined(separator: " ")
                .trimmingCharacters(in: .whitespacesAndNewlines)
            setDiag { $0.lastHeardText = text }
            guard !text.isEmpty else { return "" }
            return Espeak.ipa(text, voice: languageCode) ?? text
        } catch {
            setDiag { $0.lastError = error.localizedDescription }
            return ""
        }
    }

    /// Load (and cache) the WhisperKit pipeline. First call triggers the Core ML
    /// model download — slow and requires network; later calls reuse it. The lock
    /// is only ever held around synchronous cache reads/writes, never across the
    /// `await` (which would be unsafe under strict concurrency).
    private func loadPipe() async throws -> WhisperKit {
        if let existing = cachedPipe() { return existing }
        let kit = try await WhisperKit(model: model)
        storePipe(kit)
        return kit
    }
    private func cachedPipe() -> WhisperKit? {
        lock.lock(); defer { lock.unlock() }; return pipe
    }
    private func storePipe(_ kit: WhisperKit) {
        lock.lock(); pipe = kit; _diag.modelLoaded = true; lock.unlock()
    }
}

/// True when the app was built with the WhisperKit dependency present.
public let whisperAvailable = true

#else

// Offline build: WhisperKit dependency absent. The picker still appears but the
// whisper option is disabled; AppModel falls back to SystemScorer.
public let whisperAvailable = false

#endif
