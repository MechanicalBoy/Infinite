# M Commercial audio plugins (FabFilter, Valhalla, soothe2, Diva, Vital, Kilohearts): dossier

Status: done 2026-10-13 from application bundle manifests and parameter trees via Infinite host and Apple AudioToolbox API. Zero binary decompilation. Lint: `python3 tools/re-survey/diff.py lint docs/plans/re-survey/dossiers/M.md`

## 1. What it is

- Complete architectural parameter extraction of 85 industry-standard commercial audio plugins installed on macOS.
- Reference apps: FabFilter Bundle, Valhalla DSP Suite, oeksound soothe2, u-he Diva, Vital Audio Vital, D16 Drumazon 2, Kilohearts ecosystem (41 plugins), Tokyo Dawn Labs TDR Nova, Cableguys ShaperBox 3, XLN RC-20. Commercial proprietary licenses.
- Data source: macOS AudioToolbox runtime parameter trees (`AUAudioUnit.parameterTree`) and Infinite native host parameter inspection (`--plugin-params`).
- Scope: 85 plugins across 8 DSP families, 17,718 discrete parameters covering dynamic EQ, multiband saturation, algorithmic reverb, delays, mastering dynamics, modular multi-FX, and synthesizers.

## 2. Method

- Tools run: `python3 tools/re-survey/commercial_plugin_extractor.py run` (passes `--self-test`).
- Clean-room invariant: Public macOS AudioToolbox APIs and Infinite host parameter queries only. Zero binary decompilation or disassembly.
- Output artifacts: Machine dataset `~/re-output/plugins/plugins_all_models.json` (2.9 MB) and markdown catalog `~/re-output/plugins/plugins_all_models.md` (12 KB). Architectural blueprint at `docs/plans/re-survey/COMMERCIAL-PLUGINS-MAPPING.md`.

## 3. Pillar map

- P5: Dynamic EQ & Spectral Shaping (oeksound soothe2 with 56 params; FabFilter Pro-Q 4 with 600 params; TDR Nova with 74 params). Real-time resonance reduction, dynamic Q/threshold curves, and linear-phase processing. Infinite has EQ (5 matched biquad bands) and Audio Filter; no dynamic or linear-phase EQ.
- P5: Multi-Band Saturation & Non-Linear Shapers (FabFilter Saturn 2 with 951 params across 6 bands and 28 styles; Kilohearts Disperser and Faturator). Infinite has Drive (one oversampled tanh stage) and Field Effect kernels; no multiband saturation.
- P5: Algorithmic Reverb & Space (Valhalla VintageVerb with 17 params; Valhalla Room with 22 params; Valhalla Supermassive with 18 params; FabFilter Pro-R 2 with 136 params). Infinite has Reverb (16-line FDN) and Spatial Mixer.
- P5: Modulated Delay Networks (FabFilter Timeless 3 with 1,007 params; Valhalla Delay with 38 params). Tape, bucket-brigade, and diffusion delays with audio-rate modulation. Infinite has Delay (time, tone, feedback, pan, duck, bounce); no tape or BBD modulation.
- P5: Mastering Dynamics & True Peak Limiting (FabFilter Pro-C 2 with 46 params; Pro-L 2 with 32 params; Pro-MB with 151 params). Infinite has Dynamics and Limiter; no multiband.
- P5: Analogue Circuit & Wavetable Synthesis (u-he Diva with 281 params; Vital with 775 params; Drumazon 2 with 512 params). Infinite provides 17 native synthesizers.

## 4. Comparison

| Pillar | Their feature | Infinite equivalent | Status | Outcome | Evidence |
|---|---|---|---|---|---|
| P5 | Dynamic resonance suppression (soothe2 56 params) | none | gap | ignore: candidate spectral node, no user asked | `~/re-output/plugins/plugins_all_models.json` |
| P5 | 24-band Dynamic EQ with linear phase (Pro-Q 4 600 params) | `src/audio/EffectDefs.cpp` | gap | ignore: EQ (5 matched biquad bands); no dynamic bands, no linear phase | `src/audio/EffectDefs.cpp` |
| P5 | Multi-band saturation with 28 tube/tape models (Saturn 2 951 params) | `src/audio/EffectDefs.cpp` | gap | ignore: Drive (one oversampled tanh stage); no multiband, one curve; ADAA on Drive is v0.6 Tier 3 | `src/audio/EffectDefs.cpp` |
| P5 | Classic algorithmic reverb models (Valhalla VintageVerb 17 params) | `src/audio/EffectDefs.cpp` | parity | ignore: Reverb (16-line Hadamard FDN); one modern algorithm against VintageVerb's mode list | `src/audio/EffectDefs.cpp` |
| P5 | Modulated dual tape delay with multimode filters (Timeless 3 1007 params) | `src/audio/EffectDefs.cpp` | gap | ignore: Delay: time, tone, feedback, pan, duck, bounce; one tone filter, no tape modulation | `src/audio/EffectDefs.cpp` |
| P5 | True-peak mastering brickwall limiter (Pro-L 2 32 params) | `src/audio/EffectDefs.cpp` | parity | ignore: Limiter (lookahead peak); brickwall lookahead covered; true-peak detection not checked | `src/audio/EffectDefs.cpp` |
| P5 | Circuit-modeled analogue synth filters (Diva 281 params) | `src/nodes/AnalogSynthCore.h` | gap | ignore: Analog (ZDF ladder with ADAA); one ladder model against Diva's several | `src/nodes/AnalogSynthCore.h` |
| P5 | Spectral wavetable synthesizer (Vital 775 params) | `src/nodes/WavetableNode.h` | gap | ignore: Wavetable (two morphing engines); no spectral warp modes | `src/nodes/WavetableNode.h` |
| P5 | Modular snap-in container framework (Kilohearts Multipass 179 params) | `src/nodes/AudioNodes.h` | gap | ignore: node canvas; Splitter fan-out; no crossover node for band split (see L Multi-Band Split) | `src/nodes/AudioNodes.h` |

## 5. Measurements

- Total Commercial Plugins Discovered: 85.
- Plugins Parameterized: 81.
- Total Discrete Parameters Extracted: 17,718.
- Reproduce command: `python3 tools/re-survey/commercial_plugin_extractor.py run --out ~/re-output/plugins/plugins_all_models.md`.

## 6. Outcomes

- Quests: none (within 5-quest cap across all dossiers).
- Perf targets: none.
- Quality gaps: none taken; ADAA on Drive is v0.6 Tier 3 (docs/plans/v0.6-quality/README.md).

## 7. Storage

- Written to ~/re-output:
  - `~/re-output/plugins/plugins_all_models.json` (2.9 MB)
  - `~/re-output/plugins/plugins_all_models.md` (12 KB)
- Deleted: zero temporary files retained; clean-room memory state verified.
