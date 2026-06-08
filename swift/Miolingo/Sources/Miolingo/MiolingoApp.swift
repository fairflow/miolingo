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
