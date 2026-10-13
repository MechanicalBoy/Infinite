# v0.6 plan: quality lead

Owner-approved scope (2026-10-13): **Tier 1 + Tier 2 + at most 3 Tier 3 items**. Source of every
row: the re-survey dossiers (`docs/plans/re-survey/`, rows checked against code 2026-10-13) and the
scoreboard (`docs/quality/SCOREBOARD.md`). v0.6 absorbs the v0.5.1 goal (escaped fixes, each with a
regression test). Judged by the NOW.md quality table, not downloads.

Every decision below is settled; a session picks up the next open block and runs it.

## Shape

```
Block 1  bugfix/v06-audio-correctness   Tier 1   (measured misses, export truth)
   │
Block 2  feature/v06-first-run          Tier 2   (first sound, drop, presets, plugin host)
   │
Block 3  feature/v06-dsp                Tier 3   (IR reverb, MSEG, ADAA)
   │
v0.6 tag (on owner ask)  →  v0.7 opens with the per-voice / audio-rate lane
```

Rules for every block: one branch, commit per step, each fix gets a regression row (smoke, selftest
or scoreboard metric), `bug-blast-radius` before each bug fix, `verify-gate` before merge, no push
without ask. Bench runs are serialized with the `re-survey-finish` session (check NOW.md claims).

## Carry-over (unfinished work from before this plan, checked 2026-10-13)

| Item | Where it stands | In v0.6 as |
|---|---|---|
| re-survey-finish steps 5-6: DAW/TD sittings (builtins_kit, stretch_kit, load/workflow/projects), then R5, B8 heavy, R8 overnight soak | not started; owned by the `re-survey-finish` claim | Block 1 item 1.7 and the 1.6 bar depend on it; if that session closes first, Block 1 runs it |
| re-survey-finish step 7: R7 device unplug, recovery prompt | not started | Block 1, last; hardware latency loopback stays the owner's |
| `bugfix/step4-offline-audio`: 3 tool commits (loopback_rec via BlackHole, TD render bench note) | not merged | merge at Block 1 start (needed for the step 5 sittings) |
| Community patches: 5 of 24 fail strict `--validate` (stale keys in fairy-type, pad-wash; empty Output in glitch-feedback; half-wired Blend Audio in limited-stretch, spectrum-slide) | open | Block 2 item 2.7: fix the patches, add them to the validate smoke set |
| Node audits not yet covered: Reaction Diffusion, Remove Background, image sources, blur accuracy, RES/BYPASS sweeps, Metaballs, Cloth, Curve Ops, Instances, Displacement | next in `docs/plans/node-audits` | Block 1 item 1.8: run the sweeps; fix what they find only if it is a correctness bug (perf findings go to the perf lane) |
| Escaped fixes since v0.5.0 (8) | each already has its fix | nothing new; the release gate counts escapes after v0.6 |
| Motion and radial blur GPU cost (image-fx G9, about 0.16 ms/node over) | perf quest in the re-survey-finish ledger | parked: perf lane |
| Metal compute for particles (R757) | parked, gates G1/G2 unmeasured | parked |
| Modulation smaller gaps: Envelope hold stage and per-stage curves, MPE | open in `docs/plans/modulation`, `docs/plans/mpe` | parked to v0.7 with the per-voice lane (same consumers) |
| `feature/ui-engine` (1 commit), `feature/node-audits-plan` (1 docs commit) | the fix is already on main; the docs are superseded | delete both branches at Block 1 start, no merge |

## Block 1: audio correctness (`bugfix/v06-audio-correctness`)

| # | Item | Today | Bar | Target files | Done check |
|---|---|---|---|---|---|
| 1.1 | Export / bounce latency shift | bounce through Drive is 73 samples late (Oversampler), Limiter lookahead ~72, plugins report their own | 0-sample offset vs dry, for Drive, Limiter, a latent plugin | `src/app/graph/AudioTopology.cpp` (PDC total already computed), offline render path (`src/core/HeadlessJob.cpp`), export writer | dossier C bounce probe re-run reads 0; smoke row per node |
| 1.2 | Audio Filter click (F13) | fx.click_db 17.30 | ≤ 12 dB | Audio Filter kernel in `src/audio/dsp/` + its row in `src/audio/EffectDefs.cpp` | scoreboard row met, exception F13 removed |
| 1.3 | Bitcrush rate spread (F14) | fx.rate_spread_db 5.38 | ≤ 1 dB | Bitcrush kernel (hold length in seconds, not samples) | row met, F14 removed |
| 1.4 | Metallic rate spread (F1) | synth.rate_spread_db 2.93 | ≤ 1 dB | Metallic synth core (rate-dependent coefficients) | row met, F1 removed |
| 1.5 | AV react latency | av.react_latency_ms 49.96 | ≤ 45 ms | ParamMailbox / Audio to CV hop (1 frame + 1 block today) | row met |
| 1.6 | Transient-aware stretch | drums: 10–14 extra onsets, -3 dB crest | 0 extra onsets in `stretch_kit`, crest within 0.5 dB | `src/audio/dsp/ClipTimeStretch.h` | `tools/re-survey/stretch_kit.py` passes; tonal cases do not regress |
| 1.7 | 9 unmeasured P8 metrics | R5 ×4, B7 soak ×3, live.frame_p95, live.drop_pct | all measured (met or a dated exception) | bench scripts | scoreboard Unmeasured = 0 |
| 1.8 | Node audit coverage | 10 node families not swept | every family swept; correctness bugs fixed with a regression row | `tools/` audit drivers, `docs/plans/node-audits/README.md` | node-audits "not yet covered" row empty |

Settled:
- **1.1** is one general fix: offline render shifts the master by the graph's total reported
  latency (the PDC number), not per-node patches. Plugins that change latency mid-render already
  re-run PDC (merged `bugfix/plugin-latency-change-pdc`).
- **1.6** keeps Signalsmith Stretch (MIT). Add onset detection (spectral flux) and lock phase at
  onsets: reset the vocoder phase per segment, so each transient is copied, not smeared
  (Laroche–Dolson 1999 phase locking; Röbel 2003 transient preservation). No new dependency.
- **1.7** is owned by `re-survey-finish` if it is still open; otherwise this block runs it last.
  Either way the tag waits for Unmeasured = 0.

## Block 2: first run and plugin host (`feature/v06-first-run`)

| # | Item | Today | Bar | Target files | Done check |
|---|---|---|---|---|---|
| 2.1 | First sound | 12 steps / 24.8 s (workflow_cost task 1; Bitwig 3, Live and Logic 4) | ≤ 3 steps | `src/app/frame/StageMenuBar.cpp` (a "New: Synth" start that wires Synth → Audio Out) | `tools/re-survey/workflow_cost.py` task 1 |
| 2.2 | Sample drop auto-wire | 3 steps (task 8; the others 1) | 1 step: dropped file plays through Audio Out | `src/app/frame/StageDropHandling.cpp` | workflow_cost task 8 = 1 step |
| 2.3 | Zoom to fit key | none | one key frames all nodes | canvas shortcut table | `shortcuts-sweep` row |
| 2.4 | Factory presets | no preset store for audio nodes (only Field presets and Metallic materials) | ≥ 8 each on 3 synths (Analog, Wavetable, FM-capable Oscillator path) + 4 effects (Delay, Reverb, Drive, Compressor) | new factory preset table keyed by node type, applied through the save/load param path | count check in a selftest; each preset loads and is audible |
| 2.5 | Plugin sidechain input | no sidechain bus in `AudioPluginNode.h` | VST3 + AU sidechain bus as a second audio input | `src/nodes/AudioPluginNode.h`, VST3/AU host files | a sidechain compressor ducks in a smoke patch on macOS; Windows/Linux VST3 compile |
| 2.6 | Crash-only plugin fallback | a plugin crash takes the app down | crash in a plugin = node goes silent + badge, app lives | `src/platform/Platform.mm` (+ Windows/Linux sides), au_oop table | crash-test plugin in selftest; `plugin-host-hardening` |
| 2.7 | Community patches validate | 5 of 24 fail strict `--validate` | 24 of 24 pass | the 5 patch files | validate smoke row over all community patches |

Settled:
- **2.6** is crash-only out of process: plugins run in-process as today; after a crash the plugin
  is re-opened in a helper process on next load (AU via the system's out-of-process AU; VST3 via a
  helper). Full sandboxing of every plugin is not v0.6 (latency and cost).
- **2.4** presets are param values only, in one table, with no per-node code. They are picked from the node's existing context menu (a Presets submenu), so no new widget. Loading one is a single undo step.
- **2.1/2.2** no onboarding wizard; the shortest path is the feature. Task 6 (four MIDI notes, 8 steps vs 5) stays out of v0.6.

## Block 3: DSP lead (`feature/v06-dsp`)

| # | Item | Bar | Target files | Done check |
|---|---|---|---|---|
| 3.1 | IR convolution reverb | zero-latency, non-uniform partitioned (direct head + growing FFT blocks; Gardner 1995, Wefers 2015); 5 s IR at 48 kHz under 3% of one core | new EffectDef in `src/audio/EffectDefs.cpp` + kernel in `src/audio/dsp/` | null test vs offline FFT convolution ≤ -90 dB; `audio-node-sweep` |
| 3.2 | Time-based MSEG | breakpoints, per-segment curve, loop A–B, sustain + release, retrigger on gate, tempo-sync divisions from `rhythmic-quantization-standard` | new `MSEGNode` in `ModulatorNodes.h` | `modulation-sweep`; round-trip save/load |
| 3.3 | ADAA on Drive and Wavetable Shaper | Drive: first-order ADAA on tanh (antiderivative log cosh), no oversampler, latency 73 → 0; Wavetable Shaper: antiderivative table (Parker 2016, Bilbao 2017) | `src/audio/dsp/DriveKernel.h`, `src/audio/dsp/WavetableShaperKernel.h` | aliasing probe ≤ today's oversampled numbers; Drive `LatencySamples()` = 0 |

Settled:
- **3.2** is a new node, not a mode of Mod Curve: Mod Curve is a transfer curve with an `in`; a clock,
  gate and loop points are a different contract and would make both UIs worse.
- **3.3** Ring Mod stays 4× oversampled: a product of two signals is not a static nonlinearity,
  so ADAA does not apply.
- **3.3** old Drive patches will sound slightly different (cleaner top end); no legacy flag
  (owner rule: small user base, no new compat flags).

## Parked (not v0.6)

| Item | Why | When |
|---|---|---|
| Per-voice + audio-rate modulation | changes voice layout and `IModulator` contract | v0.7 opens with it: design doc, then semi-brain check, then code (`feature/mod-poly`) |
| Unison spread (`VoiceSpreadNode`) | needs per-voice | after mod-poly |
| SIMD voices | needs the new voice layout | after mod-poly |
| Multicore audio graph | audio thread not the bottleneck yet | when P8 shows audio thread > 50% |
| geo.instance_ms 2.73 (Blender 1.26), geo.subdiv_ms 12.01 (8.1) | perf lane, not quality | perf initiative |
| B8 heavy windows (p99 33.2 ms, 9.36% missed vsync at 4×2160) | perf lane | perf initiative |
| Roar-style multi-stage template | patch, not engine | optional, any time |
| Metal compute (R757), motion/radial blur GPU cost | perf lane; gates unmeasured | perf initiative |
| Envelope hold/curves, MPE | same consumers as per-voice | v0.7 with mod-poly |

## Release gate (v0.6)

| Check | Want |
|---|---|
| Blocks 1–3 merged | yes |
| Scoreboard: behind/miss | 0 outside dated exceptions; F1, F13, F14 removed |
| Scoreboard: unmeasured | 0 |
| Escaped fixes after v0.6 vs after v0.5.0 | fewer than v0.5.0 (8 on 2026-10-13) |
| Known test failures (macOS / Linux) | ≤ 3 / 6 |
| Reverts | 0 |
| `release-notes-audit` | clean |
