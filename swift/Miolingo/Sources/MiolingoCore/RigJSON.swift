import Foundation

// =====================================================================
// RigJSON — load a Berth + Rig + DeckPlan from the language-neutral JSON
// grammar (Phase 3). The grammar is the source of truth; the Swift loft is one
// consumer, a future ComposeLoft/WebLoft another. Types are a compact string
// tag (e.g. "code:dynamic:languages", "bounded:80:450") so any platform can
// parse them without polymorphic-JSON gymnastics.
// =====================================================================

// --- the wire DTOs (Decodable straight from the JSON files) ---
struct BerthJSON: Decodable {
    let schema: String
    let berth: String
    let cleats: [CleatJSON]
    let constraints: [[String: [String]]]?      // e.g. [{"distinct": ["set_source","set_target"]}]
    struct CleatJSON: Decodable { let name: String; let role: String; let type: String? }
}
struct RigJSON_: Decodable { let schema: String; let `for`: String; let fittings: [String: String] }
struct DeckJSON: Decodable {
    let schema: String; let `for`: String; let groups: [Group]
    struct Group: Decodable { let title: String?; let cleats: [String] }
}

public enum RigGrammar {
    /// Parse a Plimsoll type from its string tag.
    static func plimsoll(_ tag: String) -> Plimsoll {
        let parts = tag.components(separatedBy: ":")
        switch parts.first {
        case "unit":  return .unit
        case "bool":  return .bool
        case "int":   return .int
        case "text":  return .text
        case "word":  return .word
        case "audio": return .audio
        case "blob":  return .blob
        case "bounded":
            if parts.count == 3, let lo = Int(parts[1]), let hi = Int(parts[2]) { return .bounded(lo, hi) }
            return .int
        case "index":
            return .index(of: parts.count > 1 ? parts[1] : "")
        case "record":
            let fields = parts.count > 1 ? parts[1].components(separatedBy: ",").filter { !$0.isEmpty } : []
            return .record(fields)
        case "code":
            // code:dynamic:<source>  OR  code:fixed:id=Label,id=Label,…
            if parts.count >= 3, parts[1] == "dynamic" { return .code(.dynamic(parts[2])) }
            if parts.count >= 3, parts[1] == "fixed" {
                let opts = parts[2...].joined(separator: ":").components(separatedBy: ",").compactMap { pair -> Choice? in
                    let kv = pair.components(separatedBy: "=")
                    guard kv.count == 2 else { return nil }
                    return Choice(kv[0], kv[1])
                }
                return .code(.fixed(opts))
            }
            return .text
        default: return .text
        }
    }

    static func role(_ s: String, _ type: Plimsoll) -> Role {
        switch s {
        case "trigger":    return .trigger
        case "projection": return .projection(type)
        default:           return .input(type)
        }
    }

    static func fitting(_ s: String) -> Fitting {
        switch s {
        case "button":     return .button
        case "textField":  return .textField
        case "stepper":    return .stepper
        case "slider":     return .slider
        case "toggle":     return .toggle
        case "panel":      return .panel
        case "collection": return .collection
        case "choice.segmented": return .choice(.segmented)
        case "choice.radio":     return .choice(.radio)
        case "choice.menu":      return .choice(.menu)
        case "choice.tabs":      return .choice(.tabs)
        case "choice.sidebar":   return .choice(.sidebar)
        default: return .textField
        }
    }

    /// Build a Berth from its JSON.
    public static func berth(from data: Data) throws -> Berth {
        let j = try JSONDecoder().decode(BerthJSON.self, from: data)
        let cleats = j.cleats.map { c -> Cleat in
            let t = plimsoll(c.type ?? "unit")
            return Cleat(c.name, role(c.role, t))
        }
        let constraints: [Constraint] = (j.constraints ?? []).compactMap { dict in
            if let group = dict["distinct"] { return .distinct(group) }
            return nil
        }
        return Berth(j.berth, cleats, constraints: constraints)
    }

    /// Build a Rig (cleat → fitting) from its JSON.
    public static func rig(from data: Data) throws -> Rig {
        let j = try JSONDecoder().decode(RigJSON_.self, from: data)
        return j.fittings.mapValues { fitting($0) }
    }

    /// Build a DeckPlan from its JSON.
    public static func deckPlan(from data: Data) throws -> DeckPlan {
        let j = try JSONDecoder().decode(DeckJSON.self, from: data)
        return DeckPlan(berth: j.for, groups: j.groups.map { DeckGroup(title: $0.title, cleats: $0.cleats) })
    }
}
