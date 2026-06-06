import SwiftUI
import MiolingoCore

@main
struct MiolingoApp: App {
    @State private var model = AppModel()

    init() { SystemScorer.requestAuthorization() }

    var body: some Scene {
        WindowGroup("Miolingo") {
            ContentView().environment(model)
        }
        .defaultSize(width: 920, height: 660)
    }
}

struct ContentView: View {
    @Environment(AppModel.self) private var model

    var body: some View {
        @Bindable var model = model
        TabView(selection: $model.selectedTab) {
            PracticeView()
                .tabItem { Label("Practice", systemImage: "mic.fill") }.tag(Tab.practice)
            StoryView()
                .tabItem { Label("Story", systemImage: "book.fill") }.tag(Tab.story)
            VocabView()
                .tabItem { Label("Vocabulary", systemImage: "tray.full.fill") }.tag(Tab.vocab)
            SettingsView()
                .tabItem { Label("Settings", systemImage: "slider.horizontal.3") }.tag(Tab.settings)
        }
        .frame(minWidth: 800, minHeight: 580)
        .padding(.top, 2)
    }
}
