import SwiftUI
import MiolingoCore

// =====================================================================
// SwiftUI views — one per component (the *View projections rendered).
// Each invokes ports on AppModel; nothing mutates state directly.
// =====================================================================

// --- shared pieces ----------------------------------------------------

struct ItemCard: View {
    let item: Phrase
    var onSpeak: () -> Void
    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Text(item.text.isEmpty ? "—" : item.text).font(.largeTitle).bold()
                Button(action: onSpeak) { Image(systemName: "speaker.wave.2.fill") }
                    .buttonStyle(.borderless)
            }
            if !item.translation.isEmpty {
                Text(item.translation).font(.title3).foregroundStyle(.secondary)
            }
            if !item.ipa.isEmpty {
                Text("/\(item.ipa)/").font(.title3).foregroundStyle(.blue)
            }
        }
        .padding()
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(.quaternary, in: RoundedRectangle(cornerRadius: 10))
    }
}

struct ScoreBadge: View {
    let score: Score
    var pct: Int { Int((score.similarity * 100).rounded()) }
    var color: Color { score.exactMatch || pct >= 70 ? .green : (pct >= 40 ? .orange : .red) }
    var body: some View {
        HStack(spacing: 8) {
            Image(systemName: score.exactMatch ? "checkmark.seal.fill" : "waveform")
                .foregroundStyle(color)
            Text(score.exactMatch ? "Exact match!" : "Similarity \(pct)%").bold().foregroundStyle(color)
            Text("(edit distance \(score.distance))").font(.caption).foregroundStyle(.secondary)
        }
    }
}

struct RecordBar: View {
    @ObservedObject var recorder: Recorder
    let hasRecording: Bool
    var onCaptured: (Data) -> Void
    var onCheck: () -> Void
    var onClear: () -> Void
    var body: some View {
        HStack(spacing: 10) {
            if recorder.isRecording {
                Button { if let d = recorder.stop() { onCaptured(d) } } label: {
                    Label("Stop", systemImage: "stop.circle.fill")
                }.tint(.red)
            } else {
                Button { recorder.start() } label: {
                    Label(hasRecording ? "Re-record" : "Record", systemImage: "mic.circle.fill")
                }
            }
            if hasRecording && !recorder.isRecording {
                Button("Check pronunciation", action: onCheck).buttonStyle(.borderedProminent)
                Button("Clear", action: onClear)
            }
        }
    }
}

// --- Practice tab -----------------------------------------------------

struct PracticeView: View {
    @Environment(AppModel.self) private var model
    @StateObject private var recorder = Recorder()
    @State private var filterText = ""

    private var sample: [Phrase] {
        [Phrase(text: "chat", translation: "cat", ipa: "ʃa"),
         Phrase(text: "chien", translation: "dog", ipa: "ʃjɛ̃")]
    }

    var body: some View {
        let v = model.ps.view
        VStack(alignment: .leading, spacing: 14) {
            Text("Quick Practice").font(.title2).bold()
            if model.psBrowsing {
                browse
            } else if model.ps.isEmpty {
                empty
            } else {
                active(v)
            }
            Spacer()
        }
        .padding(20)
    }

    private var empty: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("No material loaded.").foregroundStyle(.secondary)
            HStack {
                Button("Open practice from vocabulary") { model.openPractice() }
                Button("Load a sample") { model.loadMaterial(sample) }
            }
        }
    }

    private var browse: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Load which words?").font(.headline)
            Button("Load all vocabulary (\(model.table.entries.count))") { model.loadAllVocab() }
            HStack {
                TextField("filter", text: $filterText).frame(width: 200)
                Button("Load filtered") { model.loadFilteredVocab(filterText) }
            }
            Button("Cancel") { model.psBrowsing = false }
        }
    }

    private func active(_ v: SessionView) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("Item \(v.pos + 1) of \(v.total)").foregroundStyle(.secondary)
                Spacer()
                Button("Clear material") { model.psClearMaterial() }
            }
            if let item = v.item { ItemCard(item: item) { model.speak(item.text) } }
            RecordBar(recorder: recorder, hasRecording: v.hasRecording,
                      onCaptured: { model.psRecorded($0) },
                      onCheck: { Task { await model.psAttempt() } },
                      onClear: { model.psClearRecording() })
            if let s = v.score {
                ScoreBadge(score: s)
                Button("Capture to vocabulary") { model.psCapture() }
            }
            HStack {
                Button("◀ Prev") { model.psPrev() }.disabled(!model.ps.canPrev)
                Button("Next ▶") { model.psNext() }.disabled(!model.ps.canNext)
            }
        }
    }
}

// --- Story tab --------------------------------------------------------

struct StoryView: View {
    @Environment(AppModel.self) private var model
    @StateObject private var recorder = Recorder()

    var body: some View {
        let v = model.story.view
        VStack(alignment: .leading, spacing: 14) {
            Text("Story Reader").font(.title2).bold()
            HStack(spacing: 16) {
                Picker("Scene", selection: Binding(get: { v.scene }, set: { model.storySelectScene($0) })) {
                    ForEach(0..<model.sceneCount, id: \.self) { Text("Scene \($0 + 1)").tag($0) }
                }.frame(width: 160)
                Picker("", selection: Binding(get: { v.mode }, set: { model.storySetMode($0) })) {
                    Text("Full").tag(ReadingMode.full)
                    Text("Browse").tag(ReadingMode.browse)
                    Text("Practice").tag(ReadingMode.practice)
                }.pickerStyle(.segmented).frame(width: 300)
            }
            switch v.mode {
            case .full: full(v)
            case .browse: browse(v)
            case .practice: practice(v)
            }
            Spacer()
        }
        .padding(20)
    }

    private func full(_ v: StoryView_) -> some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 10) {
                ForEach(Array(v.phrases.enumerated()), id: \.offset) { _, p in
                    VStack(alignment: .leading) {
                        HStack {
                            Text(p.text).font(.title3).bold()
                            Button { model.speak(p.text) } label: { Image(systemName: "speaker.wave.2") }
                                .buttonStyle(.borderless)
                        }
                        Text(p.translation).foregroundStyle(.secondary)
                    }
                    Divider()
                }
            }
        }
    }

    private func navRow() -> some View {
        HStack {
            Button("◀ Prev") { model.storyPrev() }.disabled(!model.story.canPrev)
            Button("Next ▶") { model.storyNext() }.disabled(!model.story.canNext)
        }
    }

    private func browse(_ v: StoryView_) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Phrase \(v.pos + 1) of \(v.count)").foregroundStyle(.secondary)
            if let item = v.item { ItemCard(item: item) { model.speak(item.text) } }
            navRow()
        }
    }

    private func practice(_ v: StoryView_) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Phrase \(v.pos + 1) of \(v.count)").foregroundStyle(.secondary)
            if let item = v.item { ItemCard(item: item) { model.speak(item.text) } }
            RecordBar(recorder: recorder, hasRecording: v.hasRecording,
                      onCaptured: { model.storyRecorded($0) },
                      onCheck: { Task { await model.storyAttempt() } },
                      onClear: { model.storyClearRecording() })
            if let s = v.score {
                ScoreBadge(score: s)
                Button("Capture to vocabulary") { model.storyCapture() }
            }
            navRow()
        }
    }
}

// typealias so the inner `StoryView` (SwiftUI) and the projection don't clash
typealias StoryView_ = MiolingoCore.StoryView

// --- Vocabulary tab ---------------------------------------------------

struct VocabView: View {
    @Environment(AppModel.self) private var model
    @State private var newWord = ""
    @State private var showImport = false
    @State private var importText = ""

    var body: some View {
        let vm = model.vocabVM
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("Vocabulary (\(vm.count))").font(.title2).bold()
                Spacer()
                Button("Import…") { showImport = true }
                Button("Practise these") { model.practiseFromVocab() }.disabled(vm.count == 0)
            }
            HStack {
                TextField("add a word", text: $newWord)
                    .frame(width: 180).onSubmit(add)
                Button("Add", action: add).disabled(newWord.trimmingCharacters(in: .whitespaces).isEmpty)
                Spacer()
                TextField("filter", text: Binding(get: { vm.filter ?? "" }, set: { model.setFilter($0) }))
                    .frame(width: 160)
                Picker("", selection: Binding(get: { vm.sort }, set: { model.setSort($0) })) {
                    Text("A–Z").tag(VocabSort.alpha)
                    Text("Recent").tag(VocabSort.recent)
                    Text("Oldest").tag(VocabSort.oldest)
                }.frame(width: 120)
            }
            List(vm.entries) { entry in
                if vm.editing == entry.id {
                    EditRow(entry: entry)
                } else {
                    VocabRow(entry: entry)
                }
            }
        }
        .padding(20)
        .sheet(isPresented: $showImport) { importSheet }
    }

    private func add() {
        let w = newWord.trimmingCharacters(in: .whitespaces)
        guard !w.isEmpty else { return }
        model.vocabAdd(w); newWord = ""
    }

    private var importSheet: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Import vocabulary").font(.headline)
            Text("First line a header `(source,target)`; then `word|translation|ipa|source|url` rows.")
                .font(.caption).foregroundStyle(.secondary)
            TextEditor(text: $importText).frame(width: 460, height: 220).border(.quaternary)
            HStack {
                Spacer()
                Button("Cancel") { showImport = false }
                Button("Import") { model.vocabImport(importText); importText = ""; showImport = false }
                    .buttonStyle(.borderedProminent)
            }
        }.padding(20)
    }
}

struct VocabRow: View {
    @Environment(AppModel.self) private var model
    let entry: VocabEntry
    var body: some View {
        HStack {
            VStack(alignment: .leading) {
                Text(entry.displayWord).bold()
                HStack(spacing: 8) {
                    if let t = entry.translation { Text(t).foregroundStyle(.secondary) }
                    if let i = entry.ipa { Text("/\(i)/").foregroundStyle(.blue) }
                }.font(.caption)
            }
            Spacer()
            Text("×\(entry.timesSeen)").font(.caption).foregroundStyle(.secondary)
            Button { model.speak(entry.displayWord) } label: { Image(systemName: "speaker.wave.2") }
                .buttonStyle(.borderless)
            Button("Autofill") { model.vocabAutofill(entry.id) }
            Button("Edit") { model.beginEdit(entry.id) }
            Button(role: .destructive) { model.vocabDelete(entry.id) } label: { Image(systemName: "trash") }
                .buttonStyle(.borderless)
        }
    }
}

struct EditRow: View {
    @Environment(AppModel.self) private var model
    let entry: VocabEntry
    @State private var display = ""
    @State private var translation = ""
    @State private var ipa = ""
    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            TextField("display word", text: $display)
            TextField("translation", text: $translation)
            TextField("ipa", text: $ipa)
            HStack {
                Spacer()
                Button("Cancel") { model.cancelEdit() }
                Button("Save") {
                    model.vocabUpdate(id: entry.id, fields: [
                        "display_word": display, "translation": translation, "ipa": ipa])
                }.buttonStyle(.borderedProminent)
            }
        }
        .onAppear {
            display = entry.displayWord
            translation = entry.translation ?? ""
            ipa = entry.ipa ?? ""
        }
    }
}

// --- Settings (Helm) tab ----------------------------------------------

struct SettingsView: View {
    @Environment(AppModel.self) private var model

    var body: some View {
        let v = model.helm.view
        let langs = model.languages()
        Form {
            Section("Languages") {
                TextField("Your language (native)", text: Binding(
                    get: { v.source }, set: { model.setSource($0) }))
                Picker("Target language", selection: Binding(
                    get: { v.target }, set: { model.setTarget($0) })) {
                    ForEach(langs, id: \.code) { Text("\($0.name) (\($0.code))").tag($0.code) }
                }
                LabeledContent("Resolved", value: v.language)
            }
            Section("Speech") {
                Picker("TTS engine", selection: Binding(
                    get: { v.tts }, set: { model.setTTS($0) })) {
                    Text("System (AVSpeech)").tag(TTSKind.system)
                    Text("espeak").tag(TTSKind.espeak)
                    Text("google").tag(TTSKind.google)
                }
                if model.helm.showsSpeed {
                    HStack {
                        Text("Speed (wpm)")
                        Slider(value: Binding(
                            get: { Double(v.speed) }, set: { model.setSpeed(Int($0)) }),
                            in: 80...450, step: 10)
                        Text("\(v.speed)")
                    }
                }
                Button("Test voice") { model.speak(model.story.view.item?.text ?? "Bonjour") }
            }
        }
        .formStyle(.grouped)
        .padding(20)
    }
}
