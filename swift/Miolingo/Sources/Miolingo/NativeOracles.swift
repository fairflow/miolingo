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
        let u = AVSpeechUtterance(string: text)
        u.voice = AVSpeechSynthesisVoice(language: languageCode)
            ?? AVSpeechSynthesisVoice(language: "en-US")
        // map wpm-ish (espeak ~250) onto AVSpeech's 0...1 rate around the default.
        let mapped = Float(rate) / 500.0
        u.rate = min(max(mapped, AVSpeechUtteranceMinimumSpeechRate),
                     AVSpeechUtteranceMaximumSpeechRate)
        synth.speak(u)
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
        let locale = Locale(identifier: bcp47(languageCode))
        guard let recogniser = SFSpeechRecognizer(locale: locale),
              recogniser.isAvailable else { return "" }
        let url = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString + ".wav")
        guard (try? audio.write(to: url)) != nil else { return "" }
        defer { try? FileManager.default.removeItem(at: url) }
        let request = SFSpeechURLRecognitionRequest(url: url)
        request.requiresOnDeviceRecognition = true
        return await withCheckedContinuation { cont in
            var resumed = false
            recogniser.recognitionTask(with: request) { result, error in
                if let result, result.isFinal {
                    if !resumed { resumed = true
                        cont.resume(returning: result.bestTranscription.formattedString) }
                } else if error != nil {
                    if !resumed { resumed = true; cont.resume(returning: "") }
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
