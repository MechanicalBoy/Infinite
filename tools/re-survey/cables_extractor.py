#!/usr/bin/env python3
"""re-survey cables_extractor: deep-extract all operators, ports, shaders, and architecture from cables.gl desktop.

Sources (public bundled Electron app.asar only, no decompilation):
  cables.gl Desktop: /Applications/cables.app/Contents/Resources/app.asar

Usage:
  python3 tools/re-survey/cables_extractor.py run [--out ~/re-output/cables/cables_all_ops.md] [--json]
  python3 tools/re-survey/cables_extractor.py --self-test
Exit: 0 ok, 1 parsing failed / self-test failed, 2 usage error.
"""

import argparse
import json
import os
import struct
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import RE_OUTPUT, SelfTest, ensure_dir, md_table, write_out  # noqa: E402

CABLES_ASAR = "/Applications/cables.app/Contents/Resources/app.asar"

PORT_TYPE_NAMES = {
    0: "Value / Number",
    1: "Trigger / Flow Pulse",
    2: "Object / Reference",
    3: "Texture (GPU Texture)",
    4: "Array",
    5: "String",
}

NAMESPACE_METADATA = {
    "Gl": {
        "title": "WebGL 3D, Shaders & Textures",
        "description": "3D meshes, procedural shaders, lighting, camera transforms, render targets, texture filters, and WebGL pipeline.",
        "pillar": "P7 (3D, compositing, output)",
    },
    "Array": {
        "title": "Arrays, Buffers & Instancing",
        "description": "Multi-dimensional arrays, point clouds, buffer conversions, matrix arrays, and GPU instancing.",
        "pillar": "P7 / P4 (Geometry & Field)",
    },
    "Math": {
        "title": "Math & Vector Calculations",
        "description": "Scalar, vector2/3/4, quaternion, trigonometry, noise functions, and matrix transformations.",
        "pillar": "P4 (Field & Math)",
    },
    "Anim": {
        "title": "Animation & Modulation",
        "description": "LFOs, envelopes, easing curves, keyframe tracks, smoothers, and timeline modulators.",
        "pillar": "P2 (Global modulation)",
    },
    "WebAudio": {
        "title": "WebAudio DSP & Synthesis",
        "description": "Oscillators, biquad filters, convolvers, gain, FFT frequency analysis, and sample playback.",
        "pillar": "P5 (Audio quality)",
    },
    "Devices": {
        "title": "Device Inputs & Hardware I/O",
        "description": "MIDI In/Out, Gamepad, Webcam, Microphone, Motion sensors, Mouse, and Keyboard.",
        "pillar": "P1 (Live AV workstation)",
    },
    "Trigger": {
        "title": "Trigger & Flow Control",
        "description": "Pulse splitters, conditional gates, counters, loop iterators, and execution barriers.",
        "pillar": "P1 (Live AV workstation)",
    },
    "Color": {
        "title": "Color & Gradients",
        "description": "RGB/HSV conversions, color palettes, gradient samplers, and hex parsers.",
        "pillar": "P7 (Compositing)",
    },
    "TimeLine": {
        "title": "Timeline & Sequencing",
        "description": "Playback transport, cue points, frame counters, and sequence automation.",
        "pillar": "P6 (Timeline & arrangement)",
    },
    "Extension": {
        "title": "Extensions (Physics, AI, WebGPU)",
        "description": "Rapier 3D physics, MediaPipe tracking, L-Systems, SuperShapes, WebGPU shaders, and particles.",
        "pillar": "P7 / P4 / P3",
    },
}


def read_asar_header(f):
    """Read asar 16-byte header and parse directory JSON."""
    f.seek(0)
    magic = f.read(4)
    if magic != b"\x04\x00\x00\x00":
        raise ValueError(f"Invalid asar magic: {magic}")
    size1, size2, json_len = struct.unpack("<III", f.read(12))
    header_json = f.read(json_len).decode("utf-8")
    header = json.loads(header_json)
    base_offset = 16 + json_len
    return header, base_offset


def parse_cables_ops(asar_path=CABLES_ASAR):
    """Parse all base and extension operators from cables.gl app.asar."""
    if not os.path.exists(asar_path):
        raise FileNotFoundError(f"cables.gl app.asar not found at {asar_path}")

    with open(asar_path, "rb") as f:
        header, base_offset = read_asar_header(f)

        ops = {}
        extensions = {}
        namespaces = Counter()
        port_types = Counter()

        dist_ops = header.get("files", {}).get("dist", {}).get("files", {}).get("ops", {}).get("files", {})
        base_ops_node = dist_ops.get("base", {}).get("files", {})

        # 1. Base Operators
        for op_name, op_node in base_ops_node.items():
            json_file = f"{op_name}.json"
            if "files" not in op_node or json_file not in op_node["files"]:
                continue

            f_node = op_node["files"][json_file]
            f.seek(base_offset + int(f_node["offset"]))
            try:
                op_json = json.loads(f.read(int(f_node["size"])).decode("utf-8"))
            except Exception:
                continue

            parts = op_name.split(".")
            ns = parts[1] if len(parts) > 1 else "Other"
            namespaces[ns] += 1

            layout = op_json.get("layout", {})
            ports_in = layout.get("portsIn", [])
            ports_out = layout.get("portsOut", [])

            for p in ports_in + ports_out:
                pt = p.get("subType") or PORT_TYPE_NAMES.get(p.get("type"), str(p.get("type")))
                port_types[pt] += 1

            ops[op_name] = {
                "name": op_name,
                "is_extension": False,
                "namespace": ns,
                "summary": op_json.get("summary", ""),
                "author": op_json.get("authorName", ""),
                "ports_in_count": len(ports_in),
                "ports_out_count": len(ports_out),
                "ports_in": [
                    {
                        "name": p.get("name", ""),
                        "type": p.get("type"),
                        "subType": p.get("subType", ""),
                        "type_name": PORT_TYPE_NAMES.get(p.get("type"), "Unknown"),
                    }
                    for p in ports_in
                ],
                "ports_out": [
                    {
                        "name": p.get("name", ""),
                        "type": p.get("type"),
                        "subType": p.get("subType", ""),
                        "type_name": PORT_TYPE_NAMES.get(p.get("type"), "Unknown"),
                    }
                    for p in ports_out
                ],
            }

        # 2. Modern Extension Operators (Rapier3D, GlParticles, WebGpu, LSystem, etc.)
        ext_node = dist_ops.get("extensions", {}).get("files", {})
        for ext_group, ext_group_node in ext_node.items():
            if ext_group in ("Ops.Extension.Deprecated", "Ops.Extension.Testing"):
                continue  # skip deprecated and test fixtures

            for op_name, op_node in ext_group_node.get("files", {}).items():
                if not op_name.startswith("Ops.") or not isinstance(op_node, dict):
                    continue
                json_file = f"{op_name}.json"
                if "files" not in op_node or json_file not in op_node["files"]:
                    continue

                f_node = op_node["files"][json_file]
                f.seek(base_offset + int(f_node["offset"]))
                try:
                    op_json = json.loads(f.read(int(f_node["size"])).decode("utf-8"))
                except Exception:
                    continue

                layout = op_json.get("layout", {})
                ports_in = layout.get("portsIn", [])
                ports_out = layout.get("portsOut", [])

                extensions[op_name] = {
                    "name": op_name,
                    "is_extension": True,
                    "extension_group": ext_group.replace("Ops.Extension.", ""),
                    "namespace": "Extension",
                    "summary": op_json.get("summary", ""),
                    "author": op_json.get("authorName", ""),
                    "ports_in_count": len(ports_in),
                    "ports_out_count": len(ports_out),
                    "ports_in": [
                        {
                            "name": p.get("name", ""),
                            "type": p.get("type"),
                            "subType": p.get("subType", ""),
                            "type_name": PORT_TYPE_NAMES.get(p.get("type"), "Unknown"),
                        }
                        for p in ports_in
                    ],
                    "ports_out": [
                        {
                            "name": p.get("name", ""),
                            "type": p.get("type"),
                            "subType": p.get("subType", ""),
                            "type_name": PORT_TYPE_NAMES.get(p.get("type"), "Unknown"),
                        }
                        for p in ports_out
                    ],
                }

    return {
        "base_ops": ops,
        "extension_ops": extensions,
        "namespaces": dict(namespaces),
        "port_types": dict(port_types),
    }


def render_markdown(catalog):
    """Render comprehensive markdown report for cables.gl operator library."""
    base_ops = catalog["base_ops"]
    ext_ops = catalog["extension_ops"]
    namespaces = catalog["namespaces"]

    total_ops = len(base_ops) + len(ext_ops)
    total_ports_in = sum(o["ports_in_count"] for o in base_ops.values()) + sum(o["ports_in_count"] for o in ext_ops.values())
    total_ports_out = sum(o["ports_out_count"] for o in base_ops.values()) + sum(o["ports_out_count"] for o in ext_ops.values())

    lines = [
        "# cables.gl — Complete Operator Library & Architecture Schema",
        "",
        "> **Clean Room Invariant**: Extracted exclusively from public application bundle "
        "`/Applications/cables.app/Contents/Resources/app.asar`. Zero binary decompilation.",
        "",
        "## 1. Executive Summary & Scale",
        "",
        f"- **Total Active Operators Cataloged**: **{total_ops:,}**",
        f"- **Base Built-In Operators**: **{len(base_ops):,}**",
        f"- **Modern Extension Operators**: **{len(ext_ops):,}** (Rapier 3D, WebGPU, GlParticles, MediaPipe, L-Systems)",
        f"- **Total Dataflow Ports**: **{total_ports_in + total_ports_out:,}** ({total_ports_in:,} Inputs, {total_ports_out:,} Outputs)",
        f"- **Top Operator Family**: `Ops.Gl` ({namespaces.get('Gl', 0):,} WebGL 3D, shader, and texture ops)",
        "",
        "---",
        "",
        "## 2. Operator Families Breakdown",
        "",
    ]

    fam_headers = ["Namespace", "Title", "Operator Count", "Pillar Map", "Scope"]
    fam_rows = []
    for ns, count in sorted(namespaces.items(), key=lambda x: -x[1]):
        meta = NAMESPACE_METADATA.get(ns, {
            "title": f"Ops.{ns}",
            "description": "General purpose dataflow operators.",
            "pillar": "P1 (Live AV workstation)",
        })
        fam_rows.append([f"`Ops.{ns}`", meta["title"], f"{count:,}", meta["pillar"], meta["description"]])

    lines.append(md_table(fam_headers, fam_rows))
    lines.append("")
    lines.append("---")
    lines.append("")

    # Modern Extensions Section
    lines.append("## 3. High-Performance Modern Extensions")
    lines.append("")
    ext_groups = Counter(o["extension_group"] for o in ext_ops.values())
    ext_headers = ["Extension Group", "Operator Count", "Capabilities", "Infinite equivalent"]
    ext_rows = [
        ["Rapier3d", ext_groups.get("Rapier3d", 0), "Real-time 3D rigid body dynamics, collision shapes, impulses, and forces.", "`Particle System`, `Cloth`; no rigid bodies (plan item 3.8)."],
        ["GlParticles", ext_groups.get("GlParticles", 0), "GPU particle systems with noise vector fields and curl noise.", "`Particle System`, `Field Modifier`."],
        ["WebGpu", ext_groups.get("WebGpu", 0), "Next-gen WebGPU compute shaders, GPU buffers, and materials.", "none (GPU particles are plan item 3.15)."],
        ["Mediapipe", ext_groups.get("Mediapipe", 0), "FaceMesh (468 landmarks), Hand tracking, and pose detection.", "`Face Track`, `Hand Track`, `Pose Track`."],
        ["LSystem", ext_groups.get("LSystem", 0), "Procedural 3D fractal branching and plant generation.", "none."],
        ["SuperShapes", ext_groups.get("SuperShapes", 0), "Gielis 3D superformula parametric geometric curves and meshes.", "`Supershape`, `Field Primitive`."],
        ["ReactionDiffusion", ext_groups.get("ReactionDiffusion", 0), "Gray-Scott chemical reaction-diffusion simulation textures.", "`Reaction Diffusion`."],
    ]
    lines.append(md_table(ext_headers, ext_rows))
    lines.append("")
    lines.append("---")
    lines.append("")

    # Sample catalog preview for top families
    lines.append("## 4. Key Operator Architectural Highlights")
    lines.append("")

    key_samples = [
        "Ops.Gl.Shader.CustomShader",
        "Ops.Graphics.Meshes.Cube",
        "Ops.Array.Instancing.InstancedMesh",
        "Ops.Anim.LFO_v3",
        "Ops.WebAudio.Oscillator",
        "Ops.Devices.MidiInput",
    ]

    for k in key_samples:
        op = base_ops.get(k)
        if not op:
            continue
        lines.append(f"### `{op['name']}`")
        if op["summary"]:
            lines.append(f"- **Summary**: {op['summary']}")
        lines.append(f"- **Namespace**: `Ops.{op['namespace']}` | **Ports**: {op['ports_in_count']} In, {op['ports_out_count']} Out")
        in_names = ", ".join(f"`{p['name']}` ({p['type_name']})" for p in op["ports_in"][:6])
        out_names = ", ".join(f"`{p['name']}` ({p['type_name']})" for p in op["ports_out"][:4])
        lines.append(f"- **Inputs**: {in_names}")
        lines.append(f"- **Outputs**: {out_names}")
        lines.append("")

    return "\n".join(lines)


def run_selftest():
    """Verify cables.gl asar parser contracts and operator catalog."""
    t = SelfTest("cables_extractor")

    if os.path.exists(CABLES_ASAR):
        catalog = parse_cables_ops()
        base_ops = catalog["base_ops"]
        ext_ops = catalog["extension_ops"]
        namespaces = catalog["namespaces"]

        t.check(len(base_ops) >= 1600, f"Base operators count >= 1600 (got {len(base_ops)})")
        t.check("Ops.Anim.LFO_v3" in base_ops, "LFO_v3 present")
        t.check("Ops.Graphics.Meshes.Cube" in base_ops, "Cube mesh present")
        t.check("Gl" in namespaces and namespaces["Gl"] >= 500, "Gl namespace >= 500 ops")
        t.check("Array" in namespaces and namespaces["Array"] >= 200, "Array namespace >= 200 ops")

        # Check extensions
        t.check(len(ext_ops) >= 50, f"Extension operators count >= 50 (got {len(ext_ops)})")
        t.check(any("Rapier3d" in k for k in ext_ops), "Rapier3d extension present")
        t.check(any("GlParticles" in k for k in ext_ops), "GlParticles extension present")

        # Check ports
        total_ports = sum(o["ports_in_count"] + o["ports_out_count"] for o in base_ops.values())
        t.check(total_ports >= 10000, f"Total ports >= 10,000 (got {total_ports})")

        md = render_markdown(catalog)
        t.check(len(md) > 2000, f"Markdown rendered successfully ({len(md)} bytes)")

    return t.done()


def main():
    parser = argparse.ArgumentParser(description="Extract all operators, ports, and architecture from cables.gl desktop.")
    parser.add_argument("command", nargs="?", default="run", choices=["run"], help="Command to run (default: run)")
    parser.add_argument("--out", help="Markdown output path (default: ~/re-output/cables/cables_all_ops.md)")
    parser.add_argument("--json", action="store_true", help="Also save complete JSON format")
    parser.add_argument("--self-test", action="store_true", help="Run internal self-tests and exit")
    args = parser.parse_args()

    if args.self_test:
        sys.exit(run_selftest())

    out_md = args.out or os.path.join(RE_OUTPUT, "cables", "cables_all_ops.md")
    ensure_dir(os.path.dirname(out_md))

    catalog = parse_cables_ops()
    md_text = render_markdown(catalog)
    write_out(md_text, out_md)
    print(f"wrote {out_md}")

    out_json = out_md.replace(".md", ".json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(catalog, f, indent=2)
    print(f"wrote {out_json}")


if __name__ == "__main__":
    main()
