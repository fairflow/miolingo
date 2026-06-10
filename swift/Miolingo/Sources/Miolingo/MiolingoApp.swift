import SwiftUI
import AppKit
import MiolingoOracles
import MiolingoCore

@main
struct MiolingoApp: App {
    @State private var model = AppModel()

    init() { SystemScorer.requestAuthorization() }

    var body: some Scene {
        WindowGroup("Miolingo") {
            ContentView()
                .environment(model)
                .environment(\.skin, model.skin)
                .tint(model.skin.accent)
        }
        .defaultSize(width: 920, height: 660)
        .commands { HelpCommands() }

        // The in-app Help window (⌘? / Help menu).
        Window("Miolingo Help", id: "help") {
            HelpView()
                .environment(\.skin, model.skin)
                .tint(model.skin.accent)
        }
        .defaultSize(width: 720, height: 660)
    }
}

/// Replace the default Help menu: ⌘? opens the rich in-app Help window; a second
/// item opens the macOS Help Book (Help Viewer) when the .help bundle is present.
struct HelpCommands: Commands {
    @Environment(\.openWindow) private var openWindow
    var body: some Commands {
        CommandGroup(replacing: .help) {
            Button("Miolingo Help") { openWindow(id: "help") }
                .keyboardShortcut("?", modifiers: .command)
            Button("Miolingo Help Book") { NSApplication.shared.showHelp(nil) }
        }
    }
}

struct ContentView: View {
    @Environment(AppModel.self) private var model

    var body: some View {
        @Bindable var model = model
        // Component switch rendered as a SIDEBAR (the rig's "tabs → sidebar"
        // variety), with the chosen component in the detail pane.
        NavigationSplitView {
            List(Tab.allCases, selection: Binding(
                get: { model.selectedTab },
                set: { if let t = $0 { model.selectedTab = t } })) { tab in
                Label(tab.rawValue, systemImage: tab.icon).tag(tab)
            }
            .navigationSplitViewColumnWidth(min: 168, ideal: 190, max: 230)
            .navigationTitle("Miolingo")
        } detail: {
            Group {
                switch model.selectedTab {
                case .practice: PracticeView()
                case .story:    StoryView()
                case .vocab:    VocabView()
                case .settings: SettingsView()
                }
            }
            .frame(minWidth: 560, maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        }
        .frame(minWidth: 840, minHeight: 600)
    }
}
