# v0.6 plan: quality lead

Owner scope (2026-10-13): everything the re-survey found worth taking goes into v0.6; nothing is
planned for v0.7. Direction is the agent's call, by one rule, set from how people actually use
Infinite (owner, 2026-10-13): **Infinite is a live design instrument.** Users design sound and 3D
work as they go, stream of consciousness, everything running while they patch; then they render it,
share the patch, or take the same patch live. Rule: **take depth that (a) keeps the flow (instant
feedback, no waiting, no hitch, click or crash while editing), (b) makes the sound or picture better
in real time, (c) makes the result easy to render, share or take live, or (d) fixes a measured miss;
ignore the rest, and say why.** Stage plumbing (DMX, timecode) ranks last; the patch is the show. Sources: the re-survey
dossiers, the extracted data in `~/re-output/`, and `docs/quality/SCOREBOARD.md`. v0.6 absorbs the
v0.5.1 goal (every escaped fix with a regression test). Judged by the NOW.md quality table.

## Shape

```
Block 1  bugfix/v06-audio-correctness      data → specs, export truth, measured misses, audits
   │
   ├── Block 2  feature/v06-sound     first run, plugin host, DSP depth, per-voice modulation
   └── Block 3  feature/v06-picture   AV nodes from TouchDesigner/Cables/Blender, visual perf
   │
v0.6 tag (on owner ask)
```

Rules for every block: one branch, commit per step, each fix gets a regression row (smoke, selftest
or scoreboard metric), `bug-blast-radius` before each bug fix, `verify-gate` before merge, no push
without ask. Bench runs are serialized with any other benching session (check NOW.md claims).

## Carry-over (unfinished work from before this plan, checked 2026-10-13)

| Item | Where it stands | In v0.6 as |
|---|---|---|
| re-survey-finish steps 5-6: DAW/TD sittings (builtins_kit, stretch_kit, load/workflow/projects), then R5, B8 heavy, R8 overnight soak | not started; owned by the `re-survey-finish` claim | Block 1 item 1.7 and the 1.6 bar depend on it; if that session closes first, Block 1 runs it |
| re-survey-finish step 7: R7 device unplug, recovery prompt | not started | Block 1, last; hardware latency loopback stays the owner's |
| `bugfix/step4-offline-audio`: 3 tool commits (loopback_rec via BlackHole, TD render bench note) | not merged | merge at Block 1 start (needed for the step 5 sittings) |
| Community patches: 5 of 24 fail strict `--validate` (stale keys in fairy-type, pad-wash; empty Output in glitch-feedback; half-wired Blend Audio in limited-stretch, spectrum-slide) | open | Block 2 item 2.7: fix the patches, add them to the validate smoke set |
| Node audits not yet covered: Reaction Diffusion, Remove Background, image sources, blur accuracy, RES/BYPASS sweeps, Metaballs, Cloth, Curve Ops, Instances, Displacement | next in `docs/plans/node-audits` | Block 1 item 1.8: run the sweeps; fix what they find only if it is a correctness bug (perf findings go to the perf lane) |
| Escaped fixes since v0.5.0 (8) | each already has its fix | nothing new; the release gate counts escapes after v0.6 |
| Motion and radial blur GPU cost (image-fx G9, about 0.16 ms/node over) | perf quest in the re-survey-finish ledger | Block 3 item 3.12 |
| Metal compute for particles (R757) | parked, gates G1/G2 unmeasured | Block 3 item 3.15 (gate, then build) |
| Modulation smaller gaps: Envelope hold stage and per-stage curves, MPE | open in `docs/plans/modulation`, `docs/plans/mpe` | Block 2 items 2.14, 2.15 |
| `feature/ui-engine` (1 commit), `feature/node-audits-plan` (1 docs commit) | the fix is already on main; the docs are superseded | delete both branches at Block 1 start, no merge |

## Block 1: trust (`bugfix/v06-audio-correctness`)

| # | Item | Today | Bar | Target files | Done check |
|---|---|---|---|---|---|
| 1.0 | Competitor data as specs | **Done.** The extracted parameter trees were unused; summary files in `~/re-output` carried unchecked claims ("SIMD ladder circuits", "C++/Metal DSP") | `tools/re-survey/param_diff.py`: 12 specs in [specs/](specs/README.md), one per Block 2 item with a comparable device (plugin trees give range, default and unit; Logic and Live give names and control kinds only). Each ends in "They have, we don't": controls at least two of their devices share. `diff.py claims` now reads the `~/re-output/*/*.md` summaries: an "Infinite equivalent" cell is backticked census nodes or "none", and no line says how Infinite is built. 68 invented cells in five extractors rewritten with real node names; Bitwig's "The Leap" column removed. Block 3 items have no parameter-tree counterpart (visual apps export node lists, not controls) | `param_diff.py --self-test` (15 checks, incl. every mapped device and node exists); `diff.py claims`: 32 summaries, 0 with claims to fix |
| 1.0b | Data ledger: no dataset unused, no result stale (and user patches as test input) | **Done.** 35 entries in `~/re-output`; several had no consumer (builtins-kit, load-bench, host-audit, project-bench, capability-map, ui-map); builtins-kit still showed Analog before its fix | `tools/re-survey/data_ledger.py`: each dataset → producer, kind and consumers (scoreboard metric, spec, plan item, doc), each consumer checked to exist. `lint` fails on a dataset nobody reads, one missing from the ledger, or an Infinite measurement older than the code it measured. builtins-kit, load-bench, stress, project-bench, host-audit and render-bench now emit `QUALITY` rows (16 new report-only rows in `docs/quality/registry.tsv`). `verify-gate` runs `data_ledger.py changed` and re-runs the kits whose sources the diff touched. `tools/website/community_patches.py --smoke`: every published user patch must open (`--validate`), play (a frame, or 2 s of sound when it has no Output) and show a picture; pixels and values are never compared, by owner rule. All eight stale kits re-run: Analog now 0.2 c and -81 dB at MIDI 108; load-bench peaks under full scale after the 1.13 trim | `data_ledger.py lint`: 29 datasets + 1 repo set, 0 without a consumer, 0 stale; community smoke 27 patches, 0 failed (5 can only be opened: no Output or Audio Out, or a live source) |
| 1.1 | Export / bounce latency shift | bounce through Drive is 73 samples late (Oversampler), Limiter lookahead ~72, plugins report their own | 0-sample offset vs dry, for Drive, Limiter, a latent plugin | `src/app/graph/AudioTopology.cpp` (PDC total already computed), offline render path (`src/core/HeadlessJob.cpp`), export writer | dossier C bounce probe re-run reads 0; smoke row per node |
| 1.2 | Audio Filter click (F13) | fx.click_db 17.30 | ≤ 12 dB | Audio Filter kernel in `src/audio/dsp/` + its row in `src/audio/EffectDefs.cpp` | scoreboard row met, exception F13 removed |
| 1.3 | Bitcrush rate spread (F14) | fx.rate_spread_db 5.38 | ≤ 1 dB | Bitcrush kernel (hold length in seconds, not samples) | row met, F14 removed |
| 1.4 | Metallic rate spread (F1) | synth.rate_spread_db 2.93 | ≤ 1 dB | Metallic synth core (rate-dependent coefficients) | row met, F1 removed |
| 1.5 | AV react latency | av.react_latency_ms 49.96 | ≤ 45 ms | ParamMailbox / Audio to CV hop (1 frame + 1 block today) | row met |
| 1.6 | Transient-aware stretch | drums: 10–14 extra onsets, -3 dB crest | 0 extra onsets in `stretch_kit`, crest within 0.5 dB | `src/audio/dsp/ClipTimeStretch.h` | `tools/re-survey/stretch_kit.py` passes; tonal cases do not regress |
| 1.7 | 9 unmeasured P8 metrics | R5 ×4, B7 soak ×3, live.frame_p95, live.drop_pct | all measured (met or a dated exception) | bench scripts | scoreboard Unmeasured = 0 |
| 1.8 | Node audit coverage | 10 node families not swept | every family swept; correctness bugs fixed with a regression row | `tools/` audit drivers, `docs/plans/node-audits/README.md` | node-audits "not yet covered" row empty |
| 1.9 | Default levels | at default settings Delay +3.0 dB, Reverb +4.3 dB, Dynamics -3.7 dB at 1 kHz (builtins-kit) | inserting an effect at default changes loudness by ≤ 1 dB (Drive excepted: drive is gain) | Delay, Reverb, Dynamics defaults | builtins-kit row per effect |
| 1.10 | Chorus / Flanger at high level | THD at -1 dBFS: Chorus -24.5 dB, Flanger -38.2 dB (at -12 dBFS: -102.6, -91.8), so they clip inside | ≤ -60 dB at -1 dBFS | Chorus, Flanger kernels | builtins-kit THD -1 column |
| 1.11 | Synth defaults that measure wrong | FieldSynth default: non-harmonic -3.9 dB at MIDI 96, 13.8 ¢ off, 362 ms attack; Metallic 41.4 ¢ off | each is fixed, or recorded as by design with the reason | FieldSynth default program, Metallic tuning | builtins-kit rows; `param-truth-audit` |
| 1.12 | RC-20 crashes in Infinite's host | Done: not a host bug. The installed copy (1.5.0, not signed by its vendor) dereferences null in its own code while it is created, on the main thread. Apple's validator (`auval`) and Apple's AU host process die at the same frames. Tier 3 in `plugin-host-hardening`: creation can't be guarded in-process | host-audit names whose crash it is | plugin host (`plugin-host-hardening`) | host-audit: `Whose` = plugin, exit 0 |
| 1.13 | Load-bench clipping | Done. Cause: the bench summed N in-phase tracks at unity, and nothing in the app said the master was over. The engine now counts samples over full scale on the master (live and offline); Audio Out shows `clipping +x dB` for 3 s, and a Timeline render that clipped ends with an "Audio clipped" notice. The bench trims its first Mixer row by 1/N | master never hard-clips silently: meter shows it, export warns | master bus / export | AUDIOPDCTEST master overs; load_bench self-test: 16 tracks peak 0.75 |
| 1.14 | Edit without a hitch | **Done, one confirmation left.** Audio never dropped (0 xruns in every run). Late frames: 13 of 75 edits before, 0 to 1 of 73 after | adding, deleting, connecting nodes, shader and Field recompiles, and preset loads never drop audio or a video frame while the patch runs | Cause: every node instance recompiled its shader from source (2 to 5 ms each; a Blur is three). Fix: `GLUtil::CompileProgram` keeps compiled stages by source, so a repeat only links; effect shaders compile ahead, one a frame after startup (`FilterNode::WarmNextShader`). No async compile was needed. The one edit still over (first Blur add, +6 ms) was measured on a loaded, locked-screen machine with 12 ms of base frame work (4.6 ms when quiet): re-run on a quiet, unlocked screen to confirm 0 | `INFINITE_BENCH_B3EDITS=1` on B3 (in `run_all.sh`): 12 edit kinds in a cycle; rows `bench.b3_edit_late_frames`, `bench.b3_edit_work_ms_max`, `bench.b3_edit_xruns` |

Settled:
- **1.0** sources, by what each can give: commercial plugins (85 plugins, 17,718 parameters with min, max, default and unit: the richest); Ableton (5,243 parameter names and types, sub-module grouping); Bitwig (232 Grid module names, 43 modulators); Blender (245 geometry nodes with sockets); Cables (1,298 ops with ports; MIT, so its op source may be read for algorithms). Only names, ranges and groupings are used; the DSP comes from papers. Spec rule: every control a node gains must be in at least two competitors or fix a measured miss.
- **1.1** is one general fix: offline render shifts the master by the graph's total reported
  latency (the PDC number), not per-node patches. Plugins that change latency mid-render already
  re-run PDC (merged `bugfix/plugin-latency-change-pdc`).
- **1.6** keeps Signalsmith Stretch (MIT). Add onset detection (spectral flux) and lock phase at
  onsets: reset the vocoder phase per segment, so each transient is copied, not smeared
  (Laroche–Dolson 1999 phase locking; Röbel 2003 transient preservation). No new dependency.
- **1.7** is owned by `re-survey-finish` if it is still open; otherwise this block runs it last.
  Either way the tag waits for Unmeasured = 0.

## Block 2: sound (`feature/v06-sound`)

| # | Item | Today | Bar | Target files | Done check |
|---|---|---|---|---|---|
| 2.1 | First sound | **Done.** 3 steps / 6.9 s, first of four (was 12 / 24.8 s): File > New Synth (Cmd+Shift+N) adds Keyboard, Analog and Audio Out cabled, starts audio and selects the Keyboard; a Keyboard that is the whole selection owns the letter keys, so Z plays with no hover. Cmd/Ctrl/Alt chords no longer play notes. Regression: `INFINITE_NEWSYNTHTEST`. Was: 12 steps / 24.8 s (workflow_cost task 1; Bitwig 3, Live and Logic 4) | ≤ 3 steps | `src/app/frame/StageMenuBar.cpp` (a "New: Synth" start that wires Synth → Audio Out) | `tools/re-survey/workflow_cost.py` task 1 |
| 2.2 | Sample drop auto-wire | **Done.** 1 step (was 3): one dropped audio file becomes an Audio File cabled into a new Audio Out with audio started; the list still opens, as "Playing x. Load into instead:", and a pick replaces the pair and is cabled to an Audio Out too. Several files wait for the pick as before. Regression: `INFINITE_DROPSOUNDTEST`. Was: 3 steps (task 8; the others 1) | 1 step: dropped file plays through Audio Out | `src/app/frame/StageDropHandling.cpp` | workflow_cost task 8 = 1 step |
| 2.3 | Standard keys | **Done.** Timeline (when focused): `F` zoom to fit, `=` / `-` zoom in/out around the playhead, `Cmd+L` loop on/off, `I` / `O` loop in/out at the playhead; play/stop was already `Space`, canvas fit already `F`. Not done: J/K/L shuttle, because the transport runs forward at 1x only (audio-driven clock); reverse and variable-rate play are engine work, not a key. `ARRANGEKEYSTEST`, shortcuts-sweep 60 rows OK. Was: no zoom-to-fit | keys the competitors share (ui-map: Final Cut 226 shortcuts; DAW manuals): zoom to fit, zoom in/out, play/stop, loop, J/K/L shuttle, I/O in-out | shortcut table | `shortcuts-sweep` rows |
| 2.4 | Factory presets | no preset store for audio nodes | ≥ 8 on every synth and on Delay, Reverb, Drive, Dynamics, EQ, the new saturator and reverb | factory preset table keyed by node type, applied through the save/load param path | selftest: count, each preset loads and is audible |
| 2.5 | Plugin sidechain input | no sidechain bus | VST3 + AU sidechain as a second audio input | `src/nodes/AudioPluginNode.h`, VST3/AU host files | sidechain compressor ducks in a smoke patch; Windows/Linux compile |
| 2.6 | Crash-only plugin fallback | a plugin crash takes the app down | node goes silent + badge, app lives; MIDI or parameter writes into a plugin handle that is being re-prepared or destroyed never touch freed memory (PR #24 fork fixed this crash: check our `AudioPluginNode` enter/re-check and `PluginDestroy` wait) | `src/platform/Platform.mm` (+ Windows/Linux), au_oop table | crash-test plugin in selftest |
| 2.7 | Community and user patches open | **Done.** 27 of 27 published patches pass the strict `--validate` and the smoke (was 5 failing). `community_patches.py` now repairs each staged copy and prints what it did: a parameter the node no longer has is dropped (Pad Wash, Fairy Type), a spare Output with nothing cabled in is dropped (Glitch Feedback), a Blend Audio with one side wired becomes a Gain at the same level (Limited Stretch, Spectrum Slide). `--smoke` is strict, so a new leftover fails verify-gate. Was: 5 of 24 community patches fail strict `--validate`; patches users send are not tested | 24 of 24, and every user patch (with permission) opens, plays and shows a picture; exact values may change as Infinite evolves | the 5 patch files, `tests/` patch set | validate + render smoke over all community and user patches |
| 2.9 | Convolution reverb from designed spaces | none | design the space (size, shape, materials, distance, decay, stereo spread) and the node builds the impulse response; files load too. Zero-latency non-uniform partitioned convolution (Gardner 1995, Wefers 2015); 5 s IR at 48 kHz < 3% of one core | new EffectDef + kernel in `src/audio/dsp/` | null vs offline FFT convolution ≤ -90 dB |
| 2.10 | Time-based MSEG | Mod Curve is a transfer curve | breakpoints, per-segment curve, loop A–B, sustain + release, retrigger, tempo sync | new `MSEGNode` in `ModulatorNodes.h` | `modulation-sweep`; save/load round trip |
| 2.11 | ADAA on Drive and Wavetable Shaper | Drive: non-harmonic -76.6 dB, 73-sample latency. Saturn 2 at similar THD: -101 dB, 0 latency | Drive non-harmonic ≤ -95 dB at 0 latency; Shaper ≤ today's 8× numbers | `src/audio/dsp/DriveKernel.h`, `WavetableShaperKernel.h` | plugin-probe re-run; `LatencySamples()` = 0 |
| 2.12 | Per-voice + audio-rate modulation | one `Value01()` shared by every voice, sampled per frame | polyphonic cables: a cable carries up to 16 voice channels; modulators run per voice and per sample when the consumer is a synth param | `IModulator`, voice layout in synth cores, `ParamMailbox` | design doc + semi-brain check first, inside this block; `modulation-sweep`; LFO-per-voice smoke patch |
| 2.13 | Unison / voice spread | no voice-index source | `VoiceSpreadNode`: spread by linear, golden ratio, primes, alternate | `ModulatorNodes.h` | needs 2.12; smoke |
| 2.14 | Envelope depth | no hold, no per-stage curve, gates on a threshold | AHDSR with per-stage curve; gates on notes directly | Envelope node | `modulation-sweep` |
| 2.15 | MPE | no MPE input | per-note pitch bend, pressure, slide into per-voice modulation | `docs/plans/mpe/README.md` targets | MPE controller smoke via a virtual MIDI port |
| 2.16 | SIMD voices | scalar voice loops | 4 voices per SIMD lane in Analog, Wavetable, the FM synth | synth cores | synth CPU per voice -50% on the probe; output bit-close (≤ -120 dB) |
| 2.17 | Multi-stage saturator | Drive is one stage | 3 stages, model per stage (tube, tape, diode, fold, rectify, crush), routing serial / parallel / mid-side / 3-band / feedback | new EffectDef (Roar, Saturn 2 shape) | `audio-node-sweep`; aliasing probe like 2.11 |
| 2.18 | Crossover split | Splitter is a 4-way fan-out | Linkwitz-Riley 4th-order crossover mode, up to 4 bands, flat sum | Splitter in `AudioNodes.h` | sum of bands within 0.1 dB of input |
| 2.20 | Tape delay | Delay: time, tone, feedback, pan, duck, bounce, mix | tape mode: wow/flutter, saturation and filter in the loop, diffusion (Echo, Valhalla Delay, Timeless) | Delay kernel | `audio-node-sweep` |
| 2.21 | Compressor styles | one Dynamics character | detector and knee styles: clean, VCA bus (glue), opto, FET (Pro-C 2, Glue) | Dynamics kernel | measured attack/release curve per style |
| 2.22 | 4-operator FM synth | Oscillator has one FM input | 4 operators, 11 algorithms, ratio/fixed, per-op envelope (Operator, FM-4) | new synth (`new-audio-node`) | `audio-node-sweep`; synth-probe pitch and aliasing rows |
| 2.23 | Phase shaping in Field | no phase-shaping builtins | bend, pinch, mirror, skew, formant builtins (Bitwig Grid phase family) | Field builtins (`field-language`) | `tests/field/corpus.txt` rows |
| 2.24 | Multicore audio graph | single audio thread; load-bench: 8 tracks of Analog+EQ use 41.8% of a core, ceiling about 13 tracks (Wavetable+Reverb about 32) | independent branches run on a worker pool; 64 tracks of Analog+EQ in real time on 8 cores | `AudioTopology.cpp` | load-bench ceiling ≥ 64 tracks ; gate: threaded output null-identical to single-thread, audio workgroup joined on macOS (Windows/Linux equivalents), one setting falls back to one thread |
| 2.25 | Filter models | Audio Filter: one SVF; Analog: one ladder | ladder, Sallen-Key (MS-20 style), diode, SVF; zero-delay feedback, per-stage saturation (Bitwig Grid 13 filters, Auto Filter models, Diva) | Audio Filter kernel, Analog core | `audio-node-sweep`; self-oscillation pitch within 5 ¢ |
| 2.26 | Wavetable phase warps | morph only | bend, sync, formant, mirror, quantize warps (Vital, Serum shape) sharing code with 2.23 | `WavetableEngine` | synth-probe aliasing rows hold |
| 2.31 | Control API | 63 scriptable members vs Live 584, Bitwig 1,729, TouchDesigner 3,649 (capability-map) | every param addressable over OSC with query and listen; node create/delete/connect | `src/nodes/OscNodes.cpp`, param registry | external script drives a patch in the smoke set |
| 2.32 | Resynthesis | none | analyse a sample into partials (sinusoidal + residual, McAulay-Quatieri 1986, Serra 1989) and play it back with pitch, formant, partial-count and morph controls (Alchemy shape) | new synth (`new-audio-node`) | resynthesised sample within 1 dB spectral error; synth-probe rows |
| 2.33 | String and modal modelling | Metallic (41 ¢ off), Shape Resonator, Resonator Bank | after 1.11: waveguide string + modal body with exciter choice (pluck, bow, strike) (Sculpture shape) | new synth or a Metallic mode, decided by the 1.0 spec | pitch within 2 ¢ across the range; synth-probe rows |
| 2.35 | Show set | none (one patch open at a time; Switcher 3D switches scenes inside a patch) | an ordered set of patches, preloaded; next/previous from a key, MIDI or OSC; audio tails and the projector cross over with no gap, silence or black frame | Stage menu, patch load path (load off the audio and render threads) | switch bench: 0 dropouts, 0 black frames, switch ≤ 1 bar at 120 BPM; switch lands on the bar (quantized, as the fork's quantized restart on sequencers does) |
| 2.36 | Show safety | missing media is reported per node; MIDI Out has a panic | show lock (no accidental delete or drag, controls still play), one global panic (notes off, audio fade, projector holds last frame), a pre-show check (missing media, plugins, devices, outputs) | Stage menu, `NodeIssue`, output nodes | pre-show check lists every issue in a broken test patch; panic silences within one block; quit with a stalled device exits in ≤ 5 s |
| 2.37 | Plugin editor with its own GL context (R282, PR #24) | Auto-Tune Pro (native VST3, Windows 11, RTX 4060) editor open freezes the UI for good; audio and video keep running; its UI uses OpenGL. Reproduction came from the PR author 2026-09-30 and 2026-10-04. Our Windows open path already holds `GlContextKeeper` and guards createView/getSize, so the stall is somewhere after attach or in the UI-thread message pump | opening a GL-UI plugin editor never freezes the UI; if it stalls, the UI stays alive and the editor is closed with a badge | `src/platform/win/PluginVST3Win.cpp` (`PluginVST3OpenEditor` after `attached`, timer and message pump), `GlContextKeeper`, a UI-thread unresponsive watchdog on Windows (macOS has one at `src/app/Startup.cpp`) | a test VST3 whose editor makes its own GL context on a child HWND opens, draws and closes in the Windows rig; the owner confirms with Auto-Tune Pro, since the plugin cannot be reproduced here |
| 2.38 | Bar-quantized launch and restart | Note nodes quantize notes, not starts; a Sequencer, Arpeggiator, Chord or MIDI File started from a button or MIDI restarts at once, off the bar | start, stop and restart of sequencing nodes land on a chosen division (none, beat, bar, 2 bars) from the quantization table, same for the Switcher and show-set switch (2.35); design use is unchanged (default none) | `src/audio/MusicTime.h` table (`rhythmic-quantization-standard`), `NoteNodes.cpp`, the transport clock | selftest: a restart triggered mid-bar sounds on the next bar line within one block |

Settled:
- **2.6** crash-only: in process as today; after a crash the plugin re-opens out of process on next load. Full sandboxing of every plugin costs latency and is not taken.
- **2.4** presets are param values in one table, picked from the node's context menu; one undo step.
- **2.10** a new node, not a Mod Curve mode (different contract).
- **2.11** Ring Mod stays 4× oversampled (a product of two signals, ADAA does not apply). Old Drive patches sound slightly cleaner; no legacy flag.
- **2.12** shape: VCV Rack's polyphonic cables (from its public manual; Rack is GPL, no source) and Bitwig's poly modulators (docs). One cable type, N channels, mono consumers sum. Order inside the block: 2.12 before 2.13, 2.15, 2.16.
- **2.17-2.22** are the owner-asked quality pass, so the `new-audio-node` minimalism rule yields for these nodes only; each control must pass the 1.0 spec rule.
- Factory presets of other apps (Ableton `.adv`/`.adg` are open XML) are read for **statistics only** (which ranges sound designers use, to set our defaults and ranges); none are copied or shipped.
- Re-evaluated 2026-10-13 and now taken: filter models (2.25), wavetable warps (2.26), control API (2.31, the real need behind "Python everywhere"). After the design-instrument correction: resynthesis (2.32), string/modal modelling (2.33), linear-phase EQ (2.34).
- Still not taken, with the reason:

| Item | Reason |
|---|---|
| Vintage console EQ emulations | character, not capability; the saturator (2.17) and compressor styles (2.21) cover the sound |
| Resonance suppressor (soothe2) | a mix-repair tool; users send designed sounds, not mixes; revisit if one asks |
| Show sync (LTC/MTC), DMX/Art-Net, gamepad | stage features; nobody performs live with Infinite |
| VST2 | Steinberg no longer licenses the SDK |
| Harmonizer | Key-Snap + Pitch Shifter already patch it |
| Hybrid algorithmic + IR reverb | patch Reverb and the IR reverb (2.9) in parallel |
| Multipass-style container | the canvas is the container |

## Block 3: picture (`feature/v06-picture`)

| # | Item | Today | Bar | Target files | Done check |
|---|---|---|---|---|---|
| 3.1 | Optical flow | none (TouchDesigner OpticalFlow TOP) | GPU flow field (pyramidal Lucas-Kanade) as an RG texture, 1080p ≤ 2 ms | new compositing node | `compositing-pipeline-sweep`; flow of a known moving pattern within 0.5 px |
| 3.2 | Time machine | Trails/Feedback hold one frame | per-pixel delay from a grey map over a 60-frame ring | new compositing node | slit-scan reference frame matches |
| 3.3 | Proximity lines | none (TD POP, plexus looks) | lines between points within a radius, spatial hash, 100k points ≤ 4 ms | new geometry node | `geometry-transform-sweep` |
| 3.4 | Sweep and revolve | Screw covers part of lathe | sweep a profile along a curve; revolve a curve (TD Sweep/Revolve, Blender Curve to Mesh) | new geometry nodes, `CurveOpsNode.h` | winding and normals pass GEOAUDIT |
| 3.5 | Render quality | not compared against a reference renderer | render the dossier G scenes in Infinite and Blender Eevee; add what is missing of soft shadows, ambient occlusion, depth of field, 3D motion blur, supersampled stills, 16-bit PNG / EXR output. Real time first: each look runs inside the frame budget while you design; an offline render mode only adds samples per frame on top | Render 3D path, `src/core/HeadlessJob.cpp` (`--frame`) | side-by-side contact sheet per scene; each added feature has a reference image |
| 3.6 | Lights and world | directional, point, sun, ambient, spot; HDRI exists (`EnvironmentNode`) | area light (soft shadows with 3.5) | `SceneNodes.h`, `EnvironmentNode.h` | render reference images |
| 3.7 | Bevel and inset | none | bevel edges (width, segments), inset faces | GeometryOp table | GEOAUDIT manifold check |
| 3.8 | Rigid bodies | Cloth and particles only (Cables Rapier ops) | boxes, spheres, convex hulls, ground, impulses; deterministic at fixed step | new simulation node | same result on all three platforms |
| 3.9 | L-system | none | axiom + rules + angle + iterations → curve | new geometry node | known plant reference |
| 3.12 | Visual perf | geo.instance 2.73 ms (Blender 1.26); geo.subdiv 12.01 ms (8.1); B8 heavy p99 33.2 ms, 9.36% missed; motion/radial blur 0.16 ms/node over | instance ≤ 1.3 ms, subdiv ≤ 8.1 ms, B8 heavy p99 ≤ 18.3 ms and < 0.5% missed, blur within G9 | perf tracker `docs/plans/perf/README.md` | scoreboard rows met |
| 3.13 | 2D fluid | none (TouchDesigner, Cables staple) | GPU stable fluids (Stam 1999): velocity, dye, vorticity, obstacles from an image; 1080p ≤ 3 ms | new compositing node | divergence below 1e-3 after projection |
| 3.14 | Clip speed in the arrangement | Video Source has speed; arrangement clips do not | per-clip speed and reverse, audio follows with 1.6's stretch | `src/arrange/` (`timeline-arrangement-architecture`) | export of a 2× clip has the right length and pitch |
| 3.15 | GPU particles (Metal compute) | CPU, capped 200k | run gate G1 of `docs/plans/metal-compute.md`; if it passes, build to its G2 bar (1M in < 2 ms); else record the number | `SimulationNodes.h` | G1 row either way |
| 3.16 | Volumes | none | volumetric fog, smoke and clouds (ray-marched density field, Field-programmable), real time at a reduced step count while designing, full steps in offline render | new geometry/render node | reference images; frame time recorded |
| 3.17 | Share a patch | users send `.inf` files by hand | one action writes a share bundle: the patch, a thumbnail and a short preview render; the website gallery lists bundles (same path as the Extensions page) | Stage menu, `tools/website/` | a bundle opens on a clean machine and matches its preview |
| 3.18 | GPU-native video codecs (HAP) | video decodes on the CPU; a large clip stutters or eats frame time when several play, for design scrubbing and live alike | HAP / HAP Alpha / HAP Q decode to a compressed texture with no colour conversion, any platform (HAP is BSD-2, spec public) | `VideoSourceNode`, a video decode helper | 4 clips of 4K HAP play with 0 late frames in the B8 bench; scrubbing a HAP clip never hitches |

Settled:
- Re-evaluated 2026-10-13 and now taken: 2D fluid (3.13), clip speed (3.14); after the design-instrument correction: render quality (3.5), light linking and IES (3.6), volumes (3.16), patch sharing (3.17).
- Still not taken: sculpting and retopology (Blender's job; Infinite designs procedurally); depth cameras (vendor SDKs on three platforms; Apple Vision tracking covers it); a web player (a second renderer; 3.17 shares a preview render instead); magnetic storyline (a film-editing model); DMX/Art-Net (stage only).


## Not in v0.6 (final list, 2026-10-13)

Owner vetted the list and asked for a professional, industry-standard verdict on every item; this is the result. Not planned; reopen only on a user ask or a measured need.

| # | Item | Why not now |
|---|---|---|
| 2.8 | CLAP hosting | hosted by Bitwig, Reaper, FL and Studio One but not Live or Logic; VST3 and AU cover what users load |
| 2.19 | Dynamic EQ | mixed industry standard (Pro-Q, Cubase yes; Live, Bitwig, Logic stock no); 2.18 crossover + 2.21 styles give band dynamics |
| 2.27 | Drum voice synth | owner: not required |
| 2.28 | Note entry | piano-roll editing is DAW table stakes, not live-design table stakes |
| 2.29 | Open an Ableton set | project migration from a DAW; users start in Infinite |
| 2.30 | Starter content | owner: not required |
| 2.34 | Linear-phase EQ mode | a mastering mode (Pro-Q has it, Live/Bitwig stock EQs do not); its latency fights instant feedback |
| 3.10 | Defocus (bokeh) blur | folded into 3.5 depth of field |
| 3.11 | Cables image-op gaps | a catalogue comparison, not a feature |

## What each source taught (2026-10-13)

| Source | Learned | Used in |
|---|---|---|
| Commercial plugins (85, 17,718 params, probed) | Saturn 2 is 25 dB cleaner than Drive at zero latency; Pro-L 2 runs 3,115 samples of lookahead; parameter trees give ranges and defaults | 2.11 bar, 2.17-2.21 specs via 1.0 |
| Ableton (103 devices) | Roar, Echo, Glue, Hybrid Reverb, Operator shapes; sub-module grouping of Meld and Drift voices | 2.9, 2.17, 2.20-2.22, 2.12 |
| Bitwig (232 Grid modules, 43 modulators) | poly modulators, Segments/Curves, phase family, crossover splits, CLAP | 2.8, 2.10, 2.12, 2.18, 2.23 |
| Logic (dossier K) | Space Designer, compressor circuit styles | 2.9, 2.21 |
| Blender (245 geometry nodes, bench) | instance and subdivide are 2× faster; bevel, curve-to-mesh | 3.4, 3.7, 3.12 |
| TouchDesigner | optical flow, time machine, proximity, sweep/revolve | 3.1-3.4 |
| Cables (1,298 ops; MIT) | rigid bodies, L-systems, the image-op catalogue; source readable | 3.8, 3.9, 3.11 |
| Pixelmator | defocus blur | 3.5 (depth of field) |
| VCV Rack (GPL: manual and behaviour only; the dossier built from its source manifests was removed) | polyphonic cables | 2.12 |
| builtins-kit (our nodes measured like the DAWs') | default level jumps, Chorus/Flanger clipping, FieldSynth and Metallic defaults | 1.9-1.11 |
| load-bench | 13-track ceiling for Analog+EQ on one core | 2.24, 2.16 |
| host-audit | RC-20 crashes in every host tried here (ours, auval, Apple's AU host): the plugin copy, not our host | 1.12 |
| project-bench formats | Ableton sets and presets are open XML; ours are the smallest (0.8 KB) | preset statistics (2.29 not in v0.6) |
| capability-map (scripting APIs) | 63 scriptable members vs 584-3,649 | 2.31 |
| ui-map | shared shortcut sets | 2.3 |

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

Order: Block 1 first (trust before features). Blocks 2 and 3 can run in parallel sessions (no shared files except the preset table and the FilterDef table; claim rows in NOW.md). Inside a block, the table order is the order. Nothing is planned past v0.6.
