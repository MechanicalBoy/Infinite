#!/usr/bin/env python3
"""Cross-check what a node's DSP does to a param against what its knob/slider
tells the user is possible - the two get written independently (a knob call
in src/main.cpp, a clamp or formula in the node's own .cpp/.h) and nothing
enforces that they agree once written.

This exists because of two real, shipped bugs in AnalogNode: the "pw" knob
was disabled unless a waveform was Square even though the DSP secretly only
ever wired it to osc1 (so it lied in *two* directions - looked inert when it
wasn't, and looked live for osc2 when it was actually a no-op); and the "fm"
knob was declared and documented 0..1 while the DSP clamped its consumer to
0..2, a full octave of dead, unreachable headroom nobody could ever dial in.
Neither is a crash, a save/load bug, or a modulation-registration gap - the
existing sweeps (audio-node-sweep, node-param-audit) don't look at *numeric
agreement* between a control's declared range and what its own DSP consumer
actually does with that range. This script automates the mechanical half of
that (range agreement); the SKILL.md covers the half that needs a reader.

    python3 scripts/audit_param_truth.py [--node NodeName]

Finds, per file pair (a node's UI draw code in src/main.cpp, its DSP in
src/nodes/*.{h,cpp}):

  1. RANGE MISMATCH - a knob/slider declares [lo, hi] but the DSP-side
     std::clamp on the same mailbox param (traced Push(kX, p.field) ->
     std::clamp(mMailbox.SmoothedValue(kX), loD, hiD)) uses different
     literal bounds. Reported both directions:
       - DSP narrower than the knob -> the knob can dial in a value the DSP
         silently clips (an audible lie: the knob visibly moves, the sound
         stops changing).
       - DSP wider than the knob -> dead headroom nobody can reach (the
         pre-fix "fm" bug: not audibly wrong, just a knob whose declared
         range doesn't match what its own consumer claims to accept).

  2. UNTRACEABLE CLAMP - a clamp on a mailbox param whose bounds aren't bare
     float literals (e.g. `20.0f, (float)mSampleRate * 0.48f`) or whose value
     passes through an affine transform before the clamp (e.g.
     `0.5f + SmoothedValue(...) * 8.0f`). Not a defect by itself - most of
     these are deliberate safety clamps (Nyquist guards) or intentional
     tapers - but the script can't verify them, so they're listed for a
     human to eyeball rather than silently skipped.

Static analysis only (regex over source, like audit_node_params.py) - no
build, no launch.
"""

import argparse
import os
import re
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN_CPP = os.path.join(ROOT, "src", "main.cpp")
NODES_DIR = os.path.join(ROOT, "src", "nodes")

# `mMailbox.Push(kFoo, p.field);` or `mMailbox.Push(kFoo, node.field);` ->
# paramId "kFoo" consumes struct field "field" (the params-struct variable
# name isn't standardized across nodes - AnalogSynthCore uses `p`,
# MetallicNode uses `node`).
PUSH_RE = re.compile(r"mMailbox\.Push\(\s*(\w+)\s*,\s*\w+\.(\w+)\s*\)")

# `std::clamp(mMailbox.SmoothedValue(kFoo), LO, HI)` - LO/HI captured raw;
# only kept as a real finding when both are bare numeric literals.
CLAMP_RE = re.compile(
    r"std::clamp\(\s*mMailbox\.SmoothedValue\(\s*(\w+)\s*\)\s*,\s*([^,]+?)\s*,\s*([^)]+?)\s*\)"
)
# Same, but the smoothed value passes through an affine transform first -
# still traced back to a field, but not range-compared (see UNTRACEABLE).
CLAMP_AFFINE_RE = re.compile(
    r"std::clamp\(\s*[^,()]*mMailbox\.SmoothedValue\(\s*(\w+)\s*\)[^,()]*,\s*([^,]+?)\s*,\s*([^)]+?)\s*\)"
)

NUMERIC_RE = re.compile(r"^-?\d+(\.\d+)?f?$")

# Knob/slider call families that carry (label, &n->field, lo, hi, ...) in that
# order - same families node-param-audit already knows about, minus the
# widgets with no declared range (checkbox, dropdown, colour).
RANGED_WIDGET_RE = re.compile(
    r'(?:row\.Knob|row\.Fader|row2\.Knob|ModKnob|ModSlider|AudioSlider)\(\s*'
    r'"([^"]+)"\s*,\s*&?\w*->(\w+)\s*,\s*([^,]+?)\s*,\s*([^,]+?)\s*,'
)
# DropdownKnob's *second* half is a ranged knob too: (..., "label", &n->field, lo, hi, ...)
DROPDOWNKNOB_RE = re.compile(
    r'DropdownKnob\([^;]*?,\s*"([^"]+)"\s*,\s*&n->(\w+)\s*,\s*([^,]+?)\s*,\s*([^,]+?)\s*,',
    re.DOTALL,
)


def is_numeric(tok):
    return bool(NUMERIC_RE.match(tok.strip()))


def to_float(tok):
    return float(tok.strip().rstrip("f"))


def find_field_pushes(text):
    """paramId -> struct field name, from every PushParams in this file."""
    return {m.group(1): m.group(2) for m in PUSH_RE.finditer(text)}


def find_dsp_clamps(path, text):
    """field name -> (lo, hi, traceable, line) for every mailbox clamp."""
    field_of = find_field_pushes(text)
    out = []
    for m in CLAMP_RE.finditer(text):
        param_id, lo_raw, hi_raw = m.group(1), m.group(2), m.group(3)
        field = field_of.get(param_id)
        if not field:
            continue
        line = text.count("\n", 0, m.start()) + 1
        traceable = is_numeric(lo_raw) and is_numeric(hi_raw)
        out.append((field, lo_raw.strip(), hi_raw.strip(), traceable, path, line))
    # Anything CLAMP_RE missed because of a pre-clamp transform still shows
    # up via the affine pattern; dedupe by (field, line).
    seen = {(f, ln) for f, *_, ln in out}
    for m in CLAMP_AFFINE_RE.finditer(text):
        param_id, lo_raw, hi_raw = m.group(1), m.group(2), m.group(3)
        field = field_of.get(param_id)
        if not field:
            continue
        line = text.count("\n", 0, m.start()) + 1
        if (field, line) in seen:
            continue
        out.append((field, lo_raw.strip(), hi_raw.strip(), False, path, line))
    return out


def find_ui_ranges(text):
    """struct field name -> list of (label, lo, hi, line) from every knob call
    found in this text (caller passes a single node's Draw*Body text, not the
    whole file - see `draw_bodies_by_class` - so unrelated nodes that happen
    to share a field name like "detune" or "mix" never collide)."""
    out = defaultdict(list)
    for regex in (RANGED_WIDGET_RE, DROPDOWNKNOB_RE):
        for m in regex.finditer(text):
            label, field, lo_raw, hi_raw = m.group(1), m.group(2), m.group(3), m.group(4)
            line = text.count("\n", 0, m.start()) + 1
            out[field].append((label, lo_raw.strip(), hi_raw.strip(), line))
    return out


# --- node class -> Draw*Body dispatch, same technique audit_node_params.py
# uses: a `dynamic_cast<Klass*>` immediately followed (within a few lines) by
# a call to its Draw function. Reused here so a DSP file's fields are only
# ever compared against *that node's own* knob calls, never another node's.
def function_bodies(text):
    out = {}
    for m in re.finditer(r"\n   (?:void|bool)\s+(Draw\w*(?:Body|Params))\s*\(", text):
        name = m.group(1)
        i = text.find("{", m.end())
        if i < 0:
            continue
        depth, j = 0, i
        while j < len(text):
            if text[j] == "{":
                depth += 1
            elif text[j] == "}":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        out[name] = text[i:j]
    return out


def dispatch_map(text):
    out = {}
    lines = text.split("\n")
    for i, line in enumerate(lines):
        m = re.search(r"dynamic_cast<(\w+)\s*\*>", line)
        if not m:
            continue
        klass = m.group(1)
        window = "\n".join(lines[i:i + 4])
        for fn in re.findall(r"\b(Draw\w*(?:Body|Params))\s*\(", window):
            out.setdefault(klass, set()).add(fn)
    return out


def guess_node_class(dsp_path):
    """DSP filename -> best-guess node class name to look up in dispatch_map.
    Best-effort: AnalogSynthCore.h -> AnalogNode, MetallicNode.cpp -> MetallicNode."""
    base = os.path.splitext(os.path.basename(dsp_path))[0]
    if base.endswith("SynthCore"):
        return base[: -len("SynthCore")] + "Node"
    if base.endswith("Node"):
        return base
    return base + "Node"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--node", help="Only report fields whose name contains this substring")
    args = ap.parse_args()

    main_text = open(MAIN_CPP, encoding="utf-8", errors="replace").read()
    bodies = function_bodies(main_text)
    dispatch = dispatch_map(main_text)

    dsp_clamps = []
    for fname in sorted(os.listdir(NODES_DIR)):
        if not (fname.endswith(".h") or fname.endswith(".cpp")):
            continue
        path = os.path.join(NODES_DIR, fname)
        text = open(path, encoding="utf-8", errors="replace").read()
        if "mMailbox.Push(" not in text or "std::clamp(mMailbox.SmoothedValue" not in text:
            continue
        for clamp in find_dsp_clamps(os.path.relpath(path, ROOT), text):
            dsp_clamps.append((fname,) + clamp)

    mismatches = []
    untraceable = []
    unscoped_files = set()
    for fname, field, lo_raw, hi_raw, traceable, path, line in dsp_clamps:
        if args.node and args.node.lower() not in field.lower():
            continue

        klass = guess_node_class(fname)
        fn_names = dispatch.get(klass)
        if not fn_names:
            unscoped_files.add((fname, klass))
            continue
        scope_text = "\n".join(bodies[fn] for fn in fn_names if fn in bodies)
        ui_ranges = find_ui_ranges(scope_text)

        if not traceable:
            untraceable.append((field, lo_raw, hi_raw, path, line))
            continue
        dsp_lo, dsp_hi = to_float(lo_raw), to_float(hi_raw)
        for label, ui_lo_raw, ui_hi_raw, ui_line in ui_ranges.get(field, []):
            if not (is_numeric(ui_lo_raw) and is_numeric(ui_hi_raw)):
                continue
            ui_lo, ui_hi = to_float(ui_lo_raw), to_float(ui_hi_raw)
            if abs(ui_lo - dsp_lo) > 1e-6 or abs(ui_hi - dsp_hi) > 1e-6:
                direction = "DSP NARROWER (knob can dial in values the DSP clips!)" \
                    if (dsp_lo > ui_lo or dsp_hi < ui_hi) else \
                    "DSP WIDER (dead headroom the knob can never reach)"
                mismatches.append((field, label, ui_lo, ui_hi, dsp_lo, dsp_hi, direction, path, line, ui_line))

    print(f"Scanned {len(dsp_clamps)} mailbox clamp(s) across src/nodes/*.{{h,cpp}}\n")

    if unscoped_files:
        print("(Could not map to a Draw*Body - skipped, verify these by hand:")
        for fname, klass in sorted(unscoped_files):
            print(f"    {fname} -> guessed class `{klass}`, not found in main.cpp's dispatch")
        print(")\n")

    if mismatches:
        print(f"=== {len(mismatches)} RANGE MISMATCH(ES) ===\n")
        for field, label, ui_lo, ui_hi, dsp_lo, dsp_hi, direction, path, line, ui_line in mismatches:
            print(f'  "{label}" (field `{field}`)')
            print(f"    UI  (src/main.cpp:{ui_line}):  {ui_lo:g}..{ui_hi:g}")
            print(f"    DSP ({path}:{line}):  {dsp_lo:g}..{dsp_hi:g}")
            print(f"    -> {direction}\n")
    else:
        print("No numeric range mismatches found.\n")

    if untraceable:
        print(f"=== {len(untraceable)} clamp(s) not mechanically comparable - eyeball these ===\n")
        for field, lo_raw, hi_raw, path, line in untraceable:
            print(f"  `{field}` clamped to ({lo_raw}, {hi_raw}) at {path}:{line}")
        print()

    return 1 if mismatches else 0


if __name__ == "__main__":
    sys.exit(main())
