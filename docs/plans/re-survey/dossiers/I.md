# I Ableton Live 12 devices and models: dossier

Status: done 2026-10-13 from public XML schema `12.0_12402.txt` within the installed Live 12 Suite bundle. Zero binary decompilation. Lint: `python3 tools/re-survey/diff.py lint docs/plans/re-survey/dossiers/I.md`

## 1. What it is

- Complete architectural deconstruction of all 103 native device models, 67 DSP sub-components, and 24 generative MIDI transform algorithms in Ableton Live 12 Suite.
- Reference app: Ableton Live 12 Suite (installed on macOS at `/Applications/Ableton Live 12 Suite.app`). Proprietary commercial licence.
- Data source: Live 12 native schema file `Contents/App-Resources/Schema/12.0_12402.txt` (412 XML class definitions).
- Scope: 17 Instruments, 13 Saturation/Color devices, 5 Dynamics processors, 5 Filter/EQ models, 6 Time/Delay devices, 3 Space/Reverb devices, 12 Modulation/Pitch processors, 2 Spectral resynthesis devices, 6 Utility/Analysis modules, 8 MIDI effects, 14 Racks/Containers, and 12 internal test/diagnostic engines.

## 2. Method

- Tools run: `python3 tools/re-survey/ableton_schema_extractor.py run` (passes `--self-test`).
- Clean-room invariant: XML schema tag, attribute and type inspection only. No Mach-O binary disassembled, no memory dumped, no reverse-engineered algorithms kept.
- Output artifacts: Machine dataset `~/re-output/ableton/ableton_all_models.json` (1.4 MB) and markdown dossier `~/re-output/ableton/ableton_all_models.md` (117 KB). Deep architectural blueprint at `docs/plans/re-survey/ABLETON-ALL-MODELS-MAPPING.md`.

## 3. Pillar map

- P5: Instruments (17). Live 12 introduces Meld (bi-timbral macro synth with 156 fields and wave transformers) and Drift (103 fields, analog drift instability, per-oscillator filter bypass, cycling function generator). Existing flagships: Wavetable (134 fields), Operator (4-op FM, 11 algorithms), Collision (modal percussion physical modeling), Tension (string physical modeling), Electric (electric piano modeling), Sampler, and Simpler. Infinite has 17 synths: subtractive (Analog), wavetable, sampling (Sampler, Slicer, MPC, Granular), modal (Metallic), spectral, plus Field Synth for user DSP kernels; FM is a patch (Oscillator `fm in`), not a 4-operator synth.
- P5: Saturation & Color (13). Live 12 introduces Roar (263 fields, 3 saturation stages, 5 routing topologies including serial/parallel/mid-side/multiband, feedback delay matrix, and 4-source mod matrix). Other processors: Drum Buss (transient shaper + sub-boom generator), Saturator (7 transfer curves), Pedal (OD/Dist/Fuzz stompbox), Amp/Cabinet (AAS physical modeling), Dynamic Tube, Vinyl Distortion, and Redux. Infinite has Drive (one oversampled tanh stage), Wavetable Shaper and Bitcrush; Roar's multi-stage routing and Drum Buss's sub-boom are key targets.
- P5: Dynamics (5). Compressor (Peak/RMS/Log + Cytomic release + expander), Glue Compressor (Cytomic SSL 4000 G-Master bus compressor), Multiband Dynamics (3-band upward/downward compressor/expander), Gate (lookahead + ducking), and Limiter (brickwall lookahead). Infinite provides Dynamics (peak/RMS, opto-like Analog mode, sidechain) and Limiter; no multiband dynamics, no gate node.
- P5: Filter & EQ (5). Auto Filter (Cytomic analog filter circuits Clean, SMP, OSR, MS2, PRD), EQ Eight (8-band parametric with Cytomic oversampling and mid/side mode), Channel EQ, and EQ Three. Infinite provides EQ (5 matched biquad bands) and Audio Filter (TPT SVF); no circuit models, no mid/side EQ.
- P5: Time, Space & Spectral (11). Echo (dual modulated tape delay with wobble, ducking, and diffusion), Hybrid Reverb (zero-latency IR convolution + 5 algorithmic engines), Spectral Time (FFT spectral delay and freeze), and Spectral Resonator (FFT modal comb resonator). Infinite provides Reverb (16-line FDN), Delay (with duck) and Spec Blur; no IR reverb (`convolve` is an image filter).
- P2: Modulation & Pitch (12). Auto Shift (real-time pitch tracking, formant follower, scale quantizer, and polyphonic MIDI harmonizer), Shifter, Chorus-Ensemble, and Phaser-Flanger. Infinite has Pitch Shifter, Key-Snap, Frequency Shifter, Chorus, Phaser, Flanger; no pitch-tracking harmonizer.
- P1: Generative MIDI Tools (24 algorithms). Live 12 introduces clip-level generative algorithms (ArpeggiateAlgorithm, LfoAlgorithm, VelocityFilterAlgorithm, TimeWarpAlgorithm, ScaleFilterAlgorithm). Infinite covers real-time node-based generation via 24 Notes nodes.

## 4. Comparison

| Pillar | Their feature | Infinite equivalent | Status | Outcome | Evidence |
|---|---|---|---|---|---|
| P5 | Roar: 3-stage saturator with 5 routing modes & feedback | none | gap | ignore: Drive (one tanh stage); a Roar-style patch template (Drive → Audio Filter → Drive with Feedback) comes before any new node; see ABLETON-GAPS-AND-OUTPACE.md | `~/re-output/ableton/ableton_all_models.json` |
| P5 | Meld: Bi-timbral macro oscillator with wave transformers | none | gap | ignore: Field Synth; a Field Synth kernel can build a macro oscillator; no native node | `~/re-output/ableton/ableton_all_models.json` |
| P5 | Drift: Subtractive synth with analog drift & cycling env | none | gap | ignore: Analog (Infinite's Drift is a Prediction node); Analog covers subtractive; no cycling envelope | `~/re-output/ableton/ableton_all_models.json` |
| P5 | Wavetable: Dual morphing wavetable synth with dual filters | `src/nodes/WavetableNode.h` | parity | ignore: Wavetable (two engines over one voice allocator, per-engine filter); two morphing engines with unison and filters | `src/nodes/WavetableNode.h` |
| P5 | Operator: 4-operator FM / additive synth | `src/nodes/OscillatorNode.h` | gap | ignore: Oscillator fm in (phase or through-zero FM); Analog osc 2 → osc 1 FM; 2-operator FM is a patch; no 4-operator synth with per-operator envelopes | `src/nodes/OscillatorNode.h` |
| P5 | Hybrid Reverb: Convolution blended with 5 algorithmic engines | none | gap | quality-gap: Reverb (16-line FDN); no IR reverb (convolve is an image filter); IR convolution reverb is v0.6 (docs/plans/v0.6-quality/README.md) | `~/re-output/ableton/ableton_all_models.json` |
| P5 | Echo: Tape delay with ducking, wobble, and reverb | `src/audio/EffectDefs.cpp` | gap | ignore: Delay: time, tone, feedback, pan, duck, bounce; ducking matches; no wobble or built-in reverb | `src/audio/EffectDefs.cpp` |
| P5 | Glue Compressor: SSL-style VCA bus compressor | `src/audio/EffectDefs.cpp` | gap | ignore: Dynamics: peak/RMS plus an opto-like Analog mode; clean compression covered; no VCA bus character | `src/audio/EffectDefs.cpp` |
| P5 | Auto Filter: Cytomic analog circuit models (SMP, OSR, MS2, PRD) | none | gap | ignore: Audio Filter (TPT SVF); no nonlinear circuit models | `~/re-output/ableton/ableton_all_models.json` |
| P2 | Auto Shift: Real-time pitch tracking & formant harmonizer | none | gap | ignore: Pitch Shifter (time-domain splice), Key-Snap; no pitch-tracking harmonizer; formant shift parked | `~/re-output/ableton/ableton_all_models.json` |
| P1 | Live 12 MIDI Transform & Generate algorithms (24 classes) | `src/nodes/NoteNodes.h` | parity | ignore: 24 Notes nodes (Chorder, Note Strum, Humanizer, Random Note Generator, Arpeggiator ...); transforms and generators run live on the canvas rather than as clip edits | `src/nodes/NoteNodes.h` |
| P5 | VST3 and Audio Unit 64-bit plugin hosting | `src/nodes/AudioPluginNode.h` | parity | ignore: Plugin (VST3 + AU); Live hosts both too; mapped plugin params take Infinite's modulators | `src/nodes/AudioPluginNode.h` |

## 5. Measurements

- Native Device Models cataloged: 103 (17 Instruments, 48 Audio Effects, 16 MIDI Effects, 22 Racks/Utilities/Internal).
- Total direct model fields and parameters: 5,243.
- Modulatable / DSP parameters: 1,842.
- DSP Sub-components cataloged: 67 (651 fields).
- Generative MIDI Algorithms cataloged: 24 (173 fields).
- Reproduce command: `python3 tools/re-survey/ableton_schema_extractor.py run --out ~/re-output/ableton/ableton_all_models.md`.

## 6. Outcomes

- Quests: none (IR reverb, ADAA and the stretch work are in docs/plans/v0.6-quality/README.md).
- Perf targets: none.
- Quality gaps: IR convolution reverb (v0.6). Roar is a patch template first (ABLETON-GAPS-AND-OUTPACE.md); Meld and Drift are ignored until a user asks.
- Ignored, with reason: AAS legacy physical modeling emulations (Collision, Tension, Electric, Amp, Cabinet) are proprietary third-party modules; Infinite has Metallic and Resonator Bank for modal sounds; no string model.

## 7. Storage

- Written to ~/re-output:
  - `~/re-output/ableton/ableton_all_models.json` (1.4 MB)
  - `~/re-output/ableton/ableton_all_models.md` (117 KB)
  - `~/re-output/ableton/ableton_live_map.json` (1.5 KB)
  - `~/re-output/ableton/ableton_live_map.md` (5.3 KB)
- Deleted: zero temporary files retained; clean-room memory state verified.
