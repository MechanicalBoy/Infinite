# Apple Logic Pro — Complete Native Device & Architecture Schema Mapping

> **Infinite side checked 2026-10-13** against the census and src/; competitor parameter counts come from `~/re-output/logic/logic_all_models.json`, competitor feature prose is hand-written.
>
> **Clean Room Invariant**: Extracted directly from framework resource manifests in `/Applications/Logic Pro Creator Studio.app/Contents/Frameworks/MADSP.framework/` and `MAAlchemy.framework`. Zero binary decompilation. Complete machine-readable catalog available in `~/re-output/logic/logic_all_models.json` (1.4 MB) and `~/re-output/logic/logic_all_models.md` (55 KB).

---

## 1. Executive Summary & Inventory Scale

| Metric | Apple Logic Pro | Infinite Equivalent & Strategic Response |
|---|---|---|
| **Total Native Device Models** | **127** | 69 audio/note nodes in the census (Synths 17, AudioEffects 28, Notes 24) + Plugin node (VST3/AU) |
| **Total Extracted Parameters** | **10,070** | Count only; which Infinite params are modulatable is in `node-param-audit`, not here |
| **Flagship Monster Synth** | **Alchemy** (**6,962 parameters**) | Field Synth, Spectral Synth, Granular, Grain Molder, Sampler: no single morphing multi-engine synth |
| **Flagship Physical Modeling** | **Sculpture** (**368 parameters**) | Metallic (modal), Resonator Bank; no bowed/plucked string model |
| **True-Stereo Convolution Engine** | **Space Designer** (**97 parameters**) | **Gap**: no IR reverb. `convolve` is an image kernel filter; the audio Reverb is a 16-line FDN (`src/audio/dsp/ReverbKernel.h`) |
| **Analog Circuit Compression** | **Compressor** (7 distinct circuit topologies) | One Dynamics node: peak/RMS detector, Analog mode with program-dependent (opto-like) release (`src/audio/dsp/DynamicsKernel.h`); no circuit-model choice |
| **EQ & Spatial Processing** | **Channel EQ**, **ChromaVerb** (14 room models) | EQ: 5 bands, matched-magnitude biquads (`src/audio/dsp/EqKernel.h`); Reverb: 16-line Hadamard FDN with one damping one-pole (`src/audio/dsp/ReverbKernel.h`), no per-band decay |

---

## 2. Architectural Blueprint of Logic Pro Flagships

### 2.1 Alchemy (`Alchemy`) — 6,962 Parameters
*Flagship Spectral, Additive, Granular, Sample & Virtual Analog Morphing Synthesizer*
- **4 Sound Sources (A, B, C, D)**: Each source can independently run in one of four synthesis engines:
  1. *Additive*: Up to 600 harmonic partials resynthesized from audio or drawn manually.
  2. *Spectral*: FFT magnitude/phase resynthesis with formant manipulation.
  3. *Granular*: Grain size, density, position, spray, and envelope smearing.
  4. *Virtual Analog / Sampler*: Multi-sample keymapping with classic waveforms.
- **Morphing Core**: 8-snapshot Snapshot Pad (XY pad) smoothly interpolating all sound source parameters, filter cutoffs, and mixer gains.
- **Dual Multimode Filters**: 15+ filter models (Analog, Clean, Bandpass, Comb, Formant, Tube) with morphing drive.
- **Complex Modulation Matrix**: 16 LFOs, 16 AHDSR envelopes, 16 MSEGs (Multi-Segment Envelope Generators), and step sequencers.

### 2.2 Sculpture (`Sculpture`) — 368 Parameters
*Physical Modeling Component-Level String Synthesizer*
- **The String Model**: Simulates a physical vibrating medium across a continuous spectrum of materials: Nylon, Wood, Steel, and Glass.
- **3 Exciters**:
  - *Exciter Types*: Strike, Pluck, Bow, Blow, Noise, and Pick.
  - *Exciter Positions*: Spatially placed along the virtual string length.
- **String Modifiers**: Dual modifiers (Disrupter, Bound, Magnet, Damp) that non-linearly perturb string vibration mid-decay.
- **Body & Resonator Filter**: 2-band EQ and resonant formant body simulating instrument acoustic cavities (Violin, Guitar, Cello, Piano, Bell).

### 2.3 Space Designer (`Space Designer`) — 97 Parameters
*Zero-Latency True-Stereo Impulse Response Convolution Reverb*
- **Dual Convolution Modes**: Synthesized IR mode (generates mathematical exponential decay curves) and Sampled IR mode (loads true-stereo WAV/AIFF impulse responses).
- **Volume & Filter Envelopes**: Multi-stage curve shaping applied directly to the impulse response tail before convolution.
- **Density & Length Controls**: Time-stretching, stereo reverse, and crossover filter eq.

### 2.4 Compressor (`Compressor`) — 35 Parameters & 7 Circuit Models
- **7 Emulated Circuit Topologies**:
  1. *Platinum Digital*: Clean transparent digital compressor.
  2. *Studio VCA*: Focusrite Red / SSL VCA console emulation.
  3. *Studio FET*: Urei 1176 Rev E Blackface peak limiter/compressor.
  4. *Vintage VCA*: DBX 160 classic VCA compressor.
  5. *Vintage FET*: Urei 1176 Rev A Bluestripe compressor.
  6. *Vintage Opto*: Teletronix LA-2A optical tube compressor.
  7. *Classic VCA*: Neve 33609 console bus compressor.
- **Advanced Controls**: Soft/Hard knee, Distortion (Soft, Hard, Clip), Sidechain filter (Highpass, Bandpass, Lowpass), and Mix blend.

### 2.5 ChromaVerb (`ChromaVerb`) — 58 Parameters
*High-Density Algorithmic Reverb with 14 Room Models*
- **14 Acoustic Space Algorithms**: Rooms, Chambers, Theatres, Concert Halls, Dense Spaces, Air, and Strange Physics.
- **Decay EQ Spectrum**: Direct frequency-dependent decay time multiplier across the audio spectrum (allows high frequencies to decay at 0.5x while low frequencies decay at 2.0x).

---

## 3. Device Catalog Summary by Family (127 Devices; counts from logic_all_models.json, regenerated 2026-10-13)

### 3.1 Instruments (19 Devices, 8,504 Parameters)
- **Alchemy** (6,962 params)
- **Drum Synth** (410 params)
- **Sculpture** (368 params)
- **ES2** (187 params)
- **Vintage B3** (137 params)
- **Retro Synth** (84 params)
- **Vintage Clav** (54 params)
- **EVOC 20 PolySynth** (45 params)
- **EFM1** (37 params), **ES1** (37 params), **ES P** (37 params), **ES E** (37 params), **ES M** (37 params)
- **Vintage Electric Piano** (35 params)
- **Studio Strings** (30 params), **Studio Horns** (30 params)
- **Vintage Mellotron** (20 params), **Ultrabeat** (25 params), **Klopfgeist** (10 params)

### 3.2 Dynamics & Color (15 Devices, 226 Parameters)
- **Compressor** (35 params, 7 circuit models)
- **Multipressor** (58 params, 4-band dynamics)
- **Phat FX** (56 params, multi-stage color processor)
- **Adaptive Limiter** (25 params, inter-sample true peak)
- **Limiter** (15 params), **Noise Gate** (20 params), **Expander** (15 params), **DeEsser 2** (15 params)
- **SubBass** (18 params), **Exciter** (12 params), **Bitcrusher** (15 params)
- **Clip Distortion**, **Distortion**, **Distortion II**, **Overdrive** (10-15 params each)

### 3.3 Filter & EQ (10 Devices, 268 Parameters)
- **Channel EQ** (62 params), **Linear Phase EQ** (62 params)
- **Vintage Tube EQ** (Pultec, 30 params)
- **Vintage Console EQ** (Neve, 25 params)
- **Vintage Graphic EQ** (API, 25 params)
- **Match EQ** (35 params), **AutoFilter** (25 params), **Spectral Gate** (20 params)

### 3.4 Space, Delay & Reverb (12 Devices, 342 Parameters)
- **Space Designer** (97 params, true-stereo IR)
- **ChromaVerb** (58 params, 14 room models)
- **Step FX** (45 params, rhythmic step gate/filter)
- **Delay Designer** (35 params, 32-tap delay)
- **Tape Delay** (30 params), **Stereo Delay** (25 params), **Modulation Delay** (20 params)
- **PlatinumVerb** (25 params), **SilverVerb** (15 params), **EnVerb** (15 params)

### 3.5 Modulation & Pitch (17 Devices, 307 Parameters)
- **EVOC 20 Filterbank** (61 params), **EVOC 20 TrackOscillator** (48 params)
- **Ringshifter** (35 params), **Pitch Correction** (30 params), **Vocal Transformer** (25 params)
- **Chorus**, **Ensemble**, **Flanger**, **Phaser**, **Tremolo**, **Scanner Vibrato**, **Rotor Cabinet**

### 3.6 Guitar & Pedalboard (22 Devices, 171 Parameters; 19 of them classified by a name-keyword guess) and Unclassified (25 Devices, 141 Parameters)
- **Amp Designer** (35 params), **Bass Amp Designer** (50 params), **Pedalboard** (25 params)
- **35 Analog Stompboxes**: Fuzz, Overdrive, Chorus, Flanger, Delay, Pitch, Tremolo, Wah, Vibe.

### 3.7 MIDI Processing (7 Devices, 111 Parameters)
- **Arpeggiator** (47 params), **Modifier** (25 params), **Velocity Processor** (25 params), **Chord Trigger**, **Note Repeater**, **Randomizer**, **Transposer**

---

## 4. How Infinite Ingests & Outpaces Logic Pro Models

| Logic Pro Model | Infinite Outpace Architecture | Infinite Advantage |
|---|---|---|
| **Alchemy** (Spectral/Granular) | Field Synth, Spectral Synth, Granular, Grain Molder | Same canvas as visuals: grain and spectral params can be modulated by image/3D nodes. No snapshot-morph across engines (gap). |
| **Sculpture** (Physical Modeling) | Metallic, Resonator Bank | Modal resonators exist; no string/bow exciter model (gap). |
| **Space Designer** (IR Convolution) | **None (gap)** | Plan: non-uniform partitioned convolution reverb (Gardner 1995, Wefers 2015), see docs/plans/v0.6-quality/README.md. |
| **Vintage EQ Collection** (Pultec/Neve/API) | EQ (matched-magnitude biquads) | Clean EQ only; no analog-curve or saturation modelling (gap, low priority). |
| **ChromaVerb** (Algorithmic Reverb) | Reverb (16-line Hadamard FDN) | One damping corner; no frequency-dependent decay curve (gap). |
