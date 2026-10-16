## What's new in v0.6.0

v0.6 is a quality release: audio that measures right, a faster first run, a deeper set of synths and effects, and a larger 3D and compositing toolbox.

### Sound: correctness first

- Offline export (Output Record and Render, Timeline) drops the graph's PDC latency, so a bounce lands on the same instants as live playback; Drive and Limiter bounces start on the dry click
- The master says when it clips: Audio Out shows `last take clipped, +x dB over`, and the Output node's status line and Timeline renders name the worst peak
- Inserting an effect leaves loudness alone; Drive and Wavetable Shaper delay 5 samples instead of 73
- Drive uses 8x half-band oversampling with ADAA and an 8 Hz DC blocker at every rate; Bitcrush has true bit depth and a TPDF dither switch; Dynamics has a sidechain high-pass
- Analog is cleaner and in tune: narrow-band oscillators and a 4x drive and filter keep aliasing under -80 dB, and voice 0 is the tuning reference so default patches play in tune
- Fixes: Metallic mallet noise runs on a fixed 48 kHz clock; Bitcrush hold clock lands on the same instants at every rate; Audio Filter envelope depth glides over 20 ms; Field Synth default no longer aliases; EQ keeps ramped biquad denominators inside the stable range; resonant shelf and peak EQs match their targets more closely
- Audio analysis is read before modulation bindings, not after
- Timeline stretch is transient-aware
- Smoother modulation: parameters ramp linearly between stamped frame values, the frame clock is interpolated between audio callbacks, and a destination's first value lands instead of ramping up from zero

### Sound: new instruments and effects

- Add FM (Synths): a 4-operator FM synth with 11 algorithms, ratio or fixed frequency, a level and envelope per operator and feedback on operator 4
- Add String (Synths): a plucked, bowed or struck waveguide string on a modal body, in tune to 1 cent
- Add Partials (Synths): play any sample as resynthesised partials with pitch, formant, partial count and morph
- Add Saturator (effect): three saturation stages (tube, tape, diode, fold, rectify, crush), each with its own amount, wired serial, parallel, mid-side, 3-band or feedback, with 8 presets
- Add a reverb whose room you design or load, and a shape you draw that plays over time
- Splitter splits into up to four Linkwitz-Riley bands that add back up flat
- Dynamics gets clean, bus, opto and FET styles (the analog switch is now called warm)
- Delay's tape mode gets wow, flutter, saturation and diffusion, plus two presets (Worn Cassette, Tape Wash)
- Filters add ladder, MS-20 and diode models that sing at the cutoff
- Field gets phase shaping (bend, pinch, mirror, skew, formant), and Wavetable warps share those shapes
- Add 79 factory presets for the synths and core effects
- Analog runs four voices per SIMD lane (about a third of the CPU for chords) and Wavetable caches its per-sample math; the audio graph runs on every core with bit-identical results to one thread

### Modulation per note

- LFO, Random and MSEG get a "per voice" switch: cabled into an Analog or Wavetable knob, each note gets its own copy, started at its note-on
- Envelope gets hold, a curve per stage and a "per voice" switch
- Add Voice Spread: each note of a chord gets its own value by its place among the held keys
- Add Note Expression: with MIDI Notes in MPE mode, each voice follows its own finger's pressure or slide
- One note output feeds up to 64 consumers (W_NOTE_FANOUT past that)
- LFO, Random, Smooth, Envelope and CV to Pitch use new maths; patches saved earlier keep the old behaviour

### First run and live use

- First sound in three steps, and a dropped sample plays in one
- The Timeline gets the keys DAWs and editors share; arrangement clips get per-clip speed and reverse
- Show set: step through patches live, switch on the bar, with audio tail and projector hold; bar-quantized pause and restart
- Show safety: a show lock, a latching panic, a pre-show check and a 4 s quit watchdog
- OSC control API: set, query and listen to any parameter; create, delete and connect nodes
- Plugins that crashed the app are isolated or left out next time; plugins with a sidechain input get a sidechain pin
- Patches and Field devices are saved beside the file and renamed over it, so a crash mid-save cannot damage the old copy
- Adding a node no longer recompiles an already-compiled shader, so adding nodes stops hitching
- Every community patch passes the strict validator
- Add Share Patch: one `.infshare` file with the cleaned patch, thumbnail, preview video and info
- Add a Library category for AI skills, with a Patch Authoring skill

### 3D and compositing

- Add Optical Flow (Compositing): pyramidal Lucas-Kanade on the GPU, flow as an RG texture
- Add Time Machine (Compositing): per-pixel delay from a grey map over a 60-frame ring
- Add Fluid (Compositing): GPU stable fluids with multigrid pressure, vorticity, obstacles, a force input and a built-in stirrer
- Add Volume (Compositing): ray-marched fog, smoke and cloud over an image, using the Render 3D camera and depth, with its own camera when none is connected
- Add Rigid Bodies (3D): box, sphere and convex-hull colliders, ground, walls and a kick
- Add L-System (3D): axiom, rules, angle and generations to a tube mesh and a followable curve
- Add Sweep and Revolve (3D): a profile along a path, and a curve about an axis; both watertight with outward winding
- Add Proximity Lines (3D): neighbour links as a thin prism mesh, 2.9 ms at 100k points
- Render 3D gets ambient occlusion, depth of field, offline supersampling and 16-bit float output
- The particle system is about 30 times faster on every OS with the same results
- Long node bodies (Volume, Rigid Bodies, Particle System) fold their lower sections behind show more / show less; folded parameters keep their modulation
- Booleans stop at a polygon budget (refused over 250k polygons) instead of running for minutes
- Subdivide drops weld-degenerate triangles at sphere poles; Group 3D, Layer Stack fit, translucent instances and sample-folder fixes from the v0.5 Discord reports

### Colour, images and filters

- Overlay, Soft Light, Hard Light and Hard Mix follow the W3C formulas
- Curves is an exact straight line by default, drawn through a 1024-entry lookup; Lookup keeps exact ends and uses tetrahedral interpolation
- Saturation uses Rec.709 weights; ASC CDL is supported
- Gaussian and box blurs convert once to premultiplied linear light; Bloom's bright pass runs once per pixel (Box blur GPU cost +77% to +20%, Bloom +26% to +16%)

### Headless and tooling

- `--audio-summary --timeline` plays the arrangement's audio lanes
- `--validate`, `--explain` and the render modes report Field compile errors as `E_FIELD_COMPILE`, and validate compiles Formula and Equation formulas, expressions and globs
- `W_PLUGIN_NOT_LOADED`, a plugins status block and `--plugin-params`
- Frame renders hold the clock at zero from the first tick, so history nodes such as Time Machine render the same every run
- Headless runs no longer read or write the learned prediction profiles, so a render does not depend on, or change, your Predictive Quantize / Velocity / Notes / Rhythm data
- Measurement audits for effects, synths, notes, modulators, geometry and compositing run in the hygiene driver and gate the release

### Fixes

- Fix Primitives (Sphere, Cylinder, Cone, Pyramid, Prism, Torus Knot, Helix, Supershape, Arrow) winding inward; flat normals no longer collapse to zero
- Fix history jumping forward piling nodes on the origin
- Fix a Smooth spring and other smoothing states after frame hitches; fix the Feedback header describing the wrong delay
- Light-theme text and hint text on text fields keep 4.5:1 contrast
- Delay, Envelope, FM and Mixer controls line up on one grid

### Changes to existing patches

- Blend modes Overlay, Soft Light, Hard Light and Hard Mix use the W3C maths for new nodes; saved patches keep the old modes
- Curves keeps the old spline in saved patches; new Curves nodes are an exact straight line
- Primitive meshes wind outward; saved patches keep the old winding
- Analog sounds different: aliasing is lower, the oscillator mix is AC-coupled, and default patches are in tune
- The LFO, Random, Smooth, Envelope and CV to Pitch maths changed for new nodes; saved patches keep the old maths
- Drive and Wavetable Shaper report 5 samples of latency, not 73
- Mixer channels is a plain stepper with no modulation pin

### Known limits

- Fluid, Instance, Cycle Shaper aliasing and Analog FM are measured misses we accepted for this release
- Three saturation stages in series alias at -46 dB
- The Plugin editor GL context guard (R282) is in but not yet verified on Windows
- Hardware controller testing for MPE is still a follow-up; the tests use injected MIDI bytes
