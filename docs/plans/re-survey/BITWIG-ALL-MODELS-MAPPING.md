# Bitwig Studio 6 — Complete The Grid, Native Devices & Modulator Mapping

> **Clean Room Invariant**: Extracted directly from application bundle manifests in `/Applications/Bitwig Studio.app/Contents/Resources/Library/`. Zero binary decompilation. Complete machine-readable catalog available in `~/re-output/bitwig/bitwig_all_assets.json` (41 KB) and `~/re-output/bitwig/bitwig_all_assets.md`.

---

> **Infinite side checked 2026-10-13** against the node census (`build/census/census.json`) and src/; run `python3 tools/re-survey/diff.py claims` after editing. Competitor numbers come from `~/re-output/`; competitor prose is hand-written.

## 1. Executive Summary & Inventory Scale

| Metric | Bitwig Studio 6 | Infinite Equivalent & Strategic Response |
|---|---|---|
| **Total Native Audio Assets** | **426** | One canvas for audio, image and 3D |
| **The Grid Modules** | **232** across 15 families (160 classified by a hand table, 72 Unclassified) | Field language (Field Synth, Field Effect, Field Graph) |
| **Native Devices** | **151** (Synthesizers, FX, Containers) | 69 audio/note nodes (census) + Plugin node (VST3/AU) |
| **Analog Drum Synthesizer Voices** | **31** | Gap: no drum synth voices (Drum Sequencer and MPC play samples) |
| **Universal Modulators** | **43** modulators | 27 Modulators + 9 Macros + 8 Prediction (census) |
| **Modular Environments** | **Poly Grid**, **FX Grid**, **Note Grid** | One node canvas for audio, notes, 3D and shaders; no per-voice (poly) modular |

---

## 2. The Grid Modular Library (232 Modules)

The Grid is Bitwig's open-architecture modular sound design environment. Modules communicate via three typed cable standards: **Audio** (orange, 48 kHz/96 kHz audio rate), **Control** (blue, control voltage/modulation rate), and **Logic/Phase** (purple, 0-to-1 normalized phase and boolean pulses).

### 2.1 Oscillators (10 Modules)
- **Sine**, **Triangle**, **Sawtooth**, **Pulse**: Classic bandlimited analog waveforms with phase input.
- **Swarm**: Multi-voice supersaw detuned unison cluster.
- **Wavetable**: Multi-frame wavetable oscillator with continuous table position interpolation.
- **Sampler**: Audio sample playback with pitch tracking, looping, and root note detection.
- **Sub**: Clean sub-harmonic generator.
- **Noise**: White, pink, and red noise sources.
- **Rasp**: Aggressive metallic harmonic pulse oscillator.

### 2.2 Filters (13 Modules)
- **Low-pass LD / MG**: Moog-style transistor ladder filters with nonlinear saturation and resonance boost.
- **SVF**: State-variable filter with simultaneous Low, Band, High, and Notch outputs.
- **Sallen-Key**: Korg MS-20 style non-linear Sallen-Key circuit model.
- **XP**: Morphing multi-pole filter with feedback drive.
- **Comb & All-pass**: Tuned feedback comb and dispersive phase allpass delay.
- **Bite, Fizz, Vowels**: Formant-rich vocal and aggressive dual-peak resonators.

### 2.3 Shapers & Distortion (12 Modules)
- **Chebyshev**: Harmonic generator using Chebyshev polynomials to synthesize exact harmonic overtones.
- **Wavefolder**: Buchla-style multi-stage wavefolder folding waveform peaks into rich harmonics.
- **Diode**: Asymmetrical diode clipping model with soft knee.
- **Heat, Howl, Push, Shred**: Dynamic tube warmth, screaming feedback, overdrive, and digital decimation.

### 2.4 Phase Engine (20 Modules)
- A dedicated 0-to-1 phase manipulation system allowing custom synthesis without traditional oscillators: **Phasor**, **Phase Bend**, **Phase Formant**, **Phase Mirror**, **Phase Pinch**, **Phase Pulse**, **Phase Skew**, **Phase Wrap**, **Phase Sinemod**.

### 2.5 Logic, Math & Routing (68 Modules)
- Complete boolean logic gates (**AND, NAND, OR, NOR, XOR, XNOR, NOT**).
- Full arithmetic math (**Add, Subtract, Multiply, Divide, Abs, MinMax, Round, Exp, Log, Sqrt**).
- Level control (**Amplify, Attenuate, Bias, Blend, Gain, Mixer, Pan, Stereo Split/Merge**).

---

## 3. Native Devices Breakdown (151 Devices)

### 3.1 Flagship Synthesizers & Instruments
- **Polymer**: Hybrid modular synthesizer assembling a Grid oscillator, filter, and envelope into a streamlined instrument.
- **Poly Grid / FX Grid / Note Grid**: Open modular canvas environments.
- **Polysynth**: Classic subtractive dual-oscillator synthesizer.
- **Sampler**: Full multi-sample instrument with multisample zones and granular looping.
- **FM-4**: 4-operator frequency modulation synth with custom carrier/modulator matrices.
- **Phase-4**: 4-operator phase-modulation and phase-distortion synthesizer.
- **Organ**: Tonewheel drawbar organ model.
- **Drum Machine**: 128-pad container with nested device chains.
- **31 Analog Drum Voices**:
  - `v8` Series (TR-808): v8 Kick, v8 Snare, v8 Tom, v8 Hat, v8 Cymbal, v8 Claves, v8 Cowbell, v8 Maracas, v8 Rimshot, v8 Clap.
  - `v9` Series (TR-909): v9 Kick, v9 Snare, v9 Tom, v9 Hat Closed, v9 Hat Open, v9 Crash, v9 Ride, v9 Rimshot, v9 Clap.
  - `v0` & `v1` Series: Vintage acoustic and analog electronic drum voices.

### 3.2 Dynamics & EQ
- **EQ+**: 8-band dynamic parametric EQ with integrated spectrum analyzer.
- **EQ-5 / EQ-2 / EQ-DJ**: Lightweight and DJ-style equalizers.
- **Compressor+ / Compressor**: VCA compressor with external sidechain and knee control.
- **Dynamics**: Dual upward/downward compressor/expander.
- **Peak Limiter**, **Gate**, **De-Esser**, **Transient Control**.

### 3.3 Space, Delay & Modulation
- **Delay+ / Delay-1 / Delay-2 / Delay-4**: Multi-tap tempo-synced stereo delays with integrated ducking and filters.
- **Reverb & Convolution**: Algorithmic diffusion and true-stereo impulse response convolution.
- **Chorus+, Flanger+, Phaser+, Freq Shifter+**: Modernized modulation suites with character color modes.
- **Resonator Bank**: 6-band tuned resonant comb filter bank.

### 3.4 Multi-Band & Split Routers
- **Freq Split**, **Harmonic Split**, **Loud Split**, **Mid-Side Split**, **Transient Split**: Advanced multi-path processing containers splitting incoming audio into separate processing chains.
- **FX Layer / FX Selector / XY FX**: Layering and morphing containers.

---

## 4. How Infinite Ingests & Outpaces Bitwig Studio

| Bitwig Architecture | Infinite Outpace Architecture | Infinite Leap |
|---|---|---|
| **The Grid (232 modular audio blocks)** | **Field language** | Field code runs in audio (Field Synth/Effect), pixels (Field Pixel) and geometry (Field Modifier). Grid modules run per voice at audio rate; Infinite modulation into Field is one value per frame. |
| **Universal Modulators (43 engines)** | Global modulation + Prediction family | Infinite modulators reach audio, 3D, lights and shaders; Bitwig's are per voice and audio-rate, Infinite's are one value per param at frame rate (gap). |
| **Multi-Band Split Routers** | **Gap** | No band-split container; build it from Audio Filter nodes in parallel. |
| **Poly Grid & Polymer** | Analog, Wavetable, Field Synth | No per-voice modulation routing (gap, v0.7 architecture lane). |
| **Analog Drum Models (31 voices)** | **Dedicated Analog Drum Nodes + Visual Impulses** | Analog drum circuits paired with hardware-accelerated VideoToolbox visual flashes and physics impulses. |
