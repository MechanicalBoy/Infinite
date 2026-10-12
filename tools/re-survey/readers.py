#!/usr/bin/env python3
"""re-survey format readers: summarise a competitor's project / catalog files as facts.

Each reader reads a documented or self-describing file format (JSON, XML, the vendor's own
expand tool, Blender's public Python API) and prints counts and structure: what kinds of
things a project contains and how they connect. No code is read: cables reads only op
*.json metadata (never the .js), TouchDesigner goes through Derivative's own toeexpand,
Blender through its public bpy API in our own script (blender_dump.py).

Readers:
  cables  <ops dir> | --fetch    cables.gl op catalog (namespaces, port types)       Q1/Q6, C2
  amxd    <file.amxd>            Max for Live device (objects, live.* params, mods)   Q1, C3
  als     <file.als>             Ableton Live set (tracks, clips, warp, automation)   Q4, C9
  fcpxml  <file.fcpxml|.fcpxmld> Final Cut XML (spine, lanes, roles, compound, retime) Q4, C10
  toe     <file.toe|.tox>        TouchDesigner network (operator families, wires, exports) Q1/Q2, C1
  blender <file.blend> | --demo  Geometry Nodes trees (node types, fields, domains, zones) Q5, C11

Usage:
  python3 tools/re-survey/readers.py als ~/x.als [--out FILE] [--json FILE]
  python3 tools/re-survey/readers.py cables --fetch [--infinite describe.json]
  python3 tools/re-survey/readers.py --self-test
Exit: 0 ok, 1 self-test failed or file unreadable, 2 usage error.
"""

import argparse
import collections
import glob
import gzip
import json
import os
import re
import shutil
import struct
import sys
import tempfile
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import RE_OUTPUT, RE_TMP, SelfTest, ensure_dir, md_table, run, write_out  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
TOEEXPAND = "/Applications/TouchDesigner.app/Contents/MacOS/toeexpand"
BLENDER = os.environ.get("BLENDER_BIN", "/Applications/Blender.app/Contents/MacOS/Blender")


def counter_table(title, c, top=25, head=("Kind", "Count")):
    if not c:
        return ""
    return "## %s\n\n%s\n" % (title, md_table(list(head), c.most_common(top)))


# ---------------------------------------------------------------- cables.gl

# Port type ids as they appear in op JSON (cables core constants).
CABLES_PORT = {0: "value", 1: "trigger", 2: "object", 3: "array", 4: "dynamic", 5: "string"}
CABLES_REPO = "https://github.com/cables-gl/cables"


def cables_fetch(dest):
    """Sparse, blob-filtered clone of only the op *.json files (no op code is fetched)."""
    if os.path.isdir(dest):
        shutil.rmtree(dest)
    for cmd in (["git", "clone", "--depth", "1", "--filter=blob:none", "--sparse", CABLES_REPO, dest],
                ["git", "-C", dest, "sparse-checkout", "set", "--no-cone", "/src/ops/base/**/*.json"]):
        rc, _, err = run(cmd, timeout=600)
        if rc != 0:
            raise RuntimeError("cables fetch failed: %s" % err.strip()[-300:])
    return os.path.join(dest, "src", "ops", "base")


def read_cables(ops_dir):
    ops = []
    for p in glob.glob(os.path.join(ops_dir, "**", "Ops.*.json"), recursive=True):
        name = os.path.basename(p)[:-5]
        if os.path.basename(os.path.dirname(p)) != name:
            continue
        try:
            d = json.load(open(p))
        except Exception:
            continue
        lay = d.get("layout") or {}
        m = re.match(r"(.*)_v(\d+)$", name)
        ops.append({"name": name, "base": m.group(1) if m else name, "version": int(m.group(2)) if m else 1,
                    "ns": ".".join(name.split(".")[:2]), "ns3": ".".join(name.split(".")[:3]),
                    "in": [CABLES_PORT.get(x.get("type"), str(x.get("type"))) + ("/" + x["objType"] if x.get("objType") else "")
                           for x in lay.get("portsIn", [])],
                    "out": [CABLES_PORT.get(x.get("type"), str(x.get("type"))) + ("/" + x["objType"] if x.get("objType") else "")
                            for x in lay.get("portsOut", [])],
                    "summary": (d.get("summary") or "")[:160]})
    latest = {}
    for o in ops:
        if o["base"] not in latest or o["version"] > latest[o["base"]]["version"]:
            latest[o["base"]] = o
    cur = list(latest.values())
    return {"all_versions": len(ops), "current": len(cur), "ops": sorted(cur, key=lambda o: o["name"])}


def cables_md(r, infinite=None):
    ops = r["ops"]
    ns = collections.Counter(o["ns"] for o in ops)
    ns3 = collections.Counter(o["ns3"] for o in ops)
    pin = collections.Counter(t for o in ops for t in o["in"])
    pout = collections.Counter(t for o in ops for t in o["out"])
    L = ["# cables.gl op catalog", "",
         "%d current ops (%d incl. old _vN versions), from op JSON metadata only." % (r["current"], r["all_versions"]), "",
         counter_table("Namespaces", ns, 40, ("Namespace", "Ops")),
         counter_table("Sub-namespaces (top 40)", ns3, 40, ("Namespace", "Ops")),
         counter_table("Input port types", pin, 20, ("Type", "Ports")),
         counter_table("Output port types", pout, 20, ("Type", "Ports"))]
    if infinite:
        cats = collections.Counter(t["category"] for t in infinite.get("types", []))
        L.append(counter_table("Infinite node categories (for the side-by-side)", cats, 40, ("Category", "Nodes")))
    return "\n".join(x for x in L if x is not None)


# ---------------------------------------------------------------- Max for Live .amxd

AMXD_KIND = {b"aaaa": "audio effect", b"iiii": "instrument", b"mmmm": "MIDI effect", b"nnnn": "note device"}


def read_amxd(path):
    b = open(path, "rb").read()
    kind = "unknown"
    if b[:4] == b"ampf" and len(b) >= 12:
        kind = AMXD_KIND.get(b[8:12], b[8:12].decode("latin1"))
    start = b.find(b"ptch")
    i = b.find(b"{", start if start >= 0 else 0)
    if i < 0:
        raise ValueError("no patcher JSON found")
    text = b[i:].decode("utf-8", "replace")
    patcher, _ = json.JSONDecoder().raw_decode(text)
    objs, params, lines = collections.Counter(), [], [0]
    depth = [0]

    def walk(p, level):
        depth[0] = max(depth[0], level)
        lines[0] += len(p.get("lines", []))
        for bx in p.get("boxes", []):
            box = bx.get("box", {})
            cls = box.get("maxclass", "?")
            if cls == "newobj":
                cls = (box.get("text") or "?").split(" ")[0]
            objs[cls] += 1
            attrs = (box.get("saved_attribute_attributes") or {}).get("valueof")
            if attrs:
                params.append({"object": cls, "name": attrs.get("parameter_longname", ""),
                               "type": attrs.get("parameter_type"), "range": [attrs.get("parameter_mmin"), attrs.get("parameter_mmax")],
                               "modmode": attrs.get("parameter_modmode"), "unitstyle": attrs.get("parameter_unitstyle")})
            if isinstance(box.get("patcher"), dict):
                walk(box["patcher"], level + 1)
    walk(patcher.get("patcher", patcher), 0)
    live_api = sum(v for k, v in objs.items() if k in ("live.path", "live.object", "live.observer", "live.remote~", "live.modulate~"))
    return {"kind": kind, "objects": objs, "params": params, "patchlines": lines[0], "depth": depth[0], "live_api": live_api}


def amxd_md(r, name):
    mods = collections.Counter(str(p.get("modmode")) for p in r["params"])
    L = ["# Max for Live device: %s" % name, "",
         md_table(["Fact", "Value"], [("Device kind", r["kind"]), ("Objects", sum(r["objects"].values())),
                                      ("Patch cords", r["patchlines"]), ("Subpatcher depth", r["depth"]),
                                      ("Automatable live.* parameters", len(r["params"])),
                                      ("Live API objects (path/object/observer/remote~/modulate~)", r["live_api"])]), "",
         counter_table("Objects by class", r["objects"], 30, ("Object", "Count")),
         counter_table("Parameter modulation modes (parameter_modmode)", mods, 10, ("modmode", "Params"))]
    if r["params"]:
        L.append("## Parameters\n\n" + md_table(["Object", "Name", "Range", "modmode", "Unit style"],
                 [(p["object"], p["name"], p["range"], p["modmode"], p["unitstyle"]) for p in r["params"][:60]]) + "\n")
    return "\n".join(L)


# ---------------------------------------------------------------- Ableton .als

WARP_MODES = {"0": "Beats", "1": "Tones", "2": "Texture", "3": "Re-Pitch", "4": "Complex", "5": "REX", "6": "Complex Pro"}
TRACK_TAGS = ("AudioTrack", "MidiTrack", "GroupTrack", "ReturnTrack", "MainTrack", "MasterTrack", "PreHearTrack")


def read_als(path):
    with gzip.open(path, "rb") as f:
        root = ET.parse(f).getroot()
    tags = collections.Counter(e.tag for e in root.iter())
    tracks = collections.Counter({t: tags[t] for t in TRACK_TAGS if tags[t]})
    warp = collections.Counter()
    for clip in root.iter("AudioClip"):
        wm = clip.find("WarpMode")
        on = clip.find("IsWarped")
        if wm is not None:
            warp[WARP_MODES.get(wm.get("Value"), wm.get("Value")) + ("" if on is None or on.get("Value") == "true" else " (unwarped)")] += 1
    devices = collections.Counter()
    for devs in root.iter("Devices"):
        for d in devs:
            devices[d.tag] += 1
    tempo = None
    for t in root.iter("Tempo"):
        m = t.find("Manual")
        if m is not None:
            tempo = m.get("Value")
            break
    return {"creator": root.get("Creator"), "schema": root.get("MajorVersion"), "tempo": tempo, "tracks": tracks,
            "clips": collections.Counter({t: tags[t] for t in ("AudioClip", "MidiClip") if tags[t]}),
            "warp_modes": warp, "warp_markers": tags["WarpMarker"], "automation_envelopes": tags["AutomationEnvelope"],
            "modulation_tags": collections.Counter({k: v for k, v in tags.items() if "Modulat" in k}),
            "scenes": tags["Scene"], "locators": tags["Locator"], "devices": devices, "tags": tags}


def als_md(r, name):
    L = ["# Ableton Live set: %s" % name, "",
         md_table(["Fact", "Value"], [("Creator", r["creator"]), ("Tempo", r["tempo"]), ("Scenes", r["scenes"]),
                                      ("Locators", r["locators"]), ("Warp markers", r["warp_markers"]),
                                      ("Automation envelopes", r["automation_envelopes"])]), "",
         counter_table("Tracks", r["tracks"], 10, ("Track type", "Count")),
         counter_table("Clips", r["clips"], 10, ("Clip type", "Count")),
         counter_table("Warp modes in use", r["warp_modes"], 10, ("Warp mode", "Clips")),
         counter_table("Devices", r["devices"], 30, ("Device", "Count")),
         counter_table("Modulation-related elements", r["modulation_tags"], 15, ("Element", "Count"))]
    return "\n".join(L)


# ---------------------------------------------------------------- Final Cut .fcpxml

CLIP_TAGS = ("asset-clip", "clip", "ref-clip", "mc-clip", "sync-clip", "gap", "title", "audition", "video", "audio",
             "transition", "caption")


def read_fcpxml(path):
    if os.path.isdir(path):
        path = os.path.join(path, "Info.fcpxml")
    root = ET.parse(path).getroot()
    res = root.find("resources")
    resources = collections.Counter(e.tag for e in res) if res is not None else collections.Counter()
    spines = list(root.iter("spine"))
    primary, connected = collections.Counter(), collections.Counter()
    lanes = collections.Counter()
    for sp in spines:
        for e in sp:
            if e.tag in CLIP_TAGS:
                primary[e.tag] += 1
    for e in root.iter():
        if e.tag in CLIP_TAGS and e.get("lane") is not None:
            connected[e.tag] += 1
            lanes[e.get("lane")] += 1
    roles = collections.Counter()
    for e in root.iter():
        for k in ("role", "audioRole", "videoRole"):
            if e.get(k):
                roles["%s=%s" % (k, e.get(k))] += 1
    interps = collections.Counter(tp.get("interp", "linear") for tp in root.iter("timept"))
    return {"version": root.get("version"), "resources": resources, "projects": len(list(root.iter("project"))),
            "spines": len(spines), "primary": primary, "connected": connected, "lanes": lanes, "roles": roles,
            "compound": resources.get("media", 0), "ref_clips": sum(1 for _ in root.iter("ref-clip")),
            "timemaps": sum(1 for _ in root.iter("timeMap")), "timept_interp": interps,
            "keyframes": sum(1 for _ in root.iter("keyframe")), "markers": sum(1 for e in root.iter() if e.tag.endswith("marker")),
            "effects": collections.Counter(e.get("name") or e.get("ref") for e in root.iter("filter-video"))}


def fcpxml_md(r, name):
    L = ["# Final Cut XML: %s" % name, "",
         md_table(["Fact", "Value"], [("FCPXML version", r["version"]), ("Projects", r["projects"]),
                                      ("Storylines (spines, nested included)", r["spines"]),
                                      ("Compound clip media / ref-clips", "%d / %d" % (r["compound"], r["ref_clips"])),
                                      ("Retimes (timeMap)", r["timemaps"]), ("Keyframes", r["keyframes"]), ("Markers", r["markers"])]), "",
         counter_table("Resources", r["resources"], 15, ("Resource", "Count")),
         counter_table("Primary storyline items (magnetic)", r["primary"], 15, ("Item", "Count")),
         counter_table("Connected items (lane attribute)", r["connected"], 15, ("Item", "Count")),
         counter_table("Lanes in use", r["lanes"], 15, ("Lane", "Items")),
         counter_table("Roles", r["roles"], 20, ("Role", "Uses")),
         counter_table("Retime interpolation", r["timept_interp"], 10, ("interp", "Points")),
         counter_table("Video filters", r["effects"], 20, ("Filter", "Uses"))]
    return "\n".join(L)


# ---------------------------------------------------------------- TouchDesigner .toe / .tox

def read_toe(path, keep=False):
    if not os.access(TOEEXPAND, os.X_OK):
        raise RuntimeError("toeexpand not found (TouchDesigner not installed at %s)" % TOEEXPAND)
    tmp = tempfile.mkdtemp(prefix="toe-", dir=ensure_dir(RE_TMP))
    try:
        local = os.path.join(tmp, os.path.basename(path))
        shutil.copy(path, local)
        rc, out, err = run([TOEEXPAND, local], timeout=300, cwd=tmp)
        d = local + ".dir"
        if not os.path.isdir(d):
            raise RuntimeError("toeexpand produced nothing: %s" % (err or out).strip()[-200:])
        families, types, flags = collections.Counter(), collections.Counter(), collections.Counter()
        wires, depth, comps = 0, 0, 0
        build = {}
        bp = os.path.join(d, ".build")
        if os.path.exists(bp):
            for line in open(bp, errors="replace"):
                k, _, v = line.strip().partition(" ")
                build[k] = v
        for p in glob.glob(os.path.join(d, "**", "*.n"), recursive=True):
            lines = open(p, errors="replace").read().splitlines()
            if not lines or ":" not in lines[0]:
                continue
            fam, typ = lines[0].split(":", 1)
            families[fam] += 1
            types[lines[0]] += 1
            comps += fam == "COMP"
            depth = max(depth, os.path.relpath(p, d).count(os.sep))
            for i, line in enumerate(lines):
                if line.startswith("flags"):
                    for w in line.split("=", 1)[-1].split():
                        if w.isalpha():
                            flags[w] += 1
                if line == "inputs" and i + 1 < len(lines) and lines[i + 1] == "{":
                    j = i + 2
                    while j < len(lines) and lines[j] != "}":
                        wires += 1
                        j += 1
        return {"build": build, "families": families, "types": types, "flags": flags, "wires": wires,
                "depth": depth, "ops": sum(families.values()), "comps": comps}
    finally:
        if not keep:
            shutil.rmtree(tmp, ignore_errors=True)


def toe_md(r, name):
    L = ["# TouchDesigner network: %s" % name, "",
         "Expanded with Derivative's own `toeexpand` into ~/re-output/tmp, read, then deleted.", "",
         md_table(["Fact", "Value"], [("Build", r["build"].get("build")), ("Saved on", r["build"].get("osname")),
                                      ("Operators", r["ops"]), ("Components (COMP)", r["comps"]),
                                      ("Wires (operator inputs)", r["wires"]), ("Network depth", r["depth"]),
                                      ("Ops with export flag (CHOP exports = modulation)", r["flags"].get("export", 0))]), "",
         counter_table("Operator families", r["families"], 10, ("Family", "Ops")),
         counter_table("Operator types (top 30)", r["types"], 30, ("Family:type", "Ops")),
         counter_table("Operator flags", r["flags"], 15, ("Flag", "Ops"))]
    return "\n".join(L)


# ---------------------------------------------------------------- Blender (public bpy API, behaviour only)

def read_blender(path=None, demo=False):
    if not os.access(BLENDER, os.X_OK):
        raise RuntimeError("Blender not found at %s (set BLENDER_BIN)" % BLENDER)
    cmd = [BLENDER, "-b"] + ([path] if path else []) + ["--factory-startup", "--python",
                                                        os.path.join(HERE, "blender_dump.py"), "--"]
    if demo:
        cmd.append("--make-fixture")
    rc, out, err = run(cmd, timeout=300)
    for line in out.splitlines():
        if line.startswith("RE_SURVEY_JSON="):
            return json.loads(line[len("RE_SURVEY_JSON="):])
    raise RuntimeError("Blender gave no dump (rc %d): %s" % (rc, (err or out).strip()[-300:]))


ZONE_WORDS = ("Simulation", "Repeat", "Foreach", "ForEach", "Bake", "Closure")


def blender_md(r, name):
    trees = r["trees"] + r["materials"]
    ttypes = collections.Counter(t["tree_type"] for t in trees)
    ntypes = collections.Counter(n["type"] for t in trees for n in t["nodes"])
    domains = collections.Counter(n["domain"] for t in trees for n in t["nodes"] if n.get("domain"))
    dtypes = collections.Counter(n["data_type"] for t in trees for n in t["nodes"] if n.get("data_type"))
    links = collections.Counter("%s -> %s" % (l["from_type"], l["to_type"]) for t in trees for l in t["links"])
    shapes = collections.Counter(s.get("shape", "?") for t in trees for n in t["nodes"] for s in n["inputs"] + n["outputs"] if s["linked"])
    zones = collections.Counter(k for k in ntypes.elements() if any(w in k for w in ZONE_WORDS))
    mods = collections.Counter(m["type"] for m in r["modifiers"])
    L = ["# Blender node trees: %s" % name, "",
         "Read through Blender %s's public Python API (our blender_dump.py). Behaviour and structure only." % r["blender"], "",
         md_table(["Fact", "Value"], [("Node trees", len(trees)), ("Nodes", sum(ntypes.values())),
                                      ("Links", sum(links.values()))]), "",
         counter_table("Tree types", ttypes, 10, ("Tree type", "Count")),
         counter_table("Modifier stack types", mods, 15, ("Modifier", "Count")),
         counter_table("Node types (top 40)", ntypes, 40, ("Node", "Count")),
         counter_table("Zones (simulation / repeat / for-each / bake)", zones, 10, ("Zone node", "Count")),
         counter_table("Attribute domains set on nodes", domains, 10, ("Domain", "Nodes")),
         counter_table("Data types set on nodes", dtypes, 10, ("Data type", "Nodes")),
         counter_table("Linked socket shapes (DIAMOND = field, CIRCLE = single value)", shapes, 10, ("Shape", "Sockets")),
         counter_table("Link socket types", links, 20, ("From -> to", "Links"))]
    return "\n".join(L)


# ---------------------------------------------------------------- self-test

def self_test():
    t = SelfTest("readers")
    tmp = tempfile.mkdtemp(prefix="re-readers-")
    try:
        # cables: two versions of one op + one other; the reader must keep only the latest and never open .js
        for name, ports in (("Ops.Math.Sum", [0, 0]), ("Ops.Math.Sum_v2", [0, 0, 5]), ("Ops.Gl.Texture", [1, 2])):
            d = ensure_dir(os.path.join(tmp, "ops", name))
            json.dump({"layout": {"portsIn": [{"type": p, "name": "p%d" % i} for i, p in enumerate(ports)],
                                  "portsOut": [{"type": 2, "name": "tex", "objType": "texture"}]}, "summary": "s"},
                      open(os.path.join(d, name + ".json"), "w"))
            open(os.path.join(d, name + ".js"), "w").write("THIS MUST NEVER BE READ")
        c = read_cables(os.path.join(tmp, "ops"))
        t.check(c["current"] == 2 and c["all_versions"] == 3, "cables keeps latest op versions only")
        t.check(any(o["name"] == "Ops.Math.Sum_v2" and "string" in o["in"] for o in c["ops"]), "cables port types mapped")
        t.check("object/texture" in cables_md(c), "cables objType shown")

        # amxd: ampf header, audio-effect kind, ptch chunk with JSON incl. a subpatcher and a live.dial
        patch = {"patcher": {"boxes": [
            {"box": {"maxclass": "newobj", "text": "cycle~ 440"}},
            {"box": {"maxclass": "live.dial", "saved_attribute_attributes": {"valueof": {
                "parameter_longname": "Rate", "parameter_mmin": 0.0, "parameter_mmax": 10.0, "parameter_modmode": 3}}}},
            {"box": {"maxclass": "newobj", "text": "p sub", "patcher": {"boxes": [{"box": {"maxclass": "newobj", "text": "live.path"}}],
                                                                        "lines": [{}]}}}], "lines": [{}, {}]}}
        js = json.dumps(patch).encode()
        blob = b"ampf" + struct.pack("<I", 4) + b"aaaa" + b"meta" + struct.pack("<I", 4) + b"\0\0\0\0" + b"ptch" + struct.pack("<I", len(js)) + js
        ap = os.path.join(tmp, "dev.amxd")
        open(ap, "wb").write(blob)
        a = read_amxd(ap)
        t.check(a["kind"] == "audio effect" and a["objects"]["cycle~"] == 1, "amxd kind and object classes")
        t.check(len(a["params"]) == 1 and a["params"][0]["modmode"] == 3, "amxd live.* parameter with modmode")
        t.check(a["patchlines"] == 3 and a["depth"] == 1 and a["live_api"] == 1, "amxd cords, subpatcher depth, Live API")

        # als: gzipped XML
        als = ('<Ableton Creator="Ableton Live 12.1"><LiveSet><Tracks><AudioTrack><DeviceChain><DeviceChain><Devices>'
               '<Eq8/><PluginDevice/></Devices></DeviceChain></DeviceChain><AudioClip><WarpMode Value="4"/><IsWarped Value="true"/>'
               '<WarpMarkers><WarpMarker/><WarpMarker/></WarpMarkers></AudioClip></AudioTrack><MidiTrack><MidiClip/>'
               '<AutomationEnvelope/></MidiTrack></Tracks><MainTrack><Tempo><Manual Value="128"/></Tempo></MainTrack>'
               '</LiveSet></Ableton>')
        lp = os.path.join(tmp, "s.als")
        with gzip.open(lp, "wb") as f:
            f.write(als.encode())
        s = read_als(lp)
        t.check(s["tempo"] == "128" and s["tracks"]["AudioTrack"] == 1 and s["clips"]["MidiClip"] == 1, "als tempo, tracks, clips")
        t.check(s["warp_modes"]["Complex"] == 1 and s["warp_markers"] == 2 and s["devices"]["Eq8"] == 1, "als warp + devices")

        # fcpxml: magnetic spine, a connected clip on lane 1, a compound ref-clip, a retime
        fx = ('<fcpxml version="1.11"><resources><format id="r1"/><asset id="r2"/><media id="r3"><sequence><spine/></sequence></media>'
              '</resources><library><event><project name="p"><sequence><spine>'
              '<asset-clip ref="r2" audioRole="dialogue"><title lane="1"/><timeMap><timept interp="smooth2"/><timept/></timeMap></asset-clip>'
              '<gap/><ref-clip ref="r3"/></spine></sequence></project></event></library></fcpxml>')
        fp = os.path.join(tmp, "t.fcpxml")
        open(fp, "w").write(fx)
        f = read_fcpxml(fp)
        t.check(f["primary"]["asset-clip"] == 1 and f["primary"]["ref-clip"] == 1 and f["connected"]["title"] == 1, "fcpxml spine vs lanes")
        t.check(f["compound"] == 1 and f["timemaps"] == 1 and f["roles"]["audioRole=dialogue"] == 1, "fcpxml compound, retime, role")

        sample = "/Applications/TouchDesigner.app/Contents/Resources/tfs/Samples/DomeViewer/DomeViewer_LinesDemo.toe"
        if os.access(TOEEXPAND, os.X_OK) and os.path.exists(sample):
            r = read_toe(sample)
            t.check(r["ops"] > 100 and r["families"]["CHOP"] > 0 and r["wires"] > 0, "toe: TD sample has ops, CHOPs and wires (%d ops)" % r["ops"])
            t.check(not glob.glob(os.path.join(RE_TMP, "toe-*")), "toe: expanded temp dir removed")
        else:
            t.skip("toe: TouchDesigner not installed")
        if os.access(BLENDER, os.X_OK):
            b = read_blender(demo=True)
            names = [n["type"] for tr in b["trees"] for n in tr["nodes"]]
            t.check("GeometryNodeInstanceOnPoints" in names and b["modifiers"][0]["type"] == "NODES", "blender: fixture GN tree dumped")
            t.check(any(s.get("shape") for tr in b["trees"] for n in tr["nodes"] for s in n["inputs"]), "blender: socket shapes (field vs value) present")
        else:
            t.skip("blender: not installed")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return t.done()


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("reader", nargs="?", choices=["cables", "amxd", "als", "fcpxml", "toe", "blender"])
    ap.add_argument("path", nargs="?")
    ap.add_argument("--fetch", action="store_true", help="cables: sparse-clone op JSON into ~/re-output/tmp, delete after")
    ap.add_argument("--demo", action="store_true", help="blender: dump a generated Geometry Nodes fixture")
    ap.add_argument("--infinite", help="cables: Infinite --describe JSON for the side-by-side")
    ap.add_argument("--keep", action="store_true", help="keep temp expansions/clones")
    ap.add_argument("--out", help="markdown path (default stdout)")
    ap.add_argument("--json", help="also write the raw summary JSON")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if not a.reader or (not a.path and not a.fetch and not a.demo):
        ap.print_usage(sys.stderr)
        return 2
    if a.path and not os.path.exists(a.path):
        print("no such file: %s" % a.path, file=sys.stderr)
        return 2
    name = os.path.basename(a.path or a.reader)
    try:
        if a.reader == "cables":
            tmp = os.path.join(RE_TMP, "cables-ops")
            ops_dir = cables_fetch(tmp) if a.fetch else a.path
            try:
                r = read_cables(ops_dir)
            finally:
                if a.fetch and not a.keep:
                    shutil.rmtree(tmp, ignore_errors=True)
            with gzip.open(os.path.join(ensure_dir(RE_OUTPUT), "cables-ops-catalog.json.gz"), "wt") as f:
                json.dump(r, f)
            md = cables_md(r, json.load(open(a.infinite)) if a.infinite else None)
        elif a.reader == "amxd":
            r = read_amxd(a.path)
            md = amxd_md(r, name)
        elif a.reader == "als":
            r = read_als(a.path)
            md = als_md(r, name)
        elif a.reader == "fcpxml":
            r = read_fcpxml(a.path)
            md = fcpxml_md(r, name)
        elif a.reader == "toe":
            r = read_toe(a.path, keep=a.keep)
            md = toe_md(r, name)
        else:
            r = read_blender(a.path, demo=a.demo)
            md = blender_md(r, name if a.path else "demo fixture")
    except Exception as e:
        print("%s: %s" % (a.reader, e), file=sys.stderr)
        return 1
    write_out(md, a.out)
    if a.json:
        write_out(json.dumps(r, indent=1, default=lambda o: dict(o) if isinstance(o, collections.Counter) else str(o)), a.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
