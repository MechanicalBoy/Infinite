#!/usr/bin/env python3
"""re-survey ableton_schema_extractor: deep-extract parameter and architectural schemas for every model in Ableton Live 12 Suite.

Sources (public XML schema and bundle structure only, no binary decompilation):
  Ableton Live 12: /Applications/Ableton Live 12 Suite.app/Contents/App-Resources/Schema/12.0_12402.txt

Usage:
  python3 tools/re-survey/ableton_schema_extractor.py run [--out ~/re-output/ableton/ableton_all_models.md] [--json]
  python3 tools/re-survey/ableton_schema_extractor.py --self-test
Exit: 0 ok, 1 parsing failed / self-test failed, 2 usage error.
"""

import argparse
import json
import os
import re
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import RE_OUTPUT, SelfTest, ensure_dir, md_table, write_out  # noqa: E402

LIVE_SCHEMA = "/Applications/Ableton Live 12 Suite.app/Contents/App-Resources/Schema/12.0_12402.txt"

# Mapping internal schema class names to user-visible display names and families
DEVICE_METADATA = {
    # --- Instruments ---
    "InstrumentMeld": {
        "display_name": "Meld",
        "family": "Instruments",
        "category": "Macro / Bi-Timbral Synthesizer",
        "introduced": "Live 12",
        "architecture": "Dual bi-timbral macro synth engines (A/B) with scale-aware resonators, wave-shaping transformers, dual complex LFOs, and extensive 19-source modulation matrix.",
    },
    "Drift": {
        "display_name": "Drift",
        "family": "Instruments",
        "category": "Subtractive Synthesizer",
        "introduced": "Live 11.3",
        "architecture": "Subtractive synth with analog drift modeling, cycling envelope (function generator), per-oscillator filter bypass, and MPE pitch/timbre expression.",
    },
    "InstrumentVector": {
        "display_name": "Wavetable",
        "family": "Instruments",
        "category": "Wavetable Synthesizer",
        "introduced": "Live 10",
        "architecture": "Dual wavetable morphing oscillators, sub-oscillator, dual Cytomic filters with serial/parallel/split routing, 3 loopable envelopes, 2 LFOs, and 13-source matrix.",
    },
    "Operator": {
        "display_name": "Operator",
        "family": "Instruments",
        "category": "FM Synthesizer",
        "introduced": "Live 4",
        "architecture": "4-operator FM/additive synthesizer with 11 routing algorithms, per-operator loopable envelopes, pitch envelope, Cytomic multi-mode filter, and waveshaper.",
    },
    "UltraAnalog": {
        "display_name": "Analog",
        "family": "Instruments",
        "category": "Virtual Analog Synthesizer",
        "introduced": "Live 7",
        "architecture": "AAS physical modeling virtual analog with dual oscillators, sub-oscillator, dual multimode filters in serial/parallel, dual amps, dual LFOs, and pitch mod.",
    },
    "Collision": {
        "display_name": "Collision",
        "family": "Instruments",
        "category": "Physical Modeling Percussion",
        "introduced": "Live 8",
        "architecture": "AAS physical modeling percussion synth with Mallet/Noise exciters driving dual coupled resonators (Beam, Marimba, String, Membrane, Plate, Pipe, Tube).",
    },
    "StringStudio": {
        "display_name": "Tension",
        "family": "Instruments",
        "category": "Physical Modeling String",
        "introduced": "Live 7",
        "architecture": "AAS string physical modeling synth simulating exciter (bow, hammer, plectrum), string stiffness/damping, termination/fretboard, damper, and body resonance.",
    },
    "LoungeLizard": {
        "display_name": "Electric",
        "family": "Instruments",
        "category": "Physical Modeling Electric Piano",
        "introduced": "Live 7",
        "architecture": "AAS electric piano modeling hammer impact, fork (tine and tone bar vibration), magnetic pickup position, and damper release mechanics.",
    },
    "OriginalSimpler": {
        "display_name": "Simpler",
        "family": "Instruments",
        "category": "Creative Sampler",
        "introduced": "Live 1",
        "architecture": "Creative sampler with Classic, 1-Shot, and Slicing modes, warp integration, Cytomic analog filter circuits, pitch/filter/amp envelopes, and LFOs.",
    },
    "MultiSampler": {
        "display_name": "Sampler",
        "family": "Instruments",
        "category": "Multi-Sample Instrument",
        "introduced": "Live 6",
        "architecture": "Multi-sample instrument with key/velocity zones, multi-mode filter, dedicated FM/AM modulation oscillator, aux envelopes, and morphing multi-stage envelopes.",
    },
    "InstrumentImpulse": {
        "display_name": "Impulse",
        "family": "Instruments",
        "category": "Drum Sampler",
        "introduced": "Live 4",
        "architecture": "8-slot percussion sampler with per-voice pitch transpose, time stretch, multimode filter, saturation, pan/volume modulation, and global reverb send.",
    },
    "DrumCell": {
        "display_name": "Drum Cell",
        "family": "Instruments",
        "category": "Drum Pad Voice",
        "introduced": "Live 10",
        "architecture": "Individual drum voice engine for pad-level sample playback, envelope shaping, and filter/pitch modulation.",
    },
    "InstrumentGroupDevice": {
        "display_name": "Instrument Rack",
        "family": "Racks & Containers",
        "category": "Multi-Instrument Container",
        "introduced": "Live 6",
        "architecture": "Multi-chain instrument container supporting split/layer zones, chain select, 8/16 macro controls with variation snapshots.",
    },
    "DrumGroupDevice": {
        "display_name": "Drum Rack",
        "family": "Racks & Containers",
        "category": "Percussion Matrix Container",
        "introduced": "Live 7",
        "architecture": "128-pad percussion matrix container with per-pad device chains, choke groups, send/return chains, and macro mapping.",
    },

    # --- Audio Effects: Saturation & Color ---
    "Roar": {
        "display_name": "Roar",
        "family": "Saturation & Color",
        "category": "Multi-Stage Color / Saturation",
        "introduced": "Live 12",
        "architecture": "Flagship 3-stage saturator with 5 routing modes (Single, Serial, Parallel, Mid/Side, Dual-Band, Multi-Band), feedback matrix, filters, and 4-source mod matrix.",
    },
    "DrumBuss": {
        "display_name": "Drum Buss",
        "family": "Saturation & Color",
        "category": "Drum Character Processor",
        "introduced": "Live 10",
        "architecture": "Analog drum bus processor combining 3 drive modes (Soft, Medium, Hard), transient shaping, sub-boom resonant bass synth, high-frequency damp, and crunch.",
    },
    "Saturator": {
        "display_name": "Saturator",
        "family": "Saturation & Color",
        "category": "Wave-Shaping Saturation",
        "introduced": "Live 4",
        "architecture": "Multi-curve waveshaping saturator (Analog Clip, Soft Sine, Medium Curve, Hard Curve, Sinoid Fold, Digital Clip) with custom transfer function curve controls.",
    },
    "Pedal": {
        "display_name": "Pedal",
        "family": "Saturation & Color",
        "category": "Guitar Stompbox Model",
        "introduced": "Live 10",
        "architecture": "Analog stompbox emulation offering Overdrive, Distortion, and Fuzz circuits, 3-band tone EQ with mid frequency shift, and Sub boost switch.",
    },
    "Overdrive": {
        "display_name": "Overdrive",
        "family": "Saturation & Color",
        "category": "Dynamic Distortion",
        "introduced": "Live 7",
        "architecture": "Non-linear dynamic overdrive featuring bandpass pre-filter with Drive, Tone, Dynamics control, and Dry/Wet blend.",
    },
    "Amp": {
        "display_name": "Amp",
        "family": "Saturation & Color",
        "category": "Guitar Amplifier Model",
        "introduced": "Live 8",
        "architecture": "AAS guitar amplifier emulation with 7 preamp topologies (Clean, Boost, Blues, Rock, Lead, Heavy, Bass), 3-band EQ, Presence, Dual-Mono processing.",
    },
    "Cabinet": {
        "display_name": "Cabinet",
        "family": "Saturation & Color",
        "category": "Speaker Cabinet Model",
        "introduced": "Live 8",
        "architecture": "AAS speaker cabinet emulation with 5 cabinet sizes, dynamic/condenser mic models, on/off-axis placement, and near/far distance controls.",
    },
    "Tube": {
        "display_name": "Dynamic Tube",
        "family": "Saturation & Color",
        "category": "Vacuum Tube Saturation",
        "introduced": "Live 5",
        "architecture": "Vacuum tube amplifier emulation with 3 tube models (A, B, C), Tube Drive, Bias control for asymmetric clipping, and Tone tone-shaping filter.",
    },
    "Vinyl": {
        "display_name": "Vinyl Distortion",
        "family": "Saturation & Color",
        "category": "Turntable Artifact Generator",
        "introduced": "Live 4",
        "architecture": "Turntable physical modeling simulating Tracing distortion (geometric stylus angle error), Pinch distortion (vertical grove narrowing), and Crackle noise.",
    },
    "Redux2": {
        "display_name": "Redux",
        "family": "Saturation & Color",
        "category": "Bitcrusher & Downsampler",
        "introduced": "Live 11",
        "architecture": "Modern bit depth reducer and sample rate downsampler with jitter modulation, anti-aliasing pre-filter, and dry/wet blend.",
    },
    "Redux": {
        "display_name": "Redux (Legacy)",
        "family": "Saturation & Color",
        "category": "Legacy Bitcrusher",
        "introduced": "Live 1",
        "architecture": "Legacy sample rate reduction and bit resolution reducer.",
    },
    "Erosion2": {
        "display_name": "Erosion",
        "family": "Saturation & Color",
        "category": "Digital Degradation",
        "introduced": "Live 4",
        "architecture": "Digital degradation generator modulating input with Noise, Sine wave, or Wide Noise (stereo uncorrelated) with frequency and amount.",
    },
    "Erosion": {
        "display_name": "Erosion (Legacy)",
        "family": "Saturation & Color",
        "category": "Digital Degradation",
        "introduced": "Live 4",
        "architecture": "Early revision of the Erosion digital artifact generator.",
    },

    # --- Audio Effects: Dynamics ---
    "Compressor2": {
        "display_name": "Compressor",
        "family": "Dynamics",
        "category": "Versatile Compressor",
        "introduced": "Live 9",
        "architecture": "VCA-style compressor with Peak, RMS, and Expand modes, modern Cytomic log release detector, lookahead, and sidechain filter EQ.",
    },
    "GlueCompressor": {
        "display_name": "Glue Compressor",
        "family": "Dynamics",
        "category": "Analog VCA Bus Compressor",
        "introduced": "Live 9",
        "architecture": "Cytomic emulation of the classic SSL 4000 G-Master bus compressor with discrete Attack/Release steps, Range limiter, and sidechain filter.",
    },
    "MultibandDynamics": {
        "display_name": "Multiband Dynamics",
        "family": "Dynamics",
        "category": "3-Band Upward/Downward Dynamics",
        "introduced": "Live 7",
        "architecture": "3-band dynamics processor with independent low/mid/high crossovers, upward/downward compression and expansion, and sidechain routing.",
    },
    "Gate": {
        "display_name": "Gate",
        "family": "Dynamics",
        "category": "Noise Gate / Ducker",
        "introduced": "Live 1",
        "architecture": "Noise gate with lookahead, Return hysteresis, Hold time, Ducking mode (inverts gate behavior), and sidechain bandpass filter.",
    },
    "Limiter": {
        "display_name": "Limiter",
        "family": "Dynamics",
        "category": "Peak Brickwall Limiter",
        "introduced": "Live 7",
        "architecture": "Mastering peak limiter with Lookahead (1.5ms, 3ms, 6ms), Ceiling, Release, and Stereo Link control.",
    },

    # --- Audio Effects: Filter & EQ ---
    "AutoFilter2": {
        "display_name": "Auto Filter",
        "family": "Filter & EQ",
        "category": "Analog Modeled Filter",
        "introduced": "Live 9.5",
        "architecture": "Cytomic analog filter circuit emulations (Clean, SMP, OSR, MS2, PRD) with Drive, envelope follower, tempo-synced stereo LFO, and sidechain envelope modulation.",
    },
    "AutoFilter": {
        "display_name": "Auto Filter (Legacy)",
        "family": "Filter & EQ",
        "category": "Legacy Auto Filter",
        "introduced": "Live 1",
        "architecture": "Early digital biquad filter with envelope follower and LFO.",
    },
    "Eq8": {
        "display_name": "EQ Eight",
        "family": "Filter & EQ",
        "category": "8-Band Parametric EQ",
        "introduced": "Live 7",
        "architecture": "8-band parametric equalizer with Cytomic oversampled filters, Stereo/Left-Right/Mid-Side processing modes, and integrated real-time spectrum display.",
    },
    "ChannelEq": {
        "display_name": "Channel EQ",
        "family": "Filter & EQ",
        "category": "Channel Strip EQ",
        "introduced": "Live 10.1",
        "architecture": "American console style channel EQ with highpass filter (80 Hz), low shelf, sweepable adaptive-Q mid band, and 8 kHz / 15 kHz high shelf.",
    },
    "FilterEQ3": {
        "display_name": "EQ Three",
        "family": "Filter & EQ",
        "category": "3-Band DJ Kill EQ",
        "introduced": "Live 1",
        "architecture": "3-band DJ mixer style EQ with individual 24 dB / 48 dB kill switches and sweepable crossover frequencies.",
    },

    # --- Audio Effects: Time & Delay ---
    "Echo": {
        "display_name": "Echo",
        "family": "Time & Delay",
        "category": "Modulated Tape / Analog Delay",
        "introduced": "Live 10",
        "architecture": "Dual delay lines with tape/analog modeling, Repitch/Fade smoothing, feedback inversion, ducking compressor, gate, wobble modulation, noise, and diffusion reverb.",
    },
    "Delay": {
        "display_name": "Delay",
        "family": "Time & Delay",
        "category": "Stereo Delay",
        "introduced": "Live 10.1",
        "architecture": "Combined Simple Delay and Ping Pong Delay replacement with Repitch/Fade/Jump delay change modes, stereo link, and integrated high/low pass filter.",
    },
    "FilterDelay": {
        "display_name": "Filter Delay",
        "family": "Time & Delay",
        "category": "3-Tap Multi-Band Delay",
        "introduced": "Live 1",
        "architecture": "3 independent delay lines (Left, Left+Right, Right) each with its own bandpass filter, tempo sync, delay time, pan, and volume.",
    },
    "GrainDelay": {
        "display_name": "Grain Delay",
        "family": "Time & Delay",
        "category": "Granular Smear Delay",
        "introduced": "Live 4",
        "architecture": "Granular delay slicing incoming audio into tiny grains with grain pitch shift, frequency mod, random pitch spray, and feedback.",
    },
    "BeatRepeat": {
        "display_name": "Beat Repeat",
        "family": "Time & Delay",
        "category": "Rhythmic Stutter & Repeat",
        "introduced": "Live 4",
        "architecture": "Rhythmic buffer capture and repeat processor with chance probability, pitch decay, repeat interval grid, and gate/mix/insert routing.",
    },
    "Looper": {
        "display_name": "Looper",
        "family": "Time & Delay",
        "category": "Live Phrase Looper",
        "introduced": "Live 8",
        "architecture": "Hardware-style phrase looper with tempo detection, overdub, multi-undo, reverse playback, half/double speed, and export to clip.",
    },

    # --- Audio Effects: Space & Reverb ---
    "Hybrid": {
        "display_name": "Hybrid Reverb",
        "family": "Space & Reverb",
        "category": "Convolution + Algorithmic Reverb",
        "introduced": "Live 11",
        "architecture": "Dual-engine reverb pairing impulse response convolution with 5 algorithmic engines (Dark Principal, Shimmer, Tides, Quartz, Prism) with serial/parallel routing and 4-band EQ.",
    },
    "Reverb": {
        "display_name": "Reverb",
        "family": "Space & Reverb",
        "category": "Algorithmic Diffusion Reverb",
        "introduced": "Live 1",
        "architecture": "Feedback delay network (FDN) algorithmic diffusion reverb with early reflection shape, room size, high/low shelf damping, and stereo chorus.",
    },
    "Resonator": {
        "display_name": "Resonators",
        "family": "Space & Reverb",
        "category": "Tuned Resonant Filter Bank",
        "introduced": "Live 4",
        "architecture": "5 parallel tuned bandpass comb resonators with root pitch, semitone intervals, decay time, constant width filter mode, and pan spread.",
    },

    # --- Audio Effects: Modulation & Pitch ---
    "AutoShift": {
        "display_name": "Auto Shift",
        "family": "Modulation & Pitch",
        "category": "Pitch Tracking & Formant Harmonizer",
        "introduced": "Live 12",
        "architecture": "Real-time monophonic pitch tracker, scale quantizer, formant shifter/follower, vibrato generator, and MIDI-controlled polyphonic harmonizer.",
    },
    "Shifter": {
        "display_name": "Shifter",
        "family": "Modulation & Pitch",
        "category": "Pitch & Frequency Shifter",
        "introduced": "Live 11.1",
        "architecture": "Multi-mode processor supporting Pitch Shifting (with delay/feedback), linear Frequency Shifting, and Ring Modulation with wide stereo LFO.",
    },
    "FrequencyShifter": {
        "display_name": "Frequency Shifter (Legacy)",
        "family": "Modulation & Pitch",
        "category": "Legacy Frequency Shifter",
        "introduced": "Live 8",
        "architecture": "Bode-style frequency shifter and ring modulator.",
    },
    "Chorus2": {
        "display_name": "Chorus-Ensemble",
        "family": "Modulation & Pitch",
        "category": "Multi-Voice Chorus & Ensemble",
        "introduced": "Live 11",
        "architecture": "Chorus, Vibrato, and vintage 3-phase string Ensemble processor with width control and warm analog-style saturation.",
    },
    "Chorus": {
        "display_name": "Chorus (Legacy)",
        "family": "Modulation & Pitch",
        "category": "Legacy Chorus",
        "introduced": "Live 1",
        "architecture": "Classic dual-delay line chorus with feedback.",
    },
    "PhaserNew": {
        "display_name": "Phaser-Flanger",
        "family": "Modulation & Pitch",
        "category": "Phaser & Comb Flanger",
        "introduced": "Live 11",
        "architecture": "Combined allpass phaser and short-delay flanger with Doubler mode, notch count adjustment, feedback color, and stereo phase offset.",
    },
    "Phaser": {
        "display_name": "Phaser (Legacy)",
        "family": "Modulation & Pitch",
        "category": "Legacy Phaser",
        "introduced": "Live 1",
        "architecture": "Multi-stage allpass filter phaser.",
    },
    "Flanger": {
        "display_name": "Flanger (Legacy)",
        "family": "Modulation & Pitch",
        "category": "Legacy Flanger",
        "introduced": "Live 1",
        "architecture": "Modulated comb delay flanger with feedback.",
    },
    "AutoPan2": {
        "display_name": "Auto Pan",
        "family": "Modulation & Pitch",
        "category": "Stereo Panner & Tremolo",
        "introduced": "Live 10",
        "architecture": "LFO-driven stereo panner and tremolo with Sine/Triangle/Spin waveforms, stereo phase offset, and Invert switch.",
    },
    "AutoPan": {
        "display_name": "Auto Pan (Legacy)",
        "family": "Modulation & Pitch",
        "category": "Legacy Auto Pan",
        "introduced": "Live 1",
        "architecture": "Early stereo panner.",
    },
    "Corpus": {
        "display_name": "Corpus",
        "family": "Modulation & Pitch",
        "category": "Physical Modeling Resonator",
        "introduced": "Live 8",
        "architecture": "AAS physical modeling resonator effect imposing acoustic material resonances (Membrane, Plate, String, Beam, Marimba, Pipe, Tube) onto incoming audio.",
    },
    "Vocoder": {
        "display_name": "Vocoder",
        "family": "Modulation & Pitch",
        "category": "40-Band Vocoder",
        "introduced": "Live 8",
        "architecture": "40-band channel vocoder with internal Noise carrier, Pitch Tracking monophonic synth carrier, External sidechain carrier, Formant shift, and band gating.",
    },

    # --- Audio Effects: Spectral Resynthesis ---
    "Spectral": {
        "display_name": "Spectral Time",
        "family": "Spectral Resynthesis",
        "category": "FFT Spectral Delay & Freeze",
        "introduced": "Live 11",
        "architecture": "Real-time FFT spectral delay and spectral freezer with frequency tilt, diffusion spray, masking filter, and transient-aware onset preservation.",
    },
    "Transmute": {
        "display_name": "Spectral Resonator",
        "family": "Spectral Resynthesis",
        "category": "FFT Modal Resonator",
        "introduced": "Live 11",
        "architecture": "FFT-based resonant comb processor with partial stretch, frequency shift, decay damping, and MIDI polyphonic pitch tracking.",
    },

    # --- Audio Effects: Utility & Analysis ---
    "StereoGain": {
        "display_name": "Utility",
        "family": "Utility & Analysis",
        "category": "Gain, Pan & Width Utility",
        "introduced": "Live 1",
        "architecture": "Audio utility providing +/-35 dB gain, stereo balance/panning, stereo width (0-400%), Bass Mono crossover (up to 500 Hz), phase invert, and DC filter.",
    },
    "Tuner": {
        "display_name": "Tuner",
        "family": "Utility & Analysis",
        "category": "Chromatic Tuner",
        "introduced": "Live 9.2",
        "architecture": "Instrument chromatic pitch detector with strobe/classic views and reference pitch calibration (410-480 Hz).",
    },
    "SpectrumAnalyzer": {
        "display_name": "Spectrum",
        "family": "Utility & Analysis",
        "category": "FFT Audio Spectrum Display",
        "introduced": "Live 7",
        "architecture": "Real-time FFT spectrum analyzer with block sizes from 256 to 16384 samples, peak hold, average curves, and stereo channel overlay.",
    },
    "SignalGenerator": {
        "display_name": "Test Tone Generator",
        "family": "Utility & Analysis",
        "category": "Signal & Noise Generator",
        "introduced": "Live 1",
        "architecture": "Calibration test generator producing pure sine test tones and pink/white noise for room and pipeline calibration.",
    },
    "SignalAnalyzer": {
        "display_name": "Signal Analyzer",
        "family": "Utility & Analysis",
        "category": "Diagnostic Signal Meter",
        "introduced": "Live 1",
        "architecture": "Internal diagnostic signal level and polarity analyzer.",
    },
    "Eq8SpectrumAnalyzer": {
        "display_name": "EQ Eight Analyzer",
        "family": "Utility & Analysis",
        "category": "EQ Embedded Spectrum Display",
        "introduced": "Live 9",
        "architecture": "Embedded FFT analysis module integrated directly into EQ Eight's display canvas.",
    },

    # --- MIDI Effects ---
    "MidiArpeggiator": {
        "display_name": "Arpeggiator",
        "family": "MIDI Effects",
        "category": "Pattern Arpeggiator",
        "introduced": "Live 4",
        "architecture": "Classic and complex arpeggiator with 20 direction styles, groove sync, octave transpose range, velocity decay/target, and chord trigger modes.",
    },
    "MidiChord": {
        "display_name": "Chord",
        "family": "MIDI Effects",
        "category": "Harmonic Chord Generator",
        "introduced": "Live 4",
        "architecture": "Adds up to 6 shifted intervals (+/-36 semitones) to incoming MIDI notes with individual velocity scaling per voice.",
    },
    "MidiScale": {
        "display_name": "Scale",
        "family": "MIDI Effects",
        "category": "Scale Quantizer",
        "introduced": "Live 4",
        "architecture": "Quantizes all incoming 12 chromatic pitches to user-defined 12-semitone target maps with base key transpose and fold range.",
    },
    "MidiRandom": {
        "display_name": "Random",
        "family": "MIDI Effects",
        "category": "Pitch Randomizer",
        "introduced": "Live 4",
        "architecture": "Randomly alters incoming note pitches within a chosen semitone range with Chance percentage and bi-directional mode.",
    },
    "MidiPitcher": {
        "display_name": "Pitch",
        "family": "MIDI Effects",
        "category": "Pitch Transpose",
        "introduced": "Live 4",
        "architecture": "Transposes incoming MIDI notes by +/-128 semitones with lowest/highest note filter range.",
    },
    "MidiVelocity": {
        "display_name": "Velocity",
        "family": "MIDI Effects",
        "category": "Velocity Curve Shaper",
        "introduced": "Live 4",
        "architecture": "Compresses, expands, clamps, and curves incoming note velocities with random spread and note-on/note-off mode.",
    },
    "MidiNoteLength": {
        "display_name": "Note Length",
        "family": "MIDI Effects",
        "category": "Gate Duration Shaper",
        "introduced": "Live 4",
        "architecture": "Sets fixed gate length or sync division for incoming notes with release velocity trigger mode.",
    },
    "MidiCcControl": {
        "display_name": "CC Control",
        "family": "MIDI Effects",
        "category": "MIDI CC Mapper & Automation",
        "introduced": "Live 12",
        "architecture": "Transmits and automates up to 8 MIDI continuous controllers (CCs) with custom CC numbers, ranges, and curve smoothing.",
    },

    # --- Racks, Routing & Containers ---
    "AudioEffectGroupDevice": {
        "display_name": "Audio Effect Rack",
        "family": "Racks & Containers",
        "category": "Multi-Chain Audio Processing Container",
        "introduced": "Live 6",
        "architecture": "Parallel and serial audio device chain container with chain selector zones, 8/16 macro controls, and macro variation states.",
    },
    "MidiEffectGroupDevice": {
        "display_name": "MIDI Effect Rack",
        "family": "Racks & Containers",
        "category": "Multi-Chain MIDI Processing Container",
        "introduced": "Live 6",
        "architecture": "Parallel MIDI processor container with key/velocity zones, chain selector, and macro controls.",
    },
    "AudioBranchMixerDevice": {
        "display_name": "Audio Chain Mixer",
        "family": "Racks & Containers",
        "category": "Rack Sub-Chain Mixer",
        "introduced": "Live 6",
        "architecture": "Individual chain volume, pan, solo, mute, and send router inside racks.",
    },
    "MidiBranchMixerDevice": {
        "display_name": "MIDI Chain Mixer",
        "family": "Racks & Containers",
        "category": "Rack Sub-Chain MIDI Router",
        "introduced": "Live 6",
        "architecture": "Individual MIDI chain mute, solo, and zone routing inside racks.",
    },
    "TrackDevice": {
        "display_name": "Track Mixer",
        "family": "Racks & Containers",
        "category": "DAW Track Mixer Module",
        "introduced": "Live 1",
        "architecture": "DAW mixer channel module providing track Volume, Pan, Solo, Arm, Mute, and send levels.",
    },
    "MainTrackDevice": {
        "display_name": "Master Track Mixer",
        "family": "Racks & Containers",
        "category": "Master Output Module",
        "introduced": "Live 1",
        "architecture": "Master bus output module with master fader, cue volume, and tempo modulation controls.",
    },
    "Metronome": {
        "display_name": "Metronome",
        "family": "Racks & Containers",
        "category": "Click Sound Generator",
        "introduced": "Live 1",
        "architecture": "Generates metronome click audio with Classic, Click, and Wood sounds with beat divisions.",
    },
    "MxDeviceAudioEffect": {
        "display_name": "Max Audio Effect",
        "family": "Racks & Containers",
        "category": "Max for Live Audio Host",
        "introduced": "Live 8.1",
        "architecture": "Hosting wrapper executing Max/MSP visual DSP patches as native Live audio effects.",
    },
    "MxDeviceInstrument": {
        "display_name": "Max Instrument",
        "family": "Racks & Containers",
        "category": "Max for Live Synth Host",
        "introduced": "Live 8.1",
        "architecture": "Hosting wrapper executing Max/MSP synthesizer patches as native Live instruments.",
    },
    "MxDeviceMidiEffect": {
        "display_name": "Max MIDI Effect",
        "family": "Racks & Containers",
        "category": "Max for Live MIDI Host",
        "introduced": "Live 8.1",
        "architecture": "Hosting wrapper executing Max visual dataflow patches as native Live MIDI effects.",
    },
    "PluginDevice": {
        "display_name": "VST Plugin Device",
        "family": "Racks & Containers",
        "category": "Third-Party VST2/VST3 Host",
        "introduced": "Live 1",
        "architecture": "Host container for external VST2 and VST3 audio plugins with parameter mapping and automation.",
    },
    "AuPluginDevice": {
        "display_name": "Audio Unit Plugin Device",
        "family": "Racks & Containers",
        "category": "Third-Party macOS AU Host",
        "introduced": "Live 4",
        "architecture": "Host container for macOS Audio Unit v2 plugins with parameter mapping and Cocoa GUI rendering.",
    },
    "ProxyAudioEffectDevice": {
        "display_name": "Proxy Audio Effect",
        "family": "Racks & Containers",
        "category": "Controller Proxy Wrapper",
        "introduced": "Live 9",
        "architecture": "Hardware controller (Push) parameter exposure proxy for audio devices.",
    },
    "ProxyInstrumentDevice": {
        "display_name": "Proxy Instrument",
        "family": "Racks & Containers",
        "category": "Controller Proxy Wrapper",
        "introduced": "Live 9",
        "architecture": "Hardware controller (Push) parameter exposure proxy for instrument devices.",
    },

    # --- Internal / Diagnostics ---
    "AudioLoadDevice": {
        "display_name": "Audio Load Test",
        "family": "Internal & Diagnostics",
        "category": "DSP Benchmarking Device",
        "introduced": "Live 1",
        "architecture": "Internal DSP engine load simulator for measuring audio engine CPU headroom.",
    },
    "AudioSequencer": {
        "display_name": "Audio Sequencer",
        "family": "Internal & Diagnostics",
        "category": "Timeline Audio Player",
        "introduced": "Live 1",
        "architecture": "Low-level audio clip timeline playback and streaming device.",
    },
    "MidiSequencer": {
        "display_name": "MIDI Sequencer",
        "family": "Internal & Diagnostics",
        "category": "Timeline MIDI Player",
        "introduced": "Live 1",
        "architecture": "Low-level MIDI clip playback and event dispatcher.",
    },
    "TestSampler": {
        "display_name": "Test Sampler",
        "family": "Internal & Diagnostics",
        "category": "Internal Test Instrument",
        "introduced": "Live 1",
        "architecture": "Internal automated QA test sample player.",
    },
    "BufferAudioDevice": {
        "display_name": "Buffer Audio Test",
        "family": "Internal & Diagnostics",
        "category": "Audio Buffer Diagnostic",
        "introduced": "Live 1",
        "architecture": "Audio buffer callback timing and alignment test fixture.",
    },
    "BufferInstrument": {
        "display_name": "Buffer Instrument Test",
        "family": "Internal & Diagnostics",
        "category": "Instrument Buffer Diagnostic",
        "introduced": "Live 1",
        "architecture": "Synth buffer allocation test fixture.",
    },
    "BufferLatencyTest": {
        "display_name": "Buffer Latency Test",
        "family": "Internal & Diagnostics",
        "category": "Driver Latency Test",
        "introduced": "Live 1",
        "architecture": "Hardware driver audio latency calibration test fixture.",
    },
    "BufferMidiDevice": {
        "display_name": "Buffer MIDI Test",
        "family": "Internal & Diagnostics",
        "category": "MIDI Buffer Diagnostic",
        "introduced": "Live 1",
        "architecture": "MIDI buffer timing and event jitter test fixture.",
    },
    "LatencyTest": {
        "display_name": "Latency Test",
        "family": "Internal & Diagnostics",
        "category": "Latency Calibration",
        "introduced": "Live 1",
        "architecture": "Hardware roundtrip latency calibration engine.",
    },
    "LatencyTestMs": {
        "display_name": "Latency Test Ms",
        "family": "Internal & Diagnostics",
        "category": "Latency Calibration Milliseconds",
        "introduced": "Live 1",
        "architecture": "Hardware roundtrip latency measurement in milliseconds.",
    },
    "MidiLatencyTest": {
        "display_name": "MIDI Latency Test",
        "family": "Internal & Diagnostics",
        "category": "MIDI Latency Calibration",
        "introduced": "Live 1",
        "architecture": "MIDI roundtrip latency measurement fixture.",
    },
    "MidiLatencyTestMs": {
        "display_name": "MIDI Latency Test Ms",
        "family": "Internal & Diagnostics",
        "category": "MIDI Latency Milliseconds",
        "introduced": "Live 1",
        "architecture": "MIDI roundtrip latency measurement fixture in milliseconds.",
    },
    "DeviceKitFakeAudioEffect": {
        "display_name": "DeviceKit Audio Stub",
        "family": "Internal & Diagnostics",
        "category": "SDK Mock Device",
        "introduced": "Live 10",
        "architecture": "Internal DeviceKit SDK unit test audio stub.",
    },
    "DeviceKitFakeInstrument": {
        "display_name": "DeviceKit Instrument Stub",
        "family": "Internal & Diagnostics",
        "category": "SDK Mock Device",
        "introduced": "Live 10",
        "architecture": "Internal DeviceKit SDK unit test instrument stub.",
    },
    "DeviceKitFakeMidiEffect": {
        "display_name": "DeviceKit MIDI Stub",
        "family": "Internal & Diagnostics",
        "category": "SDK Mock Device",
        "introduced": "Live 10",
        "architecture": "Internal DeviceKit SDK unit test MIDI stub.",
    },
}

# Subcomponents known to belong to parent devices
SUBCOMPONENT_PARENTS = {
    "OperatorFilter": "Operator",
    "OperatorGlobals": "Operator",
    "OperatorLfo": "Operator",
    "OperatorOperator": "Operator",
    "OperatorOperatorTune": "Operator",
    "OperatorPitchEnvelope": "Operator",
    "OperatorShaper": "Operator",
    "OperatorTimeableModConnection": "Operator",
    "CollisionLfo": "Collision",
    "CollisionMallet": "Collision",
    "CollisionModTarget": "Collision",
    "CollisionNoise": "Collision",
    "CollisionResonator": "Collision",
    "UltraAnalogEnvelope": "UltraAnalog",
    "UltraAnalogSignalChain1": "UltraAnalog",
    "UltraAnalogSignalChain2": "UltraAnalog",
    "SimplerAuxEnvelope": "OriginalSimpler",
    "SimplerAuxEnvelopeHolder": "OriginalSimpler",
    "SimplerAuxLfo": "OriginalSimpler",
    "SimplerAuxLfoHolder": "OriginalSimpler",
    "SimplerFilter": "OriginalSimpler",
    "SimplerFilterEnvelope": "OriginalSimpler",
    "SimplerFilterHolder": "OriginalSimpler",
    "SimplerGlobals": "OriginalSimpler",
    "SimplerLfo": "OriginalSimpler",
    "SimplerLfoHolder": "OriginalSimpler",
    "SimplerLoopModulators": "OriginalSimpler",
    "SimplerOneShotEnvelope": "OriginalSimpler",
    "SimplerPitch": "OriginalSimpler",
    "SimplerPitchEnvelope": "OriginalSimpler",
    "SimplerPitchEnvelopeHolder": "OriginalSimpler",
    "SimplerPlayer": "OriginalSimpler",
    "SimplerShaper": "OriginalSimpler",
    "SimplerShaperHolder": "OriginalSimpler",
    "SimplerSubOsc": "OriginalSimpler",
    "SimplerSubOscHolder": "OriginalSimpler",
    "SimplerVolumeAndPan": "OriginalSimpler",
    "AutoFilterLfo": "AutoFilter2",
    "AutoPanLfo": "AutoPan2",
    "FlangerLfo": "Flanger",
    "FrequencyShifterLfo": "FrequencyShifter",
    "PhaserLfo": "Phaser",
    "VocoderFilterBank": "Vocoder",
    "VocoderCarrierSource": "Vocoder",
    "Eq8BandParameter": "Eq8",
    "ModulationConnectionsForMeld": "InstrumentMeld",
    "ModulationConnectionsForInstrumentVector": "InstrumentVector",
    "SideChain": "Compressor2",
    "SideChainEq": "Compressor2",
}


def classify_field(name, cls, typ):
    """Categorize a parameter based on name and class."""
    if any(t in cls for t in ["TimeableFloat", "UserFloat", "TimeablePluginFloat"]):
        return "Audio/DSP Float Parameter (Modulatable/Automatable)"
    elif "TimeableEnum" in cls or "RemoteableEnum" in cls:
        return "Discrete Enum / Mode Selector"
    elif "TimeableBool" in cls or "RemoteableBool" in cls:
        return "Boolean Gate / Toggle"
    elif "RemoteableInt" in cls or "RangedRemoteableInt" in cls or "Int" in cls:
        return "Integer Counter / Index"
    elif "RemoteableString" in cls or "String" in cls:
        return "String / Name"
    elif "Slot" in cls:
        return "Sub-Component / Slot Reference"
    elif "List" in cls:
        return "List / Collection"
    elif "View" in cls:
        return "UI View State"
    else:
        return f"Structure / {cls}"


def parse_schema(schema_path=LIVE_SCHEMA):
    """Parse Ableton XML schema into complete device catalog, subcomponents, and MIDI algorithms."""
    if not os.path.exists(schema_path):
        raise FileNotFoundError(f"Schema file not found at {schema_path}")

    tree = ET.parse(schema_path)
    root = tree.getroot()

    all_classes = {child.tag: child for child in root}

    # Discover devices (classes that contain ParametersListWrapper)
    devices = {}
    for tag, elem in all_classes.items():
        fields_dict = {sub.tag: sub.attrib for sub in elem}
        if "ParametersListWrapper" in fields_dict:
            meta = DEVICE_METADATA.get(tag, {
                "display_name": tag,
                "family": "Other Devices",
                "category": "Generic Device",
                "introduced": "Live",
                "architecture": "Live device model.",
            })

            params = []
            dsp_params_count = 0
            automation_params_count = 0

            for sub in elem:
                sub_cls = sub.attrib.get("Class", "")
                sub_typ = sub.attrib.get("Type", "")
                cat = classify_field(sub.tag, sub_cls, sub_typ)

                is_dsp = any(t in sub_cls for t in ["Timeable", "UserFloat", "UserInt", "UserBool"])
                is_auto = "Timeable" in sub_cls or "UserFloat" in sub_cls or "Remoteable" in sub_cls

                if is_dsp:
                    dsp_params_count += 1
                if is_auto:
                    automation_params_count += 1

                params.append({
                    "name": sub.tag,
                    "class": sub_cls,
                    "type": sub_typ,
                    "category": cat,
                    "is_dsp": is_dsp,
                    "is_automatable": is_auto,
                })

            devices[tag] = {
                "schema_class": tag,
                "display_name": meta["display_name"],
                "family": meta["family"],
                "category": meta["category"],
                "introduced": meta["introduced"],
                "architecture": meta["architecture"],
                "total_fields": len(elem),
                "dsp_params_count": dsp_params_count,
                "automation_params_count": automation_params_count,
                "parameters": params,
                "subcomponents": [],
            }

    # Discover DSP subcomponents
    subcomponents = {}
    for tag, elem in all_classes.items():
        if tag not in devices:
            fields_dict = {sub.tag: sub.attrib for sub in elem}
            has_timeable = any("Timeable" in sub.attrib.get("Class", "") for sub in elem)
            if has_timeable or tag in SUBCOMPONENT_PARENTS:
                params = []
                for sub in elem:
                    sub_cls = sub.attrib.get("Class", "")
                    sub_typ = sub.attrib.get("Type", "")
                    params.append({
                        "name": sub.tag,
                        "class": sub_cls,
                        "type": sub_typ,
                        "category": classify_field(sub.tag, sub_cls, sub_typ),
                    })
                parent = SUBCOMPONENT_PARENTS.get(tag, "Unknown / Shared")
                subcomponents[tag] = {
                    "schema_class": tag,
                    "parent_device": parent,
                    "total_fields": len(elem),
                    "parameters": params,
                }
                # Link to parent device if found
                if parent in devices:
                    devices[parent]["subcomponents"].append(tag)

    # Discover MIDI / Transform algorithms
    midi_algorithms = {}
    for tag, elem in all_classes.items():
        if "Algorithm" in tag and tag not in devices and tag not in subcomponents:
            params = []
            for sub in elem:
                sub_cls = sub.attrib.get("Class", "")
                sub_typ = sub.attrib.get("Type", "")
                params.append({
                    "name": sub.tag,
                    "class": sub_cls,
                    "type": sub_typ,
                    "category": classify_field(sub.tag, sub_cls, sub_typ),
                })
            midi_algorithms[tag] = {
                "schema_class": tag,
                "total_fields": len(elem),
                "parameters": params,
            }

    return {
        "version": root.attrib.get("Version", "5"),
        "translator": root.attrib.get("TranslatorNumber", "12402"),
        "devices": devices,
        "subcomponents": subcomponents,
        "midi_algorithms": midi_algorithms,
    }


def render_markdown(catalog):
    """Render comprehensive markdown report across all Ableton Live 12 models."""
    devices = catalog["devices"]
    subcomponents = catalog["subcomponents"]
    algorithms = catalog["midi_algorithms"]

    total_devices = len(devices)
    total_device_fields = sum(d["total_fields"] for d in devices.values())
    total_dsp_params = sum(d["dsp_params_count"] for d in devices.values())
    total_sub_fields = sum(s["total_fields"] for s in subcomponents.values())
    total_algo_fields = sum(a["total_fields"] for a in algorithms.values())

    lines = [
        "# Ableton Live 12 Suite — Complete Device & Architecture Schema Mapping",
        "",
        "> **Clean Room Invariant**: Extracted exclusively from public application schema "
        "`12.0_12402.txt` in Live 12 Suite bundle. Zero decompilation or reverse assembly of commercial binaries.",
        "",
        "## 1. Executive Summary & Scale",
        "",
        f"- **Schema Version**: {catalog['version']} (Translator Number {catalog['translator']})",
        f"- **Total Native Device Classes**: **{total_devices}**",
        f"- **Total Direct Device Parameters & Fields**: **{total_device_fields:,}**",
        f"- **Direct Modulatable / DSP Parameters**: **{total_dsp_params:,}**",
        f"- **DSP Sub-Component Modules**: **{len(subcomponents)}** ({total_sub_fields:,} fields)",
        f"- **Live 12 Generative / Transform Algorithms**: **{len(algorithms)}** ({total_algo_fields:,} fields)",
        f"- **Combined Architectural Footprint**: **{total_device_fields + total_sub_fields + total_algo_fields:,} structured parameters**",
        "",
        "---",
        "",
        "## 2. Models by Family Breakdown",
        "",
    ]

    # Group by family
    families = {}
    for dev in devices.values():
        fam = dev["family"]
        families.setdefault(fam, []).append(dev)

    family_order = [
        "Instruments",
        "Saturation & Color",
        "Dynamics",
        "Filter & EQ",
        "Time & Delay",
        "Space & Reverb",
        "Modulation & Pitch",
        "Spectral Resynthesis",
        "Utility & Analysis",
        "MIDI Effects",
        "Racks & Containers",
        "Internal & Diagnostics",
    ]

    # Family summary table
    summary_headers = ["Family", "Device Count", "Direct Fields", "DSP / Mod Params"]
    summary_rows = []
    for fam in family_order:
        devs = families.get(fam, [])
        f_count = sum(d["total_fields"] for d in devs)
        d_count = sum(d["dsp_params_count"] for d in devs)
        summary_rows.append([fam, len(devs), f"{f_count:,}", f"{d_count:,}"])

    lines.append(md_table(summary_headers, summary_rows))
    lines.append("")
    lines.append("---")
    lines.append("")

    # Detailed section for each family
    for fam in family_order:
        devs = sorted(families.get(fam, []), key=lambda x: x["display_name"])
        if not devs:
            continue

        lines.append(f"## 3.{family_order.index(fam)+1} {fam} ({len(devs)} Devices)")
        lines.append("")

        for dev in devs:
            lines.append(f"### {dev['display_name']} (`{dev['schema_class']}`)")
            lines.append(f"- **Category**: {dev['category']} *(Introduced in {dev['introduced']})*")
            lines.append(f"- **Total Fields**: {dev['total_fields']} | **DSP / Modulatable Params**: {dev['dsp_params_count']}")
            lines.append(f"- **Architecture Blueprint**: {dev['architecture']}")

            if dev["subcomponents"]:
                subs_str = ", ".join(f"`{s}`" for s in dev["subcomponents"])
                lines.append(f"- **Sub-Component Modules**: {subs_str}")

            # Top 12 parameters preview
            params = dev["parameters"]
            dsp_sample = [p for p in params if p["is_dsp"]][:12]
            if dsp_sample:
                p_headers = ["Parameter", "Class", "Type", "Classification"]
                p_rows = [[p["name"], p["class"], p["type"], p["category"]] for p in dsp_sample]
                lines.append("")
                lines.append(md_table(p_headers, p_rows))
                if len(params) > 12:
                    lines.append(f"*... and {len(params) - 12} more parameters in JSON schema.*")

            lines.append("")

    # DSP Subcomponents section
    lines.append("---")
    lines.append("")
    lines.append(f"## 4. DSP Sub-Component Modules ({len(subcomponents)} Classes)")
    lines.append("")
    lines.append("These modular structs define internal engines (oscillators, filters, envelopes, resonators) embedded into devices:")
    lines.append("")

    sub_headers = ["Subcomponent Class", "Parent Device", "Field Count", "Sample Fields"]
    sub_rows = []
    for s_name in sorted(subcomponents.keys()):
        s = subcomponents[s_name]
        sample = ", ".join(p["name"] for p in s["parameters"][:4])
        sub_rows.append([f"`{s_name}`", s["parent_device"], s["total_fields"], sample])

    lines.append(md_table(sub_headers, sub_rows))
    lines.append("")

    # Live 12 MIDI / Transform Algorithms
    lines.append("---")
    lines.append("")
    lines.append(f"## 5. Live 12 MIDI Transform & Generative Algorithms ({len(algorithms)} Classes)")
    lines.append("")
    lines.append("Live 12 introduces generative MIDI Tools with dedicated algorithm schemas:")
    lines.append("")

    algo_headers = ["Algorithm Class", "Field Count", "Parameters"]
    algo_rows = []
    for a_name in sorted(algorithms.keys()):
        a = algorithms[a_name]
        param_str = ", ".join(p["name"] for p in a["parameters"][:6])
        algo_rows.append([f"`{a_name}`", a["total_fields"], param_str])

    lines.append(md_table(algo_headers, algo_rows))
    lines.append("")

    return "\n".join(lines)


def run_selftest():
    """Verify schema parser contracts and catalog integrity."""
    t = SelfTest("ableton_schema_extractor")

    if os.path.exists(LIVE_SCHEMA):
        catalog = parse_schema()
        devices = catalog["devices"]
        subcomponents = catalog["subcomponents"]
        algorithms = catalog["midi_algorithms"]

        t.check(len(devices) == 103, f"Expected 103 devices, got {len(devices)}")
        t.check("InstrumentMeld" in devices, "Meld device present")
        t.check("Roar" in devices, "Roar device present")
        t.check("Drift" in devices, "Drift device present")
        t.check("InstrumentVector" in devices, "Wavetable device present")
        t.check("AutoShift" in devices, "AutoShift device present")
        t.check("Echo" in devices, "Echo device present")
        t.check("Hybrid" in devices, "Hybrid Reverb present")
        t.check("Compressor2" in devices, "Compressor2 present")
        t.check("GlueCompressor" in devices, "GlueCompressor present")
        t.check("Vocoder" in devices, "Vocoder present")

        # Check field counts on flagship devices
        t.check(devices["Roar"]["total_fields"] >= 200, "Roar has >= 200 fields")
        t.check(devices["InstrumentMeld"]["total_fields"] >= 150, "Meld has >= 150 fields")
        t.check(devices["InstrumentVector"]["total_fields"] >= 130, "Wavetable has >= 130 fields")

        # Check subcomponents and algorithms
        t.check(len(subcomponents) >= 40, f"Subcomponents count >= 40 (got {len(subcomponents)})")
        t.check("VocoderFilterBank" in subcomponents, "VocoderFilterBank present")
        t.check("CollisionResonator" in subcomponents, "CollisionResonator present")
        t.check("OperatorFilter" in subcomponents, "OperatorFilter present")

        t.check(len(algorithms) >= 10, f"MIDI algorithms count >= 10 (got {len(algorithms)})")
        t.check("ArpeggiateAlgorithm" in algorithms, "ArpeggiateAlgorithm present")
        t.check("LfoAlgorithm" in algorithms, "LfoAlgorithm present")

        # Check markdown rendering
        md = render_markdown(catalog)
        t.check(len(md) > 5000, f"Markdown rendered successfully ({len(md)} bytes)")

    return t.done()


def main():
    parser = argparse.ArgumentParser(description="Extract parameter and architecture schema for every model in Ableton Live 12.")
    parser.add_argument("command", nargs="?", default="run", choices=["run"], help="Command to run (default: run)")
    parser.add_argument("--out", help="Markdown output path (default: ~/re-output/ableton/ableton_all_models.md)")
    parser.add_argument("--json", action="store_true", help="Also save complete JSON format")
    parser.add_argument("--self-test", action="store_true", help="Run internal self-tests and exit")
    args = parser.parse_args()

    if args.self_test:
        sys.exit(run_selftest())

    out_md = args.out or os.path.join(RE_OUTPUT, "ableton", "ableton_all_models.md")
    ensure_dir(os.path.dirname(out_md))

    catalog = parse_schema()
    md_text = render_markdown(catalog)
    write_out(md_text, out_md)
    print(f"wrote {out_md}")

    # Always write JSON when running default
    out_json = out_md.replace(".md", ".json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(catalog, f, indent=2)
    print(f"wrote {out_json}")


if __name__ == "__main__":
    main()
