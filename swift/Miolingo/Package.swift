// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "Miolingo",
    platforms: [.macOS(.v15)],   // Translation framework (live autofill) is macOS 15+
    products: [
        .library(name: "MiolingoCore", targets: ["MiolingoCore"]),
        .executable(name: "Miolingo", targets: ["Miolingo"]),
    ],
    dependencies: [
        // OPT-IN Whisper ASR engine. This breaks the zero-dependency / offline-build
        // invariant (network at resolve; Core ML model download on first run), so the
        // default ASR engine stays SFSpeech — see WhisperScorer.swift + report.
        .package(url: "https://github.com/argmaxinc/WhisperKit", from: "1.0.0"),
    ],
    targets: [
        // Pure domain ported from the CCS spec (spec/*.wl). Foundation + SQLite only;
        // no UI, so it builds and tests headlessly.
        .target(
            name: "MiolingoCore",
            linkerSettings: [.linkedLibrary("sqlite3")]
        ),
        // The LIVE oracles (AVSpeech TTS, espeak TTS, SFSpeech + Whisper ASR) as a
        // library, so both the app AND the headless test harness can drive them —
        // the TTS→ASR closed loop made testable.
        .target(
            name: "MiolingoOracles",
            dependencies: [
                "MiolingoCore",
                .product(name: "WhisperKit", package: "WhisperKit"),
            ],
            swiftSettings: [
                .swiftLanguageMode(.v5),
                .define("WHISPERKIT"),
            ]
        ),
        // The SwiftUI app: wraps MiolingoCore, renders the views, hosts the oracles.
        .executableTarget(
            name: "Miolingo",
            dependencies: ["MiolingoCore", "MiolingoOracles"],
            resources: [.process("Resources")],
            // The native oracle code (Speech/AVFoundation completion handlers)
            // predates strict-concurrency; core + tests stay Swift 6.
            swiftSettings: [
                .swiftLanguageMode(.v5),
                // Gate WhisperScorer on this flag so the app still compiles if the
                // WhisperKit dependency is removed for an offline build.
                .define("WHISPERKIT"),
            ]
        ),
        // Headless closed-loop harness: espeak GENERATES audio for known words
        // (TTS), the selected ASR engine transcribes it, the pure scorer
        // evaluates — the spec Speaker agent's round-trip law on real engines.
        .executableTarget(
            name: "MiolingoHarness",
            dependencies: ["MiolingoCore", "MiolingoOracles"],
            swiftSettings: [
                .swiftLanguageMode(.v5),
                .define("WHISPERKIT"),
            ]
        ),
        .testTarget(
            name: "MiolingoCoreTests",
            dependencies: ["MiolingoCore"]
        ),
    ]
)
