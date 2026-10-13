# v0.6 plan: quality lead

Owner scope (2026-10-13): everything the re-survey found worth taking goes into v0.6; nothing is
planned for v0.7. Direction is the agent's call, by one rule, set from how people actually use
Infinite (owner, 2026-10-13: users treat it as a design instrument and send sound-design and 3D
patches, or share and render the work; nobody performs live with it): **take depth that (a) makes the sound or picture a user
designs better, (b) makes a patch easier to make, finish, render, export or share, or (c) fixes a measured
miss; ignore the rest, and say why.** Live-stage features rank last. Sources: the re-survey
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
| 1.0 | Competitor data as specs | the extracted parameter trees are unused; summary files in `~/re-output` carry unchecked claims ("SIMD ladder circuits", "C++/Metal DSP") | `tools/re-survey/param_diff.py`: for each node this plan touches, the nearest competitor devices' controls (name, range, default, unit) next to ours; `diff.py claims` also reads the `~/re-output/*/*.md` summaries | the tool's self-test; one spec table per Block 2/3 item in `docs/plans/v0.6-quality/specs/`; claims lint clean |
| 1.0b | Data ledger: no dataset unused, no result stale (and user patches as test input) | 35 datasets in `~/re-output`; several have no consumer (builtins-kit, load-bench, host-audit, project-bench, capability-map, ui-map); builtins-kit still shows Analog before its fix | `tools/re-survey/data_ledger.py`: each dataset → its consumers (scoreboard metric, spec, plan item); every kit and probe emits `QUALITY` lines into `docs/quality/registry.tsv` (synth-probe already does); `verify-gate` re-runs any kit whose source changed; patches users send (with their permission) join the community validate and render smoke sets | ledger lint: 0 datasets without a consumer, 0 stale results |
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
| 1.12 | RC-20 crashes in Infinite's host | SIGSEGV in AU and VST3 (host-audit); it runs in DAWs, so it is a host bug | loads, processes, closes | plugin host (`plugin-host-hardening`) | host-audit row OK |
| 1.13 | Load-bench clipping | every load-bench render peaks at exactly 1.000 | master never hard-clips silently: meter shows it, export warns | master bus / export | load-bench peak < 1.0 with a sane patch |

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
| 2.1 | First sound | 12 steps / 24.8 s (workflow_cost task 1; Bitwig 3, Live and Logic 4) | ≤ 3 steps | `src/app/frame/StageMenuBar.cpp` (a "New: Synth" start that wires Synth → Audio Out) | `tools/re-survey/workflow_cost.py` task 1 |
| 2.2 | Sample drop auto-wire | 3 steps (task 8; the others 1) | 1 step: dropped file plays through Audio Out | `src/app/frame/StageDropHandling.cpp` | workflow_cost task 8 = 1 step |
| 2.3 | Standard keys | no zoom-to-fit | keys the competitors share (ui-map: Final Cut 226 shortcuts; DAW manuals): zoom to fit, zoom in/out, play/stop, loop, J/K/L shuttle, I/O in-out | shortcut table | `shortcuts-sweep` rows |
| 2.4 | Factory presets | no preset store for audio nodes | ≥ 8 on every synth and on Delay, Reverb, Drive, Dynamics, EQ, the new saturator and reverb | factory preset table keyed by node type, applied through the save/load param path | selftest: count, each preset loads and is audible |
| 2.5 | Plugin sidechain input | no sidechain bus | VST3 + AU sidechain as a second audio input | `src/nodes/AudioPluginNode.h`, VST3/AU host files | sidechain compressor ducks in a smoke patch; Windows/Linux compile |
| 2.6 | Crash-only plugin fallback | a plugin crash takes the app down | node goes silent + badge, app lives | `src/platform/Platform.mm` (+ Windows/Linux), au_oop table | crash-test plugin in selftest |
| 2.7 | Community patches validate | 5 of 24 fail strict `--validate` | 24 of 24 | the 5 patch files | validate smoke row over all community patches |
| 2.8 | CLAP hosting | VST3 + AU only (Bitwig hosts CLAP) | CLAP plugins scan, load, automate, report latency on all three platforms | new CLAP host beside the VST3 host (CLAP SDK is MIT) | a CLAP test plugin in the plugin smoke set |
| 2.9 | IR convolution reverb | none | zero-latency non-uniform partitioned (Gardner 1995, Wefers 2015); 5 s IR at 48 kHz < 3% of one core | new EffectDef + kernel in `src/audio/dsp/` | null vs offline FFT convolution ≤ -90 dB |
| 2.10 | Time-based MSEG | Mod Curve is a transfer curve | breakpoints, per-segment curve, loop A–B, sustain + release, retrigger, tempo sync | new `MSEGNode` in `ModulatorNodes.h` | `modulation-sweep`; save/load round trip |
| 2.11 | ADAA on Drive and Wavetable Shaper | Drive: non-harmonic -76.6 dB, 73-sample latency. Saturn 2 at similar THD: -101 dB, 0 latency | Drive non-harmonic ≤ -95 dB at 0 latency; Shaper ≤ today's 8× numbers | `src/audio/dsp/DriveKernel.h`, `WavetableShaperKernel.h` | plugin-probe re-run; `LatencySamples()` = 0 |
| 2.12 | Per-voice + audio-rate modulation | one `Value01()` shared by every voice, sampled per frame | polyphonic cables: a cable carries up to 16 voice channels; modulators run per voice and per sample when the consumer is a synth param | `IModulator`, voice layout in synth cores, `ParamMailbox` | design doc + semi-brain check first, inside this block; `modulation-sweep`; LFO-per-voice smoke patch |
| 2.13 | Unison / voice spread | no voice-index source | `VoiceSpreadNode`: spread by linear, golden ratio, primes, alternate | `ModulatorNodes.h` | needs 2.12; smoke |
| 2.14 | Envelope depth | no hold, no per-stage curve, gates on a threshold | AHDSR with per-stage curve; gates on notes directly | Envelope node | `modulation-sweep` |
| 2.15 | MPE | no MPE input | per-note pitch bend, pressure, slide into per-voice modulation | `docs/plans/mpe/README.md` targets | MPE controller smoke via a virtual MIDI port |
| 2.16 | SIMD voices | scalar voice loops | 4 voices per SIMD lane in Analog, Wavetable, the FM synth | synth cores | synth CPU per voice -50% on the probe; output bit-close (≤ -120 dB) |
| 2.17 | Multi-stage saturator | Drive is one stage | 3 stages, model per stage (tube, tape, diode, fold, rectify, crush), routing serial / parallel / mid-side / 3-band / feedback | new EffectDef (Roar, Saturn 2 shape) | `audio-node-sweep`; aliasing probe like 2.11 |
| 2.18 | Crossover split | Splitter is a 4-way fan-out | Linkwitz-Riley 4th-order crossover mode, up to 4 bands, flat sum | Splitter in `AudioNodes.h` | sum of bands within 0.1 dB of input |
| 2.19 | Dynamic EQ | static 5 bands | each band gets threshold, range, attack, release (Pro-Q 4, TDR Nova) | EQ kernel | `param-truth-audit` row per band |
| 2.20 | Tape delay | Delay: time, tone, feedback, pan, duck, bounce, mix | tape mode: wow/flutter, saturation and filter in the loop, diffusion (Echo, Valhalla Delay, Timeless) | Delay kernel | `audio-node-sweep` |
| 2.21 | Compressor styles | one Dynamics character | detector and knee styles: clean, VCA bus (glue), opto, FET (Pro-C 2, Glue) | Dynamics kernel | measured attack/release curve per style |
| 2.22 | 4-operator FM synth | Oscillator has one FM input | 4 operators, 11 algorithms, ratio/fixed, per-op envelope (Operator, FM-4) | new synth (`new-audio-node`) | `audio-node-sweep`; synth-probe pitch and aliasing rows |
| 2.23 | Phase shaping in Field | no phase-shaping builtins | bend, pinch, mirror, skew, formant builtins (Bitwig Grid phase family) | Field builtins (`field-language`) | `tests/field/corpus.txt` rows |
| 2.24 | Multicore audio graph | single audio thread; load-bench: 8 tracks of Analog+EQ use 41.8% of a core, ceiling about 13 tracks (Wavetable+Reverb about 32) | independent branches run on a worker pool; 64 tracks of Analog+EQ in real time on 8 cores | `AudioTopology.cpp` | load-bench ceiling ≥ 64 tracks |
| 2.25 | Filter models | Audio Filter: one SVF; Analog: one ladder | ladder, Sallen-Key (MS-20 style), diode, SVF; zero-delay feedback, per-stage saturation (Bitwig Grid 13 filters, Auto Filter models, Diva) | Audio Filter kernel, Analog core | `audio-node-sweep`; self-oscillation pitch within 5 ¢ |
| 2.26 | Wavetable phase warps | morph only | bend, sync, formant, mirror, quantize warps (Vital, Serum shape) sharing code with 2.23 | `WavetableEngine` | synth-probe aliasing rows hold |
| 2.27 | Drum voice synth | DrumSequencer, no drum synth | kick, snare, hat, clap, tom voices from published analog-drum models; one node, voice selector | new synth (`new-audio-node`) | synth-probe rows; Drum Sequencer smoke patch |
| 2.28 | Note entry | workflow_cost task 6: 8 steps (Bitwig 5) | ≤ 5 steps | arrangement clip editor | workflow_cost task 6 |
| 2.29 | Open an Ableton set | none; `.als` is gzip XML (project-bench) | import tempo, track names, MIDI clips and locators; instruments map to Infinite synths by role | new importer in `src/core/` | 3 sample sets import; notes match |
| 2.30 | Starter content | no samples or clips (gap P6 E) | drum one-shots and loops rendered by Infinite's own synths (2.27), shipped as patches | tools script + `patches/` | count check |
| 2.31 | Control API | 63 scriptable members vs Live 584, Bitwig 1,729, TouchDesigner 3,649 (capability-map) | every param addressable over OSC with query and listen; node create/delete/connect | `src/nodes/OscNodes.cpp`, param registry | external script drives a patch in the smoke set |
| 2.32 | Resynthesis | none | analyse a sample into partials (sinusoidal + residual, McAulay-Quatieri 1986, Serra 1989) and play it back with pitch, formant, partial-count and morph controls (Alchemy shape) | new synth (`new-audio-node`) | resynthesised sample within 1 dB spectral error; synth-probe rows |
| 2.33 | String and modal modelling | Metallic (41 ¢ off), Shape Resonator, Resonator Bank | after 1.11: waveguide string + modal body with exciter choice (pluck, bow, strike) (Sculpture shape) | new synth or a Metallic mode, decided by the 1.0 spec | pitch within 2 ¢ across the range; synth-probe rows |
| 2.34 | Linear-phase EQ mode | minimum phase only | linear-phase option on EQ for design and export (latency reported, PDC handles it) | EQ kernel | phase response flat; PDC smoke |

Settled:
- **2.6** crash-only: in process as today; after a crash the plugin re-opens out of process on next load. Full sandboxing of every plugin costs latency and is not taken.
- **2.4** presets are param values in one table, picked from the node's context menu; one undo step.
- **2.10** a new node, not a Mod Curve mode (different contract).
- **2.11** Ring Mod stays 4× oversampled (a product of two signals, ADAA does not apply). Old Drive patches sound slightly cleaner; no legacy flag.
- **2.12** shape: VCV Rack's polyphonic cables (from its public manual; Rack is GPL, no source) and Bitwig's poly modulators (docs). One cable type, N channels, mono consumers sum. Order inside the block: 2.12 before 2.13, 2.15, 2.16.
- **2.17-2.22** are the owner-asked quality pass, so the `new-audio-node` minimalism rule yields for these nodes only; each control must pass the 1.0 spec rule.
- Factory presets of other apps (Ableton `.adv`/`.adg` are open XML) are read for **statistics only** (which ranges sound designers use, to set our defaults and ranges); none are copied or shipped.
- Re-evaluated 2026-10-13 and now taken: filter models (2.25), wavetable warps (2.26), drum synth (2.27), note entry (2.28), control API (2.31, the real need behind "Python everywhere"). After the design-instrument correction: resynthesis (2.32), string/modal modelling (2.33), linear-phase EQ (2.34).
- Still not taken, with the reason:

| Item | Reason |
|---|---|
| Vintage console EQ emulations | character, not capability; the saturator (2.17) and dynamic EQ (2.19) cover the sound |
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
| 3.5 | Render quality | not compared against a reference renderer | render the dossier G scenes in Infinite and Blender Eevee; add what is missing of soft shadows, ambient occlusion, depth of field, 3D motion blur, supersampled stills, 16-bit PNG / EXR output plus an offline render mode: export quality set by samples per frame, not by the real-time budget | Render 3D path, `src/core/HeadlessJob.cpp` (`--frame`) | side-by-side contact sheet per scene; each added feature has a reference image |
| 3.6 | Lights and world | directional, point, sun, ambient, spot | area light, light linking, IES profiles; HDRI and sky world | `SceneNodes.h`, `EnvironmentNode.h` | render reference images |
| 3.7 | Bevel and inset | none | bevel edges (width, segments), inset faces | GeometryOp table | GEOAUDIT manifold check |
| 3.8 | Rigid bodies | Cloth and particles only (Cables Rapier ops) | boxes, spheres, convex hulls, ground, impulses; deterministic at fixed step | new simulation node | same result on all three platforms |
| 3.9 | L-system | none | axiom + rules + angle + iterations → curve | new geometry node | known plant reference |
| 3.10 | Defocus (bokeh) blur | none (Pixelmator) | depth-driven bokeh | new FilterDef | `compositing-pipeline-sweep` |
| 3.11 | Cables image-op gaps | 108 Cables ImageCompose ops not compared op by op | gaps from the 1.0 tool that pass the spec rule become FilterDefs | `src/core/FilterDefs.cpp` | each new filter in the image-fx audit |
| 3.12 | Visual perf | geo.instance 2.73 ms (Blender 1.26); geo.subdiv 12.01 ms (8.1); B8 heavy p99 33.2 ms, 9.36% missed; motion/radial blur 0.16 ms/node over | instance ≤ 1.3 ms, subdiv ≤ 8.1 ms, B8 heavy p99 ≤ 18.3 ms and < 0.5% missed, blur within G9 | perf tracker `docs/plans/perf/README.md` | scoreboard rows met |
| 3.13 | 2D fluid | none (TouchDesigner, Cables staple) | GPU stable fluids (Stam 1999): velocity, dye, vorticity, obstacles from an image; 1080p ≤ 3 ms | new compositing node | divergence below 1e-3 after projection |
| 3.14 | Clip speed in the arrangement | Video Source has speed; arrangement clips do not | per-clip speed and reverse, audio follows with 1.6's stretch | `src/arrange/` (`timeline-arrangement-architecture`) | export of a 2× clip has the right length and pitch |
| 3.15 | GPU particles (Metal compute) | CPU, capped 200k | run gate G1 of `docs/plans/metal-compute.md`; if it passes, build to its G2 bar (1M in < 2 ms); else record the number | `SimulationNodes.h` | G1 row either way |
| 3.16 | Volumes | none | volumetric fog, smoke and clouds (ray-marched density field, Field-programmable), for stills and export first, real time where the budget allows | new geometry/render node | reference images; frame time recorded |
| 3.17 | Share a patch | users send `.inf` files by hand | one action writes a share bundle: the patch, a thumbnail and a short preview render; the website gallery lists bundles (same path as the Extensions page) | Stage menu, `tools/website/` | a bundle opens on a clean machine and matches its preview |

Settled:
- Re-evaluated 2026-10-13 and now taken: 2D fluid (3.13), clip speed (3.14); after the design-instrument correction: render quality (3.5), light linking and IES (3.6), volumes (3.16), patch sharing (3.17).
- Still not taken: sculpting and retopology (Blender's job; Infinite designs procedurally); depth cameras (vendor SDKs on three platforms; Apple Vision tracking covers it); a web player (a second renderer; 3.17 shares a preview render instead); magnetic storyline (a film-editing model); DMX/Art-Net (stage only).

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
| Pixelmator | defocus blur | 3.10 |
| VCV Rack (GPL: manual and behaviour only; the dossier built from its source manifests was removed) | polyphonic cables | 2.12 |
| builtins-kit (our nodes measured like the DAWs') | default level jumps, Chorus/Flanger clipping, FieldSynth and Metallic defaults | 1.9-1.11 |
| load-bench | 13-track ceiling for Analog+EQ on one core | 2.24, 2.16 |
| host-audit | RC-20 crashes only in our host | 1.12 |
| project-bench formats | Ableton sets and presets are open XML; ours are the smallest (0.8 KB) | 2.29, preset statistics |
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
