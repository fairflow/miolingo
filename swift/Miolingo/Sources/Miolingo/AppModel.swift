import Foundation
import Observation
import MiolingoCore

enum Tab: String, CaseIterable, Identifiable {
    case practice = "Practice", story = "Story", vocab = "Vocabulary", settings = "Settings"
    var id: String { rawValue }
}

// =====================================================================
// AppModel — composes the components (= mioCore) and wires the restricted
// cross-component channels (vocabUpsert / goPractice / langRead / vocabRead)
// as direct calls: these are the τ's the walk harness auto-fires. All ports
// the UI invokes funnel through here, mirroring MioCore.wl.
// =====================================================================
@MainActor @Observable
final class AppModel {
    var helm: Helm
    var ps: PracticeSession
    var table: VocabTable
    var vocab: Vocab
    var story: StoryReader

    // transient UI
    var selectedTab: Tab = .practice
    var psBrowsing = false        // open_practice taken; choosing what to load
    var lastError: String?
    var lastRecognised = ""       // what ASR heard (phonemes) — visible feedback
    var isScoring = false

    private let db: Database
    private let tts: TTSEngine
    private let scorer: SpeechScorer
    private let enrich: EnrichOracle

    init() {
        let database = (try? Database(path: Database.defaultPath()))
            ?? ((try? Database(path: NSTemporaryDirectory() + "miolingo.sqlite"))!)
        db = database
        helm = database.loadHelm()
        table = VocabTable(entries: database.loadEntries())
        ps = PracticeSession()
        vocab = Vocab()
        story = StoryReader(library: BundledStoryLibrary.shared)
        tts = SystemTTS()
        scorer = SystemScorer()
        // translation from the bundled lexicon + IPA from espeak (offline autofill).
        enrich = DictionaryEnrichOracle(table: AppModel.loadLexicon(),
                                        useEspeakIPA: Espeak.available)
    }

    /// The bundled offline lexicon (targetCode → word → native translation).
    private static func loadLexicon() -> [String: [String: String]] {
        guard let url = Bundle.module.url(forResource: "lexicon", withExtension: "json"),
              let data = try? Data(contentsOf: url),
              let raw = try? JSONDecoder().decode([String: [String: String]].self, from: data)
        else { return [:] }
        return raw
    }

    // --- persistence ---
    private func persistVocab() { db.saveEntries(table.entries) }
    private func persistHelm() { db.saveHelm(helm) }
    func languages() -> [(code: String, name: String)] { db.languages() }

    // --- Helm ports ---
    func setSource(_ s: String) { helm.setSource(s); persistHelm() }
    func setTarget(_ t: String) { helm.setTarget(t); persistHelm() }
    func setTTS(_ e: TTSKind)   { helm.setTTS(e); persistHelm() }
    func setSpeed(_ w: Int)     { helm.setSpeed(w); persistHelm() }

    // --- TTS (read Helm; AVSpeech) ---
    func speak(_ text: String) {
        tts.speak(text, languageCode: bcp47(helm.target), rate: Double(helm.speed))
    }

    // --- PracticeSession flow ---
    func openPractice() { psBrowsing = true }                 // open_practice → (vocabRead) → PSBrowse
    func loadAllVocab() { ps.load(practiseList(table.read(), filter: nil)); psBrowsing = false }
    func loadFilteredVocab(_ q: String) {
        ps.load(practiseList(table.read(), filter: q)); psBrowsing = false
    }
    func loadMaterial(_ ph: [Phrase]) { ps.load(ph) }         // load_material
    func psSelect(_ i: Int) { ps.select(i) }
    func psRecorded(_ audio: Data) { ps.recordingMade(audio) }
    func psClearRecording() { ps.clearRecording() }
    func psNext() { ps.next() }
    func psPrev() { ps.prev() }
    func psClearMaterial() { ps.clearMaterial() }
    func psAttempt() async {                                   // attempt_made + langRead + ASR
        guard let rec = ps.rec else { return }
        isScoring = true; defer { isScoring = false }
        let phon = await scorer.recognise(audio: rec.audio, languageCode: helm.target)
        lastRecognised = phon
        ps.score(recognisedPhonemes: phon)
    }
    func psCapture() {                                         // capture_vocab → vocabUpsert
        if let w = ps.captureWord { table.upsert(w); persistVocab() }
    }

    // --- Vocab tab: writes go through VocabTable; params are Vocab-owned ---
    func openVocab() { vocab.openVocab() }
    func setSort(_ s: VocabSort) { vocab.setSort(s) }
    func setFilter(_ q: String?) { vocab.setFilter(q) }
    func beginEdit(_ id: Int) { vocab.beginEdit(id) }
    func cancelEdit() { vocab.cancelEdit() }
    func vocabAdd(_ word: String) { table.upsert(word); persistVocab() }      // add → vocabUpsert
    func vocabImport(_ contents: String) {                                    // import_bulk → vocabImport
        table.importBulk(ImportRequest(contents: contents, expectedTarget: helm.target))
        persistVocab()
    }
    func vocabDelete(_ id: Int) { table.remove(id); persistVocab() }          // delete → vocabRemove
    func vocabUpdate(id: Int, fields: [String: String]) {                     // update → vocabAmend
        table.amend(id: id, fields: fields); vocab.endEdit(); persistVocab()
    }
    func vocabAutofill(_ id: Int) {                                           // autofill → langRead + vocabAmend
        let f = autofillFields(table.read(), id: id, lang: helm.langPair, oracle: enrich)
        if !f.isEmpty { table.amend(id: id, fields: f); persistVocab() }
    }

    /// Native-language CODE for the source NAME Helm stores (for translation target).
    var nativeCode: String {
        ["English": "en", "French": "fr", "Portuguese": "pt",
         "German": "de", "Spanish": "es", "Italian": "it"][helm.source] ?? "en"
    }

    /// Autofill driven by the live Apple Translation framework (VocabView supplies
    /// `translation`); espeak still provides the IPA via the enrich oracle. Both
    /// honour only-empty / never-overwrite. `translation == nil` falls back to the
    /// offline lexicon path.
    func applyAutofill(id: Int, translation: String?) {
        var fields = autofillFields(table.read(), id: id, lang: helm.langPair, oracle: enrich)
        if let t = translation?.trimmingCharacters(in: .whitespaces), !t.isEmpty,
           let row = table.read().first(where: { $0.id == id }),
           (row.translation ?? "").isEmpty {
            fields["translation"] = t       // prefer the live translation
        }
        if !fields.isEmpty { table.amend(id: id, fields: fields); persistVocab() }
    }
    func practiseFromVocab() {                                                // practise_vocab → goPractice → PS pull
        ps.load(practiseList(table.read(), filter: vocab.filter))
        selectedTab = .practice
    }

    // --- StoryReader ---
    func storySetMode(_ m: ReadingMode) { story.setMode(m) }
    func storySelectScene(_ s: Int) { story.selectScene(s) }
    func storySelectItem(_ i: Int) { story.selectItem(i) }
    func storyNext() { story.next() }
    func storyPrev() { story.prev() }
    func storyRecorded(_ audio: Data) { story.recordingMade(audio) }
    func storyClearRecording() { story.clearRecording() }
    func storyAttempt() async {                                               // story_attempt_made + langRead + ASR
        guard let rec = story.rec else { return }
        isScoring = true; defer { isScoring = false }
        let phon = await scorer.recognise(audio: rec.audio, languageCode: helm.target)
        lastRecognised = phon
        story.score(recognisedPhonemes: phon)
    }
    func storyCapture() {                                                     // story_capture_vocab → vocabUpsert
        if let w = story.captureWord { table.upsert(w); persistVocab() }
    }

    // --- projections (the *View ports) ---
    var vocabVM: VocabViewModel { vocab.view(entries: table.entries) }
    var sceneCount: Int { BundledStoryLibrary.shared.sceneCount }
}
