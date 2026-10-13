# H TouchDesigner by operator family (TOP, CHOP, SOP, POP, MAT, DAT, COMP): dossier

Status: written 2026-10-13 from TouchDesigner's public documentation wiki (the category pages for each family) and Infinite's own node list. No TouchDesigner session was run for this dossier. Lint: `python3 tools/re-survey/diff.py lint docs/plans/re-survey/dossiers/H.md`

## 1. What it is

- A family-by-family comparison of TouchDesigner's operators against Infinite's node categories. Block D covered only its 720p render row, which still waits on one owner paste.
- Reference app: TouchDesigner (proprietary; non-commercial licence, 1280×720 render cap). Public docs only.
- About "MOP": TouchDesigner has no operator family with that name. The families are TOP (images), CHOP (channels and audio), SOP (classic 3D geometry), POP (point operators, the newer GPU family), MAT (materials), DAT (tables and text) and COMP (containers). The request listed "MOP"; the closest real family is MAT, and it is covered below. If "MOP" meant something else, say where it was seen.
- Counts are names on each wiki category page (a few entries on those pages are help topics, not operators), so they are approximate: TOP about 130, CHOP about 150, SOP about 110, POP about 110, MAT 13.

## 2. Method

- TouchDesigner side: the category pages `docs.derivative.ca/Category:TOPs`, `CHOPs`, `SOPs`, `POPs`, `MATs`, read as a name list, then grouped by purpose.
- Infinite side: node names from `.claude/skills/infinite-patch-authoring/SKILL.md` (Source 34, Compositing 37, Effects 28, 3D 86, Modulators 30, Notes 24, AudioEffects 28, Synths 17, Utility 18, Macros 9).
- Matching is by purpose, not by name. A row says what a TouchDesigner user builds with the family and whether an Infinite user can build the same thing from Infinite's nodes.
- Not done: no behaviour run, no timing. `parity` here means "the capability exists as a node or a Field kernel", not "the output matches".

## 3. Pillar map

- P7: TOP, images. TouchDesigner: generators (Noise, Ramp, Circle, Rectangle, Text, Constant), filters (Blur, Bloom, Edge, Emboss, Level, HSV Adjust, Lookup, Threshold, Chroma Key, Lens Distort), compositing (Composite, Over, Layer, Layer Mix, Cross), temporal (Feedback, Cache, Time Machine, Optical Flow, Slope), user shaders (GLSL, GLSL Multi), I/O (Movie File In/Out, NDI, Syphon Spout, Screen Grab, Video Device, Web Render, Photoshop In, SVG), cameras and sensors (Kinect, RealSense, ZED, Orbbec, Leap Motion), AI (NVIDIA Background, Denoise, Upscaler). Infinite's image side is Source (34), Compositing (37) and Effects (28): shapes, Noise, Ramp, Text, Video, Image Source, Blend, Layer Stack, Feedback, Trails, Reaction Diffusion, color and alpha operations, and FieldPixel and Formula as the user-shader route. Edge (`edge sobel`), Emboss and Lens Distortion (`lensdistortion`) exist. Missing: Optical Flow, Time Machine (a frame cache scrubbed by time), depth-camera inputs, Web Render.
- P1: CHOP, channels. TouchDesigner's CHOPs carry control signals and audio in one type (LFO, Noise, Math, Lag, Filter, Envelope, Trigger, Logic, Timer, Beat, Audio Spectrum, MIDI In, OSC In and Out, DMX, Serial, Keyboard, Mouse, Joystick). Infinite splits them: Modulators (30), Notes (24), AudioEffects (28), Synths (17), Utility (OSC Send and Receive, MIDI Out, Audio In and Out, Mixer). Infinite's split is deliberate: audio is sample-accurate on its own thread, modulation is per frame. Missing: DMX in and out, Serial, Joystick and Keyboard as sources, a Timeline or Timecode source, LTC.
- P7: SOP, classic geometry. TouchDesigner: generators (Box, Sphere, Torus, Tube, Grid, Circle, Font, Metaball, LSystem), operators (Extrude, Boolean, Subdivide, Twist, Deform, Lattice, Sweep, Revolve, Skin, Polyloft, Fillet, Carve, Resample, Polyreduce), instancing via Copy, and attribute handling (Attribute Create, Group, Sort, Sprinkle). Infinite's 3D category (86 nodes) covers generators (30-odd), Extrude, booleans, Subdivide, Twist, Solidify, Screw, Mirror, Array, Decimate, Wrap, Displacement, Instance on Points and Field Modifier. Missing: Revolve, Sweep, Polyloft, Fillet, Lattice, Carve, LSystem as named nodes.
- P4: POP, point operators. TouchDesigner's newer GPU family works on points, primitives and attributes: generators (Point Generator, Grid, Sphere, Torus), math and noise (Math, Noise, Random, Field), attribute tools (Attribute, Attribute Combine, Lookup Attribute/Channel/Texture), simulation (Particle, Force Radial, Accumulate, Proximity, Neighbor), and GLSL POPs for user code, plus conversion nodes between POP and SOP, CHOP and TOP. The nearest Infinite things are the Field language (Field Primitive and Field Modifier: a kernel per element, with audio and modulation inputs), Particle System, Distribute Points and Instance on Points. TouchDesigner leads in breadth of named attribute operations and in conversion nodes; Infinite leads in that a Field kernel is plain text, reads audio and modulation directly, and the same language also drives pixels, notes and synths.
- P7: MAT, materials (13). Constant, Phong, PBR, Point Sprite, Line, Depth, Wireframe, GLSL MAT. Infinite's Material node carries a full Principled-style set in one node (metallic, roughness, emission, transmission, clearcoat, sheen, iridescence, anisotropy, dispersion). Parity; no user-shader material in Infinite.
- P1: DAT, tables and text (not in the request, listed for completeness). Scripts, tables, web, serial, OSC messages as text. Infinite's nearest: Text, Field text, OSC Send and Receive. TouchDesigner's scripting (Python in every operator) has no Infinite counterpart except the Field language.
- P1: COMP, containers. Panels, Base, Geometry, Camera, Light, Window. Infinite: Group, Group 3D, Macros, Output and Projection. TouchDesigner's UI-building COMPs (Button, Slider, Container) have no user-facing equivalent; Infinite's Macro nodes are the nearest.
- P8: Real-time speed and the 1280×720 cap. TouchDesigner's non-commercial licence caps output at 1280×720; Infinite renders 4K (Block D). TouchDesigner's own frame timing, GPU memory and audio-reactive latency are not measured.

## 4. Comparison

| Pillar | Their feature | Infinite equivalent | Status | Outcome | Evidence |
|---|---|---|---|---|---|
| P7 | TOP generators, filters and compositing (about 80 of the 130) | `src/core/FilterDefs.cpp` | parity | ignore: Source 34, Compositing 37, Effects 28; Source, Compositing and Effects cover the working set | `src/core/FilterDefs.cpp` |
| P7 | TOP Optical Flow and Time Machine | none | gap | ignore: Trails, Feedback are the nearest; no user has asked; Time Machine is the more live-useful of the two (a delayed frame scrubbed by a modulator), revisit with evidence | census: no optical flow node |
| P7 | GLSL TOP, user shader | `src/nodes/FieldPixelNode.h` | parity | ignore: FieldPixel, Formula; FieldPixel compiles to GLSL (`src/core/field/GlslBackend.cpp`) | `src/nodes/FieldPixelNode.h` |
| P7 | Depth and sensor cameras (Kinect, RealSense, ZED) | none | gap | ignore: Video In is a plain camera; hardware-specific, no user asked | census: no depth camera node |
| P1 | CHOP control signals (LFO, Noise, Lag, Filter, Trigger, Logic, Timer) | `src/nodes/ModulatorNodes.h` | parity | ignore: LFO, Random, Smoothing, Compare, Math ...; 30 modulators; no Timer | `src/nodes/ModulatorNodes.h` |
| P1 | CHOP I/O (DMX, Serial, Joystick, Keyboard, LTC) | `src/nodes/OscNodes.cpp` | gap | ignore: OSC Receive/Send, MIDI CC; OSC and MIDI cover live use; DMX is the one a lighting user would ask for | `src/nodes/OscNodes.cpp` |
| P5 | CHOP audio (spectrum, dynamics, EQ, VST) | `src/audio/EffectDefs.cpp` | lead | ignore: 28 audio effects, 17 synths, VST3/AU Plugin; TouchDesigner's audio is a side path; Infinite's is the sample-accurate core | `src/audio/EffectDefs.cpp` |
| P7 | SOP generators and operators (Box, Torus, Extrude, Boolean, Subdivide, Twist) | `src/nodes/GeometryOpNodes.cpp` | parity | ignore: Cube, Torus, Extrude, Union/Intersect/Difference, Subdivide, Twist; all present | `src/nodes/GeometryOpNodes.cpp` |
| P7 | SOP Revolve, Sweep, Polyloft, Fillet, Lattice, LSystem | none | gap | ignore: Screw (revolve-like) only; same reasoning as Blender curve profile and bevel; wait for a user who asks | `dossiers/G.md` |
| P4 | POP attribute operations, GPU simulation, GLSL POP | `src/nodes/FieldElementNode.h` | parity | ignore: Field Modifier; Field kernels with audio and modulation inputs; named attribute operations are TouchDesigner's breadth | `src/nodes/FieldElementNode.h` |
| P7 | MAT (Phong, PBR, GLSL MAT) | `src/nodes/UtilityNodes.h` | parity | ignore: Material; Material carries the full Principled set; no user GLSL material | `src/nodes/UtilityNodes.h` |
| P1 | DAT and Python in every operator | none | gap | ignore: Field language (not Python); the Field language is Infinite's scripting layer | `dossiers/F.md` |
| P7 | Output resolution (non-commercial cap 1280×720) | `src/core/HeadlessJob.cpp` | lead | ignore: 4K measured | `dossiers/D.md` |

## 5. Measurements

- None new. Block D's TouchDesigner row (720p render speed and AV sync) still waits on the owner's Textport paste from `render_bench.py td-prep`.

| Not measured | Why | What it needs |
|---|---|---|
| TouchDesigner frame time and audio-reactive latency | no headless mode | the Textport paste, then a timing script like `render_bench_td.py` |
| Output equivalence between a TouchDesigner TOP and its Infinite node | no run | a shared test image through both |

## 6. Outcomes

- Quests: none.
- Quality gaps: none. Checked 2026-10-13: Edge, Emboss and Lens Distortion exist; Optical Flow and Time Machine do not and are ignored with the reason in the table.
- Ignored, with reason: sensor-camera TOPs, DMX and Serial, SOP curve-surface operators, DAT and Python (the Field language is the scripting layer).
- Owner sittings needed: the one Textport paste (shared with Block D).

## 7. Storage

- Nothing written to ~/re-output by this dossier.
