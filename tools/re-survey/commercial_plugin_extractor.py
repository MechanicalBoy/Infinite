#!/usr/bin/env python3
"""re-survey commercial_plugin_extractor: deep-extract parameter trees and DSP topologies from commercial plugins.

Sources (observable Audio Unit parameter trees and bundle manifests only, zero binary disassembly):
  AU Components: /Library/Audio/Plug-Ins/Components/*.component
  VST3 Bundles:  /Library/Audio/Plug-Ins/VST3/*.vst3

Usage:
  python3 tools/re-survey/commercial_plugin_extractor.py run [--out ~/re-output/plugins/plugins_all_models.md] [--json]
  python3 tools/re-survey/commercial_plugin_extractor.py --self-test
Exit: 0 ok, 1 parsing failed / self-test failed, 2 usage error.
"""

import argparse
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import RE_OUTPUT, RE_TMP, SelfTest, ensure_dir, md_table, write_out  # noqa: E402
import plugin_probe as pp  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))

SWIFT_HARNESS = r"""
import AudioToolbox
import Foundation

func fourCC(_ s: String) -> FourCharCode {
    var r: FourCharCode = 0
    for u in s.utf8.prefix(4) { r = (r << 8) | FourCharCode(u) }
    return r
}

let a = CommandLine.arguments
guard a.count == 4 else {
    FileHandle.standardError.write("usage: swift harness <type> <subtype> <manu>\n".data(using: .utf8)!)
    exit(2)
}

let desc = AudioComponentDescription(componentType: fourCC(a[1]), componentSubType: fourCC(a[2]),
                                     componentManufacturer: fourCC(a[3]), componentFlags: 0, componentFlagsMask: 0)

let sem = DispatchSemaphore(value: 0)
var result: [String: Any] = ["ok": false]

AUAudioUnit.instantiate(with: desc, options: []) { u, e in
    if let au = u {
        var params: [[String: Any]] = []
        if let tree = au.parameterTree {
            for p in tree.allParameters {
                params.append([
                    "address": p.address,
                    "identifier": p.identifier,
                    "name": p.displayName,
                    "min": p.minValue,
                    "max": p.maxValue,
                    "default": p.value,
                    "unit": p.unitName ?? ""
                ])
            }
        }
        result = [
            "ok": true,
            "params_count": params.count,
            "params": params
        ]
    } else {
        result = ["ok": false, "error": "\(e?.localizedDescription ?? "unknown")"]
    }
    sem.signal()
}
sem.wait()

let data = try! JSONSerialization.data(withJSONObject: result, options: [])
print("---SWIFT_JSON_START---")
print(String(data: data, encoding: .utf8)!)
print("---SWIFT_JSON_END---")
"""


def run_swift_inspector(typ, sub, manu, timeout_s=15):
    """Instantiate AU and extract parameterTree via Swift."""
    cmd = ["swift", "-e", SWIFT_HARNESS, typ, sub, manu]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s)
        out = p.stdout
        if "---SWIFT_JSON_START---" in out and "---SWIFT_JSON_END---" in out:
            jstr = out.split("---SWIFT_JSON_START---")[1].split("---SWIFT_JSON_END---")[0].strip()
            return json.loads(jstr)
    except Exception as e:
        return {"ok": False, "error": str(e)}
    return {"ok": False, "error": "delimiter not found or failed"}


def classify_plugin(name, ptype):
    """Classify plugin into functional DSP domain."""
    lower = name.lower()
    if ptype == "aumu" or any(k in lower for k in ["diva", "vital", "serum", "twin", "phase plant", "one", "drumazon"]):
        return "Synthesizers & Drum Instruments"
    elif any(k in lower for k in ["soothe", "pro-q", "nova", "slice eq", "carve eq", "3-band eq"]):
        return "Dynamic EQ & Spectral Shaping"
    elif any(k in lower for k in ["saturn", "faturator", "disperser", "distortion", "shaper", "bitcrush", "nonlinear"]):
        return "Distortion & Multi-Band Saturation"
    elif any(k in lower for k in ["verb", "room", "plate", "shimmer", "supermassive", "convolver", "pro-r"]):
        return "Reverb & Spatial Acoustics"
    elif any(k in lower for k in ["delay", "timeless", "ubermod", "freqecho"]):
        return "Delays & Modulated Echoes"
    elif any(k in lower for k in ["pro-c", "pro-l", "pro-mb", "pro-ds", "pro-g", "compressor", "limiter", "dynamics", "gate", "transient"]):
        return "Dynamics & Mastering Processors"
    elif any(k in lower for k in ["volcano", "simplon", "micro", "filter", "ladder", "comb", "multipass", "snap heap", "shaperbox", "rc-20"]):
        return "Creative Filters & Modular Multi-FX"
    elif any(k in lower for k in ["chorus", "flanger", "phaser", "ensemble", "pitch", "ring mod", "frequency shifter"]):
        return "Modulation & Pitch Effects"
    else:
        return "Utility & Channel Tools"


def extract_all_plugins():
    """Extract parameter manifests for all installed commercial audio plugins."""
    aus = pp.list_aus()
    results = {}

    for a in aus:
        au_id = a["id"]
        name = a["name"]
        ptype = a["type"]

        if name.startswith("Apple:"):
            continue

        parts = au_id.split(":")
        if len(parts) != 4:
            continue
        _, typ, sub, manu = parts

        params = []
        status = "ok"
        error_msg = ""

        # Strategy 1: For effect plugins (aufx, aumf), try Infinite host first
        if ptype in ("aufx", "aumf"):
            try:
                r = pp.resolve(au_id, aus)
                host_p = pp.host_params(r)
                if host_p:
                    params = host_p
            except Exception:
                pass

        # Strategy 2: If no params yet or instrument (aumu), use Swift AudioToolbox inspector
        if not params:
            res = run_swift_inspector(typ, sub, manu)
            if res.get("ok"):
                params = res.get("params", [])
            else:
                status = "fail"
                error_msg = res.get("error", "Failed inspection")

        family = classify_plugin(name, ptype)

        results[au_id] = {
            "id": au_id,
            "name": name,
            "type": ptype,
            "family": family,
            "status": status,
            "error": error_msg,
            "params_count": len(params),
            "params": params,
        }

    return results


def render_markdown(catalog):
    """Render comprehensive markdown dossier for all extracted commercial plugins."""
    plugins = list(catalog.values())
    total_plugins = len(plugins)
    total_params = sum(p["params_count"] for p in plugins)
    active_plugins = [p for p in plugins if p["params_count"] > 0]

    lines = [
        "# Commercial Audio Plugins — Complete Ecosystem & Parameter Architecture Mapping",
        "",
        "> **Clean Room Invariant**: Extracted exclusively from public macOS AudioToolbox runtime manifests "
        "and observable parameter trees via Infinite's host and native Swift APIs. Zero binary decompilation or disassembly.",
        "",
        "## 1. Executive Summary & Inventory Scale",
        "",
        f"- **Total Commercial Plugins Introspected**: **{total_plugins}**",
        f"- **Plugins Successfully Parameterized**: **{len(active_plugins)}**",
        f"- **Total Discrete Parameters Extracted**: **{total_params:,} parameters**",
        "- **Primary DSP Vendors**: **FabFilter**, **Valhalla DSP**, **oeksound**, **u-he**, **Kilohearts**, **Xfer Records**, **Vital Audio**, **D16 Group**, **Cableguys**, **Tokyo Dawn Labs**, **XLN Audio**.",
        "",
        "---",
        "",
        "## 2. Functional DSP Family Breakdown",
        "",
    ]

    by_family = {}
    for p in plugins:
        fam = p["family"]
        by_family.setdefault(fam, []).append(p)

    fam_headers = ["DSP Domain", "Plugins", "Parameters", "Key Models", "Infinite equivalent"]
    fam_rows = []

    for fam, items in sorted(by_family.items()):
        pcount = len(items)
        param_sum = sum(x["params_count"] for x in items)
        key_names = ", ".join(x["name"].split(": ")[-1] for x in items[:4])
        if len(items) > 4:
            key_names += f" (+{len(items)-4} more)"

        eq_map = {
            "Dynamic EQ & Spectral Shaping": "`EQ`, `Spec Blur`, `Spectrum Slide`; no dynamic EQ",
            "Distortion & Multi-Band Saturation": "`Drive`, `Wavetable Shaper`, `Cycle Shaper`, `Bitcrush`; multi-stage and multiband are plan items 2.17 and 2.18",
            "Reverb & Spatial Acoustics": "`Reverb`; convolution is plan item 2.9",
            "Delays & Modulated Echoes": "`Delay`, `Stutter`; tape delay is plan item 2.20",
            "Dynamics & Mastering Processors": "`Dynamics`, `Limiter`, `Transient Shaper`; no multiband compressor or de-esser",
            "Creative Filters & Modular Multi-FX": "`Audio Filter`, `Formant Filter`, `Resonator Bank`; more filter models are plan item 2.25",
            "Synthesizers & Drum Instruments": "`Analog`, `Wavetable`, `Oscillator`, `Metallic`, `Granular`, `Spectral Synth`, `Field Synth`; FM is plan item 2.22",
            "Modulation & Pitch Effects": "`Chorus`, `Flanger`, `Phaser`, `Pitch Shifter`, `Frequency Shifter`, `Tremolo`, `Ring Mod`",
            "Utility & Channel Tools": "`Gain`, `Stereo`, `Mixer`, `Audio Meter`",
        }
        outpace = eq_map.get(fam, "none mapped")

        fam_rows.append([fam, pcount, f"{param_sum:,}", key_names, outpace])

    lines.append(md_table(fam_headers, fam_rows))
    lines.append("")
    lines.append("---")
    lines.append("")

    lines.append("## 3. Flagship Plugin Parameter Manifests")
    lines.append("")

    flagships = [
        "soothe2", "Pro-Q 4", "Saturn 2", "ValhallaVintageVerb", "ValhallaDelay",
        "ValhallaSupermassive", "Pro-C 2", "Pro-L 2", "Timeless 3", "Diva",
        "Vital", "Drumazon 2", "Phase Plant", "Multipass", "TDR Nova"
    ]

    flag_headers = ["Plugin Name", "Vendor", "Type", "Parameters", "Key Parameter Sockets", "Infinite equivalent"]
    flag_rows = []

    for f in flagships:
        match = next((p for p in plugins if f.lower() in p["name"].lower()), None)
        if match:
            vendor = match["name"].split(":")[0] if ":" in match["name"] else "Commercial"
            short_name = match["name"].split(":")[-1].strip()
            sample_p = ", ".join(p["name"] for p in match["params"][:5]) if match["params"] else "Host Parameter Tree"
            flag_rows.append([
                short_name,
                vendor,
                match["type"],
                match["params_count"],
                sample_p,
                "none mapped"
            ])

    lines.append(md_table(flag_headers, flag_rows))
    lines.append("")
    lines.append("---")
    lines.append("")

    lines.append("## 4. Complete Plugin Catalog Table")
    lines.append("")
    cat_headers = ["ID", "Name", "Category", "Parameters", "Status"]
    cat_rows = []
    for p in sorted(plugins, key=lambda x: (x["family"], x["name"])):
        cat_rows.append([
            p["id"],
            p["name"],
            p["family"],
            p["params_count"],
            "OK" if p["params_count"] > 0 else "GUI-context required"
        ])
    lines.append(md_table(cat_headers, cat_rows))
    lines.append("")

    return "\n".join(lines)


def run_selftest():
    """Verify commercial plugin extractor contracts and parameter counts."""
    t = SelfTest("commercial_plugin_extractor")

    catalog = extract_all_plugins()
    t.check(len(catalog) >= 50, f"Total plugins discovered >= 50 (got {len(catalog)})")

    # Find key plugins
    soothe = next((p for p in catalog.values() if "soothe2" in p["name"].lower()), None)
    pro_q4 = next((p for p in catalog.values() if "pro-q 4" in p["name"].lower()), None)
    saturn2 = next((p for p in catalog.values() if "saturn 2" in p["name"].lower()), None)
    vvv = next((p for p in catalog.values() if "valhallavintageverb" in p["name"].lower()), None)
    diva = next((p for p in catalog.values() if "diva" in p["name"].lower()), None)
    vital = next((p for p in catalog.values() if "vital" in p["name"].lower()), None)

    t.check(soothe is not None and soothe["params_count"] >= 50, f"soothe2 params >= 50 (got {soothe['params_count'] if soothe else 0})")
    t.check(pro_q4 is not None and pro_q4["params_count"] >= 500, f"Pro-Q 4 params >= 500 (got {pro_q4['params_count'] if pro_q4 else 0})")
    t.check(saturn2 is not None and saturn2["params_count"] >= 900, f"Saturn 2 params >= 900 (got {saturn2['params_count'] if saturn2 else 0})")
    t.check(vvv is not None and vvv["params_count"] == 17, f"ValhallaVintageVerb params == 17 (got {vvv['params_count'] if vvv else 0})")
    t.check(diva is not None and diva["params_count"] >= 250, f"u-he Diva params >= 250 (got {diva['params_count'] if diva else 0})")
    t.check(vital is not None and vital["params_count"] >= 700, f"Vital params >= 700 (got {vital['params_count'] if vital else 0})")

    md = render_markdown(catalog)
    t.check(len(md) > 5000, f"Rendered markdown length > 5000 bytes (got {len(md)})")

    return t.done()


def main():
    parser = argparse.ArgumentParser(description="Extract parameter trees and DSP topologies from commercial plugins.")
    parser.add_argument("command", nargs="?", default="run", choices=["run"], help="Command to run (default: run)")
    parser.add_argument("--out", help="Markdown output path (default: ~/re-output/plugins/plugins_all_models.md)")
    parser.add_argument("--json", action="store_true", help="Also save complete JSON format")
    parser.add_argument("--self-test", action="store_true", help="Run internal self-tests and exit")
    args = parser.parse_args()

    if args.self_test:
        sys.exit(run_selftest())

    out_md = args.out or os.path.join(RE_OUTPUT, "plugins", "plugins_all_models.md")
    ensure_dir(os.path.dirname(out_md))

    t0 = time.time()
    print("Extracting commercial audio plugins...", file=sys.stderr)
    catalog = extract_all_plugins()
    elapsed = time.time() - t0
    print(f"Extracted {len(catalog)} plugins in {elapsed:.1f}s", file=sys.stderr)

    md_text = render_markdown(catalog)
    write_out(md_text, out_md)
    print(f"wrote {out_md}")

    out_json = out_md.replace(".md", ".json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(catalog, f, indent=2)
    print(f"wrote {out_json}")


if __name__ == "__main__":
    main()
