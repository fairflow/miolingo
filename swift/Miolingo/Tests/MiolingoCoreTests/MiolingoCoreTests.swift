import XCTest
@testable import MiolingoCore

// Behavioural assertions transcribed from the spec test suites
// (spec/tests/*.wls) — the Swift port must match the .wl behaviour.
final class MiolingoCoreTests: XCTestCase {

    // ---- Vocab value-functions (VocabFunctions.wl) ----
    func testValidateWord() {
        XCTAssertNil(validateWord("   "))
        XCTAssertNil(validateWord("...."))            // only punctuation
        XCTAssertNil(validateWord("two words"))       // not single word
        XCTAssertEqual(validateWord("Chat!")?.display, "Chat")
        XCTAssertEqual(validateWord("Chat!")?.key, "chat")
        XCTAssertEqual(validateWord("«bonjour»")?.key, "bonjour")
    }

    func testAddEntryDedupAndBump() {
        var es = addEntry([], "souris")
        XCTAssertEqual(es.count, 1)
        XCTAssertEqual(es[0].timesSeen, 1)
        XCTAssertEqual(es[0].displayWord, "souris")
        // re-capture same key (different case) bumps, keeps original display
        es = addEntry(es, "Souris")
        XCTAssertEqual(es.count, 1)
        XCTAssertEqual(es[0].timesSeen, 2)
        XCTAssertEqual(es[0].displayWord, "souris")
    }

    func testAddEntryCoalesceFillNeverOverwrite() {
        var es = addEntry([], Capture(word: "chat", translation: "cat"))
        es = addEntry(es, Capture(word: "chat", translation: "feline", ipa: "ʃa"))
        XCTAssertEqual(es[0].translation, "cat")     // not overwritten
        XCTAssertEqual(es[0].ipa, "ʃa")              // filled
    }

    func testDeleteAndUpdate() {
        var es = addEntry(addEntry([], "chat"), "chien")
        let chatId = es.first { $0.word == "chat" }!.id
        es = deleteFrom(es, chatId)
        XCTAssertEqual(es.map(\.word), ["chien"])
        // update editable field
        let id = es[0].id
        es = updateEntry(es, id: id, fields: ["translation": "dog"])
        XCTAssertEqual(es[0].translation, "dog")
        // unknown field rejected (no-op)
        es = updateEntry(es, id: id, fields: ["bogus": "x"])
        XCTAssertEqual(es[0].translation, "dog")
        // display_word that changes the key is rejected
        es = updateEntry(es, id: id, fields: ["display_word": "cat"])
        XCTAssertEqual(es[0].displayWord, "chien")
    }

    func testSortAndFilter() {
        var es = addEntry([], "banana")            // seq 1
        es = addEntry(es, "apple")                 // seq 2
        es = addEntry(es, "banana")                // re-capture bumps last_seq -> 3
        XCTAssertEqual(sortEntries(es, .alpha).map(\.word), ["apple", "banana"])
        XCTAssertEqual(sortEntries(es, .recent).first?.word, "banana") // bumped
        XCTAssertEqual(sortEntries(es, .oldest).first?.word, "banana") // first captured
        XCTAssertEqual(applyFilter(es, "app").map(\.word), ["apple"])
    }

    func testImportRoundTripAndTargetGuard() {
        // header is (target, source): target fr matches expectedTarget fr
        let req = ImportRequest(contents: "(fr,en)\nsouris|mouse|[suʁi]\nchat|cat",
                                expectedTarget: "fr")
        let es = importInto([], req)
        XCTAssertEqual(Set(es.map(\.word)), ["souris", "chat"])
        XCTAssertEqual(es.first { $0.word == "souris" }?.ipa, "suʁi")   // []-stripped
        // wrong target -> no capture (file target en ≠ fr)
        XCTAssertEqual(importInto([], ImportRequest(contents: "(en,fr)\nx|y", expectedTarget: "fr")).count, 0)
        // no header -> no capture
        XCTAssertEqual(importInto([], ImportRequest(contents: "x|y")).count, 0)
    }

    func testImportOutcomeReasons() {
        if case let .ok(n) = importOutcome([], ImportRequest(contents: "(fr,en)\nchat|cat", expectedTarget: "fr")).result {
            XCTAssertEqual(n, 1)
        } else { XCTFail("expected .ok") }
        if case let .targetMismatch(ft, e) = importOutcome([], ImportRequest(contents: "(en,fr)\nx|y", expectedTarget: "fr")).result {
            XCTAssertEqual(ft, "en"); XCTAssertEqual(e, "fr")
        } else { XCTFail("expected .targetMismatch") }
        if case .noHeader = importOutcome([], ImportRequest(contents: "x|y", expectedTarget: "fr")).result {} else { XCTFail("expected .noHeader") }
    }

    func testExportCsvHeaderAndQuoting() {
        let es = addEntry([], Capture(word: "chat", translation: "a, cat"))
        let csv = exportCsv(es)
        let lines = csv.components(separatedBy: "\n")
        XCTAssertTrue(lines[0].hasPrefix("word,translation,ipa,source_language,source,"))
        XCTAssertTrue(lines[1].contains("\"a, cat\""))      // comma -> quoted
    }

    func testPractiseListShape() {
        let es = addEntry([], Capture(word: "chat", translation: "cat", ipa: "ʃa"))
        let ph = practiseList(es, filter: nil)
        XCTAssertEqual(ph, [Phrase(text: "chat", translation: "cat", ipa: "ʃa")])
    }

    // ---- Practice scoring (PracticeSessionFunctions.wl) ----
    func testLevenshteinAndCompare() {
        XCTAssertEqual(levenshtein("kitten", "sitting"), 3)
        let exact = comparePhonemes(user: "ʃa", correct: "ʃa")
        XCTAssertTrue(exact.exactMatch)
        XCTAssertEqual(exact.similarity, 1.0, accuracy: 1e-9)
        let empty = comparePhonemes(user: "abc", correct: "")
        XCTAssertEqual(empty.similarity, 0.0)
        XCTAssertEqual(empty.distance, 3)
    }

    func testTargetOfAndSelectPos() {
        let ph = [Phrase(text: "a"), Phrase(text: "b")]
        XCTAssertEqual(targetOf(ph, 1).text, "b")
        XCTAssertEqual(targetOf(ph, 9).text, "")             // out of range -> empty
        XCTAssertEqual(selectPos(ph, 1, 0), 1)
        XCTAssertEqual(selectPos(ph, 5, 0), 0)               // out of range -> keep current
    }

    // ---- Practice-mode scoring detail (alignPhonemes) — ported from spec ----
    func testAlignPhonemesAndDetail() {
        XCTAssertEqual(normalisePhonemes("k o m"), "kom")
        let sub = alignPhonemes(user: "kat", correct: "kit")
        XCTAssertEqual(sub.map(\.op), [.equal, .sub, .equal])
        XCTAssertEqual(sub[1].target, "i"); XCTAssertEqual(sub[1].user, "a")
        let del = alignPhonemes(user: "ka", correct: "kat")       // target longer → del
        XCTAssertEqual(del.map(\.op), [.equal, .equal, .del])
        XCTAssertEqual(del[2].target, "t"); XCTAssertEqual(del[2].user, "")
        let ins = alignPhonemes(user: "kat", correct: "ka")       // user longer → ins
        XCTAssertEqual(ins.map(\.op), [.equal, .equal, .ins])
        XCTAssertEqual(ins[2].user, "t"); XCTAssertEqual(ins[2].target, "")
        XCTAssertTrue(alignPhonemes(user: "", correct: "").isEmpty)
        // evaluate normalises both sides and carries the detail
        let s = evaluate(target: Phrase(text: "x", ipa: "a b c"), recognisedPhonemes: "a b d")
        XCTAssertEqual(s.distance, 1)
        XCTAssertEqual(s.user, "abd"); XCTAssertEqual(s.target, "abc")
        XCTAssertEqual(s.alignment.last?.op, .sub)
        XCTAssertEqual(s.alignment.last?.target, "c"); XCTAssertEqual(s.alignment.last?.user, "d")
    }

    func testScoringMethods() {
        let p = Phrase(text: "x", ipa: "ABC")
        let strict = evaluate(target: p, recognisedPhonemes: "abc", method: .editDistance)
        XCTAssertFalse(strict.exactMatch)        // case differs → not exact
        let lenient = evaluate(target: p, recognisedPhonemes: "abc", method: .lenient)
        XCTAssertTrue(lenient.exactMatch)        // lenient folds case/diacritics → match
    }

    // ---- Component behaviour (the agents) ----
    func testPracticeSessionFlow() {
        var ps = PracticeSession()
        XCTAssertTrue(ps.isEmpty)
        ps.load([Phrase(text: "chat", ipa: "ʃa"), Phrase(text: "chien", ipa: "ʃjɛ̃")])
        XCTAssertEqual(ps.pos, 0)
        // out-of-range select is a no-op (the interleaving bug guard)
        ps.select(5); XCTAssertEqual(ps.pos, 0)
        ps.recordingMade(Data([1, 2, 3]))
        XCTAssertNotNil(ps.rec)
        ps.score(recognisedPhonemes: "ʃa")
        XCTAssertEqual(ps.res?.exactMatch, true)
        XCTAssertEqual(ps.captureWord, "chat")
        ps.next(); XCTAssertEqual(ps.pos, 1); XCTAssertNil(ps.rec)  // next clears rec/res
    }

    func testStoryModeSwitchPreservesPosition() {
        var sr = StoryReader()                 // scene 0, pos 0, browse
        sr.next()                              // pos 1
        XCTAssertEqual(sr.pos, 1)
        sr.setMode(.practice)                  // PRESERVES (scene,pos)
        XCTAssertEqual(sr.scene, 0); XCTAssertEqual(sr.pos, 1); XCTAssertEqual(sr.mode, .practice)
        sr.selectScene(1)                      // new scene -> pos resets
        XCTAssertEqual(sr.scene, 1); XCTAssertEqual(sr.pos, 0)
    }

    func testStoryPracticeCaptureWord() {
        var sr = StoryReader(mode: .practice)
        sr.recordingMade(Data([9]))
        sr.score(recognisedPhonemes: "bɔ̃ʒuʁ")
        XCTAssertEqual(sr.captureWord, "Bonjour")
        XCTAssertEqual(sr.res?.exactMatch, true)
    }

    func testHelmViewAndSpeedGuard() {
        var h = Helm()
        XCTAssertEqual(h.view.language, "French")
        h.setSpeed(180)                        // system tts -> guard blocks
        XCTAssertEqual(h.speed, 250)
        h.setTTS(.espeak); h.setSpeed(180)
        XCTAssertEqual(h.speed, 180)
    }

    // ---- Store round-trip (SQLite) ----
    func testStoreRoundTrip() throws {
        let tmp = NSTemporaryDirectory() + "miolingo-test-\(UUID().uuidString).sqlite"
        let db = try Database(path: tmp)
        var t = VocabTable(entries: db.loadEntries())
        t.upsert(Capture(word: "chat", translation: "cat", ipa: "ʃa"))
        db.saveEntries(t.entries)
        let reloaded = db.loadEntries()
        XCTAssertEqual(reloaded.first?.word, "chat")
        XCTAssertEqual(reloaded.first?.translation, "cat")
        var h = db.loadHelm(); h.setTarget("pt"); db.saveHelm(h)
        XCTAssertEqual(db.loadHelm().target, "pt")
        XCTAssertFalse(db.languages().isEmpty)
        try? FileManager.default.removeItem(atPath: tmp)
    }
}
