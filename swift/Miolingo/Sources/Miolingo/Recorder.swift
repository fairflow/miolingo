import Foundation
import AVFoundation

// Microphone capture → WAV Data (PCM 16k mono), suitable for SFSpeech + the
// `recording_made` port. Needs NSMicrophoneUsageDescription (set by make_app.sh).
@MainActor
final class Recorder: NSObject, ObservableObject {
    @Published var isRecording = false
    private var recorder: AVAudioRecorder?
    private var url: URL?

    func start() {
        let u = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString + ".wav")
        let settings: [String: Any] = [
            AVFormatIDKey: Int(kAudioFormatLinearPCM),
            AVSampleRateKey: 16000.0,
            AVNumberOfChannelsKey: 1,
            AVLinearPCMBitDepthKey: 16,
            AVLinearPCMIsFloatKey: false,
            AVLinearPCMIsBigEndianKey: false,
        ]
        do {
            let r = try AVAudioRecorder(url: u, settings: settings)
            r.record()
            recorder = r; url = u; isRecording = true
        } catch {
            isRecording = false
        }
    }

    /// Stop and return the captured audio bytes.
    func stop() -> Data? {
        recorder?.stop()
        isRecording = false
        defer { recorder = nil }
        guard let url else { return nil }
        return try? Data(contentsOf: url)
    }
}
