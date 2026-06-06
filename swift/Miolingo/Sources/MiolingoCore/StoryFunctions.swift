import Foundation

// =====================================================================
// StoryFunctions — ported from spec/StoryFunctions.wl. sceneOf is the
// STORY-CONTENT BOUNDARY: the spec uses an in-spec fixture standing in for a
// deferred StoryLibrary store. Here it is a protocol with the same fixture as
// default, so a real (bundled JSON / DB) library can be swapped in later
// without changing StoryReader.
// =====================================================================

public protocol StoryLibrary: Sendable {
    func scene(_ index: Int) -> [Phrase]
    var sceneCount: Int { get }
}

/// The spec fixture (StoryFunctions.wl sceneOf), verbatim.
public struct FixtureStoryLibrary: StoryLibrary {
    public init() {}
    public var sceneCount: Int { 2 }
    public func scene(_ index: Int) -> [Phrase] {
        switch index {
        case 0: return [
            Phrase(text: "Bonjour", translation: "Hello", ipa: "bɔ̃ʒuʁ"),
            Phrase(text: "Comment ça va?", translation: "How are you?", ipa: "kɔmɑ̃ sa va")]
        case 1: return [
            Phrase(text: "Au revoir", translation: "Goodbye", ipa: "o ʁəvwaʁ")]
        default: return []
        }
    }
}

public struct StoryView: Equatable, Sendable {
    public var scene: Int
    public var mode: ReadingMode
    public var pos: Int
    public var count: Int
    public var phrases: [Phrase]
    public var item: Phrase?
    public var hasRecording: Bool
    public var score: Score?
}

public func storyView(scene: Int, pos: Int, mode: ReadingMode,
                      rec: Recording?, res: Score?, library: StoryLibrary) -> StoryView {
    let phrases = library.scene(scene)
    return StoryView(scene: scene, mode: mode, pos: pos,
                     count: phrases.count, phrases: phrases,
                     item: phrases.isEmpty ? nil : targetOf(phrases, pos),
                     hasRecording: rec != nil, score: res)
}
