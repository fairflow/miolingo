import Foundation
import MiolingoCore

// StoryLibrary backed by a bundled JSON resource (distributed WITH the app);
// falls back to the spec fixture if the resource is missing. This is the
// concrete StoryLibrary store the spec defers (sceneOf is its fixture).
struct BundledStoryLibrary: StoryLibrary {
    static let shared = BundledStoryLibrary()
    private let scenes: [[Phrase]]

    init() {
        if let url = BundledResource.url(forResource: "stories", withExtension: "json"),
           let data = try? Data(contentsOf: url),
           let decoded = try? JSONDecoder().decode([[Phrase]].self, from: data),
           !decoded.isEmpty {
            scenes = decoded
        } else {
            let fx = FixtureStoryLibrary()
            scenes = (0..<fx.sceneCount).map { fx.scene($0) }
        }
    }

    var sceneCount: Int { scenes.count }
    func scene(_ index: Int) -> [Phrase] {
        (0..<scenes.count).contains(index) ? scenes[index] : []
    }
}
