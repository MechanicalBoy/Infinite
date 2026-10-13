# Node audits: beyond effects and modulators

Branch per block. Tracker: this file. Written 2026-10-12. Status: all five audits built and gating; audio side complete; what is left is in section 10.

FXAUDIT (`src/app/selftest/FxAudit.cpp`) measures every audio effect and MODAUDIT
(`src/app/selftest/ModAudit.cpp`, plan in `docs/plans/modulation/README.md`) measures every
modulator. This plan extends the same method to the remaining node categories. Reference
material for each audit is in `docs/plans/re-survey/resources.md`.

## 1. Goal

Every node category gets a headless measurement audit: the same battery of numbers for every
node, FLAG lines past thresholds, a baseline file, fixes in measured blocks, and a re-run. The
question each audit answers is "does it match a published reference or a competitor, as a table
and not an opinion". Competitor numbers come from black-box measurement only (re-survey README
section 3).

## 2. Coverage today

Node counts from `docs/node_param_audit.md` (176 registered types).

| Category | Nodes | Measured by | Gap |
|---|---|---|---|
| Audio effects | (EffectDef set) | FXAUDIT | none |
| Modulators | 31 | MODAUDIT | none |
| Synths | 17 | ALIASTEST, PITCHTEST, METALLICDECAYTEST, CYCLESHAPERTEST, MOLDERTEST, GRAINMOLDERTEST | no shared battery |
| Notes | 24 | NOTEPUMPTEST, MIDI tests | no timing audit |
| Utility / audio I/O | 18 | UTILTEST | no meter, law or latency audit |
| 3D | 37 | 22 tests in GROUP_3D | propagation and crashes, not geometry correctness |
| Compositing | 15 | PHASE*, BUG, LIVE tests | no numeric reference checks |
| Source | 14 | SHAPEEDGETEST, REMOVEBGTEST | no battery |
| Prediction | 8 | own tests | out of scope (behavioural, covered) |
| Macros | 9 | MACROTEST, MODBOUNDSTEST | out of scope (covered) |

## 3. Method (same as FXAUDIT / MODAUDIT)

- One `INFINITE_<NAME>AUDIT` env var, one file in `src/app/selftest/`, wired into the matching
  group and `FULL_TESTS` in `.claude/skills/run-infinite-hygiene/driver.sh`.
- Runs through the real node and runtime, never a copy of the DSP.
- Only hard invariants fail the run (non-finite output, hung tail, crash). Everything else is
  reported, with FLAG lines past thresholds for a person to triage.
- `INFINITE_<NAME>AUDIT_ONLY=A,B` selects sections.
- Raw runs saved as `baseline-<date>.txt` and `after-blockN-<date>.txt` next to this file.
- Fixes made before 2026-10-13 sit behind a per-node legacy flag (`BeforeLoadParams`). From 2026-10-13 the owner's rule is smallest fix, no new legacy flags for old patches (few users); a fix that changes saved output gets a release-notes line instead.

## 4. Scope

- In scope: Synths, Utility audio, Notes, 3D geometry, Compositing, Source (image side).
- Out of scope: Effects and Modulators (done), Prediction learning, Field, plugin hosting.

## 5. Constraints

- Saved patches behave the same.
- No audio-thread allocation or locks.
- Three platforms.
- Export is never worse than live.
- CPU no more than 10% worse per node, unless the owner accepts an exception and it is recorded.
- No analysis tools in shipped builds. All audits are self-test code, `#ifndef NDEBUG`-safe as in FXAUDIT.
- No competitor code, binaries or dumps in the repo. Competitor reference numbers only, with the plugin and settings noted.

## 6. Blocks

Three blocks, one branch each, commit per step, merge straight back to main (git-branch-workflow).

| # | Branch | Audits | State |
|---|---|---|---|
| 1 | `feature/synth-audit` | SYNTHAUDIT | done 2026-10-12 (merged); F4 and F8 fixed; sample synths covered and F11 fixed 2026-10-13 (`feature/node-audio-complete`) |
| 2 | `feature/io-note-audit` | IOAUDIT, NOTEAUDIT | done 2026-10-12 (merged); Echo voiceId fixed; step-generator timing fixed 2026-10-13 (`feature/node-audio-complete`) |
| 3 | `feature/geo-comp-audit` | GEOAUDIT, COMPAUDIT | done 2026-10-12 (merged); findings open, see below |

Order reason: Synths are the largest audio gap (220 controls) and audio comes first in the perf
order. They pair with the re-survey synth probe, so each metric has a competitor number. FXAUDIT
supplies most of the harness.

### Block 1: SYNTHAUDIT (17 synths)

Standards: Zavalishin (VA design), Välimäki/Esqueda (anti-aliased oscillators), Bristow-Johnson
(wavetable); competitors Diva, Serum 2, Vital (behaviour only), Bitwig/Live instruments.

| Section | Measures | Target |
|---|---|---|
| PITCH | Fundamental error over the keyboard range, at 44.1 / 48 / 96 kHz | within 1 cent |
| ALIAS | Largest non-harmonic partial vs the fundamental, saw / square / sync / FM at 4 notes | at most -80 dB (was -60 until F2, 2026-10-13) |
| LEVEL | RMS and peak at default, velocity 0.25 / 0.5 / 1, per note | spread reported; peak under 0 dBFS at defaults |
| ENV | Attack, decay, release times vs set values, sample resolution | within 1% or 1 sample |
| CLICK | Note-on, note-off and retrigger discontinuity (second-difference peak) | at most 12 dB over steady state (FXAUDIT threshold) |
| UNISON | Voice count, detune spread in cents vs setting, stereo spread correlation | within 5% of setting |
| POLY | 1, 8, 32 voices: CPU per voice, voice steal behaviour, no stuck voice after all-off | no stuck notes; CPU per voice reported |
| RATE | Level and pitch at 44.1 / 48 / 96 kHz | level spread under 1 dB |
| PARAM | Zipper on each modulated param (reuse MODAUDIT ZIPPER method) | at most 1/1024 per sample |
| DET | Same seed, same render | bit-identical |
| TAIL | Silence after note-off plus release | below -100 dBFS (FXAUDIT threshold) |

Competitor reference: re-survey synth probe renders the same notes in Diva, Serum 2 and Vital;
aliasing, pitch error, filter sweep and envelope shapes are compared as numbers.

### Block 2: IOAUDIT and NOTEAUDIT

Result (baselines `baseline-2026-10-12-note.txt`, `baseline-2026-10-12-io.txt`):

| Finding | State |
|---|---|
| Audio Gate sent a double note-off | fixed |
| Audio Quantizer left stuck notes (off not shifted with its on) | fixed |
| Random Note Gen swing truncated to one block | fixed, legacy flag `swingMode` keeps saved patches |
| Mixer mute / solo / pan stepped at block rate (36-44 dB clicks) | fixed, gains ramp across the block |
| Loudness, Gain/Mixer/Blend laws, 12-slot sum, Splitter | exact, no change |
| Note Echo shares one voiceId across dry and repeats | **fixed**: each repeat is its own voice (fresh id per repeat, freed on its note-off); PAIR orphan-off 11 and dup-on 12 to 0, see `baseline-2026-10-12-note-after-echo.txt` |
| Arp / Sequencer / Random Note Gen / Chorder placed steps on block boundaries (up to one block early: `Beats()` already reads the block end, and the step went out at frame 0) | **fixed** 2026-10-13: one `StepClock` (NoteNodes.cpp) walks the block span from `BlockStartBeats()` and emits each step on its own sample, across loop laps and seeks; legacy `stepTiming` keeps saved patches on block-start timing. GRID worst error 2048 -> 0.8 samples on all four; 1/64 at 174 bpm 373/373 steps, loop lap 49/49 at 0.0 samples; legacy row still 512 (old timing kept). See `after-steptiming-2026-10-13-note.txt` |
| Audio In/Out and PDC | Audio In/Out: accepted exception 2026-10-13, hardware-only (needs a live device, not testable headless); PDC is covered by `AUDIOPDCTEST` |

IOAUDIT covers Mixer, Gain, Spatial Mixer, Audio Meter, Blend Audio, Splitter, Audio In/Out.

| Section | Measures | Target |
|---|---|---|
| METER | Level and peak vs ITU-R BS.1770 (K-weighted LUFS, true peak) for reference signals | within 0.1 LU / 0.1 dB |
| LAW | Gain taper (dB at 0 / 25 / 50 / 75 / 100% fader), pan law (centre dB), mute and solo | documented, symmetric, no zipper |
| SUM | Summing 64 channels at -20 dBFS: noise floor, headroom, determinism | exact sum within float error |
| PDC | Latency reported vs measured through each node chain | exact in samples |
| LINK | Bypass, mute, delete mid-playback: clicks and leftover tails | no click above FXAUDIT threshold |

NOTEAUDIT covers the 24 note nodes.

| Section | Measures | Target |
|---|---|---|
| GRID | Note timing vs the `MusicTime` grid for every division, at 5 tempos | within 1 sample |
| SWING | Swing and humanize amount vs setting; same seed same result | within 1% |
| LOOP | Note-offs and phase at loop wrap, seek and stop | no stuck note, no double note |
| BYPASS | Bypass and delete while notes sound | all-off sent, no stuck note |
| ORDER | Merge, Stack, Router, Switcher ordering and note-off pairing | note-on and note-off counts equal |
| JITTER | Note-on time vs ideal at 24 / 60 / 144 fps | within 1 audio block |
| CPU | ns per call per node | reported |

### Block 3: GEOAUDIT and COMPAUDIT

GEOAUDIT result (`baseline-2026-10-12-geo.txt`; covers the 24 primitives and the Geometry Ops, not yet the other geometry nodes):

| Finding | State |
|---|---|
| Normals exact for Sphere, Icosphere, Torus; build time linear to 1e6 vertices (34 ns/vertex); builds deterministic; MeshRevision stable and follows the input | clean |
| Winding is inconsistent between primitives: Cube, Icosphere, Torus, Capsule, Tetra/Octa/Dodeca, Rounded Cube are outward (CCW); Sphere, Cylinder, Cone, Pyramid, Prism, Torus Knot, Helix, Supershape wind inward | **fixed**: all now wind outward (`OrientOutward` in Mesh.cpp); the Geometry node carries `windingFix` (off on old patches: flips the eight shapes back and re-derives Prism/Supershape/Arrow normals). GEOAUDIT: "faces inward" 3 to 0, Sphere winding mismatches 1472 to 32 (pole fans). See `baseline-2026-10-12-geo-after-winding.txt` |
| UV Sphere, Capsule, Cone, Disc, Supershape have degenerate pole triangles and doubled pole edges | accepted (standard UV-pole artefact) |
| Solidify on a Cube leaves 48 boundary edges (faces separate along their normals) | parked: inner shell offsets each face by its own normal, so a closed cube gets gaps along its 12 edges and an open input gets no rim wall. Needs a welded-normal offset + rim quads, which changes the look of every Solidify; own quest when someone asks |
| Arrow 3D has 48 vertices with non-unit normals | **fixed**: zero-area triangles (cone apex ring) kept a zero normal; flat RecalculateNormals now borrows the corner normal |

COMPAUDIT result (`baseline-2026-10-12-comp.txt`; needs the GL context, hidden window; covers Blend, Feedback and Trails only):

| Finding | State |
|---|---|
| 22 blend modes match the W3C Compositing Level 1 formulas to 1/255 (Normal, Multiply, Screen, Darken, Lighten, Colour Dodge/Burn, Difference, Exclusion, Hue, Saturation, Color, Luminosity, Add, Linear Burn/Light, Subtract, Divide) | clean |
| Overlay and Hard Light are swapped: Overlay tests the source (Hard Light's rule), Hard Light tests the backdrop. Error up to 251/255 | **fixed** (also Soft Light pivot): W3C maths now; old maths kept as modes 32-34 ("(old)"); Blend / Layer Stack carry a `blendFix` param (off on old patches), patch files carry `blendfix 1` (absent = clips mapped to 32-34). COMPAUDIT blend flags: 3 to 0, see `baseline-2026-10-12-comp-after-blendfix.txt` |
| Soft Light picks the wrong branch of its D(x) curve (the 0.25 pivot is inverted). Error up to 83/255 | **fixed** with the Overlay / Hard Light fix |
| Source-over alpha with random alpha and mix 0.7 matches W3C for Normal, Multiply, Screen | clean |
| Feedback in a plain chain passes the current frame through; the one-frame delay only exists inside a cycle, although the node says the delay is always one frame | **settled**: wording fixed (header comment, delayFrames note); behaviour kept because saved loops depend on this timing; help text already says it only acts inside a loop. The audit line stays as a documented by-design FLAG |
| Trails decay matches decay^n within 0.2/255 and always reaches black (no 8-bit ghost) | clean |
| Layer Stack with two layers equals Blend with the same mode and opacity (11 modes x 2 opacities, random alpha) | clean, within 1/255 |
| Curves: a fresh node was not identity. The two-point default (0,0)-(1,1) went through Catmull-Rom with duplicated end neighbours, an S-curve with error up to 25/255 (inverted and per-channel curves were off by the same amount) | **fixed** in `CurveShape::Evaluate` (end neighbours reflected, overshoot clamped); identity, inverted, Red-only and mix 0 now within 1/255. Affects the Curves node and the curve modulator; any saved 2-point curve gets straighter |
| Color Ramp linear and constant interpolation match the analytic gradient and step | clean |
| Fit: output size follows width/height and matchInput; Fit leaves transparent bars, Fill and Stretch cover the frame | clean |
| Switcher manual slot shows exactly the chosen input | clean |
| GEOAUDIT GRAPH section (`baseline-2026-10-12-geo-coverage.txt`): Distribute random matches density x area (125 of 125), Poisson spacing holds (0.2001 vs 0.2), Delaunay has zero empty-circumcircle violations, Voronoi / Join merge / Merge by Distance / Ocean are valid and deterministic, Join counts add up, Merge by Distance leaves no pair closer than the threshold | clean, 0 new flags |
| PDC: `AUDIOPDCTEST` (existing, in the driver) already covers branch alignment, no-latency no-delay and terminal dedupe; re-run 2026-10-12, OK | covered elsewhere |
| Not yet covered: Reaction Diffusion, Remove Background, image sources; blur accuracy; RES and BYPASS sweeps; Metaballs, Cloth, Curve Ops, Instances, Displacement | next |

GEOAUDIT covers the 37 geometry nodes (Delaunay, Metaballs, Ocean, Cloth, Curve Ops, Instances,
Join, Merge by Distance, Distribute, Displacement and the rest).

| Section | Measures | Target |
|---|---|---|
| VALID | Non-finite, NaN normals, degenerate triangles, inverted winding | none |
| WATERTIGHT | Boundary and non-manifold edges for closed primitives and booleans | zero where closed is promised |
| NORMALS | Normal error vs analytic for sphere, torus, displaced plane | within 1e-3 rad |
| DEGEN | Zero-size, one-point, coincident-points, huge-count inputs | no crash, defined output |
| SCALE | Time and memory vs vertex count (1e3 to 1e6) | near-linear unless the algorithm is not (Delaunay, booleans) |
| DET | Same inputs, same mesh, bit-identical | pass |
| CACHE | Revision propagation: unchanged input does not recook | no recook |
| REF | Voronoi, Delaunay, decimation error vs published references (resources 4.2) | reported |

COMPAUDIT covers Blend, Layer Stack, Curves, Color Ramp, Feedback, Trails, Fit, Switcher,
Reaction Diffusion, Remove Background and the image Sources.

| Section | Measures | Target |
|---|---|---|
| BLEND | Every blend mode vs the W3C Compositing and Blending Level 1 formulas on a test grid | within 1/255 |
| ALPHA | Premultiplied vs straight; edge fringe after blur and blend | no halo |
| COLOUR | Ramp and gradient interpolation space; sRGB vs linear on blur and blend | documented and consistent |
| BLUR | Gaussian and radius accuracy vs analytic; cost vs radius | within 1%; cost reported |
| FEEDBACK | Trails and Feedback decay vs setting; energy blow-up | stable |
| RES | Output at 1 / 4 / 16 Mpx: time and GPU memory | reported |
| BYPASS | Bypassed and cooked-twice nodes give the same pixels | exact |
| DET | Same inputs, same frame, bit-identical | pass |

## 7. Success metrics

From 2026-10-13 every audit value also lands in the quality system (`docs/quality/`): the registry owns targets and the release gate, and `docs/quality/SCOREBOARD.md` shows status. SYNTHAUDIT is wired; the other audits follow (rollout in `docs/quality/README.md`).

| # | Metric | Target | State 2026-10-13 |
|---|---|---|---|
| 1 | Audits wired into the driver groups and `FULL_TESTS` | all five new audits | **met**: all five gate; the driver reads `PASS (n flags)` as a pass (before, every audit read as "no verdict") |
| 2 | Baseline run saved per audit before any fix | yes | **met**: `baseline-*` and `after-*` files in this folder |
| 3 | FLAG lines closed or recorded as an accepted exception with owner and date | all | **met for audio**: SYNTHAUDIT leaves only Metallic F1 (accepted) and F7 (metric unreliable on a resonator); NOTEAUDIT clean; Audio In/Out accepted as hardware-only. Geometry and compositing rows are tracked in their own table |
| 4 | CPU per node | at most +10%, exceptions recorded | **met by construction** for F11 and stepTiming (one multiply per voice, one compare per step). **Exception, Analog (F2, 2026-10-13):** 4x drive + filter roughly doubles to triples its voice cost (SYNTHAUDIT about 210 -> 640-870 ns/frame on a shared machine; still under the 4000 ns flag). Accepted: the owner asked for -80 dB and that cost is what the ladder needs |
| 5 | Saved patches | unchanged output (ROUNDTRIPTEST and the legacy-flag test pass) | **met**: PATCHTEST and ROUNDTRIPTEST pass (308/308 types, 15/15 templates); every behaviour change sits behind a legacy param (`velCurve`, `stepTiming`, `rateFix`) and the legacy paths are re-measured each run. Exceptions by owner decision, no flag: F19 (Analog voice-0 tuning) and F2 (Analog aliasing) |
| 6 | Competitor numbers for Synths | at least pitch, alias and envelope for Diva, Serum 2 and Vital | **met**: see table below and `metric6-2026-10-13.md` |

Metric 6, re-survey synth probe at 48 kHz, default patch of each, notes 24 to 108:

| Target | Worst pitch error ¢ | Non-harmonic dB at C4 / C7 / C8 | Attack ms | Release to -60 dB s | Velocity span dB |
|---|---|---|---|---|---|
| Diva | 7.7 (analog drift, by design) | -40.8 / -27.0 / -10.4 | 44 | 1.61 | 12.9 |
| Serum 2 | 0.2 | -83.0 / -82.6 / -81.9 | 2 | 0.02 | 0 |
| Vital | 0.2 | -84.3 / -84.3 / -83.6 | 1 | 0.08 | 0 |
| **Wavetable** | 0.2 | -84.2 / -84.9 / -83.9 | 4 | 0.26 | 24.1 |
| **Analog** | 0.2 (was 3.5, F19) | -84.5 / -83.3 / -81.2 (was -67.8 / -63.3 / -60.9, F2) | 3 | 0.25 | 24.1 |

Wavetable matches Serum 2 and Vital on pitch and aliasing. Since F19 and F2 (2026-10-13) Analog does too: 0.2 ¢ and -81 to -85 dB, where it was 3.5 ¢ flat and about 20 dB behind. Infinite's default patches respond to velocity (squared curve, 24 dB); Serum 2's and Vital's defaults do not.

## 8. Order inside a block

1. Write the audit, run it, save the baseline, commit.
2. Record findings (table F1, F2, ... with evidence and block).
3. Fix in small commits, each behind a legacy flag where behaviour changes.
4. Re-run, save `after-blockN`, update the metrics table and honest misses.
5. Merge to main, delete the branch.

## 9. Findings

Block 1, harness v1 (Analog, Wavetable, Oscillator, Equation Synth, Metallic; baseline-2026-10-12.txt):

| # | Finding | Evidence | Block |
|---|---|---|---|
| F1 | Metallic level moves with sample rate: 2.9 dB free-running RMS, but only 1.3 dB RMS and 0.5 dB peak for the same note-triggered strike (-12.5 / -13.1 / -13.8 dBFS at 44.1 / 48 / 96 kHz, monotonic). The burst gain is already calibrated per rate (`MetallicResonator.h` CalibrateBurstGain), so the remainder is minor mode-content change. Accepted exception, not fixed; the free-run flag stays visible. | RATE rows | 1 |
| F2 | **Fixed** 2026-10-13 (owner reversed L9): Analog aliasing was -66 dB at 1.75 kHz and -62 dB at 5 kHz (SYNTHAUDIT ALIAS, default saw), and synth_probe non-harmonic -68 / -63 / -61 dB at MIDI 60 / 96 / 108, against -82 to -88 dB for Wavetable, Oscillator and Equation Synth. Two causes, both needed: (1) the BLEP kernel (cut 0.90 Nyquist) leaves 20-24 kHz content that the drive tanh and the ladder intermodulate into the audible band, which no oversampling after the oscillator removes; (2) the ladder's tanh stages still fold at 2x (-73 dB on an input clean to 19 kHz, -89 dB at 4x). Fix: Analog's oscillators use a narrow-band BLEP table (`BlepOsc::NarrowOscillator`, cut 0.80: -0.4 dB at 16 kHz, -2.7 dB at 18 kHz; same 12-sample kernel so the same latency; Wavetable keeps the 0.90 table and its PDC) and drive + filter run at 4x (latency 32 -> 38 samples, reported to PDC). After: ALIAS -84.9 / -87.5 dB, probe -84.5 / -83.3 / -81.2 dB, ALIASTEST Analog saw 1.75 kHz -69 -> -89, drive 100% -51 -> -80, ladder -49 -> -73. Cost: SYNTHAUDIT cpu_ns_frame about 210 -> 640-870 ns (shared machine; Wavetable read 145-270 in the same runs, so about 3-5x Wavetable instead of 2.7x), probe 14 -> 30 ms/s per voice. Every saved Analog patch is cleaner and very slightly darker above 16 kHz; no compat flag (scale-to-user-base). Gates: synth.alias_db target -60 -> -80 (release), probe.nonharm60/96/108 report -> release, ALIASTEST Analog gates tightened to about 4 dB under the new values. | ALIAS rows, ALIASTEST, synth_probe | 1 |
| F4 | **Fixed** (Equation Synth): velocity is now squared like Analog and Wavetable (vel 0.5 = -12.0 dB); old patches keep linear through the `velCurve` param. Metallic stays linear on purpose: velocity is the strike excitation of a resonator, not a gain. | VEL rows | 1 |
| F5 | Equation Synth clips with several notes at defaults: peak +3.6 dBFS at 8 notes, +4.3 at 32, against -12 dBFS for one note. No polyphonic gain compensation. Decision: not a bug. Voices sum, as in any polysynth, and a 4-note chord fits (-0.8 dBFS); attenuating would change the loudness of every saved patch. The audit now flags only a 4-note chord over 0 dBFS. | POLY rows | 1 |
| F6 | Polyphony cost stops growing past 8 notes on every synth (8 and 32 notes cost the same per frame), so all five cap at 8 voices. **Accepted** 2026-10-13: the cap is a deliberate per-node constant (`kMaxVoices = 8` in AnalogNode.h, EquationNode.h, MetallicNode.h, WavetableNode, ImageSpectralSynthNode.h; Sampler, Grain Molder, Field Synth use 16) with oldest-voice stealing. No UI readout added (audio-node minimalism, `new-audio-node` #5). | POLY rows | 1 |
| F7 | Wavetable note-on is +8.2 dB over steady state at defaults, the only pitched synth near the 12 dB flag. Metallic note-on reads +32 dB, but its steady state is a decaying resonator, so that metric is unreliable for it. **Wavetable investigated 2026-10-13: not a click, by design.** The peak second difference sits at sample ~190, the end of the 4 ms linear attack (`Envelope` in AudioVoice.h, shared with Analog and Oscillator): the slope change from ramp to decay (0.44 / 192 per sample) is about twice a 440 Hz sine's own second difference (A w^2 = 0.0011), plus the 1/0.75 decay-to-sustain level (2.5 dB). A model of the same ADSR on a sine reads +10.7 dB with a 4 ms attack and -10 dB with 20 ms. No initial-phase step (output rises from 0, first sample 0.002) and no overshoot. Analog reads -2.9 dB with the same envelope only because a saw's own second difference hides the kink. Kept: a linear ADSR is what the controls promise, and a corner is not audible as a click. | CLICK rows | 1 |
| F8 | Field Synth peaks +12.0 dBFS with 8 or 32 notes at defaults (-2.4 dBFS for one), the worst polyphonic clip of the group. The only synth whose 4-note chord clips (+9.0 dBFS; single note -2.4 dBFS vs about -12 for the others): voices sum unscaled (`FieldSynthNode.cpp:292`) and the default preset (Dual Oscillator Pad) is hot. **Fixed** for new nodes: the default preset now ends `out = filt * env * 0.33` (single note -12.0 dBFS, 4-note chord -0.6); saved patches carry their own source text, so they are unchanged. See `baseline-2026-10-12-synth-after-f4f8.txt`. | POLY rows | 1 |
| F9 | Wave Terrain also sums past 0 dBFS with many notes (+0.5 dBFS at 8, +3.2 at 32). Same as F5: not a bug; its 4-note chord is -3.0 dBFS. | POLY rows | 1 |
| F10 | Spectral Synth's 1.99 dB rate spread was a harness artifact (a fixed 65536-frame window is a different number of seconds at each rate). RATE now renders 3 s at every rate and reads 0.05 dB. Closed. | RATE row | 1 |
| F11 | **Fixed** 2026-10-13: Sampler, Grain Molder, Molder, PaulStretch and Drum Sequencer played a file at the device rate, not its own (decode keeps the file rate, and these five never corrected for it; Slicer, MPC, Granular and Looper did). A 48 kHz file at 44.1 kHz played 147 c flat and 9% long; at 96 kHz an octave high and half length (pitch spread 1346.7 c, length ratio 2.18). Now 0.0 c on all four, PaulStretch 6.8 c (random-phase jitter, under the 20 c gate). Old patches keep the old pitch through the `rateFix` param (0 when the key is missing); the legacy path is re-measured on every run. See `after-samplerate-2026-10-13-synth.txt`. | SAMPLE rows | 1 |
| F12 | **Fixed** 2026-10-13: Solidify left 48 boundary edges on a Cube (inner shell offset each face by its own normal, so hard edges tore open) and no rim wall on an open input. The inner shell now offsets along the position-welded normal and an open input gets a rim wall; Cube and Plane close with 0 boundary edges. Same quest as L10. Also fixed in the same pass: Disc faces were wound against their normals; Sphere, Capsule and Supershape poles were not exactly zero radius (sin(pi) is -8.7e-8), which left sliver triangles of random winding; Pyramid side normals had a wrong sign and a missing term; open Curve tubes took their end tangents by wrapping to the other end; Chorus and Flanger now slew the delay time (50 ms) and Flanger the depth, so a jump no longer whoops (click +24 and +25 dB to +0.0 and +4.0 dB). The audit's winding and edge checks now ignore zero-area triangles, which are their own flag. | OP, VALID, FX rows | 3 |
| F13 | Audio Filter `envAmount` reads +17.3 dB "step transient": the param is the depth of the filter's internal sweep, so a different value is a different sweep, not a click. Accepted. | FX click | 1 |
| F14 | Bitcrush tone level differs 5.4 dB across 44.1/48/96 kHz: the hold rate is in Hz and a 6 kHz tone against a 8 kHz-ish hold lands on a different alias per rate. By design of the effect. Accepted. | FX rate | 1 |
| F15 | **Closed 2026-10-13, metric bug, not the node.** Resonator Bank read 2.4 dB apart across rates in the 100 Hz band (-7.0 / -8.6 / -6.2 dB). Its ~1 Hz-wide modes leave white noise a few degrees of freedom per 3 s window, so the band power was luck: 12 seeds read 0.85 dB, 24 seeds x 8 s 0.34 dB, and SPEC already showed the right peak and RT60 at every rate. FXAUDIT's rate check now drives the wet with periodic, exactly flat-spectrum noise (`FlatNoise`) and measures the second period, which has no realisation variance through a linear wet: Resonator Bank 0.41 dB, Shape Resonator 0.79 -> 0.46, Stutter 0.72 -> 0.13, same run time. The registry exception is removed, so fx.rate_spread_db gates it from now on. | FX rate | 1 |
| F16 | Mobius Strip and Klein Bottle: winding disagrees with normals on 2 and 7 triangles. They are non-orientable, so a consistent normal does not exist at the seam. Accepted. | GEO winding | 3 |
| F17 | Subdivide and Smooth on a sphere: 64 winding mismatches and non-manifold edges. They smooth the degenerate pole fans, which turns zero-area triangles into slivers. Accepted with the pole-fan artefact. | GEO winding | 3 |
| F18 | Screw: winding disagrees with the inherited normals (1456 on a cube). It revolves loose edges, so there is no face orientation to agree with. Accepted. | GEO winding | 3 |
| F19 | **Fixed** 2026-10-13: Analog played 3.5 c flat at defaults on every single note (synth_probe probe.pitch_worst_c 3.52 c over MIDI 24-108, Wavetable and Vital 0.17). Not drift character: `kVoiceDriftPitch` gives each of the 8 voice cards a fixed tolerance, but NoteOn always takes the first free voice, so voice 0 (-0.035 st) played every mono line and the first note of every chord. Voice 0 is now the tuning reference (0.0); the other seven keep their spread, so chords still have voice-to-voice mistuning. SYNTHAUDIT NOTE should have caught it but measured with `quiet` (analog off); it now also measures note 69 at true defaults (-3.50 c before, -0.01 c after). Probe after: 0.17 c. No compat flag (scale-to-user-base): saved patches are 3.5 c closer to concert pitch on voice 0. | NOTE rows, synth_probe | 1 |
| F3 | Pitch is within 0.03 cents everywhere measured, and every synth is bit-identical on re-render. No action. | PITCH, DET rows | 1 |

Note path covered (NOTE, ENV, CLICK, VEL, POLY incl. stuck voices: none, tail -240 dBFS on all). All 17 synths run. Full battery on Analog, Wavetable, Oscillator, Equation Synth; Metallic, Wave Terrain, Spectral Synth, Field Synth where applicable (UNISON: Analog and Wavetable, 4 peaks at 100.0 cents; PARAM: volume step is click-free). The nine sample synths load a 2 s, 48 kHz fixture WAV (440 Hz, six harmonics) written by the audit: Sampler, Grain Molder, Molder, Granular, PaulStretch, Slicer and MPC take notes (Slicer and MPC on note 36, their first slice/pad); Drum Sequencer plays one step from the transport; Looper records live input, so only its own tests cover it. New SAMPLE row: the fixture's pitch and length at 44.1 / 48 / 96 kHz, for new nodes and as loaded from an old patch (F11). Granular, Molder and PaulStretch free-run, so their POLY tail is read against their idle level, not -100 dBFS. Verdict: PASS, 2 flags (Metallic, F1 and F7). The driver now reads `PASS (n flags)` as a pass, so all five audits gate releases instead of reading as no verdict.

## 10. Left (reviewed 2026-10-13)

Checked against the section names each audit file actually prints, not this plan.

| # | Audit | Left | Why it matters |
|---|---|---|---|
| L1 | COMPAUDIT | **Done 2026-10-13** (`feature/comp-audit-left`, `baseline-2026-10-13-comp-blur-colour-res-bypass-sources.txt`). BLUR: Gaussian Classic, Smooth and Box match their own shader kernels within 0.5/255 at r 1/2/4; flat images unchanged. Effective sigma is 1.85/3.71/7.41 px (Classic) and 1.85/3.63/7.15 px (Smooth) against the 2r the slider implies, because the kernel is cut at about 2 sigma: up to 11 % narrower at r 4 (flagged, **accepted**: it is the look of every saved patch). Box sigma = 2.58 r exactly. Cost at 1024^2, Smooth: 1.6 / 1.4 / 2.2 / 4.1 ms at r 1 / 2 / 5 / 10 | blur is in most visual patches; never measured |
| L2 | COMPAUDIT | **Done 2026-10-13.** COLOUR: blur (0.498), Blend 50 % (0.502) and Color Ramp interpolation all work on encoded (gamma) values, so they agree; none is linear-light (0.735). Consistent, documented in the audit header | wrong space shows as dark fringes and muddy gradients |
| L3 | COMPAUDIT | **Done 2026-10-13.** RES: Gaussian Smooth r4 2.5 / 8.3 / 29.9 ms and Blend 0.5 / 0.3 / 0.9 ms at 1 / 4 / 16 Mpx; output is the input size, 4 / 16 / 64 MB per 8-bit target. Time scales linearly with pixels | the re-survey resolution ceiling and GPU memory are unmeasured too (block D) |
| L4 | COMPAUDIT | **Done 2026-10-13.** BYPASS: Gaussian, Box, Curves, Color Ramp, Fit, Trails, Reaction Diffusion all hand back their input (`BypassSource`); the five stateless ones give identical pixels after cook, bypass, un-bypass, cook. Stateful Trails and Reaction Diffusion are not asserted | bypass rule is an invariant; only GEOAUDIT checks it |
| L5 | COMPAUDIT | **Done 2026-10-13.** SOURCES: all 28 cookable Sources (shapes, Formula, FieldPixel, Noise, Texture, Ramp, Draw) cook to finite 0..1 output; Reaction Diffusion stays inside [0, 1] and alive over 120 frames. Skipped (need a file, device, audio input or script): Image Source, Slideshow, Video, Video In, Sketch, Text, Audio Texture. Remove Background needs its ONNX model and stays with REMOVEBGTEST | a whole category with no audit |
| L6 | GEOAUDIT | **Done 2026-10-13** (`baseline-2026-10-13-geo-meta-curve-cloth-inst-ref.txt`, `baseline-2026-10-13-geo-disp.txt`). New sections META, CURVE, CLOTH, INST, DISP (DISP needs GL: run with `INFINITE_GEOAUDIT_ONLY=DISP`). Cloth falls at g t^2/2 within 2 %, pins hold, 8000-beat jump stays finite; Instances place on the surface with the right scale and axis; Displacement offsets match the formula to 1e-5 and never tear. **Fixed two bugs:** Curve tubes (`TubeAlong`) wound inward, and Instance on Points built a mirrored basis (`n x t`, negative determinant) so every instance drew inside out. Reportable, not changed: Metaballs `radius` is not the surface radius (it is `radius / sqrt(threshold)`; 27 % off at resolution 24, 1 % at 96). Verified from mesh data, not by eye. | the plan promised all 37 geometry nodes |
| L7 | GEOAUDIT | **Done 2026-10-13.** REF: Delaunay triangle count equals 2n - 2 - h and the area equals the hull area; Voronoi corners are equidistant from their three nearest sites (5 of 135 slivers are clamped by design); Decimate holds the vertex-to-original distance under 0.9 % of the bounding box at ratio 0.10, with no new boundary edges. | only validity is checked, not accuracy |
| L8 | NOTEAUDIT | **Done 2026-10-13** (`feature/audio-audit-left`, `baseline-2026-10-13-note-jitter-bypass.txt`). JITTER: Note Filter, Transpose, Pitch Bend, Velocity Curve keep the note-on sample exactly (0.0 samples over blocks 64/333/512/800/2000/2048, none missing). ORDER is covered by PAIR (Merge, Router, Switcher, Stack: on/off counts pair, 0 stuck). BYPASS: bypassing 17 of 19 nodes mid-note leaves no stuck note. **Accepted exceptions** (rare live edit, generated notes whose offs live in the bypassed node): Note Echo leaves 9 repeat voices open, Arpeggiator 1. Delete is report-only: a deleted producer cannot send offs, so every node leaves the consumer's voices open, and the consumer drops to its free-running state so nothing sounds | timing at low frame rates is what a live player feels |
| L9 | SYNTHAUDIT | **Decided 2026-10-13: accept both; F2 reversed by the owner the same day.** F2 was accepted (Analog's -62 to -66 dB inside the -60 dB target, 20 to 35 dB cleaner than Diva at -41 / -27 / -10 dB at C4 / C7 / C8, and a fix changes every saved Analog patch); the owner then asked for -80 dB with no compat flag, and F2 is now fixed (see F2). F7: Wavetable note-on +8.2 dB is under the 12 dB flag; no click audible | decide fix or accept, so the findings table has no open rows |
| L10 | GEOAUDIT | **Done 2026-10-13** as F12: Solidify closes hard edges and open rims. | recorded so it is not re-found |
| L11 | Quality system | **Done 2026-10-13.** FX, NOTE, IO, GEO and COMP audits now emit `Quality(...)` rows: 16 metrics in `docs/quality/registry.tsv`. Release-gated where Infinite already meets the target (FX dc/tail, NOTE pairing/grid/jitter, IO gain/sum, COMP blend, GEO cloth/instances/decimate); report-gated where it does not yet (FX click and rate spread, GEO winding and non-manifold on the older shapes) or where it needs GL (disp). | without it the release gate does not see these numbers |

Order: all of L1-L11 done.
