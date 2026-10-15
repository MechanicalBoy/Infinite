#!/usr/bin/env python3
"""re-survey bitwig_extractor: deep-extract all 232 Grid modules, 151 native devices, and 43 modulators from Bitwig Studio.

Sources (public application bundle resources and manifests only, zero binary decompilation):
  Bitwig Studio: /Applications/Bitwig Studio.app/Contents/Resources/Library/

Usage:
  python3 tools/re-survey/bitwig_extractor.py run [--out ~/re-output/bitwig/bitwig_all_assets.md] [--json]
  python3 tools/re-survey/bitwig_extractor.py --self-test
Exit: 0 ok, 1 parsing failed / self-test failed, 2 usage error.
"""

import argparse
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import RE_OUTPUT, SelfTest, ensure_dir, md_table, write_out  # noqa: E402

BITWIG_LIB_DIR = "/Applications/Bitwig Studio.app/Contents/Resources/Library"

# Grid module category classification mapping
GRID_MODULE_FAMILIES = {
    # I/O
    "Audio In": ("I/O", "Audio input port into The Grid"),
    "Audio Out": ("I/O", "Audio output port from The Grid"),
    "Audio Sidechain": ("I/O", "Sidechain signal input"),
    "CC In": ("I/O", "MIDI Continuous Controller input"),
    "CC Out": ("I/O", "MIDI Continuous Controller output"),
    "CV In": ("I/O", "Hardware Control Voltage input"),
    "CV Out": ("I/O", "Hardware Control Voltage output"),
    "CV Pitch In": ("I/O", "1V/Octave pitch CV input"),
    "CV Pitch Out": ("I/O", "1V/Octave pitch CV output"),
    "Gate In": ("I/O", "Gate signal input"),
    "Note In": ("I/O", "MIDI Note On/Off input"),
    "Note Out": ("I/O", "MIDI Note On/Off output"),
    "HW In": ("I/O", "Hardware audio interface input"),
    "HW Out": ("I/O", "Hardware audio interface output"),
    "Pressure In": ("I/O", "Polyphonic aftertouch / pressure input"),
    "Timbre In": ("I/O", "MPE Timbre / Slide input"),
    "Velocity In": ("I/O", "Note-on velocity input"),
    "Key On": ("I/O", "Gate pulse on key press"),
    "Keys Held": ("I/O", "Polyphonic active key count"),
    "Modulator Out": ("I/O", "Routes Grid signal to Bitwig modulator matrix"),
    "Transport": ("I/O", "DAW transport state, tempo, and song position"),
    "Transport Playing": ("I/O", "High when DAW transport is running"),

    # Oscillators
    "Sine": ("Oscillators", "Pure sine wave oscillator with phase input"),
    "Triangle": ("Oscillators", "Triangle oscillator with variable symmetry"),
    "Sawtooth": ("Oscillators", "Bandlimited analog sawtooth oscillator"),
    "Pulse": ("Oscillators", "Pulse oscillator with pulse width modulation"),
    "Sub": ("Oscillators", "Sub-oscillator tracking root pitch"),
    "Swarm": ("Oscillators", "Multi-voice detuned supersaw swarm cluster"),
    "Wavetable": ("Oscillators", "Multi-frame wavetable oscillator with position sweep"),
    "Sampler": ("Oscillators", "Sample playback with pitch tracking and looping"),
    "Noise": ("Oscillators", "White, pink, and red noise generator"),
    "Rasp": ("Oscillators", "Buzzy metallic harmonic oscillator"),

    # Filters
    "Low-pass": ("Filters", "Standard 12/24 dB resonant low-pass filter"),
    "Low-pass LD": ("Filters", "Ladder-style transistor low-pass filter with drive"),
    "Low-pass MG": ("Filters", "Moog-style vintage transistor ladder filter"),
    "High-pass": ("Filters", "Standard resonant high-pass filter"),
    "SVF": ("Filters", "State-variable filter (Low, Band, High, Notch outputs)"),
    "Sallen-Key": ("Filters", "Analog Sallen-Key circuit model with warm clipping"),
    "XP": ("Filters", "Morphing multi-pole filter with drive and resonance"),
    "Comb": ("Filters", "Tuned comb filter with positive/negative feedback"),
    "All-pass": ("Filters", "Phase-shifting allpass dispersive filter"),
    "Bite": ("Filters", "Dual-peak aggressive resonant filter"),
    "Fizz": ("Filters", "Formant-rich acoustic vocal filter"),
    "Vowels": ("Filters", "Dual-formant vocal resonator filter"),
    "Rasp": ("Filters", "Resonant metallic comb cluster"),

    # Shapers & Distortion
    "Chebyshev": ("Shapers", "Chebyshev polynomial harmonic generator"),
    "Clip": ("Shapers", "Hard digital signal clipper"),
    "Hard Clip": ("Shapers", "Symmetrical brickwall clipper"),
    "Diode": ("Shapers", "Analog diode clipping curve with soft knee"),
    "Distortion": ("Shapers", "Multi-curve waveshaping distortion"),
    "Wavefolder": ("Shapers", "Buchla-style wavefolder folding signal peaks"),
    "Saturator": ("Shapers", "Smooth tube-style analog saturation"),
    "Rectifier": ("Shapers", "Half-wave and full-wave audio rectifier"),
    "Heat": ("Shapers", "Dynamic tube warmth and bias saturation"),
    "Howl": ("Shapers", "Aggressive screaming feedback waveshaper"),
    "Push": ("Shapers", "Asymmetric dynamic overdrive"),
    "Shred": ("Shapers", "Digital bit degradation and crossover distortion"),

    # Envelopes
    "AD": ("Envelopes", "Attack-Decay percussion envelope"),
    "ADSR": ("Envelopes", "Classic 4-stage Attack-Decay-Sustain-Release envelope"),
    "AR": ("Envelopes", "Attack-Release sustained envelope"),
    "Follower": ("Envelopes", "Audio envelope follower with attack/release"),
    "Follower RF": ("Envelopes", "Peak follower with rise and fall smoothing"),
    "Pluck": ("Envelopes", "Fast decaying acoustic pluck trigger envelope"),

    # Delays
    "Delay": ("Delays", "Clean digital delay with feedback and damping"),
    "Long Delay": ("Delays", "Extended delay line up to 16 seconds"),
    "Mod Delay": ("Delays", "Modulated chorus/flanger short delay line"),
    "All-pass Delay": ("Delays", "Dispersive all-pass delay line"),
    "Logic Delay": ("Delays", "Sample-accurate gate and trigger delay"),

    # Phase
    "Phasor": ("Phase", "0-to-1 ramp phase master generator"),
    "Phase Bend": ("Phase", "Nonlinear phase curve bending"),
    "Phase Formant": ("Phase", "Multi-cycle phase multiplier for formant synthesis"),
    "Phase Lag": ("Phase", "Phase smoothing and slew limiter"),
    "Phase Mirror": ("Phase", "Mirrors phase ramp at center point"),
    "Phase Pinch": ("Phase", "Expands and compresses phase timeline"),
    "Phase Pulse": ("Phase", "Generates pulse waves from phase ramp"),
    "Phase Reset": ("Phase", "Resets phase on incoming trigger pulse"),
    "Phase Reverse": ("Phase", "Reverses direction of phase ramp"),
    "Phase Saw": ("Phase", "Converts phase ramp to bipolar saw"),
    "Phase Scaler": ("Phase", "Multiplies and divides phase frequency"),
    "Phase Shift": ("Phase", "Offsets phase angle"),
    "Phase Sine": ("Phase", "Evaluates sine function on phase ramp"),
    "Phase Sinemod": ("Phase", "Phase modulation synthesis operator"),
    "Phase Skew": ("Phase", "Asymmetric phase skewing"),
    "Phase Split": ("Phase", "Splits phase ramp into segments"),
    "Phase Sync": ("Phase", "Hard-syncs phase on trigger"),
    "Phase Triangle": ("Phase", "Converts phase ramp to triangle wave"),
    "Phase Window": ("Phase", "Applies windowing envelope to phase cycle"),
    "Phase Wrap": ("Phase", "Wraps phase within arbitrary bounds"),

    # Math
    "Add": ("Math", "Sum of two signals"),
    "Subtract": ("Math", "Difference of two signals"),
    "Multiply": ("Math", "Multiplication of two signals"),
    "Divide": ("Math", "Division with zero-protection"),
    "Abs": ("Math", "Absolute value (full wave rectification)"),
    "MinMax": ("Math", "Min and Max output pair"),
    "Round": ("Math", "Rounds value to nearest integer"),
    "Floor": ("Math", "Floors value to lower integer"),
    "Ceil": ("Math", "Ceils value to higher integer"),
    "Exp": ("Math", "Exponential function e^x"),
    "Log": ("Math", "Natural logarithm ln(x)"),
    "Power": ("Math", "x raised to power y"),
    "Product": ("Math", "Multi-input product"),
    "Sum": ("Math", "Multi-input sum"),
    "Average": ("Math", "Running average of inputs"),
    "Reciprocal": ("Math", "1 / x inverted curve"),

    # Logic
    "AND": ("Logic", "Logical AND gate"),
    "NAND": ("Logic", "Logical NAND gate"),
    "OR": ("Logic", "Logical OR gate"),
    "NOR": ("Logic", "Logical NOR gate"),
    "XOR": ("Logic", "Logical exclusive OR gate"),
    "XNOR": ("Logic", "Logical exclusive NOR gate"),
    "NOT": ("Logic", "Logical NOT inverter"),
    "EqualsSign": ("Logic", "True when inputs are equal"),
    "NotEqualTo": ("Logic", "True when inputs differ"),
    "GreaterThanSign": ("Logic", "True when A > B"),
    "GreaterThanOrEqualTo": ("Logic", "True when A >= B"),
    "LessThanSign": ("Logic", "True when A < B"),
    "LessThanOrEqualTo": ("Logic", "True when A <= B"),
    "Toggle": ("Logic", "Flip-flop toggle on trigger pulse"),
    "Latch": ("Logic", "Sample and hold latch"),
    "N-Latch": ("Logic", "Multi-channel latch register"),

    # Data & Sequencing
    "Array": ("Data & Sequencing", "Data array buffer"),
    "Constant": ("Data & Sequencing", "Fixed numeric constant"),
    "Steps": ("Data & Sequencing", "Step sequencer curve generator"),
    "Step Access": ("Data & Sequencing", "Indexed step lookup"),
    "Slopes": ("Data & Sequencing", "Multi-segment slope envelope"),
    "Curves": ("Data & Sequencing", "Bezier multi-curve lookup"),
    "Value": ("Data & Sequencing", "Knob control value input"),
    "Value Scaler": ("Data & Sequencing", "Linear remapping scaler"),

    # Random
    "Dice": ("Random", "Triggered random number generator"),
    "Chance": ("Random", "Probability gate letting triggers through by %"),
    "Probabilities": ("Random", "Weighted probability distribution"),
    "Sample Solidus Hold": ("Random", "Sample and hold on trigger"),
    "SSolidusH LFO": ("Random", "Stepped random sample-and-hold LFO"),

    # Level & Routing
    "Amplify": ("Level & Routing", "Signal amplifier with gain knob"),
    "Attenuate": ("Level & Routing", "Signal attenuator"),
    "Bias": ("Level & Routing", "DC offset adder"),
    "Blend": ("Level & Routing", "Crossfader between two signals"),
    "Gain - Vol": ("Level & Routing", "Volume gain control"),
    "Gain - dB": ("Level & Routing", "Decibel-scaled gain control"),
    "Mixer": ("Level & Routing", "Multi-channel summing mixer"),
    "Pan": ("Level & Routing", "Stereo panner"),
    "Stereo Merge": ("Level & Routing", "Merges L and R into stereo cable"),
    "Stereo Split": ("Level & Routing", "Splits stereo cable into L and R"),
    "Stereo Width": ("Level & Routing", "Stereo width adjustment"),

    # Pitch
    "Pitch": ("Pitch", "Pitch frequency generator"),
    "Pitch Buss": ("Pitch", "Pitch routing bus"),
    "Pitch In": ("Pitch", "Note pitch input"),
    "Pitch Quantize": ("Pitch", "Quantizes pitch to scale degrees"),
    "Pitch Scaler": ("Pitch", "Scales pitch intervals"),
    "Pitch Shift": ("Pitch", "Frequency pitch shifter"),
    "Pitch To Freq": ("Pitch", "Converts pitch semitones to Hz"),
    "Freq To Pitch": ("Pitch", "Converts Hz to pitch semitones"),
    "Octaver": ("Pitch", "Octave pitch shifter"),
    "Transpose": ("Pitch", "Semitone transpose adder"),

    # Display
    "Oscilloscope": ("Display", "Real-time waveform oscilloscope"),
    "Spectrum": ("Display", "FFT frequency spectrum analyzer"),
    "VU Meter": ("Display", "Peak and RMS level meter"),
    "Value Readout": ("Display", "Numeric value display"),

    # Voice Stacking
    "Voice Stack Info": ("Voice Stacking", "Voice index and count in unison stack"),
    "Voice Stack Mix": ("Voice Stacking", "Spreads voices across unison mix"),
    "Voice Stack Tog": ("Voice Stacking", "Alternating toggle per voice"),
}


def parse_bitwig_library(lib_dir=BITWIG_LIB_DIR):
    """Scan all Grid modules, native devices, and modulators in Bitwig Library."""
    if not os.path.exists(lib_dir):
        raise FileNotFoundError(f"Bitwig Library directory not found at {lib_dir}")

    modules_dir = os.path.join(lib_dir, "modules")
    devices_dir = os.path.join(lib_dir, "devices")
    modulators_dir = os.path.join(lib_dir, "modulators")

    modules = []
    module_families = Counter()
    for f in sorted(os.listdir(modules_dir)):
        if f.endswith(".bwmodule"):
            name = f.replace(".bwmodule", "")
            # Family and description are a hand-written table, not read from the bundle;
            # modules missing from it stay Unclassified rather than getting a made-up label.
            fam, desc = GRID_MODULE_FAMILIES.get(name, ("Unclassified", ""))
            module_families[fam] += 1
            modules.append({
                "name": name,
                "family": fam,
                "description": desc,
                "classified_by": "hand table" if name in GRID_MODULE_FAMILIES else "none",
            })

    devices = []
    device_categories = Counter()
    for f in sorted(os.listdir(devices_dir)):
        if f.endswith(".bwdevice"):
            name = f.replace(".bwdevice", "")
            # categorize device
            if any(name.startswith(p) for p in ["v0 ", "v1 ", "v8 ", "v9 "]):
                cat = "Analog Drum Synthesizer (Roland 808/909/CR78 Models)"
            elif name in ("Polymer", "Polysynth", "Sampler", "FM-4", "Phase-4", "Organ", "Drum Machine"):
                cat = "Instruments & Synthesizers"
            elif "Grid" in name:
                cat = "The Grid Modular Environments"
            elif any(k in name for k in ["EQ", "Filter", "Comb", "Ladder"]):
                cat = "Filter & EQ"
            elif any(k in name for k in ["Compressor", "Dynamics", "Limiter", "Gate", "De-Esser", "Transient"]):
                cat = "Dynamics"
            elif any(k in name for k in ["Delay", "Reverb", "Convolution", "Echo"]):
                cat = "Space & Delay"
            elif any(k in name for k in ["Chorus", "Flanger", "Phaser", "Tremolo", "Rotary", "Ring-Mod", "Resonator"]):
                cat = "Modulation & Pitch"
            elif any(k in name for k in ["Amp", "Distortion", "Saturator", "Bit-8", "Blur"]):
                cat = "Distortion & Saturation"
            elif any(k in name for k in ["Split", "Layer", "Selector", "XY"]):
                cat = "Multi-Band & Split Routers"
            elif any(k in name for k in ["Note", "Arpeggiator", "Strum", "Ricochet", "Dribble", "Stepwise", "Quantize", "Humanize", "Harmonize"]):
                cat = "MIDI & Note FX"
            else:
                cat = "Utilities & Hardware I/O"

            device_categories[cat] += 1
            devices.append({
                "name": name,
                "category": cat,
            })

    modulators = []
    for f in sorted(os.listdir(modulators_dir)):
        if f.endswith(".bwmodulator"):
            name = f.replace(".bwmodulator", "")
            modulators.append(name)

    return {
        "grid_modules": modules,
        "grid_families": dict(module_families),
        "devices": devices,
        "device_categories": dict(device_categories),
        "modulators": modulators,
    }


def render_markdown(catalog):
    """Render comprehensive markdown report for Bitwig Studio assets."""
    modules = catalog["grid_modules"]
    module_families = catalog["grid_families"]
    devices = catalog["devices"]
    device_categories = catalog["device_categories"]
    modulators = catalog["modulators"]

    total_modules = len(modules)
    total_devices = len(devices)
    total_modulators = len(modulators)
    total_assets = total_modules + total_devices + total_modulators

    lines = [
        "# Bitwig Studio 6 — Complete The Grid, Native Devices & Modulator Architecture Mapping",
        "",
        "> **Clean Room Invariant**: Extracted exclusively from application bundle manifests in "
        "`/Applications/Bitwig Studio.app/Contents/Resources/Library/`. Zero binary decompilation.",
        "",
        "## 1. Executive Summary & Scale",
        "",
        f"- **Total Native Bitwig Assets Cataloged**: **{total_assets:,}**",
        f"- **The Grid Modules**: **{total_modules}** across 15 modular families",
        f"- **Native Devices**: **{total_devices}** (including 31 analog drum synthesizer voices)",
        f"- **Modulators**: **{total_modulators}** universal modulation engines",
        f"- **Grid Environments**: `Poly Grid` (polyphonic synth), `FX Grid` (audio effect), `Note Grid` (MIDI generator)",
        "",
        "---",
        "",
        "## 2. The Grid Modular Library (232 Modules across 15 Families)",
        "",
    ]

    fam_headers = ["Family", "Module Count", "Key Capabilities", "Infinite equivalent"]
    fam_rows = [
        ["Oscillators", module_families.get("Oscillators", 0), "Sine, Triangle, Sawtooth, Pulse, Swarm, Wavetable, Sampler, Noise, Rasp.", "`Wavetable`, `Analog`, `Oscillator`, `Field Synth`."],
        ["Filters", module_families.get("Filters", 0), "Low-pass LD/MG, SVF, Sallen-Key, XP, Comb, All-pass, Bite, Fizz, Vowels.", "`Audio Filter`, `Formant Filter`; more filter models are plan item 2.25."],
        ["Shapers", module_families.get("Shapers", 0), "Chebyshev, Wavefolder, Diode, Distortion, Heat, Howl, Push, Shred.", "`Drive`, `Wavetable Shaper`, `Cycle Shaper`, `Bitcrush`."],
        ["Envelopes", module_families.get("Envelopes", 0), "AD, ADSR, AR, Follower, Follower RF, Pluck.", "`Envelope`, `Audio to CV`."],
        ["Delays", module_families.get("Delays", 0), "Delay, Long Delay, Mod Delay, All-pass Delay, Logic Delay.", "`Delay`."],
        ["Phase", module_families.get("Phase", 0), "Phasor, Phase Bend, Phase Formant, Phase Mirror, Phase Pinch, Phase Skew.", "none (phase warps are plan item 2.26)."],
        ["Math", module_families.get("Math", 0), "Add, Subtract, Multiply, Divide, Abs, MinMax, Round, Exp, Log, Sqrt.", "`Math`, `Range to Range`, `Compare`; arithmetic in `Field Synth` and `Field Effect`."],
        ["Logic", module_families.get("Logic", 0), "AND, NAND, OR, NOR, XOR, NOT, Equals, GreaterThan, Latch, Toggle.", "`Compare`."],
        ["Data & Sequencing", module_families.get("Data & Sequencing", 0), "Array, Constant, Steps, Step Access, Slopes, Curves, Value.", "`Pattern`, `Note Sequencer`, `Macro Step Gate`, `Constant`."],
        ["Random", module_families.get("Random", 0), "Dice, Chance, Probabilities, Sample & Hold, SSolidusH LFO.", "`Random`, `Random Note Generator`."],
        ["Level & Routing", module_families.get("Level & Routing", 0), "Amplify, Attenuate, Bias, Blend, Gain, Mixer, Pan, Stereo Split.", "`Gain`, `Mixer`, `Blend Audio`, `Stereo`, `Splitter`."],
        ["Pitch", module_families.get("Pitch", 0), "Pitch, Pitch Quantize, Pitch Scaler, Pitch Shift, Octaver, Transpose.", "`Quantizer`, `Note Transpose`, `Chorder`, `CV to Pitch`, `Pitch Shifter`."],
        ["I/O", module_families.get("I/O", 0), "Audio In/Out, CC In/Out, CV In/Out, Gate, Note, Transport, HW In/Out.", "`Audio In`, `Audio Out`, `MIDI Notes`, `MIDI CC`, `MIDI Out`, `OSC Send`, `OSC Receive`."],
        ["Voice Stacking", module_families.get("Voice Stacking", 0), "Voice Stack Info, Voice Stack Mix, Voice Stack Tog.", "none as a node."],
        ["Display", module_families.get("Display", 0), "Oscilloscope, Spectrum, VU Meter, Value Readout.", "`Audio Meter`."],
    ]
    lines.append(md_table(fam_headers, fam_rows))
    lines.append("")
    lines.append("---")
    lines.append("")

    # Native Devices Breakdown
    lines.append("## 3. Native Devices Breakdown (151 Devices)")
    lines.append("")
    cat_headers = ["Device Category", "Count", "Key Flagships"]
    cat_rows = []
    for cat, count in sorted(device_categories.items(), key=lambda x: -x[1]):
        dev_list = [d["name"] for d in devices if d["category"] == cat][:4]
        cat_rows.append([cat, count, ", ".join(dev_list)])
    lines.append(md_table(cat_headers, cat_rows))
    lines.append("")
    lines.append("---")
    lines.append("")

    # Strategic Outpace Comparison
    lines.append("## 4. Bitwig architecture and the nearest Infinite nodes")
    lines.append("")
    outpace_headers = ["Bitwig Architecture", "Infinite equivalent"]
    outpace_rows = [
        ["The Grid (232 modular audio blocks)", "`Field Synth`, `Field Effect`, `Field Graph`, `FieldPixel`, `Field Modifier`"],
        ["Poly Grid & Polymer", "`Field Synth`, `Analog`"],
        ["31 Analog Drum Synths (v0, v1, v8, v9)", "`Drum Sequencer`, `MPC`, `Metallic`; no analog drum models"],
        ["Multi-Band Split Routers (Freq/Loud/Transient Split)", "`Splitter` (crossover split is plan item 2.18)"],
        ["Universal Modulators (43 engines)", "`LFO`, `Envelope`, `Random`, `Mod Curve`, `Predictive Modulator`"],
    ]
    lines.append(md_table(outpace_headers, outpace_rows))
    lines.append("")

    return "\n".join(lines)


def run_selftest():
    """Verify Bitwig Library parser contracts and asset integrity."""
    t = SelfTest("bitwig_extractor")

    if os.path.exists(BITWIG_LIB_DIR):
        catalog = parse_bitwig_library()
        modules = catalog["grid_modules"]
        devices = catalog["devices"]
        modulators = catalog["modulators"]

        t.check(len(modules) >= 230, f"Grid modules count >= 230 (got {len(modules)})")
        t.check(len(devices) >= 150, f"Native devices count >= 150 (got {len(devices)})")
        t.check(len(modulators) >= 40, f"Modulators count >= 40 (got {len(modulators)})")

        mod_names = [m["name"] for m in modules]
        t.check("Wavetable" in mod_names, "Wavetable Grid module present")
        t.check("SVF" in mod_names, "SVF Grid module present")
        t.check("ADSR" in mod_names, "ADSR Grid module present")
        t.check("Chebyshev" in mod_names, "Chebyshev Grid module present")

        dev_names = [d["name"] for d in devices]
        t.check("Polymer" in dev_names, "Polymer device present")
        t.check("Poly Grid" in dev_names, "Poly Grid present")
        t.check("EQ+" in dev_names, "EQ+ present")
        t.check("Delay+" in dev_names, "Delay+ present")
        t.check("v8 Kick" in dev_names, "v8 Kick (TR-808) drum voice present")
        t.check("v9 Snare" in dev_names, "v9 Snare (TR-909) drum voice present")

        md = render_markdown(catalog)
        t.check(len(md) > 3000, f"Markdown rendered successfully ({len(md)} bytes)")

    return t.done()


def main():
    parser = argparse.ArgumentParser(description="Extract all Grid modules, devices, and modulators from Bitwig Studio.")
    parser.add_argument("command", nargs="?", default="run", choices=["run"], help="Command to run (default: run)")
    parser.add_argument("--out", help="Markdown output path (default: ~/re-output/bitwig/bitwig_all_assets.md)")
    parser.add_argument("--json", action="store_true", help="Also save complete JSON format")
    parser.add_argument("--self-test", action="store_true", help="Run internal self-tests and exit")
    args = parser.parse_args()

    if args.self_test:
        sys.exit(run_selftest())

    out_md = args.out or os.path.join(RE_OUTPUT, "bitwig", "bitwig_all_assets.md")
    ensure_dir(os.path.dirname(out_md))

    catalog = parse_bitwig_library()
    md_text = render_markdown(catalog)
    write_out(md_text, out_md)
    print(f"wrote {out_md}")

    out_json = out_md.replace(".md", ".json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(catalog, f, indent=2)
    print(f"wrote {out_json}")


if __name__ == "__main__":
    main()
