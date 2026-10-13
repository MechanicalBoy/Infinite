# L Bitwig Studio: dossier

Status: done 2026-10-13 from application bundle manifests in `/Applications/Bitwig Studio.app/Contents/Resources/Library/`. Zero binary decompilation. Lint: `python3 tools/re-survey/diff.py lint docs/plans/re-survey/dossiers/L.md`

## 1. What it is

- Complete architectural deconstruction of all 232 Grid modules, 151 native devices, and 43 modulators in Bitwig Studio 6.
- Reference app: Bitwig Studio 6 (installed on macOS at `/Applications/Bitwig Studio.app`). Proprietary commercial licence.
- Data source: Bitwig Studio application resource manifests in `Contents/Resources/Library/` (232 `.bwmodule`, 151 `.bwdevice`, 43 `.bwmodulator`, and 249 device settings).
- Scope: 232 modular Grid sound design blocks across 15 families, 151 native instruments, audio effects, note effects, and split routers, plus 43 universal modulators.

## 2. Method

- Tools run: `python3 tools/re-survey/bitwig_extractor.py run` (passes `--self-test`).
- Clean-room invariant: Application resource manifests and module asset catalogs only. Zero Java bytecode or native binary decompilation.
- Output artifacts: Machine dataset `~/re-output/bitwig/bitwig_all_assets.json` (41 KB) and markdown catalog `~/re-output/bitwig/bitwig_all_assets.md` (4.9 KB). Architectural blueprint at `docs/plans/re-survey/BITWIG-ALL-MODELS-MAPPING.md`.

## 3. Pillar map

- P1: Modular Sound Design Environment (The Grid: 232 modules). Poly Grid (polyphonic synth), FX Grid (audio effect), and Note Grid (MIDI generator) provide visual block-based modular DSP. Modules span 15 families: Oscillators (10), Filters (13), Shapers (12), Envelopes (6), Delays (5), Phase (20), Math (16), Logic (16), Data (8), Random (5), Level (11), Pitch (10), I/O (22), Voice Stacking (3), Display (4). Infinite's Field Synth/Effect/Graph and the node canvas give modular DSP; Grid has more ready-made blocks.
- P2: Universal Modulation (43 modulators). ADSR, Curves, ParSeq-8, Audio Rate, HW CV In, Voice Stack, Expressions. Infinite has 30 Modulator nodes and the Prediction family (learned); no per-voice or audio-rate modulation (BITWIG-GAPS-AND-OUTPACE.md).
- P5: Native Instruments & Synthesizers (Polymer, Polysynth, Sampler, FM-4, Phase-4, Organ, Drum Machine, plus 31 analog drum voices across v0, v1, v8 TR-808, and v9 TR-909 models). Infinite has 17 synths (subtractive, wavetable, sampling, modal, spectral); no synthesized drum voices, FM only as a patch.
- P5: Multi-Band Split Routers (Freq Split, Harmonic Split, Loud Split, Mid-Side Split, Transient Split). Splitting audio by frequency, amplitude, or transients for parallel processing. Infinite's Splitter is a fan-out, not a crossover: no band, loudness or transient split.

## 4. Comparison

| Pillar | Their feature | Infinite equivalent | Status | Outcome | Evidence |
|---|---|---|---|---|---|
| P1 | The Grid: 232 modular audio blocks across 15 families | `src/nodes/FieldSynthNode.h` | parity | ignore: Field Synth, Field Effect, Field Graph + node canvas; text kernels plus the canvas give modular DSP; Grid has more ready blocks | `src/nodes/FieldSynthNode.h` |
| P2 | Universal Modulators (43 engines modulating any device knob) | `src/nodes/ModulatorNodes.h` | lead | ignore: 30 modulators; fewer modulators (map: 18 gaps), but one modulator reaches audio, 3D, shaders and plugin params | `src/nodes/ModulatorNodes.h` |
| P5 | Polymer: Hybrid modular synth assembling Grid blocks | `src/nodes/AnalogNode.h` | parity | ignore: Analog (oscillators, ZDF filter, envelopes); subtractive voice covered | `src/nodes/AnalogNode.h` |
| P5 | 31 Analog Drum Models (TR-808 v8 and TR-909 v9 series) | none | gap | ignore: Drum Sequencer (sample lanes); no synthesized drum voices | `~/re-output/bitwig/bitwig_all_assets.json` |
| P5 | Phase Engine: 20 phase-shaping synthesis modules | none | gap | ignore: Oscillator PM input, Cycle Shaper; no phase-distortion module set | `~/re-output/bitwig/bitwig_all_assets.json` |
| P5 | Multi-Band Split Routers (Freq, Loud, Transient Split) | `src/nodes/AudioNodes.h` | gap | ignore: Splitter is a fan-out, not a crossover; no band, loudness or transient split | `src/nodes/AudioNodes.h` |
| P5 | VST3 and CLAP plugin hosting with sandboxing | `src/nodes/AudioPluginNode.h` | gap | quality-gap: Plugin (VST3 + AU, in-process); no CLAP, no sandbox (a plugin crash takes the app down); crash-only fallback is v0.6 | `src/nodes/AudioPluginNode.h` |
| P1 | Live AV synthesis crossing audio and visual boundary | `src/nodes/FieldPixelNode.h` | lead | ignore: Field Synth, FieldPixel, Field Modifier; Bitwig is audio-only; one Field language runs in audio, pixels and geometry | `src/nodes/FieldPixelNode.h` |

## 5. Measurements

- Total Native Bitwig Assets: 426.
- The Grid Modules: 232 across 15 families.
- Native Devices: 151 (including 31 analog drum voices).
- Universal Modulators: 43.
- Reproduce command: `python3 tools/re-survey/bitwig_extractor.py run --out ~/re-output/bitwig/bitwig_all_assets.md`.

## 6. Outcomes

- Quests: none (per-voice and audio-rate modulation are in v0.6 Block 2, docs/plans/v0.6-quality/README.md).
- Perf targets: none (Bitwig CPU measured in dossier B).
- Quality gaps: plugin crash isolation (v0.6). Phase-4 style modules and 808/909 voices are ignored until a user asks.

## 7. Storage

- Written to ~/re-output:
  - `~/re-output/bitwig/bitwig_all_assets.json` (41 KB)
  - `~/re-output/bitwig/bitwig_all_assets.md` (4.9 KB)
- Deleted: zero temporary files retained; clean-room memory state verified.
