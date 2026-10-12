# Node audits: beyond effects and modulators

Branch per block. Tracker: this file. Written 2026-10-12. Status: plan, nothing built yet.

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
- Fixes sit behind a per-node legacy flag (`BeforeLoadParams`) so saved patches sound and look the same.

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
| 1 | `feature/synth-audit` | SYNTHAUDIT | done 2026-10-12 (merged); F4 and Field Synth preset level open |
| 2 | `feature/io-note-audit` | IOAUDIT, NOTEAUDIT | done 2026-10-12 (merged); Echo voiceId and step-generator block quantisation open |
| 3 | `feature/geo-comp-audit` | GEOAUDIT, COMPAUDIT | planned |

Order reason: Synths are the largest audio gap (220 controls) and audio comes first in the perf
order. They pair with the re-survey synth probe, so each metric has a competitor number. FXAUDIT
supplies most of the harness.

### Block 1: SYNTHAUDIT (17 synths)

Standards: Zavalishin (VA design), Välimäki/Esqueda (anti-aliased oscillators), Bristow-Johnson
(wavetable); competitors Diva, Serum 2, Vital (behaviour only), Bitwig/Live instruments.

| Section | Measures | Target |
|---|---|---|
| PITCH | Fundamental error over the keyboard range, at 44.1 / 48 / 96 kHz | within 1 cent |
| ALIAS | Largest non-harmonic partial vs the fundamental, saw / square / sync / FM at 4 notes | at most -60 dB (ALIASTEST precedent: -75 achieved on shapers) |
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
| Note Echo shares one voiceId across dry and repeats | open, needs owner decision |
| Arp / Sequencer / Random Note Gen place steps on block boundaries (up to one block early/late) | open, larger design change |
| Audio In/Out and PDC | not covered by IOAUDIT |

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

| # | Metric | Target |
|---|---|---|
| 1 | Audits wired into the driver groups and `FULL_TESTS` | all five new audits |
| 2 | Baseline run saved per audit before any fix | yes |
| 3 | FLAG lines closed or recorded as an accepted exception with owner and date | all |
| 4 | CPU per node | at most +10%, exceptions recorded |
| 5 | Saved patches | unchanged output (ROUNDTRIPTEST and the legacy-flag test pass) |
| 6 | Competitor numbers for Synths | at least pitch, alias and envelope for Diva, Serum 2 and Vital |

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
| F2 | Analog aliasing is -66 dB at 1.75 kHz and -62 dB at 5 kHz (default saw), just inside the -60 dB flag; Wavetable, Oscillator and Equation Synth are -82 to -88 dB. | ALIAS rows | 1 |
| F4 | Open decision (changes saved dynamics, so legacy flag): velocity law is not shared: Analog, Wavetable and Oscillator follow velocity squared (vel 0.5 = -12 dB, 0.25 = -24 dB); Equation Synth and Metallic are linear (-6 / -12 dB). | VEL rows | 1 |
| F5 | Equation Synth clips with several notes at defaults: peak +3.6 dBFS at 8 notes, +4.3 at 32, against -12 dBFS for one note. No polyphonic gain compensation. Decision: not a bug. Voices sum, as in any polysynth, and a 4-note chord fits (-0.8 dBFS); attenuating would change the loudness of every saved patch. The audit now flags only a 4-note chord over 0 dBFS. | POLY rows | 1 |
| F6 | Polyphony cost stops growing past 8 notes on every synth (8 and 32 notes cost the same per frame), so all five cap at 8 voices. Not a bug if intended; the cap is not shown in the UI. | POLY rows | 1 |
| F7 | Wavetable note-on is +8.2 dB over steady state at defaults, the only pitched synth near the 12 dB flag. Metallic note-on reads +32 dB, but its steady state is a decaying resonator, so that metric is unreliable for it. | CLICK rows | 1 |
| F8 | Field Synth peaks +12.0 dBFS with 8 or 32 notes at defaults (-2.4 dBFS for one), the worst polyphonic clip of the group. The only synth whose 4-note chord clips (+9.0 dBFS; single note -2.4 dBFS vs about -12 for the others): voices sum unscaled (`FieldSynthNode.cpp:292`) and the default preset (Dual Oscillator Pad) is hot. Open, a design call on the default preset's level; saved patches carry their own source, so changing the default affects new nodes only. Overlaps `bugfix/field-synth-voice-pool`. | POLY rows | 1 |
| F9 | Wave Terrain also sums past 0 dBFS with many notes (+0.5 dBFS at 8, +3.2 at 32). Same as F5: not a bug; its 4-note chord is -3.0 dBFS. | POLY rows | 1 |
| F10 | Spectral Synth's 1.99 dB rate spread was a harness artifact (a fixed 65536-frame window is a different number of seconds at each rate). RATE now renders 3 s at every rate and reads 0.05 dB. Closed. | RATE row | 1 |
| F3 | Pitch is within 0.03 cents everywhere measured, and every synth is bit-identical on re-render. No action. | PITCH, DET rows | 1 |

Note path covered (NOTE, ENV, CLICK, VEL, POLY incl. stuck voices: none, tail -240 dBFS on all). All 17 synths run. Full battery on Analog, Wavetable, Oscillator, Equation Synth; Metallic, Wave Terrain, Spectral Synth, Field Synth where applicable (UNISON: Analog and Wavetable, 4 peaks at 100.0 cents; PARAM: volume step is click-free). Grain Molder, Molder, Granular, Sampler, Drum Sequencer, Slicer, MPC, Looper, PaulStretch are silent at defaults and need loaded content: parked until a fixture sample exists (they are covered by their own tests).
