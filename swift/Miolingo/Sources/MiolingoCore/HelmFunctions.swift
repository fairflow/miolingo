import Foundation

// =====================================================================
// HelmFunctions — ported from spec/HelmFunctions.wl (src/ui/sidebar.py,
// language_state.py). Helm OWNS the session settings; everyone READS this
// projection.
// =====================================================================

let helmTrainingNames: [String: String] = [
    "en": "English", "fr": "French", "pt": "Portuguese",
    "de": "German", "es": "Spanish", "it": "Italian"]

/// target code → training-map full name; unknown codes pass through.
public func trainingNameOf(_ code: String) -> String {
    helmTrainingNames[code] ?? code
}

public struct HelmView: Equatable, Sendable {
    public var source: String      // native language NAME
    public var target: String      // target language CODE
    public var language: String    // trainingNameOf(target)
    public var tts: TTSKind
    public var speed: Int
}

public func helmView(source: String, target: String, tts: TTSKind, speed: Int) -> HelmView {
    HelmView(source: source, target: target,
             language: trainingNameOf(target), tts: tts, speed: speed)
}
