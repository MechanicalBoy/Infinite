# Modulators to industry grade

Branch per block. Tracker: this file. Measured by `INFINITE_MODAUDIT`
(`src/app/selftest/ModAudit.cpp`). Raw runs: `baseline-2026-10-12.txt`,
`after-block2-2026-10-12.txt`, `after-block3-2026-10-12.txt`.

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
| 2 | `feature/mod-clock` | Shared sample-accurate phase source; per-sample ramp delivery to audio params; per-destination fps-independent smoothing | done (see After Block 2) |
| 3 | `feature/mod-maths` | Per-node fixes, each with a legacy flag | done (see After Block 3) |

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

### After Block 2 (2026-10-12)

| # | Metric | Baseline | After Block 2 |
|---|---|---|---|
| 2 | Zipper excess step (limit 9.8e-4) | LFO 1/4 beat 1.7e-3, Vibrato 1.07e-3: **fail** | worst 5.2e-4 (LFO 1/4 beat at 24 fps), 2.3e-4 at 60 fps, Vibrato 8.8e-5: **pass** on every source and schedule |
| 2 | Tracking rms after the fixed lag | LFO 1/4 beat 0.24 | 0.022 (60 fps), 0.014 (144 fps); slow sources ≤ 2e-3 |
| 2 | Lag to audio params | up to 1 frame + 5 ms tail, varying | fixed: 1 frame + 1 block (27.3 ms at 60 fps / 512, 17.6 ms at 144 fps, 52 ms at 24 fps). Under the 125 ms audio-after-video detectability bound of ITU-R BT.1359 |
| 3 | Live video/3D clock vs frame time | 0.7–10.7 ms off: **fail** | 0.000 ms (modelled schedule); render − realtime ≤ 6e-8: **pass** |
| 5a | Same-sample bit-exact | pass | pass (0/200 everywhere) |
| 5b | Per-destination smoothing, moving input (sine 2 Hz) vs 1440 fps | (old per-frame Smooth: 0.266 at 24 fps) | 1.0e-2 at 24 fps, 1.7e-3 at 60, 2.9e-4 at 144 (tau 20 ms). The residual is input sampling (chord of the sine between frames), not the filter |
| 5b | Per-destination smoothing, step input | n/a | **miss**: 0.56 at 24 fps, 0.30 at 60, 0.14 at 144 (tau 20 ms); 0.04 / 0.016 / 0.006 at tau 500 ms. A step is only seen at frame times, so its timing moves by up to a frame |
| 8 | CPU per Value01() | harness 3.6 ns, LFO 9.3, Pattern 5.3 | harness 3.9 ns, LFO 9.2, Pattern 5.2 (latch check only on the live branch); Beats() under a live frame latch 3.6 ns: **pass** |

What Block 2 changed:

- `Transport::BeginFrameClock()` latches, for the main thread's frame, the
  transport position interpolated between audio callbacks by wall time
  (monotonic per epoch, loop-wrap aware, dropped on seek/stop/engine change,
  lapses after 8 blocks). Offline is unchanged (exact video time).
- `ParamMailbox` ramps linearly to each new frame value, arriving at the
  frame's engine-time stamp + one frame interval (`PublishFrame`), queueing
  one ramp behind the active one. Before any frame is published it ramps
  over 5 ms. `BlockValue()` for params read once per block (Video Source).
- `Modulation::Source::smoothMs`: per-binding smoothing, an exact one-pole of
  the linearly interpolated input stepped by real frame dt
  (`Modulation::SmoothStep`), in the binding popup as "smooth" and saved as a
  trailing token after curve (absent = 0, so old patches load unchanged).

Known limits:

- Offline backpressure lookahead and preroll render audio ahead of the frame
  that set the values, so those spans see the ramps run late (staircase-like,
  as before Block 2).
- FM-rate modulation stays with the audio nodes (settled).
- The schedule in ZIPPER/VIDEO is modelled; host jitter on the real callback
  wall time is not.

Frame-rate dependence (max diff vs a 1440 fps reference, row 5b):

| Node | 24 fps | 60 fps | 144 fps |
|---|---|---|---|
| Smooth per-frame (the default mode) | 0.266 | 0.100 | 0.010 |
| Smooth time 0.25 s, step in | 0.090 | 0.037 | 0.015 |
| Smooth time, sine in | 0.038 | 0.015 | 0.006 |
| Smooth spring 3 Hz | 0.170 | 0.042 | 0.010 |
| Envelope ADSR | 0.031 | 0.006 | 0.003 |
| CV to Pitch glide 100 ms | 0.195 | 0.086 | 0.035 |

### After Block 3 (2026-10-12)

Every fix sits behind a per-node `maths` int (1 new, 0 legacy) or a mode
default. `INode::BeforeLoadParams()` runs before `LoadParams` on load and
paste and sets the legacy values, so saved patches, Field children and
hand-written `.inf` files without the key behave exactly as before; picker
spawns get the new maths.

| # | Metric | After Block 2 | After Block 3 |
|---|---|---|---|
| 1 | Synced LFO/Random drift, 10 min (triplets) | 0.858 samples (float beats) | 0 samples in `synced` mode (period from the `MusicTime` division); legacy beats mode 0.858, kept |
| 4 | Shape: LFO Hz 3.7 / synced 1/4T @beat 1e5 / free 2 Hz | n/a (no such modes) | 2.8e-7 / 3.0e-8 / 2.8e-8: **pass** |
| 5b | Stateful node maths vs 1440 fps fed the same frame samples (24..144 fps) | Smooth 0.45, Envelope 0.49, spring 0.12, CV glide 0.09 | ≤ 3.8e-6 every node and rate (Envelope 0): **pass** |
| 5b | Same, vs the true 1440 fps input | Smooth time step 0.090 @24 | 0.047 @24 (step) and 2.6e-3 (sine). The rest is input sampling (a step is seen at frame times), not node maths |
| 7 | Envelope ADSR stage times vs analytic, 48k / 60 / 61 / 24 fps | attack 16.67 ms for 10 @60 | ≤ 5e-8 of range at every rate: **pass**. The gate edge is placed where the frame-sampled gate crosses 0.5, at most half a frame from the true edge (legacy: up to one frame late) |
| 6 | Seeds | LFO S&H unseeded (spawns in lockstep); Random 1.0 / 1.0005 collide | per-spawn LFO seed; 64-bit salt from every seed bit; no collisions; same seed same output: **pass** (legacy behaviour kept on maths 0) |
| F9 | Loop wrap, 3-beat LFO in a 4-beat loop | jump 0.427 | `phase from: free` 0.0223 (= normal step); `retrigger` phase error 2e-8 vs (t − edge) · rate. Default stays `transport` (Bitwig Sync) |
| F4 | Envelope output | centred (rest 0.5, release dips to 0.2) | `output: ADSR` 0..1 on new nodes; `centred` on saved ones |
| F11 | Predictor dt live | wall clock | engine frame seconds when the engine runs; wall clock only without one |
| 8 | CPU per Value01() (min of 5 runs, harness 3.9 ns) | LFO 9.2, Random 8.0, Smooth 13.0, Envelope 13.5, CV to Pitch 16.4 | LFO 9.8 (legacy 10.0), Random 8.2 (7.9), Envelope 13.3 (13.4), CV to Pitch 15.7 (16.3): **pass**. Smooth 16.5 (13.0): **+27%, miss** (exact step: one `exp` and a `Seconds()` read instead of a per-frame multiply) |

What Block 3 changed:

- LFO and Random: `rate in` synced / beats / Hz. Synced uses the
  `MusicTime` division list (the note nodes' menu); a rate off the menu (a
  cable, a Field kernel) stays continuous. The division period is memoised
  per node on (rate, time signature).
- LFO `phase from`: transport (default), free (cycles over
  `Transport::FreeSeconds()`, bends with tempo, render starts at phase 0),
  retrigger (`trig` input, sub-frame edge). Seeded S&H with a `seed` control.
- Smooth: `amount` is now a time constant (amount^60 per second), so the
  default mode is fps-independent; time and spring are exact for a linearly
  moving input (`Modulation::SmoothStep`, `Modulation::SpringStep`).
- Envelope: closed-form stage levels at any time, gate edges between frames,
  `output` dropdown.
- CV to Pitch: piecewise glide across the frame, exact for a moving input.
- `CookFrame`: predictor dt from engine frame seconds; per-destination
  smoothing entries pruned when their binding goes away.
- Patch authoring skill: new `.inf` files should write `i maths 1`.

Honest misses:

| Miss | Why | Next |
|---|---|---|
| Step input through any stateful node or per-destination smoothing at 24 fps: 0.56 (tau 20 ms), 0.94 on a 10 ms Envelope attack vs the true edge | A step is only seen at frame times; its edge timing moves by up to half a frame. Node maths is exact for the samples it gets | Needs sub-frame event timestamps from the source (gates, MIDI): its own block |
| Live video with host callback jitter: 0.0248 of range for LFO 1/4 beat with 0..1 ms late callbacks | The frame clock interpolates between callbacks by wall time; a late callback bends it | Host-timing limit; offline export is exact |
| Smooth CPU +27% | Exact maths costs an `exp` per call | Accepted: Value01 is memoised, so this is once per frame per node (~4 ns) |
| F10 no-engine clock | Wall-clock driven when no audio device is open | Unchanged by design |
| F12 Audio to CV reaches params once per frame | Block 2 ramps smooth it; not sample-locked | Unchanged |
| Offline lookahead / preroll | Audio rendered ahead of the frame sees ramps late | As Block 2 |
| Translations | 2 help strings (LFO, Envelope) changed English text | Translators |
| In-process re-render of a hand-written patch with an unseeded Random differs | `RandomNode::Create` takes the next spawn seed; pre-existing (the LFO now has its own counter, so Random's sequence is unchanged) | Leave: two spawns differing is intended |

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
