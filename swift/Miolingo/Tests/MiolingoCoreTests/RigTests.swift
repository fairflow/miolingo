import XCTest
@testable import MiolingoCore

// The rig model is platform-neutral data; these lock its shape and the
// "one-line re-skin" lever (a Rig is just Cleat name → Fitting).
final class RigTests: XCTestCase {

    // A Helm-like berth declared as typed cleats (the whole "spec" a loft needs).
    private let berth = Berth("Helm", [
        Cleat("set_source", .input(.text)),
        Cleat("set_target", .input(.code(.dynamic("languages")))),
        Cleat("set_tts",    .input(.code(.fixed([Choice("system", "System"),
                                                 Choice("espeak", "espeak")])))),
        Cleat("set_speed",  .input(.bounded(80, 450))),
        Cleat("view",       .projection(.record(["source", "target"]))),
    ])

    func testBerthShape() {
        XCTAssertEqual(berth.cleats.count, 5)
        // a projection vs an input is distinguishable structurally
        let view = berth.cleats.first { $0.name == "view" }!
        if case .projection = view.role {} else { XCTFail("view should be a projection") }
    }

    func testStaticDomainCarriesChoices() {
        let tts = berth.cleats.first { $0.name == "set_tts" }!
        guard case let .input(.code(.fixed(opts))) = tts.role else { return XCTFail() }
        XCTAssertEqual(opts.map(\.id), ["system", "espeak"])
    }

    func testRigIsAOneLineReskin() {
        var rig: Rig = ["set_tts": .choice(.segmented)]
        XCTAssertEqual(rig["set_tts"], .choice(.segmented))
        rig["set_tts"] = .choice(.radio)            // the lever: radio vs segmented vs tabs
        XCTAssertEqual(rig["set_tts"], .choice(.radio))
    }

    func testPlimValueAccessors() {
        XCTAssertEqual(PlimValue.text("hi").asText, "hi")
        XCTAssertEqual(PlimValue.code("fr").asCode, "fr")
        XCTAssertEqual(PlimValue.int(7).asInt, 7)
        let rec = PlimValue.record([RecordField("a", .int(3)), RecordField("b", .text("x"))])
        if case let .record(fs) = rec { XCTAssertEqual(fs.map(\.display), ["3", "x"]) }
        else { XCTFail() }
    }
}
