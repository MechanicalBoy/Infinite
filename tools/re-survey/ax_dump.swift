// re-survey ax_dump: read-only walk of one running app's macOS accessibility tree, printed as JSON.
// Reads attributes only; never performs an action, sets a value or sends a key. Built and run by
// ui_map.py (swiftc ships with the Command Line Tools). Usage: ax_dump <pid> [max_depth] [max_nodes] | ax_dump --windows <pid>
import ApplicationServices
import Foundation

let args = CommandLine.arguments
// `ax_dump --windows <pid>`: count the pid's normal windows (any Space; a full-screen app is off the current one) (>= 100x100) from the window server.
// Needs no accessibility and sees windows an app does not expose to it (GLFW, Java, custom toolkits).
if args.count == 3 && args[1] == "--windows", let wpid = Int(args[2]) {
    let list = (CGWindowListCopyWindowInfo([.optionAll, .excludeDesktopElements], kCGNullWindowID) as? [[String: Any]]) ?? []
    let n = list.filter { w in
        guard (w[kCGWindowOwnerPID as String] as? Int) == wpid, (w[kCGWindowLayer as String] as? Int) == 0,
              let b = w[kCGWindowBounds as String] as? [String: Any],
              let wd = b["Width"] as? Double, let ht = b["Height"] as? Double else { return false }
        return wd >= 100 && ht >= 100
    }.count
    print(n)
    exit(0)
}
guard args.count >= 2, let pid = pid_t(args[1]) else {
    FileHandle.standardError.write("usage: ax_dump <pid> [max_depth] [max_nodes]\n".data(using: .utf8)!)
    exit(2)
}
let maxDepth = args.count > 2 ? Int(args[2]) ?? 40 : 40
let maxNodes = args.count > 3 ? Int(args[3]) ?? 50000 : 50000
if !AXIsProcessTrusted() {
    FileHandle.standardError.write("not trusted for accessibility\n".data(using: .utf8)!)
    exit(3)
}

let app = AXUIElementCreateApplication(pid)
AXUIElementSetMessagingTimeout(app, 2.0)
var count = 0
var truncated = false

func attr(_ e: AXUIElement, _ name: String) -> AnyObject? {
    var v: AnyObject?
    return AXUIElementCopyAttributeValue(e, name as CFString, &v) == .success ? v : nil
}

func str(_ e: AXUIElement, _ name: String) -> String? {
    guard let v = attr(e, name) else { return nil }
    if let s = v as? String { return s.isEmpty ? nil : String(s.prefix(200)) }
    if let n = v as? NSNumber { return n.stringValue }
    return nil
}

func frame(_ e: AXUIElement) -> [Double]? {
    guard let p = attr(e, kAXPositionAttribute), let s = attr(e, kAXSizeAttribute) else { return nil }
    var pt = CGPoint.zero, sz = CGSize.zero
    AXValueGetValue(p as! AXValue, .cgPoint, &pt)
    AXValueGetValue(s as! AXValue, .cgSize, &sz)
    return [Double(pt.x), Double(pt.y), Double(sz.width), Double(sz.height)].map { ($0 * 10.0).rounded() / 10.0 }
}

func children(_ e: AXUIElement) -> [AXUIElement] {
    return (attr(e, kAXChildrenAttribute) as? [AXUIElement]) ?? []
}

func node(_ e: AXUIElement, _ depth: Int, menu: Bool) -> [String: Any] {
    count += 1
    var d: [String: Any] = [:]
    for (k, a) in [("role", kAXRoleAttribute), ("subrole", kAXSubroleAttribute), ("title", kAXTitleAttribute),
                   ("desc", kAXDescriptionAttribute), ("help", kAXHelpAttribute), ("id", kAXIdentifierAttribute),
                   ("roleDesc", kAXRoleDescriptionAttribute)] {
        if let s = str(e, a) { d[k] = s }
    }
    if menu {
        if let c = str(e, kAXMenuItemCmdCharAttribute) { d["key"] = c }
        if let g = str(e, kAXMenuItemCmdGlyphAttribute), g != "0" { d["glyph"] = g }
        if let m = attr(e, kAXMenuItemCmdModifiersAttribute) as? NSNumber { d["mods"] = m.intValue }
        if let en = attr(e, kAXEnabledAttribute) as? Bool, !en { d["disabled"] = true }
    } else {
        if let f = frame(e) { d["frame"] = f }
        if let v = attr(e, kAXValueAttribute) {
            if let s = v as? String, !s.isEmpty { d["value"] = String(s.prefix(80)) }
            else if let n = v as? NSNumber { d["value"] = n }
        }
    }
    if depth < maxDepth {
        var kids: [[String: Any]] = []
        for c in children(e) {
            if count >= maxNodes { truncated = true; break }
            kids.append(node(c, depth + 1, menu: menu))
        }
        if !kids.isEmpty { d["kids"] = kids }
    }
    return d
}

var out: [String: Any] = ["pid": Int(pid)]
if let mb = attr(app, kAXMenuBarAttribute) {
    out["menubar"] = node(mb as! AXUIElement, 0, menu: true)
}
let menuNodes = count
let wins = (attr(app, kAXWindowsAttribute) as? [AXUIElement]) ?? []
out["windows"] = wins.map { node($0, 0, menu: false) }
out["counts"] = ["menu": menuNodes, "window": count - menuNodes]
out["truncated"] = truncated
let data = try! JSONSerialization.data(withJSONObject: out, options: [])
FileHandle.standardOutput.write(data)
