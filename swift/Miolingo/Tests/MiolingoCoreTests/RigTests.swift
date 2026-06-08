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

    // The JSON grammar (Phase 3) parses to the same model the loft renders.
    func testRigGrammarParsesBerthRigDeck() throws {
        let berthJSON = """
        { "schema":"rig/1","berth":"Helm","cleats":[
          {"name":"set_target","role":"input","type":"code:dynamic:languages"},
          {"name":"set_tts","role":"input","type":"code:fixed:system=System,espeak=espeak"},
          {"name":"set_speed","role":"input","type":"bounded:80:450"},
          {"name":"view","role":"projection","type":"record:source,target"} ],
          "constraints":[{"distinct":["set_source","set_target"]}] }
        """.data(using: .utf8)!
        let b = try RigGrammar.berth(from: berthJSON)
        XCTAssertEqual(b.name, "Helm")
        XCTAssertEqual(b.cleats.count, 4)
        // dynamic code domain
        guard case .input(.code(.dynamic(let src))) = b.cleats[0].role else { return XCTFail() }
        XCTAssertEqual(src, "languages")
        // fixed code domain carries the choices
        guard case .input(.code(.fixed(let opts))) = b.cleats[1].role else { return XCTFail() }
        XCTAssertEqual(opts.map(\.id), ["system", "espeak"])
        // bounded + projection record
        guard case .input(.bounded(80, 450)) = b.cleats[2].role else { return XCTFail() }
        guard case .projection(.record(let fields)) = b.cleats[3].role else { return XCTFail() }
        XCTAssertEqual(fields, ["source", "target"])
        XCTAssertEqual(b.constraints, [.distinct(["set_source", "set_target"])])

        let rig = try RigGrammar.rig(from: """
        {"schema":"rig/1","for":"Helm","fittings":{"set_tts":"choice.segmented","view":"panel"}}
        """.data(using: .utf8)!)
        XCTAssertEqual(rig["set_tts"], .choice(.segmented))
        XCTAssertEqual(rig["view"], .panel)

        let deck = try RigGrammar.deckPlan(from: """
        {"schema":"deck/1","for":"Helm","groups":[{"title":"Languages","cleats":["set_target"]},{"title":null,"cleats":["view"]}]}
        """.data(using: .utf8)!)
        XCTAssertEqual(deck.groups.count, 2)
        XCTAssertEqual(deck.groups[0].title, "Languages")
        XCTAssertNil(deck.groups[1].title)
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
