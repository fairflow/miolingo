import Foundation
import AVFoundation
import Speech
import MiolingoCore

// =====================================================================
// Native macOS implementations of the oracle seams (PORTING.md decisions
// 5–7). They satisfy the MiolingoCore protocols; the pure spec logic
// (comparePhonemes, evaluate) is untouched.
// =====================================================================

/// TTS via AVSpeechSynthesizer (offline, multilingual, no API key).
final class SystemTTS: TTSEngine, @unchecked Sendable {
    private let synth = AVSpeechSynthesizer()

    func speak(_ text: String, languageCode: String, rate: Double) {
        guard !text.trimmingCharacters(in: .whitespaces).isEmpty else { return }
        if synth.isSpeaking { synth.stopSpeaking(at: .immediate) }
        let u = AVSpeechUtterance(string: text)
        u.voice = Self.bestVoice(for: languageCode)
        // map wpm-ish (espeak ~250) onto AVSpeech's 0...1 rate around the default.
        let mapped = Float(rate) / 500.0
        u.rate = min(max(mapped, AVSpeechUtteranceMinimumSpeechRate),
                     AVSpeechUtteranceMaximumSpeechRate)
        synth.speak(u)
    }

    /// Exact locale, else any installed voice whose language shares the prefix
    /// (e.g. "fr"), else the system default — so it always speaks something.
    static func bestVoice(for code: String) -> AVSpeechSynthesisVoice? {
        if let v = AVSpeechSynthesisVoice(language: code) { return v }
        let prefix = String(code.prefix(2)).lowercased()
        if let v = AVSpeechSynthesisVoice.speechVoices()
            .first(where: { $0.language.lowercased().hasPrefix(prefix) }) { return v }
        return AVSpeechSynthesisVoice(language: "en-US")
    }

    func stop() { synth.stopSpeaking(at: .immediate) }
}

/// Live diagnostics for one recognise() call — surfaced in Settings so the
/// "nothing recognised" failure mode is never a black box. Captured on every
/// call (success or failure).
struct ScorerDiagnostics: Sendable {
    var authStatus = "—"          // human-readable SFSpeechRecognizer.authorizationStatus()
    var recogniserExists = false  // SFSpeechRecognizer(locale:) returned non-nil
    var isAvailable = false       // recogniser.isAvailable
    var supportsOnDevice = false  // recogniser.supportsOnDeviceRecognition
    var usedOnDevice = false      // which path the last attempt actually used
    var lastAudioBytes = 0        // size of the WAV handed to the recogniser
    var lastError = ""            // recogniser error description, if any
    var lastHeardText = ""        // raw transcript before espeak (empty ⇒ true miss)
}

/// recognisePhonemes via SFSpeechRecognizer (on-device) → recognised text →
/// espeak IPA (the spec pipeline ASR→text→phonemes). Returns "" if
/// unavailable/unauthorised, which the pure scorer treats as a miss.
final class SystemScorer: SpeechScorer, @unchecked Sendable {
    private var activeTask: SFSpeechRecognitionTask?   // retained while running (calls are serial)

    /// Last call's diagnostics, readable from the UI thread.
    private let diagLock = NSLock()
    private var _diag = ScorerDiagnostics()
    var diagnostics: ScorerDiagnostics {
        diagLock.lock(); defer { diagLock.unlock() }; return _diag
    }
    private func setDiag(_ mutate: (inout ScorerDiagnostics) -> Void) {
        diagLock.lock(); mutate(&_diag); diagLock.unlock()
    }

    /// Fire the one-time authorization prompt at launch (fire-and-forget).
    static func requestAuthorization() {
        SFSpeechRecognizer.requestAuthorization { _ in }
    }

    /// Request authorization and await the result — used to retry on first use
    /// when the launch-time status was still `.notDetermined`.
    private static func awaitAuthorization() async -> SFSpeechRecognizerAuthorizationStatus {
        await withCheckedContinuation { cont in
            SFSpeechRecognizer.requestAuthorization { cont.resume(returning: $0) }
        }
    }

    static func describe(_ s: SFSpeechRecognizerAuthorizationStatus) -> String {
        switch s {
        case .authorized:    return "authorized"
        case .denied:        return "denied"
        case .restricted:    return "restricted"
        case .notDetermined: return "notDetermined"
        @unknown default:    return "unknown(\(s.rawValue))"
        }
    }

    func recognise(audio: Data, languageCode: String) async -> String {
        let text = await transcribe(audio: audio, languageCode: languageCode)
        guard !text.isEmpty else { return "" }
        // ASR text → phonemes (espeak), matching the target language voice.
        return Espeak.ipa(text, voice: languageCode) ?? text
    }

    private func transcribe(audio: Data, languageCode: String) async -> String {
        setDiag { $0 = ScorerDiagnostics(); $0.lastAudioBytes = audio.count }

        // Speech Recognition is a SEPARATE TCC permission from the microphone.
        // If the launch prompt never resolved (notDetermined — common for an
        // unsigned/ad-hoc build whose identity changed), request now and await.
        var status = SFSpeechRecognizer.authorizationStatus()
        if status == .notDetermined { status = await Self.awaitAuthorization() }
        setDiag { $0.authStatus = Self.describe(status) }
        guard status == .authorized else { return "" }

        let locale = Locale(identifier: bcp47(languageCode))
        let recogniser = SFSpeechRecognizer(locale: locale)
        setDiag {
            $0.recogniserExists = recogniser != nil
            $0.isAvailable = recogniser?.isAvailable ?? false
            $0.supportsOnDevice = recogniser?.supportsOnDeviceRecognition ?? false
        }
        guard let recogniser, recogniser.isAvailable else { return "" }

        let url = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString + ".wav")
        guard (try? audio.write(to: url)) != nil else { return "" }
        defer { try? FileManager.default.removeItem(at: url) }

        // Prefer on-device when supported; if that yields nothing or errors,
        // retry via the server path (the on-device model may be absent/partial).
        if recogniser.supportsOnDeviceRecognition {
            let onDev = await runTask(recogniser, url: url, onDevice: true)
            if !onDev.text.isEmpty { return onDev.text }
            // on-device produced nothing — try server as a fallback
            let server = await runTask(recogniser, url: url, onDevice: false)
            return server.text
        } else {
            let server = await runTask(recogniser, url: url, onDevice: false)
            return server.text
        }
    }

    private func runTask(_ recogniser: SFSpeechRecognizer, url: URL, onDevice: Bool)
        async -> (text: String, error: String) {
        let request = SFSpeechURLRecognitionRequest(url: url)
        request.requiresOnDeviceRecognition = onDevice
        setDiag { $0.usedOnDevice = onDevice }
        return await withCheckedContinuation { cont in
            var resumed = false
            var best = ""
            func finish(_ s: String, _ err: String) {
                if !resumed {
                    resumed = true; activeTask = nil
                    setDiag {
                        if !s.isEmpty { $0.lastHeardText = s }
                        if !err.isEmpty { $0.lastError = err }
                    }
                    cont.resume(returning: (s, err))
                }
            }
            activeTask = recogniser.recognitionTask(with: request) { result, error in
                if let result {
                    best = result.bestTranscription.formattedString   // keep latest partial
                    if result.isFinal { finish(best, "") }
                }
                if let error { finish(best, error.localizedDescription) }  // keep what we heard
            }
        }
    }
}

/// Map a Helm target code to a best-effort BCP-47 locale for the recogniser.
func bcp47(_ code: String) -> String {
    let map = ["en": "en-US", "fr": "fr-FR", "pt": "pt-BR",
               "de": "de-DE", "es": "es-ES", "it": "it-IT"]
    return map[code] ?? code
}
