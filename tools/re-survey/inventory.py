#!/usr/bin/env python3
"""re-survey inventory: what an app or plugin bundle is made of, without reading its code.

Uses only tools macOS ships (plutil via plistlib, otool, nm, lipo, codesign, strings).
Reports facts, never contents: Info.plist keys, file formats it claims, architectures,
linked/bundled frameworks (tech stack), plugin formats, signing, symbol COUNTS per
top-level namespace, and pillar keyword COUNTS from `strings`. No raw strings, symbol
names below namespace level, or code are ever written out.

Usage:
  python3 tools/re-survey/inventory.py /Applications/Bitwig\\ Studio.app [--out FILE] [--json FILE]
  python3 tools/re-survey/inventory.py --self-test
Default --out is ~/re-output/inventory/<name>.md.

Exit: 0 ok, 1 self-test failed, 2 usage error / path missing.
"""

import argparse
import collections
import json
import os
import plistlib
import re
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import PILLARS, RE_OUTPUT, SelfTest, human_bytes, md_table, run, write_out  # noqa: E402

MACHO_MAGIC = {b"\xcf\xfa\xed\xfe", b"\xce\xfa\xed\xfe", b"\xca\xfe\xba\xbe", b"\xfe\xed\xfa\xcf", b"\xbe\xba\xfe\xca"}

PLUGIN_EXT = {".vst3": "VST3", ".vst": "VST2", ".component": "AU", ".clap": "CLAP", ".aaxplugin": "AAX",
              ".appex": "App extension (AUv3 if AudioComponents)", ".bundle": "bundle", ".plugin": "plugin",
              ".tox": "TouchDesigner component", ".py": "Python script"}

# Framework/dylib name fragment -> what it tells us (tech stack). Licence notes matter for P5/P7 choices.
STACK = [
    ("Electron Framework", "Electron (JS shell; use REA, not native tools)"),
    ("app.asar", "Electron app.asar"),
    ("QtCore", "Qt"), ("Python.framework", "Embedded Python"), ("libpython", "Embedded Python"),
    ("Syphon", "Syphon (P7)"), ("libndi", "NDI (P7)"), ("NDI", "NDI (P7)"), ("Spout", "Spout (P7)"),
    ("libavcodec", "FFmpeg (LGPL/GPL build - check)"), ("libavformat", "FFmpeg (LGPL/GPL build - check)"),
    ("Sparkle", "Sparkle updater"), ("libtbb", "oneTBB threads (P8)"), ("tbb", "oneTBB threads (P8)"),
    ("libvulkan", "Vulkan"), ("MoltenVK", "MoltenVK (Vulkan on Metal)"), ("Metal.framework", "Metal"),
    ("OpenGL.framework", "OpenGL"), ("CoreML", "CoreML (P3)"), ("onnxruntime", "ONNX Runtime (P3)"),
    ("libtorch", "PyTorch (P3)"), ("tensorflow", "TensorFlow (P3)"), ("AudioToolbox", "Audio Units host/plugin"),
    ("CoreMIDI", "CoreMIDI"), ("libusd", "OpenUSD (P7)"), ("Alembic", "Alembic (P7)"), ("OpenVDB", "OpenVDB (P7)"),
    ("libembree", "Embree"), ("OpenImageIO", "OpenImageIO"), ("OpenColorIO", "OpenColorIO"),
    ("rubberband", "Rubber Band (GPL/commercial)"), ("elastique", "zplane elastique (P6)"),
    ("JavaScriptCore", "JavaScriptCore"), ("libluajit", "LuaJIT"), ("lua", "Lua"), ("juce", "JUCE"),
    ("libLTO", "LLVM (JIT or runtime compilation likely)"), ("libLLVM", "LLVM (JIT or runtime compilation likely)"),
    ("JavaVM", "Java VM (JVM)"), ("libjvm", "Java VM (JVM)"), ("Mono", "Mono / .NET"),
    ("Chromium Embedded", "CEF"), ("libcef", "CEF"), ("WebKit", "WebKit"), ("libspout", "Spout"),
]

# Pillar keyword counts over `strings` output (case-insensitive substrings). Counts only.
KEYWORDS = {
    "P1": ["osc", "midi", "ableton link", "timecode", "ltc", "show control", "cue"],
    "P2": ["modulat", "lfo", "envelope follower", "macro", "modulator", "mod matrix", "per-voice", "polyphonic"],
    "P3": ["machine learning", "neural", "onnx", "coreml", "tensorflow", "inference", "predict", "regression"],
    "P4": ["glsl", "hlsl", "spir-v", "shader", "python", "lua", "javascript", "webgpu", "expression"],
    "P5": ["vst3", "audiounit", "clap", "aax", "oversampl", "coreaudio", "asio", "latency", "dither"],
    "P6": ["timeline", "arrange", "warp", "stretch", "crossfade", "ripple", "compound", "retime", "lane"],
    "P7": ["syphon", "spout", "ndi", "dmx", "art-net", "sacn", "projection", "fbx", "usd", "alembic", "gltf", "instanc"],
    "P8": ["vulkan", "metal", "cuda", "opencl", "thread pool", "simd", "avx", "neon", "gpu", "cook"],
}

USAGE_KEYS = {
    "NSCameraUsageDescription": "camera", "NSMicrophoneUsageDescription": "microphone",
    "NSBluetoothAlwaysUsageDescription": "bluetooth", "NSLocalNetworkUsageDescription": "local network (OSC/NDI)",
    "NSAppleEventsUsageDescription": "Apple Events", "NSMotionUsageDescription": "motion sensors",
    "NSScreenCaptureUsageDescription": "screen capture", "NSPhotoLibraryUsageDescription": "photos",
}


def is_macho(path):
    try:
        with open(path, "rb") as f:
            return f.read(4) in MACHO_MAGIC
    except OSError:
        return False


def read_plist(path):
    try:
        with open(path, "rb") as f:
            return plistlib.load(f)
    except Exception:
        return None


def walk_bundle(root, max_files=200000):
    files, dirs = [], []
    if os.path.isfile(root):
        return [root], []
    for dp, dn, fn in os.walk(root):
        for d in dn:
            dirs.append(os.path.join(dp, d))
        for f in fn:
            files.append(os.path.join(dp, f))
            if len(files) >= max_files:
                return files, dirs
    return files, dirs


def plist_facts(root):
    p = os.path.join(root, "Contents", "Info.plist")
    if not os.path.exists(p):
        p = os.path.join(root, "Info.plist")
    d = read_plist(p) or {}
    facts = collections.OrderedDict()
    for k in ("CFBundleName", "CFBundleIdentifier", "CFBundleShortVersionString", "CFBundleVersion",
              "LSMinimumSystemVersion", "CFBundleExecutable", "NSPrincipalClass", "LSApplicationCategoryType"):
        if k in d:
            facts[k] = d[k]
    docs = []
    for t in d.get("CFBundleDocumentTypes", []) or []:
        exts = t.get("CFBundleTypeExtensions") or []
        utis = t.get("LSItemContentTypes") or []
        docs.append((t.get("CFBundleTypeName", ""), ", ".join(exts) or ", ".join(utis), t.get("CFBundleTypeRole", "")))
    for t in (d.get("UTExportedTypeDeclarations") or []) + (d.get("UTImportedTypeDeclarations") or []):
        tags = (t.get("UTTypeTagSpecification") or {}).get("public.filename-extension") or []
        if isinstance(tags, str):
            tags = [tags]
        docs.append((t.get("UTTypeDescription", t.get("UTTypeIdentifier", "")), ", ".join(tags), "UTI"))
    au = []
    for c in d.get("AudioComponents", []) or []:
        au.append(("au:%s:%s:%s" % (c.get("type", ""), c.get("subtype", ""), c.get("manufacturer", "")), c.get("name", "")))
    usage = sorted(v for k, v in USAGE_KEYS.items() if k in d)
    schemes = [s for t in (d.get("CFBundleURLTypes") or []) for s in (t.get("CFBundleURLSchemes") or [])]
    return facts, docs, au, usage, schemes


def archs(path):
    rc, out, _ = run(["lipo", "-archs", path], timeout=30)
    return out.strip() if rc == 0 else "?"


def linked_libs(path):
    rc, out, _ = run(["otool", "-L", path], timeout=60)
    libs = []
    if rc == 0:
        for line in out.splitlines()[1:]:
            line = line.strip()
            if line:
                libs.append(line.split(" (")[0])
    return libs


def classify_lib(lib):
    if lib.startswith("/System/Library/Frameworks/") or lib.startswith("/System/Library/PrivateFrameworks/"):
        return "system", lib.split("/")[4].replace(".framework", "")
    if lib.startswith("/usr/lib/"):
        return "system", os.path.basename(lib)
    return "bundled", os.path.basename(lib.split(".framework")[0]) if ".framework" in lib else os.path.basename(lib)


def symbol_namespaces(path, top=15):
    """Count exported symbols per top-level C++ namespace / ObjC class prefix. Counts only."""
    rc, out, _ = run(["nm", "-gUjC", path], timeout=120)
    if rc != 0:
        return 0, []
    c = collections.Counter()
    total = 0
    for s in out.splitlines():
        s = s.strip()
        if not s:
            continue
        total += 1
        if "::" in s:
            ns = s.split("::")[0].split(" ")[-1].split("<")[0]
            c[ns + "::"] += 1
        elif s.startswith("_OBJC_CLASS_$_"):
            c["ObjC classes"] += 1
        elif s.startswith("_$s"):
            c["Swift"] += 1
        else:
            c["C / other"] += 1
    return total, c.most_common(top)


def keyword_counts(paths, budget_bytes=600 * 1024 * 1024):
    counts = {p: collections.Counter() for p in KEYWORDS}
    scanned = 0
    for path in paths:
        try:
            size = os.path.getsize(path)
        except OSError:
            continue
        if scanned + size > budget_bytes:
            break
        scanned += size
        rc, out, _ = run(["strings", "-n", "5", path], timeout=300)
        if rc != 0:
            continue
        low = out.lower()
        for pillar, words in KEYWORDS.items():
            for w in words:
                n = low.count(w)
                if n:
                    counts[pillar][w] += n
    return counts, scanned


def codesign_facts(root):
    rc, out, err = run(["codesign", "-dv", "--verbose=2", root], timeout=60)
    text = out + err
    facts = {}
    for key in ("TeamIdentifier", "Identifier", "Format"):
        m = re.search(r"^%s=(.*)$" % key, text, re.M)
        if m:
            facts[key] = m.group(1)
    m = re.search(r"flags=0x[0-9a-f]+\(([^)]*)\)", text)
    if m:
        facts["flags"] = m.group(1)
    auth = re.findall(r"^Authority=(.*)$", text, re.M)
    if auth:
        facts["Authority"] = auth[0]
    rc, out, err = run(["codesign", "-d", "--entitlements", "-", "--xml", root], timeout=60)
    ents = re.findall(r"<key>([^<]+)</key>", out)
    facts["entitlements"] = sorted(set(ents))
    return facts


def inventory(root):
    root = os.path.abspath(root.rstrip("/"))
    files, dirs = walk_bundle(root)
    total = 0
    by_ext = collections.Counter()
    for f in files:
        try:
            total += os.path.getsize(f)
        except OSError:
            pass
        by_ext[os.path.splitext(f)[1].lower() or "(none)"] += 1
    facts, docs, au, usage, schemes = plist_facts(root)
    exe = None
    if os.path.isfile(root):
        exe = root
    elif facts.get("CFBundleExecutable"):
        exe = os.path.join(root, "Contents", "MacOS", facts["CFBundleExecutable"])
    machos = sorted([f for f in files if is_macho(f)], key=lambda p: -os.path.getsize(p))
    if exe and not os.path.exists(exe):
        exe = machos[0] if machos else None
    plugins = collections.Counter()
    plugin_examples = collections.defaultdict(list)
    for d in dirs + [f for f in files if f.endswith((".tox", ".py"))]:
        ext = os.path.splitext(d)[1].lower()
        if ext in PLUGIN_EXT:
            plugins[PLUGIN_EXT[ext]] += 1
            if len(plugin_examples[PLUGIN_EXT[ext]]) < 3:
                plugin_examples[PLUGIN_EXT[ext]].append(os.path.basename(d))
    frameworks = sorted({os.path.basename(d) for d in dirs if d.endswith(".framework")})
    # Nested apps / XPC services = separate processes (audio engine, renderer, plugin sandbox...).
    helpers = sorted({os.path.relpath(d, root) for d in dirs if d.endswith((".app", ".xpc")) and d != root
                      and ".app/" not in os.path.relpath(d, root)})
    libs = linked_libs(exe) if exe else []
    sys_libs = sorted({classify_lib(l)[1] for l in libs if classify_lib(l)[0] == "system"})
    bundled = sorted({classify_lib(l)[1] for l in libs if classify_lib(l)[0] == "bundled"})
    names = " ".join(frameworks + bundled + sys_libs + [os.path.basename(f) for f in machos[:400]])
    names += " " + " ".join(os.path.basename(f) for f in files if f.endswith(".asar"))
    stack = []
    for frag, label in STACK:
        if frag.lower() in names.lower() and label not in stack:
            stack.append(label)
    sym_total, namespaces = symbol_namespaces(exe) if exe else (0, [])
    kw, scanned = keyword_counts(machos[:25])
    return {
        "path": root, "name": os.path.basename(root), "size": total, "files": len(files),
        "plist": facts, "doc_types": docs, "audio_components": au, "usage": usage, "url_schemes": schemes,
        "executable": os.path.relpath(exe, root) if exe and exe != root else exe,
        "archs": archs(exe) if exe else "?", "macho_count": len(machos),
        "biggest_binaries": [(os.path.relpath(m, root) if m != root else os.path.basename(m), os.path.getsize(m)) for m in machos[:8]],
        "frameworks": frameworks, "helpers": helpers, "linked_system": sys_libs, "linked_bundled": bundled,
        "stack": stack, "plugins": dict(plugins), "plugin_examples": dict(plugin_examples),
        "ext_histogram": by_ext.most_common(15), "codesign": codesign_facts(root),
        "exported_symbols": sym_total, "namespaces": namespaces,
        "keywords": {p: dict(c.most_common()) for p, c in kw.items()}, "strings_scanned": scanned,
    }


def to_markdown(r):
    L = ["# Inventory: %s" % r["name"], "",
         "Generated by `tools/re-survey/inventory.py` from bundle metadata and macOS tools only. "
         "Counts and facts, no code or raw strings.", ""]
    L += ["## Identity", "", md_table(["Key", "Value"], list(r["plist"].items()) + [
        ("Path", r["path"]), ("Size", "%s in %d files" % (human_bytes(r["size"]), r["files"])),
        ("Executable", r["executable"]), ("Architectures", r["archs"]),
        ("Mach-O files", r["macho_count"]), ("Exported symbols (main exe)", r["exported_symbols"])]), ""]
    cs = r["codesign"]
    L += ["## Signing", "", md_table(["Key", "Value"], [(k, ", ".join(v) if isinstance(v, list) else v) for k, v in cs.items()]), ""]
    if r["usage"] or r["url_schemes"]:
        L += ["## Privacy capabilities and URL schemes", "",
              "- Usage descriptions: " + (", ".join(r["usage"]) or "none"),
              "- URL schemes: " + (", ".join(r["url_schemes"]) or "none"), ""]
    if r["doc_types"]:
        L += ["## File formats it claims", "", md_table(["Name", "Extensions / UTIs", "Role"], r["doc_types"]), ""]
    if r["audio_components"]:
        L += ["## Audio Unit components (plugin_probe ids)", "", md_table(["id", "name"], r["audio_components"]), ""]
    L += ["## Tech stack (from framework and library names)", "", "- " + ("\n- ".join(r["stack"]) or "nothing recognised"), ""]
    if r["plugins"]:
        L += ["## Bundled plugins / extensions", "", md_table(["Kind", "Count", "Examples"],
              [(k, v, ", ".join(r["plugin_examples"].get(k, []))) for k, v in sorted(r["plugins"].items())]), ""]
    if r["helpers"]:
        L += ["## Helper processes (nested apps / XPC services)", "",
              "Separate processes are an architecture fact (P5 plugin sandboxing, P8 engine isolation).", "",
              "\n".join("- " + h for h in r["helpers"]), ""]
    L += ["## Bundled frameworks", "", (", ".join(r["frameworks"]) or "none"), "",
          "## Linked system frameworks (main exe)", "", (", ".join(r["linked_system"]) or "none"), "",
          "## Linked non-system libraries (main exe)", "", (", ".join(r["linked_bundled"]) or "none"), ""]
    L += ["## Biggest binaries", "", md_table(["File", "Size"], [(f, human_bytes(s)) for f, s in r["biggest_binaries"]]), ""]
    if r["namespaces"]:
        L += ["## Exported symbols by top-level namespace (counts)", "", md_table(["Namespace", "Count"], r["namespaces"]), ""]
    rows = []
    for p, words in r["keywords"].items():
        top = sorted(words.items(), key=lambda kv: -kv[1])[:6]
        rows.append((p, PILLARS[p], sum(words.values()), ", ".join("%s %d" % kv for kv in top)))
    L += ["## Pillar keyword counts (`strings`, %s scanned)" % human_bytes(r["strings_scanned"]), "",
          "Hints where to look, not findings. A high count is a question for the dossier, not an answer.", "",
          md_table(["Pillar", "Name", "Hits", "Top keywords"], rows), ""]
    L += ["## File types", "", md_table(["Extension", "Files"], r["ext_histogram"]), ""]
    return "\n".join(L)


def self_test():
    t = SelfTest("inventory")
    tmp = tempfile.mkdtemp(prefix="re-inv-")
    try:
        app = os.path.join(tmp, "Fake.app")
        os.makedirs(os.path.join(app, "Contents", "MacOS"))
        os.makedirs(os.path.join(app, "Contents", "Frameworks", "Syphon.framework"))
        os.makedirs(os.path.join(app, "Contents", "PlugIns", "Thing.vst3"))
        shutil.copy("/usr/bin/true", os.path.join(app, "Contents", "MacOS", "Fake"))
        with open(os.path.join(app, "Contents", "Info.plist"), "wb") as f:
            plistlib.dump({"CFBundleName": "Fake", "CFBundleExecutable": "Fake", "CFBundleShortVersionString": "1.2.3",
                           "CFBundleIdentifier": "test.fake", "NSMicrophoneUsageDescription": "x",
                           "CFBundleDocumentTypes": [{"CFBundleTypeName": "Fake Patch", "CFBundleTypeExtensions": ["fkp"],
                                                      "CFBundleTypeRole": "Editor"}],
                           "AudioComponents": [{"type": "aufx", "subtype": "fake", "manufacturer": "Test", "name": "T: F"}]}, f)
        r = inventory(app)
        md = to_markdown(r)
        t.check(r["plist"].get("CFBundleShortVersionString") == "1.2.3", "Info.plist version read")
        t.check(r["archs"] not in ("", "?"), "lipo found architectures (%s)" % r["archs"])
        t.check(r["plugins"].get("VST3") == 1, "VST3 plugin bundle detected")
        t.check("Syphon (P7)" in r["stack"], "Syphon framework recognised in stack")
        t.check(("Fake Patch", "fkp", "Editor") in r["doc_types"], "document type extension listed")
        t.check(r["audio_components"] == [("au:aufx:fake:Test", "T: F")], "AU id in plugin_probe format")
        t.check("microphone" in r["usage"], "privacy usage key mapped")
        t.check(r["macho_count"] == 1, "Mach-O detection by magic")
        t.check("## Pillar keyword counts" in md and "| P5 |" in md, "markdown has pillar table")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return t.done()


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("path", nargs="?")
    ap.add_argument("--out", help="markdown path ('-' = stdout); default ~/re-output/inventory/<name>.md")
    ap.add_argument("--json", help="also write raw facts as JSON")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if not a.path or not os.path.exists(a.path):
        ap.print_usage(sys.stderr)
        return 2
    r = inventory(a.path)
    out = a.out or os.path.join(RE_OUTPUT, "inventory", os.path.splitext(r["name"])[0].replace(" ", "_") + ".md")
    write_out(to_markdown(r), out)
    if a.json:
        write_out(json.dumps(r, indent=1, default=str), a.json)
    if out != "-":
        print("wrote %s" % out, file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
