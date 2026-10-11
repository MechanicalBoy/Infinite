# Modulators to industry grade

Branch per block. Tracker: this file. Measured by `INFINITE_MODAUDIT`
(`src/app/selftest/ModAudit.cpp`). Raw baseline: `baseline-2026-10-12.txt`.

```bash
INFINITE_MODAUDIT=1 build/Infinite.app/Contents/MacOS/Infinite
INFINITE_MODAUDIT=1 INFINITE_MODAUDIT_ONLY=ZIPPER,FRATE build/Infinite.app/Contents/MacOS/Infinite
```

## 1. Goal

Match the accuracy and smoothness of Bitwig's modulators, Ableton's LFO and
Envelope Follower, and Serum's LFOs. Then go past them where Infinite is
different: one modulation driving audio, video and 3D at once,
per-destination smoothing, and learned (green) modulators.

## 2. Standards chased

| Area | Reference | Why |
|---|---|---|
| Phase | Sample-accurate, transport-locked (Bitwig, Ableton sync) | A 10-minute set must not drift off the grid |
| Delivery to audio | Per-sample ramps, no frame staircase (Bitwig, Serum) | Fast LFOs on filters/gain must not zipper |
| Delivery to video/3D | Value at the frame's own time | Picture locked to sound, export = live |
| Shapes | Analytic formula | A sine is a sine; phase origin documented |
| Divisions | `MusicTime` table (rhythmic-quantization-standard) | Triplets exact, same menu as the note nodes |
| Envelopes / followers | Stage times in ms, independent of fps | Ableton Envelope Follower, Bitwig ADSR |
| Randomness | Seeded, reproducible, independent per instance | Renders repeat; two LFOs don't march together |

## 3. Scope

- In scope: every IModulator (36 registered, all covered by the CPU/range pass),
  the modulation apply loop (`ApplyModulationAndPalette`), ParamMailbox
  delivery, and Prediction *output* delivery.
- Out of scope: audio DSP nodes, Field, Prediction learning.

## 4. Constraints

- Saved patches behave the same. A corrected default gets a legacy flag through BeforeLoadParams.
- No audio-thread allocation or locks.
- Works on all 3 platforms.
- Export is never worse than live.
- CPU no more than 10% worse.

## 5. Blocks

| # | Branch | Work | State |
|---|---|---|---|
| 1 | `feature/mod-audit` | MODAUDIT and this baseline | done |
| 2 | `feature/mod-clock` | Shared sample-accurate phase source; per-sample ramp delivery to audio params; per-destination fps-independent smoothing | not started |
| 3 | `feature/mod-maths` | Per-node fixes, each with a legacy flag | not started |

## 6. Success metrics

| # | Metric | Target | Baseline (2026-10-12) |
|---|---|---|---|
| 1 | Phase drift, 10 min, live/offline/loop/tempo change/seek | < 1 sample | **pass**: ≤ 9.4e-9 samples everywhere; seek exact; tempo change seamless |
| 2 | Zipper: per-sample step beyond the ideal curve's step, audio destination | ≤ 1/1024 | **fail** at fast rates: LFO 1/4 beat 1.7e-3 (b512, 60 fps), Vibrato 5 Hz 1.07e-3. Slower sources pass. Tracking error rms 0.24 (LFO 1/4 beat), 0.16 (Vibrato) |
| 3 | Video/3D value at the frame's time vs analytic | ≤ 1e-4 | offline **pass** (exact clock). Live **fail**: the clock is read 0.7–10.7 ms after frame time (block-quantised), worth 0.26 of range on LFO 1/4 beat, 0.017 on LFO 4 beats, full edges on Step Gate |
| 4 | Shape error | ≤ 1e-4 | **pass**: sine 2.1e-7, others 0, at beat 0 and 1e5; Vibrato 2.8e-8 at 1 h |
| 5a | Render vs realtime, pure nodes, same transport time | bit-exact | **pass**: 0/200 mismatches on every pure source |
| 5b | Render vs realtime, stateful nodes | ≤ 1e-4 | **fail**: all six stateful cases depend on frame rate (see 8 below) |
| 6 | Same seed, same output | identical | **pass** for Random and offline reruns; determinism-check.py pass. Flags: LFO S&H has no seed (two instances identical); Random seeds 1.0 and 1.0005 collide |
| 7 | Envelope / follower stage times | ±1% or ±1 sample | Envelope at sample resolution **pass** (10.00 / 199.96 / 399.94 ms). At 60 fps the attack is **16.67 ms for 10 ms** (frame granular). Audio to CV **pass** (10.67 ms at 64-sample resolution, 100.00 ms) |
| 8 | CPU per Value01() | ≤ +10% | baseline: 2–16 ns/call, harness 3.6 ns (table in baseline file) |

Frame-rate dependence (max diff vs a 1440 fps reference, row 5b):

| Node | 24 fps | 60 fps | 144 fps |
|---|---|---|---|
| Smooth per-frame (the default mode) | 0.266 | 0.100 | 0.010 |
| Smooth time 0.25 s, step in | 0.090 | 0.037 | 0.015 |
| Smooth time, sine in | 0.038 | 0.015 | 0.006 |
| Smooth spring 3 Hz | 0.170 | 0.042 | 0.010 |
| Envelope ADSR | 0.031 | 0.006 | 0.003 |
| CV to Pitch glide 100 ms | 0.195 | 0.086 | 0.035 |

## 7. Findings

| # | Finding | Evidence | Block |
|---|---|---|---|
| F1 | Modulation is evaluated once per UI frame. Audio params get that value through ParamMailbox's fixed 5 ms one-pole, which gives a staircase with rounded corners plus up to a frame of lag | ZIPPER rows; tracking rms 0.24 at 8 Hz | 2 |
| F2 | Live video/3D reads `Transport::Seconds()`, which only moves at audio-block boundaries, so the value is up to one block (10.7 ms at 512/48k) away from the frame's time. Offline reads exact video time, so export differs from live (export is the correct one) | VIDEO rows | 2 |
| F3 | Every stateful node integrates per call at frame time. Smooth per-frame (the default) is frame-rate dependent by definition. Time and spring modes and CV to Pitch glide are exact only for a held input; with a moving input they sample it at frame rate | FRATE table | 2 (per-destination smoother), 3 (node maths) |
| F4 | Envelope output is centred: rest 0.5, sustain 0.8 for level 0.6, and release dips to 0.2 below rest. The param reads as a 0..1 ADSR but behaves as a bipolar offset | ENV row, `ModulatorNodes.cpp` EnvelopeNode | 3 (legacy flag) |
| F5 | Envelope stage edges are found once per frame, so attack is quantised to the frame (16.67 ms for 10 ms at 60 fps) | ENV @60 | 2/3 |
| F6 | LFO S&H uses `Hash01(floor(cycle))` with no seed: every S&H LFO on the canvas plays the same sequence | SEED row | 3 |
| F7 | Random's seed salt is `(long long)(seed*1013)`, so seeds closer than 1/1013 collide | SEED row | 3 |
| F8 | LFO/Random rate is a free float slider (0.05–32 beats) with no MusicTime division snap and no Hz mode, unlike the note nodes. Float storage of triplets drifts 0.86 samples in 10 min (under the limit, but only just) | QUANT rows | 3 |
| F9 | A 3-beat LFO in a 4-beat loop jumps 0.43 of range at the wrap. The phase follows the transport (Bitwig "Sync"); there is no free-run or retrigger mode | SEEK rows | 3 (option, default unchanged) |
| F10 | The no-audio fallback clock (`Transport::Tick`) is wall-clock driven, not sample-locked; it accumulates exactly but is only as steady as frame dt | CLOCK row | 2 |
| F11 | Predictors (Drift, Moves) tick with wall-clock dt live (`glfwGetTime`) but video-seconds dt offline, so learned modulators can differ between live and export | code read; not measurable headless (needs learned state) | 2 |
| F12 | Audio to CV follows per sample, but its level reaches params once per UI frame (atomic read), so its output steps at frame rate like F1 | ENV row note | 2 |

What already meets the bar, and is kept as it is: the transport clock itself
(live, offline, loop, seek and tempo change are all sub-nanosample), the LFO,
Pattern and Vibrato shape maths, idempotency (1 vs 8 calls per frame give
identical traces for every stateful node), seek on pure nodes, tempo change
continuity, and offline reproducibility.

### Measurement notes

- ZIPPER and live VIDEO model the frame/block schedule (frames at a fixed fps,
  callbacks due by each frame's wall time). The nodes, Transport and OnePole
  are the real ones. Real hosts add scheduling jitter on top, so these are best
  cases.
- Not measured headless: MIDI, OSC, Note/Velocity to CV, Path, Geometry Table,
  CV Recorder, Drift, Moves and Predictive need live input or learned state.
  They are covered by the CPU/range pass only, as constructed.
