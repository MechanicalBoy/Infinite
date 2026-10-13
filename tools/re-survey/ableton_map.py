#!/usr/bin/env python3
"""re-survey ableton_map: extract and compare Ableton Live 12 Suite's device architecture against Infinite.

Sources (public bundle metadata only, no decompilation):
  Ableton Live 12: /Applications/Ableton Live 12 Suite.app/Contents/App-Resources/Builtin/Devices
  Infinite:        src/nodes/ headers, skills/infinite-patch-authoring/SKILL.md, src/audio/dsp/

Usage:
  python3 tools/re-survey/ableton_map.py run [--out ~/re-output/ableton/ableton_live_map.md]
  python3 tools/re-survey/ableton_map.py --self-test
Exit: 0 ok, 1 parsing failed / self-test failed, 2 usage error.
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import RE_OUTPUT, SelfTest, census_role, census_types, ensure_dir, md_table, parity_cell, write_out  # noqa: E402

LIVE_APP = "/Applications/Ableton Live 12 Suite.app"
DEVICES_DIR = os.path.join(LIVE_APP, "Contents", "App-Resources", "Builtin", "Devices")

CATEGORIES = ["Instruments", "Audio Effects", "MIDI Effects", "MIDI Tools"]

# Curated architecture comparison. The Infinite side is checked: counts come from the
# node census (build/census/census.json) and every parity node name is looked up there.
# Leads and gaps are hand-written judgements, not measurements.
CATEGORY_ANALYSIS = {
    "Instruments": {
        "title": "Instruments (Synths, Samplers, Physical Modeling)",
        "live_role": "Stock instruments covering subtractive, FM, wavetable, physical modeling, and sampling",
        "infinite_cats": ["Synths"],
        "parity": [
            ("Analog", ["Analog"]),
            ("Wavetable", ["Wavetable"]),
            ("Simpler / Sampler", ["Sampler", "Slicer"]),
            ("Collision (modal resonance)", ["Metallic"]),
            ("Granulator III (M4L)", ["Granular", "Grain Molder"]),
        ],
        "infinite_leads": [
            "Field Synth: the user writes the synth's DSP in the Field language",
            "Same canvas as visuals: audio drives image and 3D nodes (Audio Analyze, Audio Texture, Audio Displacement) with no bridge app",
        ],
        "gaps_to_outpace": [
            "Operator: dedicated multi-operator FM with per-operator envelopes (Equation Synth is a formula synth, not an FM operator matrix)",
            "Meld (Live 12): bi-timbral macro oscillator, scale-aware",
            "Drift (Live 12): small analog-drift synth (Infinite's 'Drift' node is a Prediction node, not a synth)",
            "Drum Sampler (Live 12): one-shot drum player with punch/sub/stretch",
        ],
    },
    "Audio Effects": {
        "title": "Audio Effects (Dynamics, Color, Time, Spectral)",
        "live_role": "Native DSP effects covering dynamics, distortion, spatial, and spectral",
        "infinite_cats": ["AudioEffects"],
        "parity": [
            ("EQ Eight", ["EQ", "Audio Filter"]),
            ("Delay / Echo", ["Delay"]),
            ("Reverb (algorithmic)", ["Reverb"]),
            ("Compressor / Gate / Limiter", ["Dynamics", "Gate", "Limiter"]),
            ("Chorus-Ensemble / Phaser-Flanger", ["Chorus", "Flanger", "Phaser"]),
            ("Saturator", ["Drive"]),
            ("Redux", ["Bitcrush"]),
            ("Frequency Shifter / Ring Mod", ["Frequency Shifter", "Ring Mod"]),
            ("Resonators", ["Resonator Bank"]),
        ],
        "infinite_leads": [
            "VST3/AU hosting on the same canvas as the visual nodes",
            "Global modulation: any modulator (LFO, Image Analyze, Predictive Modulator) can drive any audio effect param",
        ],
        "gaps_to_outpace": [
            "Hybrid Reverb / Convolution: no IR reverb in Infinite ('convolve' is an image kernel filter)",
            "Roar (Live 12): multi-stage saturation with serial/parallel/mid-side routing and feedback",
            "Drum Buss: transient + sub boom + saturation in one device",
            "Spectral Time / Spectral Resonator: FFT freeze, spectral delay",
            "Auto Shift (Live 12): pitch correction with formant preservation",
        ],
    },
    "MIDI Effects": {
        "title": "MIDI Effects & Generative Tools",
        "live_role": "MIDI transformers plus Live 12's generative MIDI Tools",
        "infinite_cats": ["Notes"],
        "parity": [
            ("Arpeggiator", ["Arpeggiator"]),
            ("Chord", ["Chorder", "Note Stack"]),
            ("Scale", ["Quantizer"]),
            ("Random", ["Random Note Generator"]),
            ("Velocity", ["Velocity Curve"]),
            ("Note Echo", ["Note Echo"]),
        ],
        "infinite_leads": [
            "Predictive Notes / Predictive Rhythm: learned note generators (Prediction family)",
        ],
        "gaps_to_outpace": [
            "Live 12 MIDI Generators: Euclidean rhythm, Stacks chord generator as clip tools",
            "MPE: no per-note pressure/timbre/slide anywhere in Infinite",
        ],
    },
}


def parse_ableton_devices(devices_dir=DEVICES_DIR):
    """Scan Ableton Live's installed builtin devices directory."""
    if not os.path.exists(devices_dir):
        raise FileNotFoundError(f"Ableton devices directory not found at {devices_dir}")

    catalog = {}
    for cat in CATEGORIES:
        cat_dir = os.path.join(devices_dir, cat)
        if not os.path.isdir(cat_dir):
            continue
        items = []
        for name in sorted(os.listdir(cat_dir)):
            if name.startswith("."):
                continue
            item_path = os.path.join(cat_dir, name)
            if os.path.isdir(item_path):
                items.append(name)
            elif name.endswith(".adv") or name.endswith(".adg"):
                clean = os.path.splitext(name)[0]
                items.append(clean)
        catalog[cat] = sorted(list(set(items)))

    return catalog


def render_markdown(catalog):
    """Render comprehensive comparison report between Ableton Live 12 and Infinite."""
    md = []
    md.append("# Audio & Instrument Architecture: Ableton Live 12 Suite vs Infinite")
    md.append("")
    md.append("Generated by `tools/re-survey/ableton_map.py`. Live device lists come from the installed bundle; Infinite counts and node names come from the census; leads, gaps and the contrast table are hand-written judgements.")
    md.append("")
    md.append("## Executive Summary")
    md.append("")

    total_devices = sum(len(devs) for devs in catalog.values())
    md.append(f"- **Ableton Live 12 Devices Cataloged**: {total_devices} native devices:")
    for cat, devs in catalog.items():
        md.append(f"  - **{cat}**: {len(devs)} devices")
    md.append("- **Infinite (from build/census/census.json)**: %s, plus the Plugin node (VST3/AU host)." % census_role(["Synths", "AudioEffects", "Notes"]))
    md.append("")
    md.append("## Fundamental Architectural Contrast")
    md.append("")
    md.append("| Architectural Axis | Ableton Live 12 Suite | Infinite | Winner |")
    md.append("|---|---|---|---|")
    md.append("| **Visual & AV Integration** | Zero native visual engine (requires Max for Live hacks or external apps) | Real-time 2D and 3D visual nodes in the same patch | **Infinite** |")
    md.append("| **Global Modulation Routing** | Modulators require separate Max for Live devices or track automation | Any modulator can modulate any audio or visual parameter (one value per param, not per voice) | **Infinite** |")
    md.append("| **Time-Stretching Quality** | Industry benchmark: Beats mode preserves drum transients with 0 flams | Phase vocoder keeps pitch, but adds 10-14 extra onsets on drums (dossier measurement) | **Live 12** |")
    md.append("| **Distortion & Color Engine** | Flagship multi-stage saturation powerhouse (**Roar**) | One tanh Drive node with bias; no multi-stage or feedback saturation | **Live 12** |")
    md.append("| **User DSP Programmability** | Proprietary Max for Live environment (separate runtime) | **Field language**: user DSP compiled inside Infinite, no separate runtime | **Infinite** |")
    md.append("")
    md.append("## Category-by-Category Teardown & Roadmap Gaps")
    md.append("")

    types = census_types()
    for cat in ["Instruments", "Audio Effects", "MIDI Effects"]:
        info = CATEGORY_ANALYSIS.get(cat, {})
        devs = catalog.get(cat, [])
        md.append(f"### {cat}")
        md.append(f"*{len(devs)} devices in Ableton Live 12.*")
        md.append("")
        md.append(f"- **Live 12 Scope**: {info.get('live_role')}")
        md.append(f"- **Infinite (census)**: {census_role(info.get('infinite_cats', []))}")
        md.append("")
        md.append("**Parity (Live device <-> Infinite node, names checked against the census):**")
        for their, nodes in info.get("parity", []):
            md.append(f"  - {parity_cell(their, nodes, types)}")
        md.append("")
        md.append("**Infinite Leads (Where Infinite Beats Ableton Live):**")
        for lead in info.get("infinite_leads", []):
            md.append(f"  - 🚀 {lead}")
        md.append("")
        md.append("**Actionable Gaps (What Infinite Needs to Build to Outpace Ableton Live):**")
        for gap in info.get("gaps_to_outpace", []):
            md.append(f"  - 🎯 {gap}")
        md.append("")

    return "\n".join(md)


def run_selftest():
    """Verify parser contracts and catalog integrity."""
    t = SelfTest("ableton_map")

    if os.path.exists(DEVICES_DIR):
        catalog = parse_ableton_devices()
        t.check(len(catalog) >= 3, "Ableton categories >= 3")
        t.check("Instruments" in catalog, "Instruments present")
        t.check("Audio Effects" in catalog, "Audio Effects present")
        t.check("MIDI Effects" in catalog, "MIDI Effects present")
        t.check(len(catalog["Instruments"]) >= 10, "Instruments count >= 10")
        t.check(len(catalog["Audio Effects"]) >= 30, "Audio Effects count >= 30")
        t.check("Roar" in catalog["Audio Effects"], "Roar found in Audio Effects")
        t.check("Wavetable" in catalog["Instruments"], "Wavetable found in Instruments")

        md = render_markdown(catalog)
        t.check(len(md) > 1000, "Markdown report rendered")
        t.check("NOT IN CENSUS" not in md, "every parity node exists in the census")

    types = census_types()
    if types:
        t.check("NOT IN CENSUS" in parity_cell("x", ["No Such Node"], types), "fake node flagged")
        t.check("NOT IN CENSUS" not in parity_cell("x", ["Audio Filter"], types), "real node passes")
    else:
        t.skip("no census built (scripts/node_census.py)")
    return t.done()


def main():
    parser = argparse.ArgumentParser(description="Extract and compare Ableton Live 12 device architecture against Infinite.")
    parser.add_argument("command", nargs="?", default="run", choices=["run"], help="Command to run (default: run)")
    parser.add_argument("--out", help="Markdown output path (default: ~/re-output/ableton/ableton_live_map.md)")
    parser.add_argument("--json", action="store_true", help="Also save JSON format")
    parser.add_argument("--self-test", action="store_true", help="Run internal self-tests and exit")
    args = parser.parse_args()

    if args.self_test:
        sys.exit(run_selftest())

    out_md = args.out or os.path.join(RE_OUTPUT, "ableton", "ableton_live_map.md")
    ensure_dir(os.path.dirname(out_md))

    catalog = parse_ableton_devices()
    md_text = render_markdown(catalog)
    write_out(md_text, out_md)
    print(f"wrote {out_md}")

    if args.json:
        out_json = out_md.replace(".md", ".json")
        with open(out_json, "w", encoding="utf-8") as f:
            json.dump(catalog, f, indent=2)
        print(f"wrote {out_json}")


if __name__ == "__main__":
    main()
