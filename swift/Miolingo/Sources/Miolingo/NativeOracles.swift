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

/// recognisePhonemes via SFSpeechRecognizer (on-device) → recognised text →
/// espeak IPA (the spec pipeline ASR→text→phonemes). Returns "" if
/// unavailable/unauthorised, which the pure scorer treats as a miss.
final class SystemScorer: SpeechScorer, @unchecked Sendable {
    static func requestAuthorization() {
        SFSpeechRecognizer.requestAuthorization { _ in }
    }

    func recognise(audio: Data, languageCode: String) async -> String {
        let text = await transcribe(audio: audio, languageCode: languageCode)
        guard !text.isEmpty else { return "" }
        // ASR text → phonemes (espeak), matching the target language voice.
        return Espeak.ipa(text, voice: languageCode) ?? text
    }

    private func transcribe(audio: Data, languageCode: String) async -> String {
        guard SFSpeechRecognizer.authorizationStatus() == .authorized else { return "" }
        let locale = Locale(identifier: bcp47(languageCode))
        guard let recogniser = SFSpeechRecognizer(locale: locale),
              recogniser.isAvailable else { return "" }
        let url = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString + ".wav")
        guard (try? audio.write(to: url)) != nil else { return "" }
        defer { try? FileManager.default.removeItem(at: url) }
        let request = SFSpeechURLRecognitionRequest(url: url)
        // prefer on-device; fall back to server if the locale has no on-device model
        request.requiresOnDeviceRecognition = recogniser.supportsOnDeviceRecognition
        return await withCheckedContinuation { cont in
            var resumed = false
            func finish(_ s: String) { if !resumed { resumed = true; cont.resume(returning: s) } }
            recogniser.recognitionTask(with: request) { result, error in
                if let result, result.isFinal {
                    finish(result.bestTranscription.formattedString)
                } else if error != nil {
                    finish("")
                }
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
