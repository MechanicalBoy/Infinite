# K Apple Logic Pro: dossier

Status: done 2026-10-13 from framework resource manifests in `/Applications/Logic Pro Creator Studio.app/Contents/Frameworks/MADSP.framework/`. Zero binary decompilation. Lint: `python3 tools/re-survey/diff.py lint docs/plans/re-survey/dossiers/K.md`

## 1. What it is

- Complete architectural deconstruction of all 127 native device models and 10,070 parameters in Apple Logic Pro.
- Reference app: Apple Logic Pro (installed on macOS at `/Applications/Logic Pro Creator Studio.app`). Proprietary commercial licence.
- Data source: Logic Pro native framework resources `MADSP.framework/Versions/A/Resources/*.plist` (130 plists) and `MAAlchemy.framework`.
- Scope: 19 Instruments, 15 Dynamics/Color devices, 10 Filter/EQ models, 12 Space/Delay devices, 17 Modulation/Pitch processors, 38 Guitar/Amp/Pedalboard models, 7 MIDI processors, and 9 utility engines.

## 2. Method

- Tools run: `python3 tools/re-survey/logic_extractor.py run` (passes `--self-test`).
- Clean-room invariant: Framework resource plists, control type declarations, and parameter ID manifests only. Zero binary code disassembly or decompilation.
- Output artifacts: Machine dataset `~/re-output/logic/logic_all_models.json` (1.4 MB) and markdown dossier `~/re-output/logic/logic_all_models.md` (55 KB). Technical architectural blueprint at `docs/plans/re-survey/LOGIC-ALL-MODELS-MAPPING.md`.

## 3. Pillar map

- P5: Monster Synthesizer Architecture (`Alchemy`: 6,962 parameters). Quad-engine additive, spectral, granular, and virtual analog synthesis with 8-way XY morphing and 16 modulation sources. Infinite covers subtractive, wavetable, spectral, granular and sampling as separate nodes, with Field Synth for user-written kernels (bytecode VM); no 4-way morph.
- P5: Physical Modeling (`Sculpture`: 368 parameters). Component-level string synthesis simulating material properties (Nylon, Wood, Steel, Glass), 3 exciter models (Strike, Pluck, Bow), and dual boundary disrupters. Infinite has Metallic and Resonator Bank (modal); no string model.
- P5: Convolution Reverb (`Space Designer`: 97 parameters). True-stereo zero-latency impulse response processor with envelope shaping. Infinite has no IR reverb: `convolve` is an image kernel filter, and the audio Reverb is a 16-line FDN (`src/audio/dsp/ReverbKernel.h`).
- P5: Analog Circuit Compressor (`Compressor`: 35 parameters, 7 circuit models). Emulates Platinum Digital, Studio VCA (Focusrite), Studio FET (1176 Blackface), Vintage VCA (DBX 160), Vintage FET (1176 Bluestripe), Vintage Opto (LA-2A), and Classic VCA (Neve 33609). Infinite has Dynamics (peak/RMS, opto-like Analog mode, sidechain); no FET or VCA models.
- P5: Vintage Equalizer Collection (`Vintage Tube EQ`, `Vintage Console EQ`, `Vintage Graphic EQ`). Pultec passive tube, Neve 1073 console, and API 560 proportional-Q models. Infinite has EQ (5 matched biquad bands); no analog models, no graphic EQ.
- P5: Algorithmic Spatial Acoustics (`ChromaVerb`: 58 parameters). 14 acoustic room models with frequency-dependent decay time multipliers. Infinite has Reverb, a 16-line Hadamard FDN with one damping one-pole; no frequency-dependent decay.
- P2: Global Modulation & MIDI Effects (7 processors). Arpeggiator, Chord Trigger, Modifier, Note Repeater, Velocity Processor. Infinite's 24 Notes nodes include Arpeggiator, Chorder, Note Echo, Velocity Curve and Quantizer.

## 4. Comparison

| Pillar | Their feature | Infinite equivalent | Status | Outcome | Evidence |
|---|---|---|---|---|---|
| P5 | Alchemy: Quad spectral, additive, granular & VA morph synth | none | gap | ignore: Spectral Synth, Granular, Analog, Field Synth; the engines exist as separate nodes; no 4-way morph | `~/re-output/logic/logic_all_models.json` |
| P5 | Sculpture: Component-level string physical modeling (368 params) | none | gap | ignore: Metallic, Resonator Bank; struck/modal sounds covered; no string model | `~/re-output/logic/logic_all_models.json` |
| P5 | Space Designer: True-stereo zero-latency IR convolution | none | gap | quality-gap: convolve is an image filter; IR convolution reverb is v0.6 (docs/plans/v0.6-quality/README.md) | `src/core/FilterDefs.cpp` |
| P5 | Compressor: 7 analog circuit models (Opto, FET, VCA) | `src/audio/EffectDefs.cpp` | gap | ignore: Dynamics: peak/RMS plus an opto-like Analog mode; one clean model and one opto-like; no FET/VCA character | `src/audio/EffectDefs.cpp` |
| P5 | Vintage EQ Collection: Pultec, Neve 1073, API 560 models | none | gap | ignore: EQ (5 matched biquad bands); clean curves only; no analog models | `~/re-output/logic/logic_all_models.json` |
| P5 | ChromaVerb: 14 acoustic spaces with decay EQ spectrum | `src/audio/EffectDefs.cpp` | gap | ignore: Reverb (16-line Hadamard FDN, one damping filter); no multi-band decay EQ or room models | `src/audio/EffectDefs.cpp` |
| P5 | Phat FX: Multi-stage distortion, filter, and bass processor | `src/audio/EffectDefs.cpp` | parity | ignore: Drive, Audio Filter, Bitcrush chained; the same chain is a patch | `src/audio/EffectDefs.cpp` |
| P2 | Arpeggiator: Pattern generator with groove and velocity | `src/nodes/NoteNodes.h` | parity | ignore: Arpeggiator; pattern styles, rates and octaves | `src/nodes/NoteNodes.h` |
| P5 | VST3 and AU plugin hosting with full automation | `src/nodes/AudioPluginNode.h` | lead | ignore: Plugin (VST3 + AU); Logic hosts AU only; mapped plugin params take Infinite's modulators | `src/nodes/AudioPluginNode.h` |

## 5. Measurements

- Total Native Devices cataloged: 127.
- Total Parameters extracted: 10,070.
- Top devices: Alchemy (6,962), Drum Synth (410), Sculpture (368), ES2 (187), Vintage B3 (137), Space Designer (97), Retro Synth (84), Channel EQ (62), ChromaVerb (58), Multipressor (58), Phat FX (56).
- Reproduce command: `python3 tools/re-survey/logic_extractor.py run --out ~/re-output/logic/logic_all_models.md`.

## 6. Outcomes

- Quests: none (within 5-quest cap).
- Perf targets: none (Logic CPU not measured here; see dossier B).
- Quality gaps: IR convolution reverb (v0.6, docs/plans/v0.6-quality/README.md). Alchemy morphing and Sculpture are ignored until a user asks.

## 7. Storage

- Written to ~/re-output:
  - `~/re-output/logic/logic_all_models.json` (1.4 MB)
  - `~/re-output/logic/logic_all_models.md` (55 KB)
- Deleted: zero temporary files retained; clean-room memory state verified.
