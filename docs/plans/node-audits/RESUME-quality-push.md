# Resume: quality-scoreboard push (paused 2026-10-13)

Paused because the owner ran out of budget. Nothing has been merged or pushed. The branches are stacked on main d6020b77:

| Branch | Commit | State |
|---|---|---|
| feature/quality-measure-unmeasured | fbed531b | done |
| bugfix/quality-analog-pitch | b57cf3c0 | done |
| bugfix/quality-analog-aliasing | WIP commit on top of b57cf3c0 | in progress |

## Done

- **Unmeasured rows** (fbed531b):
  - geo.disp_offset was measured with GEOAUDIT DISP. Result: 0.0 units, met. It stays a report row because the driver's GEOAUDIT run has no DISP.
  - probe.cpu_voice_ms_s: Analog 14.1, Wavetable 3.0 ms/s. It shows as info because there is no target. The machine is shared, so the number is noisy (Analog read 9.2 in an earlier run).
  - P7 is now 7/7 met.
- **Analog pitch** (b57cf3c0, F19):
  - Cause: kVoiceDriftPitch[0] was -0.035 st, and first-free allocation means voice 0 plays every mono line, so default patches played 3.5 c flat.
  - Fix: voice 0 is now 0.0.
  - probe.pitch_worst_c: 3.52 -> 0.17 c, now a release row.
  - SYNTHAUDIT NOTE now also measures at true defaults.

## In progress: Analog aliasing to <= -80 dB (owner's L9 reversal)

Before (probe nonharm 60 / 96 / 108): -67.8 / -63.3 / -60.9 dB.

WIP commit: the analog hiss went from 0.001 to 0.0001 in both the voice and free paths.
- nonharm60 went from -68 to -77 dB.
- 96 and 108 did not move. This change alone does not meet the target.

Root cause, found with a standalone rig. The rig lives in the scratchpad (`lad/t.cpp`) and reproduces the app's numbers. There are two parts, and both must be fixed:

1. **BLEP content from 20 to 24 kHz.**
   - The kernel is cut at 0.9 Nyquist with a wide transition.
   - The tanh drive and the ladder intermodulate this content (and the upsampler images it makes) down to k+0.47 harmonics in the audible band.
   - Oversampling after the oscillator cannot remove it.
2. **The nonlinear ladder aliases at 2x.**
   - With an input clean to 19 kHz, the ladder alone reads -73 dB at 2x and -89 dB at 4x.

Standalone results at 261 / 2093 / 4186 Hz, full chain:

| Configuration | Result (dB) |
|---|---|
| Current: BLEP 12 taps, cut 0.90, 2x | -77 / -66 / -64 |
| 4x only | -77 / -67 / -64 |
| BLEP cut 0.80 with 32 taps, 2x | not tested |
| BLEP cut 0.80 with 32 taps, 4x | -87.6 / -91.1 / -89.2 |
| BLEP cut 0.75 with 12 taps, 4x | -87.6 / -91.0 / -88.7 |
| Linear ladder reference | -87.8 / -91.0 / -89.4 |

## Next steps

1. **Analog aliasing.**
   - Set kFilterOversample = 4 in AnalogSynthCore.h.
   - Lower the oscillator band edge for Analog only. Two options:
     - A per-Oscillator BLEP cutoff of about 0.75-0.80, either as a second table set or by templating BlepOscillator.h.
     - A base-rate lowpass near 19 kHz before `os.Up`.
   - Do not change the shared kernel: Wavetable uses it, and its kLatency drives PDC.
   - Then:
     - Re-run synth_probe for node:Analog (with CPU).
     - Run SYNTHAUDIT and `quality.py check --source SYNTHAUDIT`.
     - Note the CPU cost on the cpu_ns_frame row.
     - Update L9/F2 in README.md to record the reversal. No compat flag.
     - Ingest, run board, and promote the nonharm rows to release if they are met.
     - Re-check that AliasTests still pass.
2. **F15 Resonator Bank** (2.4 dB rate spread).
   - Likely estimator variance: about 0.88 Hz pole bandwidth over a 3 s window, roughly 2.6 degrees of freedom per seed.
   - Test with more seeds or longer renders in FxAudit's rate check (lines 385-472). If the spread collapses, fix the metric.
3. **F7 Wavetable** (note-on +8.2 dB). Not investigated yet. Look at the envelope start, the initial phase, and the decay-to-sustain overshoot.
4. **F7/F1 Metallic** (click metric on decaying resonators). Use max(steady at hold/2, MaxD2 over on+5..50 ms) as the reference, then check what it does to Wavetable.
5. **F17 Sphere poles under Subdivide/Smooth** (64 winding mismatches, 198 non-manifold edges).
   - In MeshOps::Subdivide (Mesh.cpp:751), skip triangles that are degenerate under the weld map (two welded corners equal).
   - Leave the Sphere primitive alone, so saved patches stay the same.
   - Re-run GEOAUDIT and drop the F17 exceptions if they reach 0.
6. F13, F14, F16 and F18 are by design. Leave them.

Every fix needs:
- a regression check in its audit;
- the gate that missed it named in the commit message;
- a findings-table update;
- the registry exception removed if the fix closes it;
- an ingest and board run.
