# Outpacing Ableton Live 12 Suite: Audio DSP & Workflow Roadmap

Companion document to `docs/plans/re-survey/dossiers/C.md` and `docs/plans/re-survey/dossiers/F.md`.  
Generated from the extraction of Ableton Live 12 Suite (`tools/re-survey/ableton_map.py`) vs Infinite's audio engine.

---

## 1. Executive Census

From `~/re-output/ableton/ableton_live_map.md`:
- **Ableton Live 12 Native Devices Cataloged**: **83 devices**:
  - **Instruments**: 17 devices (*Analog, Collision, Drift, Drum Rack, Drum Sampler, Electric, Meld, Operator, Sampler, Simpler, Tension, Wavetable, etc.*)
  - **Audio Effects**: 48 devices (*Roar, Drum Buss, Hybrid Reverb, Echo, Spectral Time, Spectral Resonator, Glue Compressor, EQ Eight, Auto Shift, etc.*)
  - **MIDI Effects & Tools**: 18 devices (16 MIDI Effects + 2 MIDI Tools) (*Arpeggiator, Chord, Scale, Random, Velocity, MPE Control, Euclidean, Velocity Shaper, etc.*)
- **Infinite (census, checked 2026-10-13)**: Synths 17, AudioEffects 28, Notes 24, plus the Plugin node (VST3/AU host).

---

## 2. Where Infinite Leads Ableton Live 12

1. **Visuals on the same canvas (Lead)**:
   - Ableton Live 12 is audio-only. To perform with visuals, Live users rely on brittle Max for Live bridges, Spout/Syphon plugins, or separate apps (Resolume).
   - Infinite runs 2D and 3D visual nodes on the same canvas, in the same process, with no bridge app.
2. **Universal Cross-Domain Modulation (Lead)**:
   - In Live, modulating parameters across tracks requires Max for Live LFO devices or multi-step clip automation.
   - Any Infinite modulator can drive any audio or visual param (one value per param per frame, ramped per sample; not per voice).
3. **The Field Language vs Max for Live (Lead)**:
   - Live relies on Max for Live, a separate runtime and licence.
   - Infinite's **Field language** compiles inside the app for pixels (Field Pixel), geometry (Field Modifier) and DSP (Field Synth, Field Effect).
4. **Predictive Performance Learning (P3 Pillar)**:
   - Infinite's Prediction family learns the performer's gestures. Live has no learning modulators.

---

## 3. The 4 Key Gaps to Outpace Ableton Live 12

To beat Ableton Live 12 on sound design, production speed, and audio processing:

### Gap 1: Multi-Stage Color & Feedback Saturation (`Roar` Architecture)
* **Live 12**: **Roar** is Live 12's flagship multi-stage coloring device. It features 3 saturation stages with flexible routing (serial, parallel, multi-band, mid/side, feedback matrix) and internal modulation.
* **Infinite Today**: One Drive node (tanh with bias, oversampled, `src/audio/dsp/DriveKernel.h`); no Saturation node, no multi-stage or feedback saturation.
* **Action for Infinite**: first a Roar-style patch template from existing nodes (Drive, Audio Filter, feedback), plus ADAA on Drive; a new multi-stage node only if the template proves too clumsy (new-audio-node minimalism rule).

### Gap 2: Transient-Preserving Audio Time-Stretching (Warp Beats Mode)
* **Live 12 Benchmark**: Live's *Beats* warp mode slices audio at transient onsets and loops the decay tail, preserving drum transients with **0 flams** and **0 cents pitch drift**.
* **Infinite Today**: Measured in dossier C: the phase vocoder keeps pitch (0.0 cents) but smears drum transients: 10-14 extra onsets and 3 dB of crest factor lost.
* **Action for Infinite**: transient-aware stretch in `src/audio/dsp/ClipTimeStretch.h`: phase-locked vocoder (Laroche-Dolson 1999) with phase reset at detected onsets (Robel 2003). v0.6.

### Gap 3: Character Drum Bus Processor (`DrumBuss` Architecture)
* **Live 12**: **Drum Buss** is an essential electronic music tool combining a character compressor, low-end resonant sub synth ("Boom" tuned to note frequency), transient shaper, and soft/medium/hard saturation.
* **Infinite Today**: Dynamics, Transient Shaper and Drive exist separately; no sub "boom" generator.
* **Action for Infinite**: a Drum Buss patch template from those nodes first; no new node unless the template fails.

### Gap 4: Real-Time Pitch Correction & Formant Shifter (`Auto Shift` Architecture)
* **Live 12**: Live 12 introduced `Auto Shift` for real-time monophonic vocal tuning, scale quantization, and formant-independent pitch shifting.
* **Infinite Today**: Has the Pitch Shifter node (time-domain splicing shifter plus analog mode, `src/audio/dsp/PitchShiftKernel.h`) and Key Snap (`src/audio/dsp/KeySnapKernel.h`); no formant preservation.
* **Action for Infinite**: formant-preserving shift (PSOLA or cepstral envelope) on the Pitch Shifter; parked (not in v0.6).
