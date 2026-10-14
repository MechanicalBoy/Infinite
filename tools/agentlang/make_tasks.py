#!/usr/bin/env python3
"""Generate tools/agentlang/tasks/: tasks.json, <id>.inf start patches (tweak tasks), <id>.solution.inf.

The one place the 30 tasks are written down. Wire tags and slot numbers are resolved from the node
facts, so a solution cannot name a slot that does not exist. Keys come from the repo: corpus .inf
files (keys_seen.json) and src/core/FilterDefs.cpp (every uXxx key of an effect/colour filter).
Run once; the output is then frozen (tasks/FROZEN.sha256) and this script is not run again.
Usage: python3 tools/agentlang/make_tasks.py     last stdout line is JSON.
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import facts  # noqa: E402

F = facts.load()
OUT = os.path.join(HERE, "tasks")
EMPTY = ""


class N:
    def __init__(self, type_, id_, **params):
        self.type, self.id, self.params = type_, id_, params


def tag_of(key, val):
    if isinstance(val, bool):
        return "b"
    if isinstance(val, int):
        return "i"
    if isinstance(val, float):
        return "f"
    return "i" if key in OPTION_KEYS else "s"


OPTION_KEYS = {"shapeType", "waveform"}   # dropdowns written by option name
INT_KEYS = {"rangeLow", "rangeHigh"}


def render(nodes, wires):
    """nodes: list of N; wires: [(dstId, slotName, srcId)] -> .inf text."""
    ids = {n.id: i + 1 for i, n in enumerate(nodes)}
    out = ["infinite-patch 1"]
    for i, n in enumerate(nodes, 1):
        tf = F.type(n.type)
        assert tf, f"unknown type {n.type}"
        out += [f"node {i} {tf.category} {n.type}", f"  id {n.id}"]
        for k, v in n.params.items():
            if k in INT_KEYS and isinstance(v, float):
                v = int(v)
            out.append(f"  {tag_of(k, v)} {k} {v}")
        out.append("end")
    by = {n.id: n for n in nodes}
    for dst, slot, src in wires:
        dt, st = F.type(by[dst].type), F.type(by[src].type)
        si = F.slot_index(dt.name, slot)
        assert si is not None, f"{dt.name} has no slot {slot}"
        kind = dt.inputs[si][1]
        assert kind == st.outputs[0][1], f"{src}->{dst}.{slot}: {st.outputs[0][1]} into {kind}"
        out.append(f"{facts.wire_tag(kind)} {dst} {slot} {src}")
    return "\n".join(out) + "\n"


def edge(dsttype, slot, srctype):
    dt, st = F.type(dsttype), F.type(srctype)
    si = F.slot_index(dt.name, slot)
    assert si is not None, (dsttype, slot)
    return [facts.wire_tag(dt.inputs[si][1]), dsttype, slot, srctype]


def P(type_, key, value=None, tol=0.0, text=None, contains=None):
    d = {"kind": "params", "type": type_, "key": key}
    if value is not None:
        d["value"], d["tol"] = value, tol
    if text is not None:
        d["text"] = text
    if contains is not None:
        d["contains"] = contains
    return d


def T(*types):
    return {"kind": "types_present", "types": list(types)}


def E(*edges):
    return {"kind": "edges", "edges": [edge(*e) for e in edges]}


def NOEDGE(*edges):
    return {"kind": "edges", "edges": [edge(*e) for e in edges], "absent": True}


NOERR = {"kind": "no_errors"}


def S(stat, lo=None, hi=None, t=0):
    d = {"kind": "frame_stats", "t": t, "seed": None, "stat": stat}
    if lo is not None:
        d["min"] = lo
    if hi is not None:
        d["max"] = hi
    return d


def OUT_(img):  # Output node fed by an image node
    return N("Output", "out")


tasks = []


def task(id_, split, kind, goal, sol, oracle, start=None):
    tasks.append({"id": id_, "split": split, "kind": kind, "goal_text": goal,
                  "start_patch": f"tools/agentlang/tasks/{id_}.inf" if start else None,
                  "oracle": oracle, "_sol": sol, "_start": start})


# ---------------------------------------------------------------- build (empty start)
task("b01", "dev", "build", "Make a picture: a star shape shown on the output.",
     ([N("Shape", "shape", shapeType="Star"), N("Output", "out")], [("out", "in", "shape")]),
     [T("Shape", "Output"), E(("Output", "in", "Shape")), P("Shape", "shapeType", text="Star"), NOERR,
      S("black_percent", hi=0.999)])
task("b02", "dev", "build", "Make a shape, blur it with a gaussian blur of radius 6, and show it on the output.",
     ([N("Shape", "shape"), N("gaussianblur", "blur", uRadius=6.0), N("Output", "out")],
      [("blur", "input", "shape"), ("out", "in", "blur")]),
     [T("Shape", "gaussianblur", "Output"), E(("gaussianblur", "input", "Shape"), ("Output", "in", "gaussianblur")),
      P("gaussianblur", "uRadius", 6, 0.5), NOERR])
task("b03", "dev", "build", "Make a shape, add bloom, then a vignette with amount 0.8, and show it on the output.",
     ([N("Shape", "shape"), N("bloom", "glow"), N("vignette", "vig", uAmount=0.8), N("Output", "out")],
      [("glow", "input", "shape"), ("vig", "input", "glow"), ("out", "in", "vig")]),
     [T("Shape", "bloom", "vignette", "Output"),
      E(("bloom", "input", "Shape"), ("vignette", "input", "bloom"), ("Output", "in", "vignette")),
      P("vignette", "uAmount", 0.8, 0.05), NOERR])
task("b04", "dev", "build", "Blend two different shapes together at 50 percent and show the result on the output.",
     ([N("Shape", "a"), N("Shape", "b"), N("Blend", "mix", mix=0.5), N("Output", "out")],
      [("mix", "input", "a"), ("mix", "input_2", "b"), ("out", "in", "mix")]),
     [T("Shape", "Blend", "Output"), {"kind": "type_count", "type": "Shape", "op": "==", "n": 2},
      E(("Blend", "input", "Shape"), ("Blend", "input_2", "Shape"), ("Output", "in", "Blend")),
      P("Blend", "mix", 0.5, 0.05), NOERR])
task("b05", "dev", "build", "Play a sine tone at 440 Hz to the speakers.",
     ([N("Oscillator", "osc", frequency=440.0, waveform="Sine"), N("Audio Out", "speakers")],
      [("speakers", "audio", "osc")]),
     [T("Oscillator", "Audio Out"), E(("Audio Out", "audio", "Oscillator")),
      P("Oscillator", "frequency", 440, 1), P("Oscillator", "waveform", text="Sine"), NOERR])
task("b06", "dev", "build", "Random notes played by a wavetable synth, through a reverb with mix 0.3, to the speakers.",
     ([N("Random Note Generator", "notes"), N("Wavetable", "synth"), N("Reverb", "verb", mix=0.3),
       N("Audio Out", "speakers")],
      [("synth", "notes", "notes"), ("verb", "audio", "synth"), ("speakers", "audio", "verb")]),
     [T("Random Note Generator", "Wavetable", "Reverb", "Audio Out"),
      E(("Wavetable", "notes", "Random Note Generator"), ("Reverb", "audio", "Wavetable"),
        ("Audio Out", "audio", "Reverb")),
      P("Reverb", "mix", 0.3, 0.03), NOERR])
task("b07", "dev", "build", "Render a 3D sphere with a camera whose field of view is 50 degrees, and show it on the output.",
     ([N("Sphere", "ball"), N("Camera", "cam"), N("Render 3D", "r3d", fov=50.0), N("Output", "out")],
      [("r3d", "geo_a", "ball"), ("r3d", "camera", "cam"), ("out", "in", "r3d")]),
     [T("Sphere", "Camera", "Render 3D", "Output"),
      E(("Render 3D", "geo_a", "Sphere"), ("Render 3D", "camera", "Camera"), ("Output", "in", "Render 3D")),
      P("Render 3D", "fov", 50, 1), NOERR])
task("b08", "held-out", "build", "Make a circle, run it through a kaleidoscope with 8 segments, and show it on the output.",
     ([N("Circle", "disc"), N("kaleidoscope", "kal", uSegments=8.0), N("Output", "out")],
      [("kal", "input", "disc"), ("out", "in", "kal")]),
     [T("Circle", "kaleidoscope", "Output"),
      E(("kaleidoscope", "input", "Circle"), ("Output", "in", "kaleidoscope")),
      P("kaleidoscope", "uSegments", 8, 0.5), NOERR])
task("b09", "held-out", "build", "Play an oscillator at 220 Hz through a delay with feedback 0.4 and time 250 ms to the speakers.",
     ([N("Oscillator", "osc", frequency=220.0), N("Delay", "echo", feedback=0.4, timeMs=250.0),
       N("Audio Out", "speakers")],
      [("echo", "audio", "osc"), ("speakers", "audio", "echo")]),
     [T("Oscillator", "Delay", "Audio Out"),
      E(("Delay", "audio", "Oscillator"), ("Audio Out", "audio", "Delay")),
      P("Oscillator", "frequency", 220, 1), P("Delay", "feedback", 0.4, 0.03), P("Delay", "timeMs", 250, 5), NOERR])
task("b10", "held-out", "build", "Join a cube and a torus into one 3D scene, render it, and show it on the output.",
     ([N("Cube", "box"), N("Torus", "ring"), N("Join Geometry", "join"), N("Render 3D", "r3d"), N("Output", "out")],
      [("join", "geo_a", "box"), ("join", "geo_b", "ring"), ("r3d", "geo_a", "join"), ("out", "in", "r3d")]),
     [T("Cube", "Torus", "Join Geometry", "Render 3D", "Output"),
      E(("Join Geometry", "geo_a", "Cube"), ("Join Geometry", "geo_b", "Torus"),
        ("Render 3D", "geo_a", "Join Geometry"), ("Output", "in", "Render 3D")), NOERR])

# ---------------------------------------------------------------- tweak (start patch shipped)
SHAPE_OUT = ([N("Shape", "shape", sizeX=0.6, shapeType="Star"), N("Output", "out")], [("out", "in", "shape")])
SYNTH = ([N("Random Note Generator", "notes"), N("Wavetable", "synth"), N("Audio Out", "speakers"),
          N("Shape", "picture"), N("Output", "out")],
         [("synth", "notes", "notes"), ("speakers", "audio", "synth"), ("out", "in", "picture")])

task("t01", "dev", "tweak", "Make the shape bigger: set its sizeX to 0.9.",
     ([N("Shape", "shape", sizeX=0.9, shapeType="Star"), N("Output", "out")], SHAPE_OUT[1]), [T("Shape", "Output"), E(("Output", "in", "Shape")), P("Shape", "sizeX", 0.9, 0.02), NOERR],
     start=SHAPE_OUT)
task("t02", "dev", "tweak", "Put a gaussian blur of radius 3 between the shape and the output.",
     ([N("Shape", "shape", sizeX=0.6, shapeType="Star"), N("gaussianblur", "blur", uRadius=3.0), N("Output", "out")],
      [("blur", "input", "shape"), ("out", "in", "blur")]),
     [T("Shape", "gaussianblur", "Output"), E(("gaussianblur", "input", "Shape"), ("Output", "in", "gaussianblur")),
      NOEDGE(("Output", "in", "Shape")), P("gaussianblur", "uRadius", 3, 0.3), NOERR], start=SHAPE_OUT)
task("t03", "dev", "tweak", "Put a reverb with mix 0.4 between the synth and the speakers.",
     ([N("Random Note Generator", "notes"), N("Wavetable", "synth"), N("Reverb", "verb", mix=0.4),
       N("Audio Out", "speakers"), N("Shape", "picture"), N("Output", "out")],
      [("synth", "notes", "notes"), ("verb", "audio", "synth"), ("speakers", "audio", "verb"),
       ("out", "in", "picture")]),
     [T("Wavetable", "Reverb", "Audio Out"),
      E(("Reverb", "audio", "Wavetable"), ("Audio Out", "audio", "Reverb")),
      NOEDGE(("Audio Out", "audio", "Wavetable")), P("Reverb", "mix", 0.4, 0.03), NOERR], start=SYNTH)
task("t04", "dev", "tweak", "Remove the picture (the shape and the output) so only the sound is left.",
     ([N("Random Note Generator", "notes"), N("Wavetable", "synth"), N("Audio Out", "speakers")],
      [("synth", "notes", "notes"), ("speakers", "audio", "synth")]),
     [T("Random Note Generator", "Wavetable", "Audio Out"), {"kind": "types_absent", "types": ["Shape", "Output"]},
      E(("Audio Out", "audio", "Wavetable")), NOERR], start=SYNTH)
BLOOM = ([N("Shape", "shape", shapeType="Star"), N("bloom", "glow"), N("Output", "out")],
         [("glow", "input", "shape"), ("out", "in", "glow")])
task("t05", "dev", "tweak", "Make the bloom stronger: set its intensity to 2.5 and its threshold to 0.3.",
     ([N("Shape", "shape", shapeType="Star"), N("bloom", "glow", uIntensity=2.5, uThreshold=0.3), N("Output", "out")],
      BLOOM[1]),
     [T("Shape", "bloom", "Output"), E(("bloom", "input", "Shape"), ("Output", "in", "bloom")),
      P("bloom", "uIntensity", 2.5, 0.1), P("bloom", "uThreshold", 0.3, 0.03), NOERR], start=BLOOM)
TWO = ([N("Shape", "left"), N("Shape", "right"), N("Blend", "mix", mix=0.5), N("Output", "out")],
       [("mix", "input", "left"), ("mix", "input_2", "right"), ("out", "in", "mix")])
task("t06", "dev", "tweak", "Replace the shape named right with a circle, and set the blend mix to 0.8.",
     ([N("Shape", "left"), N("Circle", "disc"), N("Blend", "mix", mix=0.8), N("Output", "out")],
      [("mix", "input", "left"), ("mix", "input_2", "disc"), ("out", "in", "mix")]),
     [T("Shape", "Circle", "Blend", "Output"), {"kind": "type_count", "type": "Shape", "op": "==", "n": 1},
      E(("Blend", "input", "Shape"), ("Blend", "input_2", "Circle"), ("Output", "in", "Blend")),
      P("Blend", "mix", 0.8, 0.05), NOERR], start=TWO)
OSC = ([N("Oscillator", "osc", frequency=1000.0, waveform="Sine", volume=0.5), N("Audio Out", "speakers")],
       [("speakers", "audio", "osc")])
task("t07", "dev", "tweak", "Lower the oscillator to 220 Hz and set its volume to 0.3.",
     ([N("Oscillator", "osc", frequency=220.0, waveform="Sine", volume=0.3), N("Audio Out", "speakers")], OSC[1]),
     [T("Oscillator", "Audio Out"), E(("Audio Out", "audio", "Oscillator")),
      P("Oscillator", "frequency", 220, 1), P("Oscillator", "volume", 0.3, 0.02), NOERR], start=OSC)
task("t08", "held-out", "tweak", "Add a vignette with amount 0.9 between the shape and the output.",
     ([N("Shape", "shape", sizeX=0.6, shapeType="Star"), N("vignette", "vig", uAmount=0.9), N("Output", "out")],
      [("vig", "input", "shape"), ("out", "in", "vig")]),
     [T("Shape", "vignette", "Output"), E(("vignette", "input", "Shape"), ("Output", "in", "vignette")),
      NOEDGE(("Output", "in", "Shape")), P("vignette", "uAmount", 0.9, 0.05), NOERR], start=SHAPE_OUT)
task("t09", "held-out", "tweak", "Set the synth volume to 0.5 and the lowest note of the random notes to 60.",
     ([N("Random Note Generator", "notes", rangeLow=60), N("Wavetable", "synth", volume=0.5), N("Audio Out", "speakers"),
       N("Shape", "picture"), N("Output", "out")], SYNTH[1]),
     [T("Random Note Generator", "Wavetable", "Audio Out"), E(("Audio Out", "audio", "Wavetable")),
      P("Wavetable", "volume", 0.5, 0.03), P("Random Note Generator", "rangeLow", 60, 0), NOERR], start=SYNTH)
CHAIN = ([N("Shape", "shape"), N("Fit", "fit"), N("Output", "out")], [("fit", "input", "shape"), ("out", "in", "fit")])
task("t10", "held-out", "tweak", "Remove the fit node and connect the shape straight to the output.",
     ([N("Shape", "shape"), N("Output", "out")], [("out", "in", "shape")]),
     [T("Shape", "Output"), {"kind": "types_absent", "types": ["Fit"]}, E(("Output", "in", "Shape")), NOERR],
     start=CHAIN)

# ---------------------------------------------------------------- Field (empty start)
def field_task(id_, split, goal, nodes, wires, ftype, code, contains, extra=()):
    nodes = [N(n.type, n.id, **({"code": code} if n.type == ftype else n.params)) for n in nodes]
    oracle = [T(*sorted({n.type for n in nodes})), P(ftype, "code", contains=contains), NOERR] + list(extra)
    oracle += [E(*[tuple(edge_of(nodes, w)) for w in wires])]
    task(id_, split, "field", goal, (nodes, wires), oracle)


def edge_of(nodes, w):
    by = {n.id: n.type for n in nodes}
    return by[w[0]], w[1], by[w[2]]


field_task("f01", "dev", "Fill the picture with a horizontal gradient: black on the left, white on the right.",
           [N("FieldPixel", "fp"), N("Output", "out")], [("out", "in", "fp")], "FieldPixel",
           "col = vec3(uv.x, uv.x, uv.x);", [r"uv\.x"], [S("min_luma", hi=0.15), S("max_luma", lo=0.7)])
field_task("f02", "dev", "Fill the picture with a black and white checkerboard of 8 by 8 squares.",
           [N("FieldPixel", "fp"), N("Output", "out")], [("out", "in", "fp")], "FieldPixel",
           "c = fmod(floor(uv.x * 8.0) + floor(uv.y * 8.0), 2.0); col = vec3(c, c, c);",
           [r"floor", r"\b8(\.0)?\b"], [S("min_luma", hi=0.15), S("max_luma", lo=0.7)])
field_task("f03", "dev", "Make a sound that plays a sine wave at the pitch of each note, silent when the key is released.",
           [N("Field Synth", "voice"), N("Audio Out", "speakers")], [("speakers", "audio", "voice")], "Field Synth",
           "out = sin(6.283185 * ((n * freq) / sr)) * gate", [r"\bsin\b", r"\bfreq\b", r"\bgate\b"])
field_task("f04", "dev", "Play a Field Synth through a Field Effect that halves the level, to the speakers.",
           [N("Field Synth", "voice"), N("Field Effect", "fx"), N("Audio Out", "speakers")],
           [("fx", "in", "voice"), ("speakers", "audio", "fx")], "Field Effect",
           "out = in * 0.5", [r"\bin\b", r"0\.5"])
field_task("f05", "dev", "Wave a sphere: move each point up and down along a sine of its x position plus time, with height 0.2. Render it to the output.",
           [N("Sphere", "ball"), N("Field Modifier", "warp"), N("Render 3D", "r3d"), N("Output", "out")],
           [("warp", "geo", "ball"), ("r3d", "geo_a", "warp"), ("out", "in", "r3d")], "Field Modifier",
           "P.y += sin(P.x * 2.0 + t) * 0.2", [r"P\.y", r"\bsin\b", r"\bt\b"])
field_task("f06", "dev", "Every quarter step play note 60 at velocity 0.8 for a quarter step, into a Field Synth, to the speakers.",
           [N("Field Notes", "seq"), N("Field Synth", "voice"), N("Audio Out", "speakers")],
           [("voice", "notes", "seq"), ("speakers", "audio", "voice")], "Field Notes",
           "if (tick(1/4) > 0.5) { note(60, 0.8, 1/4) }", [r"\bnote\(", r"\b60\b"])
field_task("f07", "held-out", "Fill the picture with a vertical gradient: black at the bottom, white at the top.",
           [N("FieldPixel", "fp"), N("Output", "out")], [("out", "in", "fp")], "FieldPixel",
           "col = vec3(uv.y, uv.y, uv.y);", [r"uv\.y"], [S("min_luma", hi=0.15), S("max_luma", lo=0.7)])
field_task("f08", "held-out", "Make a sine voice at half volume that is silent when the key is released.",
           [N("Field Synth", "voice"), N("Audio Out", "speakers")], [("speakers", "audio", "voice")], "Field Synth",
           "out = sin(6.283185 * ((n * freq) / sr)) * gate * 0.5", [r"\bsin\b", r"\bgate\b", r"0\.5"])
field_task("f09", "held-out", "Play a Field Synth through a Field Effect that flips the sign of the signal, to the speakers.",
           [N("Field Synth", "voice"), N("Field Effect", "fx"), N("Audio Out", "speakers")],
           [("fx", "in", "voice"), ("speakers", "audio", "fx")], "Field Effect",
           "out = -in", [r"out\s*=\s*-\s*in"])
field_task("f10", "held-out", "Lift a sphere's points: move each point up by its distance from the vertical axis times 0.3. Render it to the output.",
           [N("Sphere", "ball"), N("Field Modifier", "warp"), N("Render 3D", "r3d"), N("Output", "out")],
           [("warp", "geo", "ball"), ("r3d", "geo_a", "warp"), ("out", "in", "r3d")], "Field Modifier",
           "P.y += length(P.xz) * 0.3", [r"P\.y", r"\blength\b"])


def main():
    os.makedirs(OUT, exist_ok=True)
    for t in tasks:
        sol, start = t.pop("_sol"), t.pop("_start")
        open(os.path.join(OUT, t["id"] + ".solution.inf"), "w").write(render(*sol))
        if start:
            open(os.path.join(OUT, t["id"] + ".inf"), "w").write(render(*start))
    json.dump({"version": 1, "tasks": tasks}, open(os.path.join(OUT, "tasks.json"), "w"), indent=1)
    kinds = {}
    for t in tasks:
        kinds.setdefault((t["kind"], t["split"]), 0)
        kinds[(t["kind"], t["split"])] += 1
    print(json.dumps({"ok": True, "tasks": len(tasks), "counts": {f"{k}/{s}": n for (k, s), n in sorted(kinds.items())}}))


if __name__ == "__main__":
    main()
