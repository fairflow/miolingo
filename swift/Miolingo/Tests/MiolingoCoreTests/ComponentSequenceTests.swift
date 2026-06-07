import XCTest
@testable import MiolingoCore

// Sequence tests — the Swift analogue of spec/walk-tests.wl's `walkTests`.
// Each replays a named plan through the component value types and the
// cross-component channels (wired here as direct calls, as AppModel does),
// asserting the end state. Names mirror the spec batch (vs-/ps-/sync-/full-).
final class ComponentSequenceTests: XCTestCase {

    // vs-capture: add a word → it lands in the store
    func test_vs_capture() {
        var table = VocabTable()
        table.upsert("souris")                                   // add → vocabUpsert
        XCTAssertEqual(table.read().map(\.word), ["souris"])
    }

    // vs-import: bulk import with a matching header
    func test_vs_import() {
        var table = VocabTable()
        table.importBulk(ImportRequest(contents: "(fr,en)\nchat|cat\nchien|dog",
                                       expectedTarget: "fr"))
        XCTAssertEqual(Set(table.read().map(\.word)), ["chat", "chien"])
    }

    // ps-score: load_material → recording_made → attempt_made(score)
    func test_ps_score() {
        var ps = PracticeSession()
        ps.load([Phrase(text: "chat", ipa: "ʃa")])              // load_material
        ps.recordingMade(Data([1]))                             // recording_made
        ps.score(recognisedPhonemes: "ʃa")                      // attempt_made (langRead+ASR upstream)
        XCTAssertEqual(ps.res?.exactMatch, true)
    }

    // sync-practise (goPractice): Vocab signals, PS pulls the collection fresh
    func test_sync_practise() {
        var table = VocabTable()
        table.upsert(Capture(word: "chat", translation: "cat", ipa: "ʃa"))
        var ps = PracticeSession()
        ps.load(practiseList(table.read(), filter: nil))        // PS pull on goPractice
        XCTAssertEqual(ps.phrases, [Phrase(text: "chat", translation: "cat", ipa: "ʃa")])
    }

    // full-roundtrip: practise an item, capture it → reaches the store (vocabUpsert)
    func test_full_roundtrip() {
        var table = VocabTable()
        var ps = PracticeSession()
        ps.load([Phrase(text: "chien", ipa: "ʃjɛ̃")])           // load_material
        ps.recordingMade(Data([2]))                             // recording_made
        ps.score(recognisedPhonemes: "ʃjɛ̃")                    // attempt_made
        if let w = ps.captureWord { table.upsert(w) }           // capture_vocab → vocabUpsert
        XCTAssertEqual(table.read().map(\.word), ["chien"])
    }

    // story-roundtrip: practise in story mode, capture → store; position preserved
    func test_story_capture_roundtrip() {
        var table = VocabTable()
        var sr = StoryReader(mode: .practice)                   // scene 0, pos 0
        sr.recordingMade(Data([3]))
        sr.score(recognisedPhonemes: "bɔ̃ʒuʁ")
        if let w = sr.captureWord { table.upsert(w) }           // story_capture_vocab → vocabUpsert
        XCTAssertEqual(table.read().first?.displayWord, "Bonjour")
        XCTAssertEqual(sr.pos, 0)                               // capture does not move position
    }

    // ---- oracle: autofill via the dictionary enrich oracle ----
    func test_dictionary_enrich_oracle() {
        let oracle = DictionaryEnrichOracle(
            table: ["fr": ["bonjour": "hello"]], useEspeakIPA: false)
        let r = oracle.enrich(word: "Bonjour", source: "English", target: "fr")
        XCTAssertEqual(r?.translation, "hello")
        XCTAssertNil(r?.ipa)
        XCTAssertNil(oracle.enrich(word: "inconnu", source: "English", target: "fr"))
    }

    func test_autofill_fills_only_empty() {
        let oracle = DictionaryEnrichOracle(
            table: ["fr": ["chat": "cat"]], useEspeakIPA: false)
        // empty translation → filled
        let es = addEntry([], "chat")
        let id = es[0].id
        let fields = autofillFields(es, id: id, lang: LangPair(source: "English", target: "fr"),
                                    oracle: oracle)
        XCTAssertEqual(fields["translation"], "cat")
        // existing translation → never overwritten
        let es2 = updateEntry(es, id: id, fields: ["translation": "feline"])
        let fields2 = autofillFields(es2, id: id, lang: LangPair(source: "English", target: "fr"),
                                     oracle: oracle)
        XCTAssertNil(fields2["translation"])
    }
}
