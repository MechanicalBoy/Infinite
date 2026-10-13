#!/usr/bin/env python3
"""re-survey param diff: a competitor device's controls next to ours, as a spec for a plan item.

For each plan item in SPECS: the Infinite nodes it touches (controls from `Infinite --describe`:
label, range, default, options) and the nearest competitor devices (controls from the extracted
parameter trees in ~/re-output). Three sources, three depths:

  plugin   ~/re-output/plugins/plugins_all_models.json   name, min, max, default, unit (AU parameter tree)
  logic    ~/re-output/logic/logic_all_models.json       name, control type
  ableton  ~/re-output/ableton/ableton_all_models.json   name, value class (DSP params only)

The "Side by side" table folds control names to one concept (threshold, attack, mix...) and lists,
per concept, who has it. "They have, we don't" is every concept at least two of their devices
share that none of our nodes has: the list a new control has to come from.

Usage:
  python3 tools/re-survey/param_diff.py list
  python3 tools/re-survey/param_diff.py spec 2.21 [--out FILE]
  python3 tools/re-survey/param_diff.py all [--dir docs/plans/v0.6-quality/specs]
  python3 tools/re-survey/param_diff.py --self-test
Exit: 0 ok, 1 a device or node in SPECS is missing / self-test failed, 2 usage error.
"""

import argparse
import collections
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import REPO, RE_OUTPUT, SelfTest, infinite_bin, md_table, run, write_out  # noqa: E402

SPEC_DIR = os.path.join(REPO, "docs", "plans", "v0.6-quality", "specs")
PLUGINS = os.path.join(RE_OUTPUT, "plugins", "plugins_all_models.json")
LOGIC = os.path.join(RE_OUTPUT, "logic", "logic_all_models.json")
ABLETON = os.path.join(RE_OUTPUT, "ableton", "ableton_all_models.json")
MAX_ROWS = 60  # per device; a 2,621-param synth is cut with a "(n more)" line

# (item, title, our nodes, their devices). A device is "source:name" or "source:name~regex":
# the regex keeps only controls whose name matches (one band, one oscillator of a big device).
SPECS = [
    ("2.9", "Convolution reverb from designed spaces", ["Reverb"],
     ["logic:Space Designer", "logic:ChromaVerb", "ableton:Hybrid Reverb", "plugin:kHs Convolver",
      "plugin:Pro-R 2~^(?!Band|Post EQ|Decay Rate EQ)", "plugin:ValhallaRoom"]),
    ("2.11", "ADAA on Drive and Wavetable Shaper", ["Drive", "Wavetable Shaper"],
     ["plugin:Saturn 2~^(Band 1 |Input|Output|Mix|High Quality|Linear Phase)", "plugin:kHs Distortion",
      "plugin:kHs Shaper", "plugin:Faturator", "ableton:Saturator", "logic:Overdrive"]),
    ("2.14", "Envelope depth", ["Envelope"],
     ["plugin:Vital~^Envelope 1 ", "plugin:Serum 2~^Env 1 ", "logic:ES2~(?i)env", "logic:Retro Synth~(?i)env"]),
    ("2.17", "Multi-stage saturator", ["Drive"],
     ["ableton:Roar", "plugin:Saturn 2~^(Band 1 |Input|Output|Mix)", "plugin:Faturator", "logic:Phat FX"]),
    ("2.18", "Crossover split", ["Splitter"],
     ["plugin:Pro-MB~^(Band 1 |Crossover|Mix|Output|Dynamics Mode|Processing)", "plugin:Multipass~(?i)(split|band|cross)",
      "ableton:Multiband Dynamics", "logic:Multipressor"]),
    ("2.20", "Tape delay", ["Delay"],
     ["ableton:Echo", "plugin:ValhallaDelay", "plugin:kHs Delay", "logic:Tape Delay",
      "plugin:Timeless 3~^(Delay|Feedback|Cross|Mix|Wet|Dry|Diffus|Lo-Fi|Drive|Pitch|Dynamics|Tap)"]),
    ("2.21", "Compressor styles", ["Dynamics"],
     ["plugin:Pro-C 2", "ableton:Glue Compressor", "ableton:Compressor", "logic:Compressor", "plugin:kHs Compressor"]),
    ("2.22", "4-operator FM synth", ["Oscillator"],
     ["ableton:Operator", "logic:EFM1"]),
    ("2.25", "Filter models", ["Audio Filter", "Analog"],
     ["ableton:Auto Filter", "logic:AutoFilter", "plugin:kHs Ladder Filter", "plugin:kHs Filter",
      "plugin:kHs Nonlinear Filter", "plugin:Diva~(?i)(vcf|filter|cutoff|reson)"]),
    ("2.26", "Wavetable phase warps", ["Wavetable"],
     ["plugin:Vital~^Oscillator 1 ", "plugin:Serum 2~^(A |Osc A)", "ableton:Wavetable"]),
    ("2.32", "Resynthesis", [],
     ["logic:Alchemy~(?i)(additive|spectral|formant|resynth|partial|morph)"]),
    ("2.33", "String and modal modelling", ["Metallic", "Shape Resonator", "Resonator Bank"],
     ["logic:Sculpture", "ableton:Collision", "ableton:Tension", "ableton:Corpus", "plugin:kHs Resonator"]),
]

# Concept folding: a control's name with case, spaces and punctuation dropped, then these.
SYNONYMS = {
    "thresh": "threshold", "drywet": "mix", "wetdry": "mix", "wet": "mix", "amount": "mix", "blend": "mix",
    "freq": "cutoff", "frequency": "cutoff", "cutofffrequency": "cutoff", "filterfrequency": "cutoff",
    "filterfreq": "cutoff", "q": "resonance", "res": "resonance", "reso": "resonance", "emphasis": "resonance",
    "attacktime": "attack", "releasetime": "release", "decaytime": "decay", "holdtime": "hold",
    "makeup": "makeup", "makeupgain": "makeup", "outputgain": "output", "outgain": "output", "gain": "output",
    "level": "output", "volume": "output", "out": "output", "inputgain": "input", "ingain": "input",
    "pregain": "input", "fb": "feedback", "regen": "feedback", "delaytime": "time", "delay": "time",
    "predelay": "predelay", "lookaheadtime": "lookahead", "kneewidth": "knee", "softknee": "knee",
    "stereowidth": "width", "spread": "width", "stereo": "width", "drivegain": "drive", "dist": "drive",
    "distortion": "drive", "saturation": "drive", "type": "mode", "model": "mode", "style": "mode",
    "shape": "mode", "filtertype": "mode", "filtermode": "mode", "algorithm": "mode", "sidechain": "sidechain",
    "sc": "sidechain", "hp": "lowcut", "hpf": "lowcut", "highpass": "lowcut", "locut": "lowcut",
    "lp": "highcut", "lpf": "highcut", "lowpass": "highcut", "hicut": "highcut", "size": "size",
    "roomsize": "size", "decay": "decay", "rt60": "decay", "tone": "tone", "color": "tone", "colour": "tone",
    "damp": "damping", "damping": "damping", "rate": "rate", "speed": "rate", "depth": "depth",
    "on": "on", "bypass": "on", "enabled": "on", "enable": "on", "active": "on", "deviceon": "on",
    "timems": "time", "outputgaindb": "output", "sidechainexternal": "sidechain", "schpf": "sidechainlowcut",
    "sidechainhpf": "sidechainlowcut", "ratediv": "syncrate", "syncrate": "syncrate", "duck": "ducking",
}
# Every device has an on switch; ours is the node's bypass, which is not a describe row.
HOST_LEVEL = {"on"}


def concept(name):
    """'Attack Time' -> 'attack'. Index digits and band prefixes stay so 'Band 2 Gain' is not 'Gain'."""
    n = re.sub(r"[^a-z0-9]+", "", name.lower())
    return SYNONYMS.get(n, n)


def fmt_num(v):
    if v is None or v == "":
        return ""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    if f == int(f) and abs(f) < 1e9:
        return str(int(f))
    return ("%.4g" % f)


def fmt_range(lo, hi):
    return "" if lo is None or hi is None or (lo == 0 and hi == 0) else "%s .. %s" % (fmt_num(lo), fmt_num(hi))


def load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def their_devices():
    """{'plugin': {name: [rows]}, 'logic': {...}, 'ableton': {...}}; a row is
    {name, range, default, unit}. Missing datasets give empty dicts."""
    out = {"plugin": {}, "logic": {}, "ableton": {}}
    for d in (load_json(PLUGINS) or {}).values():
        if d.get("status") != "ok":
            continue
        out["plugin"][d["name"]] = [
            {"name": p.get("name", ""), "range": fmt_range(p.get("min"), p.get("max")),
             "default": fmt_num(p.get("default")), "unit": p.get("unit", "")} for p in d.get("params", [])]
    for name, d in ((load_json(LOGIC) or {}).get("devices") or {}).items():
        out["logic"][name] = [{"name": p.get("name", ""), "range": "", "default": "", "unit": p.get("control_type", "")}
                              for p in d.get("parameters", [])]
    for d in ((load_json(ABLETON) or {}).get("devices") or {}).values():
        out["ableton"][d.get("display_name", d.get("schema_class", "?"))] = [
            {"name": p.get("name", ""), "range": "", "default": "", "unit": p.get("class", "")}
            for p in d.get("parameters", []) if p.get("is_dsp")]
    return out


def find_device(devices, ref):
    """'plugin:Pro-C 2~regex' -> (label, rows, total) or None. Plugin names carry a vendor prefix,
    so a plugin matches on the part after 'Vendor: '."""
    src, _, rest = ref.partition(":")
    name, _, only = rest.partition("~")
    pool = devices.get(src, {})
    hit = None
    for k in pool:
        short = k.split(": ", 1)[-1]
        if k == name or short == name:
            hit = k
            break
    if hit is None:
        return None
    rows = pool[hit]
    if only:
        rx = re.compile(only)
        kept = []
        for r in rows:
            m = rx.search(r["name"])
            if not m:
                continue
            # A leading match is the part's prefix ("Envelope 1 Attack"): fold on the rest.
            rest_name = r["name"][m.end():].strip() if m.start() == 0 else ""
            kept.append(dict(r, fold=rest_name) if rest_name else r)
        rows = kept
    label = "%s (%s)" % (hit.split(": ", 1)[-1], {"plugin": "plugin", "logic": "Logic", "ableton": "Live"}[src])
    return label, rows, len(pool[hit])


def our_nodes(describe=None):
    """{type: [rows]} from `Infinite --describe`; a row is {name, range, default, unit}. None without a build."""
    if describe is None:
        exe = infinite_bin()
        if exe is None:
            return None
        rc, out, _ = run([exe, "--describe"], timeout=120)
        try:
            describe = json.loads(out.strip().split("\n")[-1]) if rc == 0 else None
        except ValueError:
            describe = None
        if describe is None:
            return None
    nodes = {}
    for t in describe.get("types", []):
        rows = []
        for r in t.get("rows", []):
            # ui:false is a control the node draws itself (type selector, sync toggle): still ours.
            opts = r.get("options") or []
            kind = ", ".join(opts) if opts else r.get("kind", "")
            rows.append({"name": r.get("label") or r.get("key", ""),
                         "range": fmt_range(r.get("min"), r.get("max")) if not opts else "",
                         "default": fmt_num(r.get("default")),
                         "unit": kind if r.get("ui", True) else (kind + ", own widget").lstrip(", ")})
        nodes[t["type"]] = rows
    return nodes


def side_by_side(ours, theirs):
    """ours: [(node, rows)], theirs: [(label, rows)] -> (table rows, missing concepts).

    One row per concept that we have or that at least two of their devices share.
    """
    our_by = collections.OrderedDict()
    for node, rows in ours:
        for r in rows:
            our_by.setdefault(concept(r.get("fold") or r["name"]), []).append((node, r))
    their_by = collections.OrderedDict()
    for label, rows in theirs:
        seen = set()
        for r in rows:
            c = concept(r.get("fold") or r["name"])
            if c in seen:
                continue
            seen.add(c)
            their_by.setdefault(c, []).append((label, r))
    table, missing = [], []
    order = list(our_by) + [c for c in their_by if c not in our_by]
    for c in order:
        t = their_by.get(c, [])
        if c not in our_by and (len(t) < 2 or c in HOST_LEVEL):
            continue
        mine = "; ".join("%s: %s%s" % (n, r["name"], " (%s)" % r["range"] if r["range"] else "") for n, r in our_by.get(c, []))
        them = "; ".join("%s%s" % (label, " (%s)" % r["range"] if r["range"] else "") for label, r in t)
        table.append((c, mine or "none", them or "none"))
        if c not in our_by:
            missing.append((c, len(t)))
    missing.sort(key=lambda m: -m[1])
    return table, missing


def spec_md(item, title, ours, theirs, unresolved):
    L = ["# Spec %s: %s" % (item, title), "",
         "Generated by `python3 tools/re-survey/param_diff.py spec %s`. Do not edit by hand." % item,
         "Their columns are what a black-box read of the device gives: the plugin parameter tree has ranges and",
         "defaults; Logic and Live give names and control kinds only.", ""]
    if unresolved:
        L += ["**Not found in the datasets:** %s" % ", ".join(unresolved), ""]
    L += ["## Ours", ""]
    if not ours:
        L += ["No node yet: this item adds one.", ""]
    for node, rows in ours:
        L += ["### %s (%d controls)" % (node, len(rows)), ""]
        L += [md_table(["Control", "Range", "Default", "Kind / options"],
                       [(r["name"], r["range"], r["default"], r["unit"]) for r in rows]) if rows else "No controls.", ""]
    L += ["## Theirs", ""]
    for label, rows, total in theirs:
        shown = rows[:MAX_ROWS]
        note = "" if len(rows) == total else ", %d of %d shown by filter" % (len(rows), total)
        L += ["### %s (%d controls%s)" % (label, len(rows), note), ""]
        L += [md_table(["Control", "Range", "Default", "Unit / kind"],
                       [(r["name"], r["range"], r["default"], r["unit"]) for r in shown]) if shown else "No controls matched.", ""]
        if len(rows) > MAX_ROWS:
            L += ["(%d more)" % (len(rows) - MAX_ROWS), ""]
    table, missing = side_by_side(ours, [(label, rows) for label, rows, _ in theirs])
    L += ["## Side by side", "",
          "One row per control we have, or that at least two of their devices share.", "",
          md_table(["Concept", "Ours", "Theirs"], table) if table else "Nothing in common.", ""]
    L += ["## They have, we don't", ""]
    L += [md_table(["Concept", "Devices"], missing) if missing else "Nothing shared by two or more of their devices.", ""]
    return "\n".join(L)


def build(item, devices, nodes):
    """(markdown, errors) for one SPECS item."""
    spec = next((s for s in SPECS if s[0] == item), None)
    if spec is None:
        return None, ["no spec for item %s" % item]
    _, title, node_names, refs = spec
    errors, ours, theirs, unresolved = [], [], [], []
    for n in node_names:
        if nodes is None:
            errors.append("no Infinite build to describe %s" % n)
        elif n not in nodes:
            errors.append("%s: Infinite has no node type '%s'" % (item, n))
        else:
            ours.append((n, nodes[n]))
    for ref in refs:
        found = find_device(devices, ref)
        if found is None:
            unresolved.append(ref)
            errors.append("%s: device '%s' is not in the datasets" % (item, ref))
        else:
            theirs.append(found)
    return spec_md(item, title, ours, theirs, unresolved), errors


def cmd_all(out_dir):
    devices, nodes = their_devices(), our_nodes()
    bad = 0
    index = []
    for item, title, node_names, refs in SPECS:
        md, errors = build(item, devices, nodes)
        for e in errors:
            print("ERROR %s" % e)
        bad += bool(errors)
        path = os.path.join(out_dir, "%s.md" % item)
        write_out(md, path)
        index.append((item, title, ", ".join(node_names) or "new node", len(refs), "[%s.md](%s.md)" % (item, item)))
    readme = ["# v0.6 specs: their controls next to ours", "",
              "Generated by `python3 tools/re-survey/param_diff.py all`. Do not edit by hand.", "",
              "One file per plan item that changes or adds an audio node with a comparable competitor device.",
              "An item's new or changed control should be on its \"They have, we don't\" list, or say why not.", "",
              md_table(["Item", "What", "Our nodes", "Their devices", "Spec"], index), "",
              "Items not listed (the rest of Block 2, all of Block 3) have no comparable device in the extracted",
              "parameter trees: the visual apps' datasets list nodes, not controls.", ""]
    write_out("\n".join(readme), os.path.join(out_dir, "README.md"))
    print("%d specs -> %s" % (len(SPECS), os.path.relpath(out_dir, REPO)))
    return 1 if bad else 0


def self_test():
    t = SelfTest("param_diff")
    t.check(concept("Attack Time") == "attack" and concept("Dry/Wet") == "mix" and concept("Thresh") == "threshold",
            "names fold to concepts")
    t.check(concept("Band 2 Gain") != concept("Gain"), "a band's control is not the plain control")
    t.check(fmt_range(-60, 0) == "-60 .. 0" and fmt_range(0, 0) == "" and fmt_num(0.600000024) == "0.6",
            "ranges and numbers format")
    devices = {"plugin": {"Vendor: Comp A": [{"name": "Threshold", "range": "-60 .. 0", "default": "-18", "unit": ""},
                                             {"name": "Knee", "range": "0 .. 72", "default": "18", "unit": ""},
                                             {"name": "Band 1 Gain", "range": "", "default": "", "unit": ""}]},
               "logic": {"Comp B": [{"name": "Thresh", "range": "", "default": "", "unit": "knob"},
                                    {"name": "Knee", "range": "", "default": "", "unit": "knob"},
                                    {"name": "Only Here", "range": "", "default": "", "unit": "knob"}]},
               "ableton": {}}
    a = find_device(devices, "plugin:Comp A")
    t.check(a is not None and a[0] == "Comp A (plugin)" and a[2] == 3, "a plugin resolves without its vendor prefix")
    f = find_device(devices, "plugin:Comp A~^Band 1 ")
    t.check(f is not None and len(f[1]) == 1 and f[2] == 3 and f[1][0].get("fold") == "Gain",
            "a filter keeps matching controls and the full count, and folds on the name after the prefix")
    t.check(find_device(devices, "logic:Nope") is None, "an unknown device is not found")
    describe = {"types": [{"type": "Dynamics", "rows": [
        {"key": "threshold", "label": "threshold", "min": -60, "max": 0, "default": "0", "kind": "float", "options": [], "ui": True},
        {"key": "mode", "label": "mode", "min": 0, "max": 2, "default": "0", "kind": "enum", "options": ["a", "b"], "ui": True},
        {"key": "hidden", "label": "hidden", "min": 0, "max": 1, "default": "0", "kind": "float", "options": [], "ui": False}]}]}
    nodes = our_nodes(describe)
    t.check(len(nodes["Dynamics"]) == 3 and nodes["Dynamics"][0]["range"] == "-60 .. 0" and nodes["Dynamics"][1]["unit"] == "a, b"
            and nodes["Dynamics"][2]["unit"] == "float, own widget", "our controls come from describe rows, self-drawn ones included")
    table, missing = side_by_side([("Dynamics", nodes["Dynamics"])],
                                  [(x[0], x[1]) for x in (find_device(devices, "plugin:Comp A"), find_device(devices, "logic:Comp B"))])
    concepts = [r[0] for r in table]
    t.check("threshold" in concepts and "Comp A (plugin) (-60 .. 0)" in table[concepts.index("threshold")][2]
            and "Comp B (Logic)" in table[concepts.index("threshold")][2], "a shared concept lists both devices")
    t.check(missing == [("knee", 2)], "a control two devices share and we lack is missing; a one-device control is not")
    on = [("A", [{"name": "On", "range": "", "default": "", "unit": ""}]), ("B", [{"name": "Bypass", "range": "", "default": "", "unit": ""}])]
    t.check(side_by_side([], on) == ([], []), "a device on switch is not a missing control")
    global SPECS
    saved = SPECS
    SPECS = [("9.9", "Test", ["Dynamics", "Ghost"], ["plugin:Comp A", "logic:Nope"])]
    md, errors = build("9.9", devices, nodes)
    SPECS = saved
    t.check(len(errors) == 2 and "Ghost" in errors[0] and "Nope" in errors[1], "a missing node and a missing device are errors")
    t.check("## They have, we don't" in md and "**Not found in the datasets:** logic:Nope" in md, "the spec has every section")
    t.check(len({s[0] for s in SPECS}) == len(SPECS), "one spec per item")

    real = their_devices()
    if not any(real.values()):
        t.skip("no datasets in %s" % RE_OUTPUT)
    else:
        lost = [ref for s in SPECS for ref in s[3] if find_device(real, ref) is None]
        t.check(not lost, "every device in SPECS is in the datasets%s" % (": missing %s" % lost if lost else ""))
        empty = [ref for s in SPECS for ref in s[3] if find_device(real, ref) and not find_device(real, ref)[1]]
        t.check(not empty, "every device filter keeps a control%s" % (": empty %s" % empty if empty else ""))
    live = our_nodes()
    if live is None:
        t.skip("no Infinite build")
    else:
        gone = [n for s in SPECS for n in s[2] if n not in live]
        t.check(not gone, "every node in SPECS is a registered type%s" % (": missing %s" % gone if gone else ""))
    return t.done()


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--self-test", action="store_true")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("list")
    sp = sub.add_parser("spec")
    sp.add_argument("item")
    sp.add_argument("--out")
    al = sub.add_parser("all")
    al.add_argument("--dir", default=SPEC_DIR)
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    if args.cmd == "list":
        print(md_table(["Item", "What", "Our nodes", "Their devices"],
                       [(i, t, ", ".join(n) or "new node", ", ".join(r.split("~")[0] for r in d)) for i, t, n, d in SPECS]))
        return 0
    if args.cmd == "spec":
        md, errors = build(args.item, their_devices(), our_nodes())
        for e in errors:
            print("ERROR %s" % e, file=sys.stderr)
        if md is None:
            return 2
        if args.out:
            write_out(md, args.out)
        else:
            print(md)
        return 1 if errors else 0
    if args.cmd == "all":
        return cmd_all(args.dir)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
