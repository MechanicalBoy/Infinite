# Commercial Audio Plugins — Complete Ecosystem & Parameter Architecture Mapping

> **Clean Room Invariant**: Extracted exclusively from public macOS AudioToolbox runtime manifests and observable parameter trees via Infinite's host (`--plugin-params`) and native Swift APIs (`AUAudioUnit.parameterTree`). Zero binary decompilation or disassembly. Complete machine-readable catalog available in `~/re-output/plugins/plugins_all_models.json` (2.9 MB) and `~/re-output/plugins/plugins_all_models.md` (12 KB).

---

> **Infinite side checked 2026-10-13** against the node census (`build/census/census.json`) and src/; run `python3 tools/re-survey/diff.py claims` after editing. Competitor numbers come from `~/re-output/`; competitor prose is hand-written.

## 1. Executive Summary & Inventory Scale

| Metric | Commercial Plugin Suite | Infinite Equivalent / Advantage |
|---|---|---|
| **Total Commercial Plugins Introspected** | **85 Plugins** | 28 audio effects + 17 synths (census) + Plugin node (VST3/AU host) |
| **Plugins Successfully Parameterized** | **81 Plugins** | Hosted plugin params are exposed on the Plugin node |
| **Total Discrete Parameters Extracted** | **17,718 Parameters** | Count only |
| **Primary Industry Vendors** | FabFilter, Valhalla DSP, oeksound, u-he, Kilohearts, Xfer, Vital, D16, Cableguys, TDR, XLN | Native C++ DSP in `src/audio/dsp/` |
| **Execution Domain** | Third-party DAW plugin format (AUv2/AUv3/VST3) | Built-in nodes + VST3/AU host |
| **Modulation Bandwidth** | Host automation at buffer/block boundaries | Frame-rate modulator values ramped per sample (ParamMailbox); not audio-rate, not per voice |

---

## 2. Functional DSP Family Breakdown

### 2.1 Dynamic EQ & Spectral Shaping (8 Plugins, 1,486 Parameters)
- **Flagship Models**:
  - **oeksound soothe2** (56 parameters): Dynamic resonance suppressor with `depth`, `selectivity`, `sharpness`, `attack`, `release`, and 5 parametric correction bands.
  - **FabFilter Pro-Q 4** (600 parameters) & **Pro-Q 3** (358 parameters): Mastering/mixing equalizers featuring 24 bands, dynamic EQ (`Dynamic Range`, `Threshold`), mid/side stereo placement, linear phase processing resolutions, and auto-gain.
  - **Tokyo Dawn Labs TDR Nova** (74 parameters): Parallel dynamic equalizer.
  - **Kilohearts Slice EQ** (198 parameters) & **Carve EQ** (4 parameters): Parametric precision & graphical curve EQs.
- **Infinite**: EQ (5 bands, matched biquads), Audio Filter, Spec Blur; no dynamic EQ and no resonance suppressor (gap).

### 2.2 Distortion & Multi-Band Saturation (12 Plugins, 1,910 Parameters)
- **Flagship Models**:
  - **FabFilter Saturn 2** (951 parameters): Up to 6 active bands across 28 saturation models (Clean Tube, Warm Tube, Broken Tube, Tape, Vintage Tape, British/American Drive, Rectifier, Bitcrush), dynamic companding, unrestricted feedback, and 50 modulation slots.
  - **Kilohearts Disperser** (5 parameters): All-pass phase rotation rotation.
  - **Kilohearts Faturator** (6 parameters): Non-linear waveshaping with dynamic color and stereo widening.
  - **Kilohearts Snap-ins**: `kHs Distortion`, `kHs Nonlinear Filter`, `kHs Shaper Table`, `kHs Bitcrush`.
- **Infinite**: Drive (tanh + bias, oversampled), Wavetable Shaper (8x oversampled), Bitcrush, Cycle Shaper; Field Effect for custom curves.

### 2.3 Reverb & Spatial Acoustics (10 Plugins, 349 Parameters)
- **Flagship Models**:
  - **Valhalla VintageVerb** (17 parameters): Algorithmic reverb inspired by classic 1970s and 1980s digital hardware (Concert Hall, Bright Hall, Plate, Room, Chamber, Random Space, Chorus Space, Sanctuary).
  - **Valhalla Room** (22 parameters) & **Valhalla Plate** (12 parameters): True stereo algorithmic reverberators.
  - **Valhalla Supermassive** (18 parameters): Complex feedback delay networks (Gemini, Hydra, Centaurus, Sagittarius, Great Annihilator).
  - **FabFilter Pro-R 2** (136 parameters): Natural acoustic space model with Decay Rate and Post-EQ curves.
- **Infinite**: Reverb (16-line Hadamard FDN); no IR convolution reverb (gap, v0.6 plan).

### 2.4 Delays & Modulated Echoes (7 Plugins, 1,816 Parameters)
- **Flagship Models**:
  - **FabFilter Timeless 3** (1,007 parameters): Dual-delay tape echo with 6 multimode filters, drive, pitch shifting, and 50 modulation slots.
  - **Valhalla Delay** (38 parameters): Tape, BBD, digital, pitch, and reverse delay models with diffusion and ratio controls.
  - **Valhalla FreqEcho** (6 parameters): Frequency shifter with feedback delay.
  - **Kilohearts Dual Delay** (12 parameters) & **kHs Delay** (11 parameters).
- **Infinite**: Delay, Note Echo, Stutter; no tape model and no grain delay.

### 2.5 Dynamics & Mastering Processors (11 Plugins, 342 Parameters)
- **Flagship Models**:
  - **FabFilter Pro-C 2** (46 parameters): 8 compression styles (Clean, Classic, Opto, Vocal, Mastering, Bus, Punch, Pumping) with lookahead and sidechain EQ.
  - **FabFilter Pro-L 2** (32 parameters): True Peak brickwall limiter with 8 limiting algorithms (Transparent, Punchy, Dynamic, Allround, Aggressive, Modern, Bus, Safe) and ITU-R BS.1770-4 loudness metering.
  - **FabFilter Pro-MB** (151 parameters): 6-band dynamic compressor/expander.
  - **Kilohearts Compressor**, **Limiter**, **Dynamics**, **Gate**, and **Transient Shaper**.
- **Infinite**: Dynamics, Gate, Limiter, Transient Shaper; no multiband dynamics (gap).

### 2.6 Modular Multi-FX & Creative Filters (12 Plugins, 2,719 Parameters)
- **Flagship Models**:
  - **FabFilter Volcano 3** (896 parameters): 4 multimode filters with vintage routing topologies (Serial, Parallel, Per-Channel).
  - **Kilohearts Multipass** (179 parameters) & **Snap Heap** (174 parameters): Multi-band split rack and serial/parallel snap-in container.
  - **Cableguys ShaperBox 3** & **XLN RC-20 Retro Color**: Rhythmic modulation and vintage degradation.
- **Infinite**: the canvas routes any audio node into any other; modulation reaches every param at frame rate.

### 2.7 Flagship Synthesizers & Instruments (9 Plugins, 9,012 Parameters)
- **Flagship Models**:
  - **u-he Diva** (281 parameters): Circuit-modeled analogue synthesizer combining Minimoog, Jupiter-8, Alpha Juno, MS-20, and Oberheim filters and oscillators.
  - **Vital Audio Vital** (775 parameters): Spectral warping wavetable synthesizer with stereo LFOs, microtuning, and format filtering.
  - **Xfer Records Serum 2** (>1,000 parameters): Dual wavetable oscillators, noise generator, sub-oscillator, and matrix routing.
  - **FabFilter Twin 3** (1,288 parameters): 4-oscillator virtual analog synthesizer with 4 filters and full FX section.
  - **D16 Group Drumazon 2** (512 parameters): Roland TR-909 drum machine emulation with analog circuit parameterization.
- **Infinite**: 17 built-in synths (census) on the same canvas as visuals.

---

## 3. Strategic Architectural Takeaways

1. **Parameter Density & Granularity**: High-end plugins dedicate 600-1,000 parameters per unit to modulation slots, multi-band splits and envelope followers. Infinite keeps nodes minimal (new-audio-node rule) and gets depth from the patch instead.
2. **Circuit Modeling & Anti-Aliasing**: Vendors employ 4x/8x oversampling and zero-delay-feedback filters. Infinite has TPT/ZDF filters (Audio Filter, Analog ladder) and oversampling on Drive, Ring Mod and Wavetable Shaper; Analog still misses the alias target (owner decision 2026-10-13).
3. **Spectral Suppression Benchmark**: oeksound soothe2's parameter model (sharpness, selectivity, band sensitivity) sets the standard for algorithmic resonance suppression that Infinite can replicate in a dedicated real-time spectral node.
