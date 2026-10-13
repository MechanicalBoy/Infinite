# Outpacing Bitwig: Modulation Gaps & Engineering Roadmap

Companion to `docs/plans/modulation/README.md`. Bitwig side: shipped localization metadata of
Bitwig Studio 6.0.3, read by `tools/re-survey/modulation_map.py` (output
`~/re-output/modulation/bitwig_modulation_map.md`). Infinite side checked 2026-10-13 against
src/ and the node census; run `python3 tools/re-survey/diff.py claims` after editing.

---

## 1. Where Infinite and Bitwig Stand Today

- **Bitwig Studio 6.0.3**: 42 modulators across 8 categories.
- **Infinite**: 36 `IModulator` node classes across `src/nodes/` (`ModulatorNodes.h`, `MacroNodes.h`,
  `NoteNodes.h`, `MidiNodes.h`, `OscNodes.h`, `PredictionNodes.h` ...); the node list
  (infinite-patch-authoring skill) has 30 Modulators, 9 Macros, 8 Prediction nodes.
- **Map result**: 24 parity, 18 gaps, 2 Infinite leads (hand-written judgements per row in the map).
- **Infinite leads**:
  1. **Learning modulators (P3)**: `PredictiveModulatorNode` and the Prediction family learn the
     performer's gestures. Bitwig has no learning modulator.
  2. **In-patch gesture recorder**: `CVRecorderNode` records and loops a live gesture inside the
     patch.
  3. **Cross-domain reach**: one modulator drives audio, 3D, shader and video params.

---

## 2. The Technical Gaps

### Gap 1: Time-based MSEG (open)
* **Bitwig**: `segments` and `curves` are drawn breakpoints that run on their own clock, loop and
  retrigger, with tempo sync.
* **Infinite**: `ModCurveNode` is a multi-point *transfer* curve (input to output), not a clock.
  You can get a drawn LFO only by feeding it an LFO saw.
* **Requirement**: a time-based MSEG: breakpoints with per-segment curvature, loop A to B,
  sustain point with release, retrigger on gate, divisions from `rhythmic-quantization-standard`.
  Either a new MSEG node or a clocked mode of Mod Curve (the v0.6 plan settles which).

### Gap 2: De-zippering (done, Block 2, 2026-10-12)
* `ParamMailbox` ramps each frame value per sample, arriving one frame after its stamp; per-binding
  smoothing (`Modulation::Source::smoothMs`) is fps-independent.
* Measured (README "After Block 2"): zipper excess step worst 5.2e-4 against the 9.8e-4 limit,
  **pass** on every source and schedule; fixed lag of 1 frame + 1 block (27.3 ms at 60 fps / 512).
* **Still open**: modulators are sampled once per UI frame, so a modulator cannot FM a param at
  audio rate, and a step input is timed to the frame (0.30 error at 60 fps, tau 20 ms). That goes
  with Gap 3.

### Gap 3: Per-voice and audio-rate modulation (open, architecture)
* **Bitwig**: any modulator can be Poly: one instance per voice, at audio rate.
* **Infinite**: `IModulator::Value01()` returns one value shared by every voice.
* **Requirement**: per-voice modulator state for synth consumers, with per-sample modulation
  buffers so the same path serves audio-rate modulation. Design doc first (semi-brain check),
  then code; it changes the voice layout, so voice SIMD comes after it.

### Gap 4: Unison spread (`stack_spread`, open, follows Gap 3)
* **Bitwig**: offsets params across unison voices by golden ratio, primes or alternation.
* **Infinite**: no voice-index source.
* **Requirement**: once Gap 3 exists, a voice-index modulator (new `VoiceSpreadNode`) is small.

### Smaller gaps from the map
* Envelope has no hold stage or per-stage curvature (`ahdsr`), and gates on its mod input crossing
  a threshold, not on notes (`note_sidechain` needs Note to CV in front).
* No MPE expressions, no channel pressure; MIDI CC is a modulator, pitch bend sits in Notes.

---

## 3. How Infinite Outpaces Bitwig

1. **Audio-reactive visuals in one process**: Audio to CV and Audio Analyze feed shaders and 3D
   directly, no Syphon/OSC hop.
2. **Field modulators (P4)**: users write modulators as Field expressions (Field Graph).
3. **Learned performance modulators (P3)**: deepen the Prediction family toward tempo- and
   style-aware gesture prediction.

---

## 4. Execution

| Block | Branch | Work | State |
|---|---|---|---|
| 2 | `feature/mod-clock` | per-sample ramps, fps-independent smoothing | done 2026-10-12 |
| MSEG | `feature/mod-mseg` | time-based MSEG (new node or clocked Mod Curve) | v0.6 plan, Tier 3 |
| Poly | `feature/mod-poly` | per-voice + audio-rate modulation | v0.6 Block 2 item 2.12 (design doc first) |
