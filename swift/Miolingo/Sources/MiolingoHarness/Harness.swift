import Foundation
import MiolingoCore
import MiolingoOracles

// =====================================================================
// MiolingoHarness — the CLOSED-LOOP speech test (the spec Speaker agent's
// round-trip law, deployed on the real engines):
//
//     TTS (espeak -w) GENERATES audio for a known word
//       → the ASR engine transcribes it
//       → espeak G2P turns the transcript into phonemes
//       → the pure scorer (evaluate) compares to the target IPA.
//
// Law under test:  speak(w) then recognise should score HIGH against w's own
// IPA, and LOWER against a different word's IPA. No microphone, no GUI.
// The CCS twin is spec/Speaker.wl + spec/tests/speaker_test.wls.
//
// Usage:  swift run MiolingoHarness [--whisper [model]] [--lang fr]
//   default engine: SFSpeech (SKIPs if the process lacks the Speech
//   Recognition TCC grant); --whisper uses WhisperKit (downloads the model
//   on first run — network needed once).
// Exit code: number of FAILED assertions (SKIPs don't fail); 3 = watchdog.
// =====================================================================

/// Generate a WAV for `text` with espeak (the TTS side of the loop).
func synthAudio(_ text: String, lang: String) -> Data? {
    let url = FileManager.default.temporaryDirectory
        .appendingPathComponent("harness-\(UUID().uuidString).wav")
    let p = Process()
    p.executableURL = URL(fileURLWithPath: Espeak.binary)
    // slower + comma-padded: bare sub-second clips trip Whisper's no-speech
    // detection; the pauses give the VAD context. (The pauses add no phonemes.)
    p.arguments = ["-v", lang, "-s", "120", "-g", "12", "-w", url.path, ", \(text) ,"]
    p.standardError = Pipe()
    do { try p.run() } catch { return nil }
    p.waitUntilExit()
    defer { try? FileManager.default.removeItem(at: url) }
    guard p.terminationStatus == 0 else { return nil }
    return try? Data(contentsOf: url)
}

struct Case { let word: String; let ipa: String }

@main
struct Harness {
    static func main() async {
        setbuf(stdout, nil)                       // unbuffer: piped output appears live
        let args = CommandLine.arguments
        let useWhisper = args.contains("--whisper")
        let model = args.firstIndex(of: "--whisper").flatMap { i -> String? in
            let j = i + 1; return (j < args.count && !args[j].hasPrefix("--")) ? args[j] : nil
        } ?? "tiny"
        let lang = args.firstIndex(of: "--lang").flatMap { i -> String? in
            let j = i + 1; return j < args.count ? args[j] : nil
        } ?? "fr"

        // Headless watchdog: SFSpeech auth/recognition can stall without a run
        // loop; never let the harness hang a pipeline.
        let deadline: Double = useWhisper ? 600 : 150
        DispatchQueue.global().asyncAfter(deadline: .now() + deadline) {
            print("ABORT: watchdog (\(Int(deadline))s) — engine stalled"); exit(3)
        }

        guard Espeak.available else {
            print("ABORT: espeak not available — cannot generate audio"); exit(2)
        }

        // Test material: words + their espeak-derived IPA (the same G2P the app's
        // enrich path uses), so the loop law is engine-consistent by construction.
        let words = ["bonjour", "merci", "fromage", "papillon"]
        let cases: [Case] = words.compactMap { w in
            Espeak.ipa(w, voice: lang).map { Case(word: w, ipa: $0) }
        }
        guard cases.count == words.count else {
            print("ABORT: espeak G2P failed for some words"); exit(2)
        }

        let scorer: SpeechScorer = useWhisper ? WhisperScorer(model: model) : SystemScorer()
        let engine = useWhisper ? "whisper(\(model))" : "sfspeech"
        print("=== Miolingo closed-loop harness — engine \(engine), lang \(lang) ===")

        var fails = 0, skips = 0
        var matched: [String: Double] = [:]

        // 1. MATCHED loop: speak w, score against w. Expect HIGH similarity.
        for c in cases {
            guard let audio = synthAudio(c.word, lang: lang) else {
                print("FAIL  synth \(c.word): no audio"); fails += 1; continue
            }
            let phon = await scorer.recognise(audio: audio, languageCode: lang, hint: "")
            if phon.isEmpty {
                print("SKIP  \(c.word): recogniser returned nothing (permission / model availability)")
                skips += 1; continue
            }
            let s = evaluate(target: Phrase(text: c.word, ipa: c.ipa),
                             recognisedPhonemes: phon, method: .lenient)
            matched[c.word] = s.similarity
            // per-word similarity is a QUALITY MEASUREMENT of the engine on
            // synthetic audio, not a pass/fail gate (engines vary); the hard
            // assertions are the LAW checks below.
            print("meas  \(c.word): heard /\(phon)/ vs /\(c.ipa)/ → similarity \(String(format: "%.2f", s.similarity))")
        }
        // LAW (hard): the engine must get at least one clean word nearly right —
        // otherwise the loop is not meaningfully closed for this engine.
        if let best = matched.values.max() {
            let ok = best >= 0.8
            if !ok { fails += 1 }
            print("\(ok ? "ok  " : "FAIL")  law: best matched similarity \(String(format: "%.2f", best)) >= 0.80")
        } else { print("SKIP  law: no word recognised at all"); skips += 1 }

        // 2. MISMATCHED control: speak bonjour, score against papillon's IPA.
        //    Honest scoring must give a LOWER score than the matched case —
        //    this is the assertion that catches a performative recogniser.
        if let mB = matched["bonjour"], let audio = synthAudio("bonjour", lang: lang) {
            let phon = await scorer.recognise(audio: audio, languageCode: lang, hint: "")
            if phon.isEmpty { print("SKIP  mismatch control: nothing recognised"); skips += 1 }
            else {
                let wrong = evaluate(target: Phrase(text: "papillon", ipa: cases[3].ipa),
                                     recognisedPhonemes: phon, method: .lenient)
                let ok = wrong.similarity < mB
                if !ok { fails += 1 }
                print("\(ok ? "ok  " : "FAIL")  mismatch control: bonjour-audio vs papillon-IPA → \(String(format: "%.2f", wrong.similarity)) (< matched \(String(format: "%.2f", mB)))")
            }
        }

        // 3. Pure G2P round-trip (no ASR): the stored IPA equals espeak's G2P.
        for c in cases {
            let again = Espeak.ipa(c.word, voice: lang) ?? ""
            let ok = again == c.ipa
            if !ok { fails += 1 }
            print("\(ok ? "ok  " : "FAIL")  G2P stable: \(c.word) → /\(again)/")
        }

        print("=== \(fails) failed, \(skips) skipped ===")
        exit(Int32(fails))
    }
}
