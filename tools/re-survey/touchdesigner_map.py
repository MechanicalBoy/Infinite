#!/usr/bin/env python3
"""re-survey touchdesigner_map: extract and compare TouchDesigner's operator ecosystem against Infinite.

Sources (public bundle metadata only, no decompilation):
  TouchDesigner: /Applications/TouchDesigner.app/Contents/Resources/tfs/Samples/Learn/OPSnippets/Snippets
  Infinite:      src/nodes/ headers, skills/infinite-patch-authoring/SKILL.md, Field language

Usage:
  python3 tools/re-survey/touchdesigner_map.py run [--out ~/re-output/touchdesigner/touchdesigner_map.md]
  python3 tools/re-survey/touchdesigner_map.py --self-test
Exit: 0 ok, 1 parsing failed / self-test failed, 2 usage error.
"""

import argparse
import collections
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import RE_OUTPUT, SelfTest, census_role, census_types, ensure_dir, md_table, parity_cell, write_out  # noqa: E402

TD_APP = "/Applications/TouchDesigner.app"
TD_SNIPPETS_DIR = os.path.join(TD_APP, "Contents", "Resources", "tfs", "Samples", "Learn", "OPSnippets", "Snippets")

FAMILIES = ["TOP", "CHOP", "SOP", "POP", "MAT", "DAT", "COMP"]

# Curated mapping of key TouchDesigner operator families to Infinite. The Infinite side is
# checked: counts come from the node census and every parity node name is looked up there.
# Leads and gaps are hand-written judgements, not measurements.
FAMILY_ANALYSIS = {
    "TOP": {
        "title": "Texture Operators (2D Image & GPU Shaders)",
        "td_role": "2D image generation, GPU filtering, color grading, compositing, temporal feedback",
        "infinite_cats": ["Source", "Compositing", "Effects"],
        "parity": [
            ("Constant / Noise / Ramp / Text TOP", ["Constant", "Noise", "Ramp", "Text"]),
            ("Blur / Bloom / Edge / Emboss / Lookup / Threshold", ["gaussianblur", "bloom", "edge sobel", "emboss", "lookup", "threshold"]),
            ("Chroma Key / Lens Distort", ["chroma key", "lensdistortion"]),
            ("Composite / Over / Cross", ["Blend", "Layer Stack", "Switcher"]),
            ("Feedback / Trails / Reaction Diffusion", ["Feedback", "Trails", "Reaction Diffusion"]),
            ("Movie File In / Video Device In / Syphon Spout / NDI", ["Video", "Video In", "Syphon In", "Syphon Out", "NDI In", "NDI Out", "Image Source"]),
        ],
        "infinite_leads": [
            "Field Pixel: per-pixel kernels in the Field language with modulation inputs, no uniform wiring",
            "MIT, free: no resolution cap (TD non-commercial is capped at 1280x720)",
        ],
        "gaps_to_outpace": [
            "Optical Flow: motion vectors from video frames",
            "Time Machine: per-pixel time displacement through a texture history",
            "Depth sensor inputs (Kinect, RealSense, ZED)",
        ],
    },
    "CHOP": {
        "title": "Channel Operators (Control, Audio, I/O)",
        "td_role": "Control signals, audio, device I/O; many named channels per wire",
        "infinite_cats": ["Modulators", "Notes", "AudioEffects", "Synths"],
        "parity": [
            ("LFO / Noise / Math / Lag / Envelope / Logic / Range", ["LFO", "Random", "Math", "Smoothing", "Envelope", "Compare", "Range to Range"]),
            ("Audio Analyze / Audio Spectrum", ["Audio to CV", "Audio Analyze"]),
            ("OSC In/Out, MIDI In, Audio Device In/Out", ["OSC Receive", "OSC Send", "MIDI CC", "MIDI Notes", "Audio In", "Audio Out"]),
        ],
        "infinite_leads": [
            "A real audio engine: synths, audio effects, latency compensation and VST3/AU hosting in the same patch",
            "Prediction family: modulators that learn the performer's gestures",
        ],
        "gaps_to_outpace": [
            "DMX / sACN / Art-Net lighting output",
            "Multi-channel wires: one TD wire carries N named channels; Infinite needs one cable per value",
        ],
    },
    "SOP": {
        "title": "Surface Operators (3D Geometry)",
        "td_role": "Procedural mesh generation and modification",
        "infinite_cats": ["3D"],
        "parity": [
            ("Box / Sphere / Torus / Tube / Text", ["Cube", "Sphere", "Torus", "Tube", "Text 3D"]),
            ("Extrude / Boolean / Subdivide / Twist / Mirror", ["Extrude", "Union", "Difference", "Intersect", "Subdivide", "Twist", "Solidify", "Screw", "Mirror", "Array", "Displacement"]),
            ("Copy SOP / Instancing", ["Instance on Points"]),
        ],
        "infinite_leads": [
            "Field Modifier: per-vertex code in the Field language with audio and modulation inputs",
        ],
        "gaps_to_outpace": [
            "Revolve / Lathe and Sweep along a path",
            "Polyloft, fillet, bevel",
        ],
    },
    "POP": {
        "title": "Point Operators (GPU particles and points, TD 2025)",
        "td_role": "GPU point clouds and particle simulation",
        "infinite_cats": ["3D"],
        "parity": [
            ("Point distribution", ["Distribute Points in Grid", "Distribute Points on Faces", "Image to Points"]),
            ("Particle forces", ["Particle System"]),
            ("Field-driven points", ["Field Modifier", "Field Primitive"]),
        ],
        "infinite_leads": [],
        "gaps_to_outpace": [
            "GPU neighbour search (lines between points within radius R)",
            "Simulation feedback loop in point space (accumulate)",
        ],
    },
    "MAT": {
        "title": "Material Operators",
        "td_role": "PBR, Phong, GLSL and constant materials",
        "infinite_cats": ["3D"],
        "parity": [
            ("PBR MAT (metallic, roughness, emission, normal, AO, clearcoat, sheen, iridescence, transmission, anisotropy, dispersion)", ["Material"]),
            ("Wireframe / Constant", ["Wireframe"]),
        ],
        "infinite_leads": [],
        "gaps_to_outpace": [
            "GLSL MAT: custom vertex/fragment shader on a mesh",
        ],
    },
}


def parse_touchdesigner_operators(snippets_dir=TD_SNIPPETS_DIR):
    """Scan TouchDesigner's installed snippets directory to catalog every operator."""
    if not os.path.exists(snippets_dir):
        raise FileNotFoundError(f"TouchDesigner snippets not found at {snippets_dir}")

    catalog = {}
    for fam in FAMILIES:
        fam_dir = os.path.join(snippets_dir, fam)
        if not os.path.isdir(fam_dir):
            continue
        ops = []
        for fname in sorted(os.listdir(fam_dir)):
            if fname.endswith(".tox"):
                raw_name = fname[:-4]
                # Clean prefix/suffix: e.g. moviefileinTOP -> Movie File In
                clean_name = raw_name
                if clean_name.lower().endswith(fam.lower()):
                    clean_name = clean_name[:-len(fam)]
                ops.append({
                    "raw_name": raw_name,
                    "clean_name": clean_name,
                    "family": fam,
                    "file": fname,
                })
        catalog[fam] = ops

    return catalog


def render_markdown(catalog):
    """Render comprehensive comparison report between TouchDesigner and Infinite."""
    md = []
    md.append("# Visual & AV Architecture: TouchDesigner vs Infinite")
    md.append("")
    md.append("Generated by `tools/re-survey/touchdesigner_map.py`. TD operator lists come from the installed 2025.32820 bundle; Infinite counts and node names come from the census; leads, gaps and the contrast table are hand-written judgements.")
    md.append("")
    md.append("## Executive Summary")
    md.append("")

    total_ops = sum(len(ops) for ops in catalog.values())
    md.append(f"- **TouchDesigner Operators Cataloged**: {total_ops} operators across 7 families:")
    for fam, ops in catalog.items():
        md.append(f"  - **{fam}**: {len(ops)} operators")
    md.append("- **Infinite (census)**: %s." % census_role(["Source", "Compositing", "Effects", "3D", "Synths", "AudioEffects", "Notes", "Modulators", "Macros", "Prediction", "Utility"]))
    md.append("")
    md.append("## Fundamental Architectural Contrast")
    md.append("")
    md.append("| Architectural Axis | TouchDesigner | Infinite | Winner |")
    md.append("|---|---|---|---|")
    md.append("| **Audio & Visual Integration** | CHOP audio is a channel stream, not a production audio engine | Audio engine with synths, effects, latency compensation, VST3/AU hosting | **Infinite** |")
    md.append("| **User Programmability** | GLSL TOPs & Python scripts require manual uniform wiring and boilerplate | The **Field language** (Field Pixel, Field Modifier): plain-text kernels with audio/modulation inputs | **Infinite** |")
    md.append("| **GPU 3D Instancing** | GPU instancing via Copy SOP / Geometry COMP | Instance on Points; no head-to-head instancing measurement yet | **Unmeasured** |")
    md.append("| **2D Texture Toolset Breadth** | 93+ specialized TOPs, hardware sensor inputs (Kinect, RealSense), optical flow | Source, Compositing and Effects nodes (counts above); no depth sensors, no optical flow | **TouchDesigner** |")
    md.append("| **Export Resolution** | Non-commercial capped at 1280x720 ($600–$2,200 commercial license for 4K) | MIT and free; ProRes 4444 export with alpha | **Infinite** |")
    md.append("")
    md.append("## Family-by-Family Teardown & Roadmap Gaps")
    md.append("")

    types = census_types()
    for fam in ["TOP", "CHOP", "SOP", "POP", "MAT"]:
        info = FAMILY_ANALYSIS.get(fam, {})
        ops = catalog.get(fam, [])
        md.append(f"### {fam}: {info.get('title', fam)}")
        md.append(f"*{len(ops)} operators in TouchDesigner.*")
        md.append("")
        md.append(f"- **TouchDesigner Role**: {info.get('td_role')}")
        md.append(f"- **Infinite (census)**: {census_role(info.get('infinite_cats', []))}")
        md.append("")
        md.append("**Parity (TD operator <-> Infinite node, names checked against the census):**")
        for their, nodes in info.get("parity", []):
            md.append(f"  - {parity_cell(their, nodes, types)}")
        md.append("")
        md.append("**Infinite Leads (Where Infinite Beats TouchDesigner):**")
        for lead in info.get("infinite_leads", []):
            md.append(f"  - 🚀 {lead}")
        md.append("")
        md.append("**Actionable Gaps (What Infinite Needs to Build to Outpace TouchDesigner):**")
        for gap in info.get("gaps_to_outpace", []):
            md.append(f"  - 🎯 {gap}")
        md.append("")

    return "\n".join(md)


def run_selftest():
    """Verify parser contracts and catalog integrity."""
    t = SelfTest("touchdesigner_map")

    if os.path.exists(TD_SNIPPETS_DIR):
        catalog = parse_touchdesigner_operators()
        t.check(len(catalog) >= 5, "TouchDesigner families >= 5")
        t.check("TOP" in catalog, "TOP family present")
        t.check("SOP" in catalog, "SOP family present")
        t.check("CHOP" in catalog, "CHOP family present")
        t.check(len(catalog["TOP"]) >= 50, "TOP operators count >= 50")
        t.check(len(catalog["SOP"]) >= 50, "SOP operators count >= 50")
        t.check(len(catalog["CHOP"]) >= 50, "CHOP operators count >= 50")

        md = render_markdown(catalog)
        t.check("NOT IN CENSUS" not in md, "every parity node exists in the census")
        t.check(len(md) > 1000, "Markdown report rendered")

    return t.done()


def main():
    parser = argparse.ArgumentParser(description="Extract and compare TouchDesigner operator ecosystem against Infinite.")
    parser.add_argument("command", nargs="?", default="run", choices=["run"], help="Command to run (default: run)")
    parser.add_argument("--out", help="Markdown output path (default: ~/re-output/touchdesigner/touchdesigner_map.md)")
    parser.add_argument("--json", action="store_true", help="Also save JSON format")
    parser.add_argument("--self-test", action="store_true", help="Run internal self-tests and exit")
    args = parser.parse_args()

    if args.self_test:
        sys.exit(run_selftest())

    out_md = args.out or os.path.join(RE_OUTPUT, "touchdesigner", "touchdesigner_map.md")
    ensure_dir(os.path.dirname(out_md))

    catalog = parse_touchdesigner_operators()
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
