import Foundation

// Robust resource lookup for bundled JSON (lexicon, stories).
//
// SwiftPM's generated `Bundle.module` resolves to
//   Bundle.main.bundleURL / "Miolingo_Miolingo.bundle"
// i.e. the .app ROOT — but a code-SIGNED .app may only contain `Contents/`, so
// the resource bundle has to live in Contents/Resources/ to be sealed. That
// makes `Bundle.module` miss it and silently fall back to the hard-coded
// .build path (works only on the build machine; an "(nothing loads)" failure
// anywhere else).
//
// This helper tries, in order:
//   1. Contents/Resources/<BIN>_<BIN>.bundle      (the signed .app)
//   2. Contents/Resources directly                (flat copy fallback)
//   3. Bundle.module                              (dev runs, `swift test`)
// The signed-.app paths are tried FIRST and on purpose: the generated
// `Bundle.module` accessor calls `fatalError` if it can't find the bundle at
// either the app root or the hard-coded .build path. In a shipped signed app
// the .build path is gone, so touching Bundle.module there would CRASH. We only
// fall back to it when the explicit paths miss (i.e. dev / `swift test`).
enum BundledResource {
    private static let resourceBundleName = "Miolingo_Miolingo.bundle"

    static func url(forResource name: String, withExtension ext: String) -> URL? {
        let resources = Bundle.main.bundleURL
            .appendingPathComponent("Contents/Resources", isDirectory: true)

        let inBundle = resources
            .appendingPathComponent(resourceBundleName, isDirectory: true)
            .appendingPathComponent("\(name).\(ext)")
        if FileManager.default.fileExists(atPath: inBundle.path) { return inBundle }

        let flat = resources.appendingPathComponent("\(name).\(ext)")
        if FileManager.default.fileExists(atPath: flat.path) { return flat }

        return Bundle.module.url(forResource: name, withExtension: ext)
    }
}
