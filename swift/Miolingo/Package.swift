// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "Miolingo",
    platforms: [.macOS(.v14)],
    products: [
        .library(name: "MiolingoCore", targets: ["MiolingoCore"]),
        .executable(name: "Miolingo", targets: ["Miolingo"]),
    ],
    targets: [
        // Pure domain ported from the CCS spec (spec/*.wl). Foundation + SQLite only;
        // no UI, so it builds and tests headlessly.
        .target(
            name: "MiolingoCore",
            linkerSettings: [.linkedLibrary("sqlite3")]
        ),
        // The SwiftUI app: wraps MiolingoCore, supplies the native oracles
        // (AVSpeechSynthesizer / SFSpeechRecognizer / espeak).
        .executableTarget(
            name: "Miolingo",
            dependencies: ["MiolingoCore"],
            resources: [.process("Resources")],
            // The native oracle code (Speech/AVFoundation completion handlers)
            // predates strict-concurrency; core + tests stay Swift 6.
            swiftSettings: [.swiftLanguageMode(.v5)]
        ),
        .testTarget(
            name: "MiolingoCoreTests",
            dependencies: ["MiolingoCore"]
        ),
    ]
)
