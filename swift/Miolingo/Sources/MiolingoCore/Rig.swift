import Foundation

// =====================================================================
// Rig — a prototype of the L2→L3 binding language the methodology calls for
// ("you rig a port to a control"; METHODOLOGY.md, methodology-and-skill-suite.md).
// Platform-NEUTRAL on purpose (it's a typing + binding language for a
// multi-platform effort); the SwiftUI renderer ("loft") lives in the app target.
//
// Invented vocabulary (nautical, to match rig/walk/helm/hold):
//   • Plimsoll — the payload TYPE language (the "load line": what a port may carry).
//   • Cleat    — a typed port: name + role + Plimsoll type. The fixed point you
//                rig a control onto. (The sort is the set of all Cleats.)
//   • Fitting  — an abstract control KIND (button, field, choice, …). Rigging maps
//                Cleats → Fittings; the loft forges Fittings into native widgets.
//   • Berth    — a component's surface: its group of Cleats.
//   • Loft     — a platform renderer of Fittings → widgets (SwiftUILoft, etc.).
//
// What's L1 (not here): which Cleats are LIVE — the afforded/ready set — is the
// component's on-the-fly `readyPorts` query (METHODOLOGY.md). The rig is over the
// whole sort; afforded-ports gates it at runtime. The two compose, stay distinct.
// =====================================================================

// --- Plimsoll: the payload type language ------------------------------
public indirect enum Plimsoll: Equatable, Sendable {
    case unit                       // no payload (a trigger)
    case bool
    case int
    case text                       // free text
    case word                       // a single token (shape hint; validateWord is the semantic guard — NOT in the type)
    case bounded(Int, Int)          // an Int in a closed range → slider/stepper
    case code(Domain)               // a value from a closed set (enum) — static or dynamic
    case index(of: String)          // a position into a list-typed projection (cleat name)
    case record([String])           // an ordered set of field names (a projection)
    case list(Plimsoll)             // a collection
    case audio
    case blob

    public enum Domain: Equatable, Sendable {
        case fixed([Choice])        // enum cases known statically
        case dynamic(String)        // domain supplied at runtime by the named cleat/source
    }
}

/// One option in a `code` domain.
public struct Choice: Equatable, Sendable, Identifiable {
    public let id: String
    public let label: String
    public init(_ id: String, _ label: String) { self.id = id; self.label = label }
}

// --- Role: how a port participates (from the port-boundary analysis) ---
public enum Role: Equatable, Sendable {
    case trigger                    // value-less input  (coLabel[nm])
    case input(Plimsoll)            // value-carrying input (coLabel[nm, binding])
    case projection(Plimsoll)       // read-only output view (label view! param)
    // internal/restricted channels (τ) are below the UI boundary → never rigged.
}

// --- Cleat: a typed port ----------------------------------------------
public struct Cleat: Equatable, Sendable, Identifiable {
    public let name: String
    public let role: Role
    public init(_ name: String, _ role: Role) { self.name = name; self.role = role }
    public var id: String { name }
}

// --- Constraint: a relation the rig enforces ACROSS cleats -------------
// (the grammar must express more than per-port types; this is the first
// cross-cleat relation — mutual exclusion of choice domains.)
public enum Constraint: Equatable, Sendable {
    /// these cleats must hold DIFFERENT values; each one's choice domain
    /// excludes the values currently held by the others (e.g. source ≠ target).
    case distinct([String])
}

// --- Berth: a component's rigging surface ------------------------------
public struct Berth: Sendable {
    public let name: String
    public let cleats: [Cleat]
    public let constraints: [Constraint]
    public init(_ name: String, _ cleats: [Cleat], constraints: [Constraint] = []) {
        self.name = name; self.cleats = cleats; self.constraints = constraints
    }
}

// --- Fitting: an abstract control kind --------------------------------
public enum Fitting: Equatable, Sendable {
    case button
    case textField
    case stepper
    case slider
    case toggle
    case choice(ChoiceStyle)        // realization of a `code` input
    case panel                      // a record projection
    case collection                 // a list projection (rows + per-row triggers)

    public enum ChoiceStyle: Equatable, Sendable {
        case segmented, radio, menu, tabs, sidebar
    }
}

/// A Rig binds Cleat names → Fittings. Changing one entry (e.g. choice(.menu) →
/// choice(.radio) or .tabs) re-skins that control with no other code change.
public typealias Rig = [String: Fitting]

// --- PlimValue: the canonical runtime value crossing the loft boundary -
// (the cross-platform wire form of a Plimsoll value)
public enum PlimValue: Equatable, Sendable {
    case unit
    case bool(Bool)
    case int(Int)
    case text(String)
    case code(String)               // the chosen Choice id
    case record([RecordField])
    case list([PlimValue])
    case none

    public var asText: String { if case let .text(s) = self { return s }; if case let .code(s) = self { return s }; return "" }
    public var asInt: Int { if case let .int(n) = self { return n }; return 0 }
    public var asCode: String { if case let .code(s) = self { return s }; return "" }
}

public struct RecordField: Equatable, Sendable, Identifiable {
    public let key: String
    public let value: PlimValue
    public init(_ key: String, _ value: PlimValue) { self.key = key; self.value = value }
    public var id: String { key }
    public var display: String {
        switch value {
        case .text(let s), .code(let s): return s
        case .int(let n): return String(n)
        case .bool(let b): return b ? "yes" : "no"
        case .none: return "—"
        default: return ""
        }
    }
}

// --- BerthDriver: what a loft asks the component (the L1 boundary) ------
// A platform-neutral adapter: current values for projections/choices, dynamic
// domains, the afforded set, and an event sink for inputs. Note inputs are
// EVENTS (emit), not two-way bindings — faithful to CCS (an input produces a
// successor, it is not mutable shared state).
public protocol BerthDriver {
    func value(for cleat: String) -> PlimValue
    func domain(for cleat: String) -> [Choice]
    func afforded() -> Set<String>
    func emit(_ cleat: String, _ value: PlimValue)
}
