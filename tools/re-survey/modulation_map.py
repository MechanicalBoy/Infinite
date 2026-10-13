#!/usr/bin/env python3
"""re-survey modulation_map: extract and compare Bitwig's modulation system against Infinite.

Sources (public metadata and headers only, no decompilation):
  Bitwig:   Modulators-resources.properties and Modulator-descriptions-resources.properties
            shipped in /Applications/Bitwig Studio.app/Contents/Resources/localization
  Infinite: src/nodes/ModulatorNodes.h, src/nodes/MacroNodes.h, src/nodes/PredictiveModulatorNode.h

Usage:
  python3 tools/re-survey/modulation_map.py run [--out ~/re-output/modulation/bitwig_modulation_map.md]
  python3 tools/re-survey/modulation_map.py --self-test
Exit: 0 ok, 1 parsing failed / self-test failed, 2 usage error.
"""

import argparse
import collections
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import RE_OUTPUT, SelfTest, ensure_dir, md_table, write_out  # noqa: E402

BITWIG_APP = "/Applications/Bitwig Studio.app"
BITWIG_LOCALIZATION = os.path.join(BITWIG_APP, "Contents", "Resources", "localization")
DESCRIPTIONS_FILE = os.path.join(BITWIG_LOCALIZATION, "Modulator-descriptions-resources.properties")
RESOURCES_FILE = os.path.join(BITWIG_LOCALIZATION, "Modulators-resources.properties")

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
# Every node header: modulators also live in MidiNodes.h, NoteNodes.h, OscNodes.h, PathNode.h,
# PredictionNodes.h and GeometryTableNode.h, not only ModulatorNodes.h.
_NODES_DIR = os.path.join(REPO_ROOT, "src", "nodes")
INFINITE_MOD_HEADERS = sorted(os.path.join(_NODES_DIR, f) for f in os.listdir(_NODES_DIR)
                              if f.endswith(".h")) if os.path.isdir(_NODES_DIR) else []

# Mapping of Bitwig modulator IDs to Infinite equivalent nodes
BITWIG_TO_INFINITE_MAP = {
    # audio-driven
    "audio_rate": ("AudioToCVNode", "gap", "Modulators are sampled once per UI frame and ramped per sample by ParamMailbox (no zipper), so no audio-rate FM of a param"),
    "audio_sidechain": ("AudioToCVNode", "parity", "Filtered and rectified audio-to-control signal"),
    "envelope_follower": ("AudioToCVNode + SmoothNode", "parity", "Attack/decay smoothing over audio level"),
    "hw_cv_in": ("AudioToCVNode", "parity", "Audio input mapped to 0..1 control value"),
    # envelope
    "adsr": ("EnvelopeNode", "parity", "ADSR contour; gate comes from its mod input crossing a threshold, not from notes"),
    "ahd_on_release": ("EnvelopeNode", "gap", "Infinite has note-on ADSR; lacks note-off attack-hold-decay"),
    "ahdsr": ("EnvelopeNode", "gap", "Envelope has A/D/S/R times only: no hold stage, no per-stage curvature"),
    "note_sidechain": ("NoteToCVNode -> EnvelopeNode", "gap", "Envelope gates on a mod signal; a note gate needs Note to CV in front, and there is no per-note retrigger"),
    "ramp": ("LFONode (Saw)", "parity", "Linear ramp over time"),
    "segments": ("ModCurveNode", "gap", "Mod Curve is a multi-point transfer curve (input to output), not a time-based MSEG that runs, loops and retriggers"),
    # interface
    "button": ("MacroToggleNode", "parity", "Toggle switch 0/1"),
    "buttons": ("MacroToggleNode", "parity", "Multiple toggle switches"),
    "globals": ("ConstantNode", "gap", "Bitwig exposes transport/groove/crossfade globals as modulators"),
    "macro": ("MacroKnobNode", "parity", "Continuous unipolar/bipolar knob"),
    "macro-4": ("MacroKnobNode x4", "parity", "Four macro knobs"),
    "select-4": ("MacroRadioSelectorNode", "parity", "Selector crossfader across 4 states"),
    "vector-4": ("MacroXYNode", "parity", "2D XY pad controlling multiple outputs"),
    "vector-8": ("MacroXYNode", "parity", "2D XY pad controlling 8 targets"),
    "xy": ("MacroXYNode", "parity", "2D XY morphing control"),
    # lfo
    "beat_lfo": ("LFONode (Synced)", "parity", "Tempo-synced LFO with musical division snapping"),
    "classic_lfo": ("LFONode", "parity", "Standard waveforms (Sine, Tri, Saw, Square, S&H)"),
    "curves": ("ModCurveNode", "gap", "Mod Curve shapes an input; no drawable curve that runs on its own clock as an LFO"),
    "lfo": ("LFONode", "parity", "Continuous morphable LFO"),
    "random": ("RandomNode", "parity", "Random noise generator with smoothing and S&H"),
    "vibrato": ("LFONode", "parity", "LFO tied to modulation wheel / pitch"),
    "wavetable_lfo": ("LFONode", "gap", "Bitwig supports arbitrary wavetable cycling as LFO"),
    # modifier
    "math": ("MathNode", "parity", "Add, subtract, multiply, min, max of two modulators"),
    "mix": ("RangeToRangeNode", "parity", "Crossfade and scale between two modulation values"),
    "polynom": ("MathNode", "gap", "Polynomial waveshaping equation f(x)"),
    "quantize": ("CompareNode / RangeToRangeNode", "gap", "Stepped quantization of continuous modulator signal"),
    "sample_and_hold": ("RandomNode (S&H)", "parity", "Clocked sample & hold of modulation input"),
    # note-driven
    "channel-16": ("None", "gap", "16 MIDI channel separate modulation streams"),
    "expressions": ("None", "gap", "No MPE note expressions (pressure, timbre, slide)"),
    "keytrack+": ("CVToPitchNode", "gap", "Custom breakpoint curve lookup for keyboard pitch"),
    "midi": ("MidiCCNode", "gap", "MIDI CC is a modulator; pitch bend lives in the Notes family and channel pressure has no node"),
    "note_counter": ("PatternNode", "parity", "Step counter incrementing on incoming notes"),
    "pitch-12": ("CVToPitchNode", "gap", "12 separate pitch class modulation slots"),
    "relative_keytrack": ("CVToPitchNode", "parity", "Pitch relative to root note with spread"),
    # sequence
    "4-stage": ("EnvelopeNode / PatternNode", "gap", "Looping 4-stage envelope generator"),
    "parseq-8": ("PatternNode", "gap", "Parameter sequencer where each step is an independent modulator"),
    "steps": ("PatternNode / MacroStepGateNode", "parity", "Step sequencer with sync and smoothing"),
    # voice stacking
    "stack_spread": ("None", "gap", "Unison voice parameter spread (golden ratio, primes, random)"),
    "voice_control": ("None", "gap", "Manual per-voice parameter tuning for unison stacks"),
}


def parse_bitwig_modulators(desc_path=DESCRIPTIONS_FILE, res_path=RESOURCES_FILE):
    """Parse Bitwig's localization properties into structured modulator definitions."""
    if not os.path.exists(desc_path):
        raise FileNotFoundError(f"Bitwig descriptions not found at {desc_path}")

    modulators = {}
    current_category = "general"

    # 1. Parse descriptions and keywords
    with open(desc_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#Mon"):
                continue
            if line.startswith("#"):
                current_category = line.lstrip("#").rstrip(".").strip()
                continue
            m = re.match(r"modulator\.([a-zA-Z0-9_\-]+)\.(desc|keywords)=(.*)", line)
            if m:
                mod_id, key, val = m.groups()
                modulators.setdefault(mod_id, {
                    "id": mod_id,
                    "category": current_category,
                    "desc": "",
                    "keywords": [],
                    "params": {},
                })
                if key == "desc":
                    modulators[mod_id]["desc"] = val
                elif key == "keywords":
                    modulators[mod_id]["keywords"] = [k.strip() for k in val.split() if k.strip()]

    # 2. Parse parameter titles and descriptions if resources file exists
    if os.path.exists(res_path):
        with open(res_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                m = re.match(r"([a-zA-Z0-9_\-]+)\.([a-zA-Z0-9_\-]+)\.(title|desc)=(.*)", line)
                if m:
                    target_id, param_name, prop, val = m.groups()
                    clean_id = target_id.replace("-modulator", "").replace("_modulator", "")
                    if clean_id in modulators:
                        p_dict = modulators[clean_id]["params"].setdefault(param_name, {"name": param_name})
                        p_dict[prop] = val

    return modulators


def parse_infinite_modulators(header_paths=None):
    """Scan Infinite's C++ headers for IModulator implementations."""
    if header_paths is None:
        header_paths = INFINITE_MOD_HEADERS

    infinite_nodes = []
    class_re = re.compile(r"class\s+([a-zA-Z0-9_]+Node)\b[^{;]*\bpublic\s+IModulator\b")

    for path in header_paths:
        if not os.path.exists(path):
            continue
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                m = class_re.search(line)
                if m:
                    node_name = m.group(1)
                    header_basename = os.path.basename(path)
                    infinite_nodes.append({
                        "name": node_name,
                        "header": header_basename,
                    })

    return infinite_nodes


def missing_classes(equiv, src=os.path.join(REPO_ROOT, "src")):
    """Class names in an Infinite-equivalent cell (e.g. "AudioToCVNode + SmoothNode") with no `class X` in src/."""
    names = re.findall(r"\b([A-Z][A-Za-z0-9]*Node)\b", equiv)
    if not names:
        return []
    found = set()
    for root, _, files in os.walk(src):
        for fn in files:
            if fn.endswith(".h"):
                with open(os.path.join(root, fn), encoding="utf-8", errors="replace") as f:
                    text = f.read()
                for n in names:
                    if re.search(r"class\s+%s\b" % n, text):
                        found.add(n)
    return [n for n in names if n not in found]


def build_comparison_report(bitwig_mods, infinite_nodes):
    """Generate Markdown and JSON comparison between Bitwig and Infinite modulation systems."""
    categories = collections.defaultdict(list)
    for mod_id, mod in sorted(bitwig_mods.items()):
        categories[mod["category"]].append(mod)

    rows = []
    status_counts = {"parity": 0, "gap": 0, "infinite_lead": 0}

    for cat, mods in sorted(categories.items()):
        for mod in mods:
            mod_id = mod["id"]
            inf_equiv, status, notes = BITWIG_TO_INFINITE_MAP.get(mod_id, ("None", "gap", "Not mapped"))
            missing = missing_classes(inf_equiv)
            if missing:
                notes += " [UNVERIFIED: no class %s in src/]" % ", ".join(missing)
            status_counts[status] = status_counts.get(status, 0) + 1
            rows.append({
                "category": cat,
                "bitwig_id": mod_id,
                "bitwig_desc": mod["desc"],
                "infinite_equiv": inf_equiv,
                "status": status,
                "notes": notes,
            })

    # Add Infinite Unique Leads (e.g. Predictive Modulators)
    infinite_leads = [
        {
            "category": "predictive (learns)",
            "bitwig_id": "none",
            "bitwig_desc": "Bitwig has no gesture-learning / inertia predictors",
            "infinite_equiv": "PredictiveModulatorNode",
            "status": "infinite_lead",
            "notes": "P3 core pillar: learns user fader movements, velocity, and spring inertia in fader-space",
        },
        {
            "category": "modifier",
            "bitwig_id": "none",
            "bitwig_desc": "Bitwig has CV recorder only via hardware I/O",
            "infinite_equiv": "CVRecorderNode",
            "status": "infinite_lead",
            "notes": "Records and loops live gesture automation buffer in-patch",
        },
    ]

    for lead in infinite_leads:
        status_counts["infinite_lead"] += 1
        rows.append(lead)

    return rows, status_counts


def render_markdown(rows, status_counts, bitwig_mods_count, inf_mods_count):
    """Render structured markdown output for the comparison dossier."""
    md = []
    md.append("# Modulation System Comparison: Bitwig Studio vs Infinite")
    md.append("")
    md.append("Generated by `tools/re-survey/modulation_map.py` from Bitwig shipped metadata and Infinite headers. The Infinite column and notes are hand-written judgements; class names are checked against src/ and marked UNVERIFIED when missing.")
    md.append("")
    md.append("## Executive Summary")
    md.append("")
    md.append(f"- **Bitwig Modulators cataloged**: {bitwig_mods_count} across 8 categories.")
    md.append(f"- **Infinite Modulator nodes cataloged**: {inf_mods_count} nodes (standard, macros, predictive).")
    md.append(f"- **Parity**: {status_counts.get('parity', 0)} features matched.")
    md.append(f"- **Infinite Lead**: {status_counts.get('infinite_lead', 0)} features unique to Infinite (Predictive family, in-patch gesture loopers).")
    md.append(f"- **Bitwig Lead (Gaps for Quest R711)**: {status_counts.get('gap', 0)} areas to address.")
    md.append("")
    md.append("## Primary Architectural Gaps for Quest R711")
    md.append("")
    md.append("1. **Multi-Segment Envelope Generator (MSEG / Curves)**:")
    md.append("   - Bitwig's `segments` and `curves` are time-based: drawn breakpoints that run, loop and retrigger.")
    md.append("   - Infinite's Mod Curve is a transfer curve (input to output). *Action*: a time-based MSEG (new node or a Mod Curve mode with its own clock).")
    md.append("2. **Audio-Rate Modulation (per-sample values, not ramped frame values)**:")
    md.append("   - Done already: ParamMailbox ramps each frame value per sample, so modulation does not zipper (docs/plans/modulation/README.md Block 2).")
    md.append("   - Still a gap: a modulator is sampled once per UI frame, so it cannot FM a parameter at audio rate.")
    md.append("   - *Action for Infinite*: per-sample modulation buffers, designed together with per-voice modulation.")
    md.append("3. **Polyphonic / Per-Voice Modulation**:")
    md.append("   - Bitwig allows any modulator to run polyphonically (`Poly` toggle) per voice.")
    md.append("   - `IModulator::Value01()` returns one value for every voice. *Action*: per-voice modulator state for synth consumers.")
    md.append("4. **Unison Voice Stacking (`stack_spread`)**:")
    md.append("   - Spreads parameter offsets across synth unison voices using golden ratios or primes.")
    md.append("")
    md.append("## Full Capability Comparison Matrix")
    md.append("")

    headers = ["Category", "Bitwig Modulator", "Infinite Equivalent", "Status", "Notes"]
    table_rows = []
    for r in rows:
        b_name = f"**{r['bitwig_id']}**" if r['bitwig_id'] != "none" else "—"
        table_rows.append([
            r["category"],
            b_name,
            f"`{r['infinite_equiv']}`",
            r["status"],
            r["notes"],
        ])

    md.append(md_table(headers, table_rows))
    md.append("")
    return "\n".join(md)


def run_selftest():
    """Verify parser contracts and mapping integrity."""
    t = SelfTest("modulation_map")

    # Test parser on Bitwig files
    if os.path.exists(DESCRIPTIONS_FILE):
        mods = parse_bitwig_modulators()
        t.check(len(mods) >= 40, "Bitwig modulators count >= 40")
        t.check("adsr" in mods, "adsr in modulators")
        t.check("curves" in mods, "curves in modulators")
        t.check("audio_rate" in mods, "audio_rate in modulators")
        t.check("segments" in mods, "segments in modulators")

    # Test parser on Infinite headers
    nodes = parse_infinite_modulators()
    t.check(len(nodes) >= 15, "Infinite modulators count >= 15")
    node_names = {n["name"] for n in nodes}
    t.check("LFONode" in node_names, "LFONode found")
    t.check("EnvelopeNode" in node_names, "EnvelopeNode found")
    t.check("PredictiveModulatorNode" in node_names, "PredictiveModulatorNode found")

    t.check(missing_classes("LFONode + SmoothNode") == [], "real classes verify")
    t.check(missing_classes("NoSuchThingNode") == ["NoSuchThingNode"], "fake class flagged")

    # Test comparison report generation
    if os.path.exists(DESCRIPTIONS_FILE):
        rows, counts = build_comparison_report(mods, nodes)
        t.check(len(rows) > len(mods), "Comparison rows generated")
        t.check(counts["parity"] > 0, "Parity count > 0")
        t.check(counts["infinite_lead"] > 0, "Infinite lead count > 0")
        t.check(counts["gap"] > 0, "Gap count > 0")

    return t.done()


def main():
    parser = argparse.ArgumentParser(description="Extract and compare Bitwig's modulation system against Infinite.")
    parser.add_argument("command", nargs="?", default="run", choices=["run"], help="Command to run (default: run)")
    parser.add_argument("--out", help="Markdown output path (default: ~/re-output/modulation/bitwig_modulation_map.md)")
    parser.add_argument("--json", action="store_true", help="Also save JSON format")
    parser.add_argument("--self-test", action="store_true", help="Run internal self-tests and exit")
    args = parser.parse_args()

    if args.self_test:
        sys.exit(run_selftest())

    out_md = args.out or os.path.join(RE_OUTPUT, "modulation", "bitwig_modulation_map.md")
    ensure_dir(os.path.dirname(out_md))

    bitwig_mods = parse_bitwig_modulators()
    inf_nodes = parse_infinite_modulators()
    rows, counts = build_comparison_report(bitwig_mods, inf_nodes)

    md_text = render_markdown(rows, counts, len(bitwig_mods), len(inf_nodes))
    write_out(md_text, out_md)
    print(f"wrote {out_md}")

    if args.json:
        out_json = out_md.replace(".md", ".json")
        with open(out_json, "w", encoding="utf-8") as f:
            json.dump({"summary": counts, "rows": rows}, f, indent=2)
        print(f"wrote {out_json}")


if __name__ == "__main__":
    main()
