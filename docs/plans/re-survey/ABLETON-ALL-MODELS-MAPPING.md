# Ableton Live 12 Suite — Complete Model & Architectural Schema Mapping

> **Infinite side checked 2026-10-13** against the census and src/. Competitor counts come from `~/re-output/ableton/`; competitor prose is hand-written.
>
> **Clean Room Invariant**: Extracted exclusively from public application schema `12.0_12402.txt` within the Ableton Live 12 Suite bundle. Zero binary decompilation or disassembly. Full machine-readable dataset available in `~/re-output/ableton/ableton_all_models.json` (1.4 MB) and `~/re-output/ableton/ableton_all_models.md` (117 KB).

---

## 1. Executive Summary & Inventory Scale

| Metric | Ableton Live 12 Suite | Infinite Parity & Plan |
|---|---|---|
| **Total Native Device Classes** | **103** | 69 audio/note nodes in the census (Synths 17, AudioEffects 28, Notes 24) + Plugin node (VST3/AU) |
| **Direct Device Fields & Parameters** | **5,243** | Count only; Infinite modulatability is in `node-param-audit` |
| **DSP Sub-Component Modules** | **67** (651 fields) | Shared DSP kernels in `src/audio/dsp/` (one per effect, no shared sub-module schema) |
| **Generative MIDI / Transform Algorithms** | **24** (173 fields) | Notes family (22) + Prediction (8); no clip-level generators |
| **Combined Architectural Footprint** | **6,067 parameters** | Cataloged in `~/re-output/ableton/`; not mapped param-by-param to Infinite |

---

## 2. Architectural Blueprint of Live 12 Flagships

### 2.1 Roar (`Roar`) — 263 Parameters
*Flagship Multi-Stage Color & Saturation Processor (Live 12)*
- **3 Saturation Stages**: Each stage features Drive, Bias (asymmetry), Trim, Morph, Peak Gain, and a dedicated multi-mode filter (Lowpass, Bandpass, Highpass, Peak, Notch).
- **5 Routing Topologies**:
  1. *Single*: Simple 1-stage drive.
  2. *Serial*: Stage 1 -> Stage 2 -> Stage 3 chained in series.
  3. *Parallel*: Stage 1 and Stage 2 split in parallel, summing into Stage 3.
  4. *Mid/Side*: Stage 1 processes Mid (sum), Stage 2 processes Side (difference), feeding Stage 3.
  5. *Dual-Band & Multi-Band*: Frequency crossover splitting lows/highs or lows/mids/highs into separate shaping stages.
- **Feedback Matrix**: Delay line in the feedback loop with time (ms / tempo-synced), feedback frequency filter, bandwidth, and amount.
- **Modulation Matrix**: 4 internal modulators (LFO 1, LFO 2, Envelope Follower, Noise) mapped across 18 destinations with bipolar amounts.
- **Master Stage**: Output soft-clipper / compressor with highpass filter, output gain, and dry/wet blend.

### 2.2 Meld (`InstrumentMeld`) — 156 Parameters
*Bi-Timbral Macro Synthesizer (Live 12)*
- **Dual Sound Engines (A & B)**: Completely independent signal paths from macro oscillator to tone filter.
- **Macro Oscillators**: 12+ synthesis algorithms (Virtual Analog, Noisy, Sub, Harmonics, Rain, Crackle, Tonal Noise, Square Sync, Fold) controlled via Macro 1 and Macro 2, with scale-aware quantization.
- **Filter Section**: Multimode filter with scale-aware harmonic tracking and dual morphing parameters.
- **Wave-Shaping LFOs**:
  - *LFO 1*: Advanced waveform generator with dual wave-shaping transformers (Fold, Quantize, Slew, Rectify).
  - *LFO 2*: Classic multi-waveform mod source.
- **Modulation Matrix**: 19 modulation sources (Envelopes, LFOs, Velocity, Release Velocity, Pressure, Slide, Key, Random, etc.) with per-voice modulation.

### 2.3 Drift (`Drift`) — 103 Parameters
*Subtractive Synthesizer with Analog Instability (Live 11.3 / 12)*
- **Analog Drift Engine**: Continuous subtle, uncorrelated pitch instability modeled across voices (`Global_DriftDepth`).
- **Oscillators**: Osc 1 (morphing shape from sine to triangle to saw to pulse) + Osc 2 (sine/saw/pulse with octave/detune) + Noise.
- **Per-Oscillator Filter Bypass**: Osc 1, Osc 2, and Noise can each independently bypass the lowpass filter into the mixer (`Filter_OscillatorThrough1`, `Filter_OscillatorThrough2`, `Filter_NoiseThrough`).
- **Cycling Envelope**: Function-generator envelope operating as an AD envelope, cycling LFO, or tempo-synced modulation source with variable midpoint curve and hold time.

### 2.4 Auto Shift (`AutoShift`) — 83 Parameters
*Real-Time Pitch Tracker, Formant Shifter & MIDI Harmonizer (Live 12)*
- **Neural/Fast Pitch Tracking**: Low-latency Monophonic pitch detection (`Global_LiveMode`).
- **Formant Shifter & Follower**: Formant shift independent of pitch, with automatic formant following based on vocal tract acoustics.
- **Scale Quantizer**: Quantizes pitch to 12 scale degrees or user-custom note bitmask (`QuantizerCustomNoteStates.0` .. `.11`).
- **Vibrato Generator**: Dedicated vocal vibrato LFO with attack delay, rate, amount, and humanization jitter.
- **MIDI Input Mode**: Turns the effect into a polyphonic vocoder/harmonizer where incoming MIDI notes dictate harmony voices (`MidiInput_NumVoices`, `MidiInput_Glide`, `MidiInput_Latch`).

### 2.5 Hybrid Reverb (`Hybrid`) — 80 Parameters
*Convolution & Algorithmic Blend Reverb (Live 11)*
- **Convolution Engine**: Zero-latency impulse response processor with IR attack, decay, and size stretching.
- **5 Algorithmic Engines**:
  - *Dark Principal*: Vintage dense plate.
  - *Shimmer*: Pitch-shifted feedback loops.
  - *Tides*: Wave-modulated undulating tail.
  - *Quartz*: Crystal room with distance damping.
  - *Prism*: Resonant comb cluster.
- **Routing Topologies**: Serial (Convolution -> Algo), Serial (Algo -> Convolution), Parallel (50/50 mix), and Send mode.
- **4-Band Parametric EQ**: Sweepable pre/post algorithmic filter network.

### 2.6 Echo (`Echo`) — 76 Parameters
*Tape / Analog Modulated Stereo Delay (Live 10)*
- **Dual Delay Channels**: Independent Left and Right delay times, tempo sync divisions, and channel offsets.
- **Repitch / Fade / Jump**: Tape repitching smoothly interpolates buffer speed when time changes.
- **Dynamics Section**: Internal ducking compressor and gate inside the feedback path.
- **Wobble & Noise**: Motor wow/flutter tape wobble and analog pre-amp hiss.
- **Diffusion Reverb**: Early reflection diffuser placed Pre, Post, or Inside the feedback loop.

---

## 3. Complete 103 Device Catalog by Family

### 3.1 Instruments (17 Devices)
1. **Meld** (`InstrumentMeld`): 156 fields, 114 DSP params (Macro bi-timbral synth)
2. **Drift** (`Drift`): 103 fields, 79 DSP params (Subtractive analog drift synth)
3. **Wavetable** (`InstrumentVector`): 134 fields, 94 DSP params (Dual wavetable synth)
4. **Operator** (`Operator`): 32 fields + 8 subcomponents (4-operator FM synth)
5. **Analog** (`UltraAnalog`): 63 fields + 3 subcomponents (AAS virtual analog synth)
6. **Collision** (`Collision`): 41 fields + 5 subcomponents (AAS mallet/membrane physical modeling)
7. **Tension** (`StringStudio`): 131 fields, 91 DSP params (AAS string physical modeling)
8. **Electric** (`LoungeLizard`): 54 fields, 32 DSP params (AAS Rhodes/Wurlitzer physical modeling)
9. **Simpler** (`OriginalSimpler`): 76 fields + 16 subcomponents (Creative sampler)
10. **Sampler** (`MultiSampler`): 51 fields, 35 DSP params (Multi-zone sample instrument)
11. **Impulse** (`InstrumentImpulse`): 53 fields, 38 DSP params (8-slot drum sampler)
12. **Drum Cell** (`DrumCell`): 64 fields, 42 DSP params (Single drum voice)
13. **Instrument Rack** (`InstrumentGroupDevice`): 173 fields (Layer/split rack)
14. **Drum Rack** (`DrumGroupDevice`): 174 fields (128-pad drum matrix)
15. **Max Instrument** (`MxDeviceInstrument`): 24 fields (Max for Live synth wrapper)
16. **VST Host** (`PluginDevice`): 32 fields (VST2/VST3 plugin container)
17. **AU Host** (`AuPluginDevice`): 28 fields (macOS Audio Unit container)

### 3.2 Saturation & Color (13 Devices)
1. **Roar** (`Roar`): 263 fields, 182 DSP params (Triple-stage multi-routing saturator)
2. **Drum Buss** (`DrumBuss`): 34 fields, 18 DSP params (Drum character/sub shaper)
3. **Saturator** (`Saturator`): 34 fields, 17 DSP params (Waveshaping distortion)
4. **Pedal** (`Pedal`): 26 fields, 13 DSP params (OD/Dist/Fuzz stompbox)
5. **Overdrive** (`Overdrive`): 25 fields, 11 DSP params (Dynamic bandpass overdrive)
6. **Amp** (`Amp`): 30 fields, 10 DSP params (7-model guitar amplifier)
7. **Cabinet** (`Cabinet`): 26 fields, 7 DSP params (Speaker cabinet simulator)
8. **Dynamic Tube** (`Tube`): 24 fields, 8 DSP params (Triode/pentode tube shaper)
9. **Vinyl Distortion** (`Vinyl`): 26 fields, 9 DSP params (Turntable pinch/crackle)
10. **Redux** (`Redux2`): 25 fields, 8 DSP params (Modern bitcrusher/downsampler)
11. **Redux (Legacy)** (`Redux`): 24 fields, 6 DSP params (Legacy bitcrusher)
12. **Erosion** (`Erosion2`): 24 fields, 7 DSP params (Sine/Noise modulator)
13. **Erosion (Legacy)** (`Erosion`): 24 fields, 6 DSP params (Legacy erosion)

### 3.3 Dynamics (5 Devices)
1. **Compressor** (`Compressor2`): 51 fields, 27 DSP params (Peak/RMS/Log compressor + expander)
2. **Glue Compressor** (`GlueCompressor`): 34 fields, 13 DSP params (Cytomic SSL G-Master bus compressor)
3. **Multiband Dynamics** (`MultibandDynamics`): 63 fields, 42 DSP params (3-band upward/downward compressor)
4. **Gate** (`Gate`): 35 fields, 14 DSP params (Lookahead gate & ducker)
5. **Limiter** (`Limiter`): 26 fields, 9 DSP params (Lookahead brickwall limiter)

### 3.4 Filter & EQ (5 Devices)
1. **Auto Filter** (`AutoFilter2`): 67 fields, 34 DSP params (Cytomic analog filter circuits Clean, SMP, OSR, MS2, PRD)
2. **Auto Filter (Legacy)** (`AutoFilter`): 39 fields, 18 DSP params (Digital biquad filter)
3. **EQ Eight** (`Eq8`): 41 fields + 8x `Eq8BandParameter` (8-band parametric EQ)
4. **Channel EQ** (`ChannelEq`): 27 fields, 7 DSP params (Console strip EQ)
5. **EQ Three** (`FilterEQ3`): 27 fields, 10 DSP params (DJ 3-band kill EQ)

### 3.5 Time & Delay (6 Devices)
1. **Echo** (`Echo`): 76 fields, 47 DSP params (Dual tape delay with wobble & reverb)
2. **Delay** (`Delay`): 55 fields, 28 DSP params (Stereo delay with filter & repitch)
3. **Filter Delay** (`FilterDelay`): 37 fields, 18 DSP params (3-tap filtered delay)
4. **Grain Delay** (`GrainDelay`): 30 fields, 12 DSP params (Granular smear delay)
5. **Beat Repeat** (`BeatRepeat`): 38 fields, 16 DSP params (Rhythmic buffer stutter)
6. **Looper** (`Looper`): 38 fields, 14 DSP params (Live phrase looper)

### 3.6 Space & Reverb (3 Devices)
1. **Hybrid Reverb** (`Hybrid`): 80 fields, 51 DSP params (IR convolution + 5 algorithm reverb)
2. **Reverb** (`Reverb`): 34 fields, 16 DSP params (FDN diffusion reverb)
3. **Resonators** (`Resonator`): 30 fields, 15 DSP params (5-band tuned comb resonators)

### 3.7 Modulation & Pitch (12 Devices)
1. **Auto Shift** (`AutoShift`): 83 fields, 52 DSP params (Pitch tracking & formant harmonizer)
2. **Shifter** (`Shifter`): 58 fields, 34 DSP params (Pitch/frequency shifter & ring mod)
3. **Frequency Shifter (Legacy)** (`FrequencyShifter`): 27 fields, 9 DSP params
4. **Chorus-Ensemble** (`Chorus2`): 36 fields, 16 DSP params (Chorus, vibrato & 3-phase ensemble)
5. **Chorus (Legacy)** (`Chorus`): 33 fields, 12 DSP params
6. **Phaser-Flanger** (`PhaserNew`): 46 fields, 23 DSP params (Allpass phaser & comb flanger)
7. **Phaser (Legacy)** (`Phaser`): 29 fields, 10 DSP params
8. **Flanger (Legacy)** (`Flanger`): 30 fields, 11 DSP params
9. **Auto Pan** (`AutoPan2`): 40 fields, 16 DSP params (Stereo panner & tremolo)
10. **Auto Pan (Legacy)** (`AutoPan`): 22 fields, 7 DSP params
11. **Corpus** (`Corpus`): 60 fields, 39 DSP params (AAS physical modeling resonator effect)
12. **Vocoder** (`Vocoder`): 44 fields + 41-band `VocoderFilterBank` (40-band channel vocoder)

### 3.8 Spectral Resynthesis (2 Devices)
1. **Spectral Time** (`Spectral`): 51 fields, 25 DSP params (FFT spectral delay & freezer)
2. **Spectral Resonator** (`Transmute`): 48 fields, 23 DSP params (FFT modal comb resonator)

### 3.9 Utility & Analysis (6 Devices)
1. **Utility** (`StereoGain`): 30 fields, 12 DSP params (Gain, pan, width, bass mono, phase)
2. **Tuner** (`Tuner`): 25 fields, 4 DSP params (Chromatic instrument tuner)
3. **Spectrum** (`SpectrumAnalyzer`): 28 fields, 5 DSP params (FFT audio spectrum display)
4. **Test Tone Generator** (`SignalGenerator`): 24 fields, 5 DSP params (Sine/Noise generator)
5. **Signal Analyzer** (`SignalAnalyzer`): 23 fields, 3 DSP params
6. **EQ Eight Analyzer** (`Eq8SpectrumAnalyzer`): 25 fields, 3 DSP params

### 3.10 MIDI Effects (8 Devices)
1. **Arpeggiator** (`MidiArpeggiator`): 37 fields, 18 params (Rhythmic arpeggiator)
2. **Chord** (`MidiChord`): 27 fields, 13 params (6-interval chord builder)
3. **Scale** (`MidiScale`): 27 fields, 14 params (Musical scale quantizer)
4. **Random** (`MidiRandom`): 27 fields, 12 params (Pitch randomizer)
5. **Pitch** (`MidiPitcher`): 23 fields, 9 params (Pitch transposer)
6. **Velocity** (`MidiVelocity`): 34 fields, 16 params (Velocity curve shaper)
7. **Note Length** (`MidiNoteLength`): 28 fields, 11 params (Gate duration shaper)
8. **CC Control** (`MidiCcControl`): 47 fields, 25 params (8-channel MIDI CC generator)

### 3.11 Racks & Containers (14 Devices)
1. `AudioEffectGroupDevice` (Audio Effect Rack): 173 fields
2. `MidiEffectGroupDevice` (MIDI Effect Rack): 169 fields
3. `AudioBranchMixerDevice` (Rack Chain Audio Mixer): 27 fields
4. `MidiBranchMixerDevice` (Rack Chain MIDI Router): 27 fields
5. `TrackDevice` (DAW Channel Mixer): 22 fields
6. `MainTrackDevice` (Master Track Mixer): 24 fields
7. `Metronome` (Click Generator): 23 fields
8. `MxDeviceAudioEffect` (Max for Live Audio): 24 fields
9. `MxDeviceMidiEffect` (Max for Live MIDI): 24 fields
10. `ProxyAudioEffectDevice` (Push Audio Proxy): 24 fields
11. `ProxyInstrumentDevice` (Push Instrument Proxy): 24 fields

---

## 4. Live 12 Generative & Transform MIDI Algorithms (24 Classes)

Live 12 introduces generative MIDI Tools directly in clip views, modeled by these core algorithmic schemas:
- `ArpeggiateAlgorithm`: Rate, Steps, Distance, Gate, Style.
- `LfoAlgorithm`: Target (Pitch Bend, Slide, Pressure), ShapeType, Rate, CurveShape, Amplitudes, Attack, Decay.
- `VelocityFilterAlgorithm`: Velocity curve shaping, humanization range.
- `TimeWarpAlgorithm`: Non-linear beat stretching, accelerando/ritardando.
- `ScaleFilterAlgorithm`: Scale mapping, root note, interval folding.
- `ConditionFilterAlgorithm`: Conditional probability triggering (first note, fill, reverse).
- `ProbabilityFilterAlgorithm`: Per-note chance weighting.
- `DurationFilterAlgorithm`: Rhythm division duration stretching.

---

## 5. How Infinite Ingests & Outpaces These Models

| Live 12 Model | Infinite Outpace Architecture | Infinite Advantage |
|---|---|---|
| **Roar** (3-stage saturator) | **Gap.** Drive (one tanh stage) + Audio Filter + feedback patch | Plan: ship a Roar-style patch template from existing nodes; ADAA on Drive. |
| **Meld** (Bi-timbral macro) | **Gap.** Wavetable, Analog, Field Synth | No bi-timbral macro oscillator. |
| **Drift** (Subtractive drift) | Analog | Analog covers subtractive; no dedicated drift engine. (Infinite's "Drift" node is a Prediction node.) |
| **Auto Shift** (Pitch/Formant) | Pitch Shifter + Key Snap | No formant preservation, no pitch detection-driven correction (gap). |
| **Hybrid Reverb** | Reverb (16-line FDN) | **Gap**: no IR convolution. Plan: partitioned convolution reverb (v0.6). |
| **Echo** (Tape delay) | Delay | No tape model; feedback can route through any audio node on the canvas. |
| **Glue Compressor** | Dynamics | One compressor with an Analog (opto-like release) mode; no bus-compressor model. |
