import SwiftUI
import MiolingoCore

// =====================================================================
// SwiftUILoft — the macOS "loft": forges Fittings into SwiftUI widgets from a
// Berth (typed Cleats) + a Rig (Cleat → Fitting) + a BerthDriver (the L1
// boundary). A second loft (ComposeLoft / WebLoft) would consume the SAME
// Berth + Rig. This is the prototype that tests "does the rig inform coding".
// =====================================================================

enum SwiftUILoft {
    /// Render grouped by a DeckPlan (layout): each group is a titled section in
    /// the declared order. The rig gives control KINDS, the deck-plan gives WHERE.
    static func render(_ berth: Berth, rig: Rig, deck: DeckPlan, driver: BerthDriver) -> AnyView {
        let live = driver.afforded()
        let byName = Dictionary(uniqueKeysWithValues: berth.cleats.map { ($0.name, $0) })
        return AnyView(
            VStack(alignment: .leading, spacing: 16) {
                ForEach(deck.groups) { group in
                    VStack(alignment: .leading, spacing: 8) {
                        if let t = group.title { Text(t).font(.headline) }
                        ForEach(group.cleats, id: \.self) { name in
                            if let cleat = byName[name], isLive(cleat, live) {
                                control(cleat, rig[name] ?? defaultFitting(cleat), driver, berth)
                            }
                        }
                    }
                }
            })
    }

    static func render(_ berth: Berth, rig: Rig, driver: BerthDriver) -> AnyView {
        let live = driver.afforded()
        return AnyView(
            VStack(alignment: .leading, spacing: 14) {
                ForEach(berth.cleats) { cleat in
                    if isLive(cleat, live) {
                        control(cleat, rig[cleat.name] ?? defaultFitting(cleat), driver, berth)
                    }
                }
            })
    }

    // projections always render; input/trigger only when afforded (L1 ready set)
    private static func isLive(_ c: Cleat, _ live: Set<String>) -> Bool {
        if case .projection = c.role { return true }
        return live.contains(c.name)
    }

    private static func defaultFitting(_ c: Cleat) -> Fitting {
        switch c.role {
        case .trigger: return .button
        case .projection: return .panel
        case .input(let t):
            switch t {
            case .bool: return .toggle
            case .bounded: return .slider
            case .code: return .choice(.menu)
            default: return .textField
            }
        }
    }

    @ViewBuilder
    private static func control(_ cleat: Cleat, _ fitting: Fitting,
                                _ d: BerthDriver, _ berth: Berth) -> some View {
        let title = label(cleat.name)
        switch (cleat.role, fitting) {
        case (.trigger, _):
            Button(title) { d.emit(cleat.name, .unit) }

        case (.input, .textField):
            HStack { Text(title).frame(width: 110, alignment: .leading)
                TextField(title, text: textBinding(d, cleat.name)) }

        case (.input, .choice(let style)):
            choiceControl(title, choices(cleat, d), style, choiceBinding(d, cleat, berth))

        case (.input, .slider):
            let r = range(cleat)
            HStack { Text("\(title): \(d.value(for: cleat.name).asInt)").frame(width: 140, alignment: .leading)
                Slider(value: intBinding(d, cleat.name), in: r, step: 10) }

        case (.input, .toggle):
            Toggle(title, isOn: boolBinding(d, cleat.name))

        case (.input, .stepper):
            Stepper(title, value: intBinding(d, cleat.name), in: range(cleat))

        case (.projection, .panel):
            panel(title, d.value(for: cleat.name))

        case (.projection, .collection):
            collection(d.value(for: cleat.name))

        default:
            Text("⚠ no loft for \(title) [\(String(describing: fitting))]").foregroundStyle(.red)
        }
    }

    // --- choice realizations: the rig's one-line lever ---
    @ViewBuilder
    private static func choiceControl(_ title: String, _ opts: [Choice],
                                      _ style: Fitting.ChoiceStyle,
                                      _ sel: Binding<String>) -> some View {
        let picker = Picker(title, selection: sel) {
            ForEach(opts) { Text($0.label).tag($0.id) }
        }
        switch style {
        case .segmented:        picker.pickerStyle(.segmented)
        case .radio:            picker.pickerStyle(.radioGroup)
        case .menu, .sidebar:   picker.pickerStyle(.menu)
        case .tabs:             picker.pickerStyle(.segmented)   // tabs ≈ segmented for an inline choice
        }
    }

    @ViewBuilder
    private static func panel(_ title: String, _ value: PlimValue) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(title).font(.headline)
            if case let .record(fields) = value {
                ForEach(fields) { f in
                    HStack { Text(f.key).foregroundStyle(.secondary).frame(width: 100, alignment: .leading)
                        Text(f.display) }.font(.callout)
                }
            }
        }
        .padding(8).frame(maxWidth: .infinity, alignment: .leading)
        .background(.quaternary, in: RoundedRectangle(cornerRadius: 8))
    }

    @ViewBuilder
    private static func collection(_ value: PlimValue) -> some View {
        if case let .list(items) = value {
            ForEach(Array(items.enumerated()), id: \.offset) { _, item in
                if case let .record(fields) = item {
                    HStack { ForEach(fields) { Text($0.display) }.font(.callout) }
                }
            }
        }
    }

    // --- helpers ---
    private static func label(_ name: String) -> String {
        let s = name.hasPrefix("set_") ? String(name.dropFirst(4)) : name
        return s.replacingOccurrences(of: "_", with: " ").capitalized
    }
    private static func choices(_ c: Cleat, _ d: BerthDriver) -> [Choice] {
        guard case let .input(t) = c.role, case let .code(dom) = t else { return [] }
        switch dom { case .fixed(let cs): return cs; case .dynamic: return d.domain(for: c.name) }
    }

    /// A choice binding that enforces `distinct` constraints by SWAP-ON-COLLISION:
    /// picking a value held by a mutex peer pushes this cleat's old value onto that
    /// peer (source ↔ target swap), rather than excluding it from the domain — so
    /// every configuration is reachable in one action.
    private static func choiceBinding(_ d: BerthDriver, _ cleat: Cleat, _ berth: Berth) -> Binding<String> {
        Binding(
            get: { d.value(for: cleat.name).asCode },
            set: { v in
                let old = d.value(for: cleat.name).asCode
                for case let .distinct(group) in berth.constraints where group.contains(cleat.name) {
                    for peer in group where peer != cleat.name {
                        if d.value(for: peer).asCode == v { d.emit(peer, .code(old)) }
                    }
                }
                d.emit(cleat.name, .code(v))
            })
    }
    private static func range(_ c: Cleat) -> ClosedRange<Double> {
        if case let .input(t) = c.role, case let .bounded(lo, hi) = t { return Double(lo)...Double(hi) }
        return 0...100
    }
    private static func textBinding(_ d: BerthDriver, _ n: String) -> Binding<String> {
        Binding(get: { d.value(for: n).asText }, set: { d.emit(n, .text($0)) })
    }
    private static func codeBinding(_ d: BerthDriver, _ n: String) -> Binding<String> {
        Binding(get: { d.value(for: n).asCode }, set: { d.emit(n, .code($0)) })
    }
    private static func intBinding(_ d: BerthDriver, _ n: String) -> Binding<Double> {
        Binding(get: { Double(d.value(for: n).asInt) }, set: { d.emit(n, .int(Int($0))) })
    }
    private static func boolBinding(_ d: BerthDriver, _ n: String) -> Binding<Bool> {
        Binding(get: { if case let .bool(b) = d.value(for: n) { return b }; return false },
                set: { d.emit(n, .bool($0)) })
    }
}

// =====================================================================
// The Helm berth, declared as typed Cleats + a default Rig. This is the whole
// "spec" the loft needs to generate the Settings UI.
// =====================================================================

let helmBerth = Berth("Helm", [
    Cleat("set_source", .input(.code(.dynamic("languages")))),
    Cleat("set_target", .input(.code(.dynamic("languages")))),
    Cleat("set_tts",    .input(.code(.fixed([
        Choice("system", "System"), Choice("espeak", "espeak"), Choice("google", "google")])))),
    Cleat("set_speed",  .input(.bounded(80, 450))),
    Cleat("view",       .projection(.record(["source", "target", "language", "tts", "speed"]))),
], constraints: [
    .distinct(["set_source", "set_target"]),   // a language can't be both
])

// The lever: flip set_tts to .choice(.radio) / .choice(.menu), or set_target to
// .choice(.segmented), and the widget changes — no other code touched.
let defaultHelmRig: Rig = [
    "set_source": .choice(.menu),
    "set_target": .choice(.menu),
    "set_tts":    .choice(.segmented),
    "set_speed":  .slider,
    "view":       .panel,
]

/// Adapts AppModel (the component) to the platform-neutral BerthDriver. The loft
/// only ever calls these on the main thread (UI), so MainActor.assumeIsolated lets
/// the driver read/emit the @MainActor model while the protocol stays nonisolated.
struct HelmBerthDriver: BerthDriver {
    let model: AppModel
    func value(for cleat: String) -> PlimValue {
        MainActor.assumeIsolated {
            let v = model.helm.view
            switch cleat {
            case "set_source": return .code(model.sourceCode)   // source as a CODE (dropdown)
            case "set_target": return .code(v.target)
            case "set_tts":    return .code(v.tts.rawValue)
            case "set_speed":  return .int(v.speed)
            case "view":       return .record([
                .init("source", .text(v.source)), .init("target", .text(v.target)),
                .init("language", .text(v.language)), .init("tts", .text(v.tts.rawValue)),
                .init("speed", .int(v.speed))])
            default: return .none
            }
        }
    }
    func domain(for cleat: String) -> [Choice] {
        MainActor.assumeIsolated {
            (cleat == "set_target" || cleat == "set_source")
                ? model.languages().map { Choice($0.code, "\($0.name) (\($0.code))") } : []
        }
    }
    func afforded() -> Set<String> {
        MainActor.assumeIsolated {
            var s: Set<String> = ["set_source", "set_target", "set_tts", "view"]
            if model.helm.showsSpeed { s.insert("set_speed") }   // espeak-only (L1 guard)
            return s
        }
    }
    func emit(_ cleat: String, _ value: PlimValue) {
        MainActor.assumeIsolated {
            switch cleat {
            case "set_source": model.setSourceByCode(value.asCode)
            case "set_target": model.setTarget(value.asCode)
            case "set_tts":    if let k = TTSKind(rawValue: value.asCode) { model.setTTS(k) }
            case "set_speed":  model.setSpeed(value.asInt)
            default: break
            }
        }
    }
}

/// The Settings UI GENERATED from helmBerth + defaultHelmRig (no hand-written
/// controls). Compare with the hand-written SettingsView.
struct RiggedHelmView: View {
    @Environment(AppModel.self) private var model
    var body: some View {
        let (berth, rig, deck) = RiggedHelmView.loaded()
        SwiftUILoft.render(berth, rig: rig, deck: deck, driver: HelmBerthDriver(model: model))
    }

    /// Load the berth/rig/deck-plan from the JSON grammar (Bundle resources);
    /// fall back to the in-code declarations if a file is missing. Proves the
    /// spec→JSON→loft flow while staying robust.
    static func loaded() -> (Berth, Rig, DeckPlan) {
        func data(_ name: String) -> Data? {
            BundledResource.url(forResource: name, withExtension: "json").flatMap { try? Data(contentsOf: $0) }
        }
        let berth = data("berth.helm").flatMap { try? RigGrammar.berth(from: $0) } ?? helmBerth
        let rig = data("rig.swiftui").flatMap { try? RigGrammar.rig(from: $0) } ?? defaultHelmRig
        let deck = data("deckplan.helm").flatMap { try? RigGrammar.deckPlan(from: $0) }
            ?? DeckPlan(berth: "Helm", groups: [DeckGroup(title: nil, cleats: helmBerth.cleats.map(\.name))])
        return (berth, rig, deck)
    }
}
