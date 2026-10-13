# tools/re-survey

Tools for the competitor survey in `docs/plans/re-survey/README.md`. All of them run headless and use only
macOS-shipped tools plus Infinite's own CLI. Big output goes to `~/re-output` (override with `RE_OUTPUT`) and is never committed.

| Tool | One-line usage | What it gives |
|---|---|---|
| `inventory.py` | `python3 tools/re-survey/inventory.py /Applications/Bitwig\ Studio.app` | Bundle facts: Info.plist, document types, archs, linked/bundled libraries, tech stack, helpers, bundled plugins, symbol namespaces (counts), pillar keyword counts, entitlements |
| `plugin_probe.py` | `python3 tools/re-survey/plugin_probe.py run dry node:Reverb "Pro-L 2"` | Latency, gain, THD/THD+N at -12 and -1 dBFS, HF aliasing, flatness, tail, RT60, CPU, parameter count; one comparable table. `list` shows AU ids |
| `synth_probe.py` | `python3 tools/re-survey/synth_probe.py run Diva "Serum 2" node:Wavetable` | Notes in, audio out: patch octave and pitch error per note (YIN), aliasing at MIDI 96/108, onset, attack, release, velocity span, L/R correlation, determinism, CPU idle and per voice |
| `ui_map.py` | `python3 tools/re-survey/ui_map.py run Logic "Ableton Live 12 Suite" Bitwig TouchDesigner` | Read-only accessibility map: every menu item with its shortcut, shortcut clashes, window outline, how much of the UI is custom-drawn, actions apps share and their shortcuts. `ax_dump.swift` is its walker |
| `capability_map.py` | `python3 tools/re-survey/capability_map.py run bitwig live td logic infinite` | What scripts can reach, from the official API references (Bitwig Javadoc, Live Object Model, TD Python classes, Logic Scripter, Infinite RPC/CLI), sorted into capability domains |
| `app_bench.py` | `python3 tools/re-survey/app_bench.py run Logic Bitwig ~/Desktop/Infinite.app --runs 3` | Launch to first window (cold, warm), idle CPU, memory, threads and processes over the whole process tree, bundle size |
| `bounce_kit.py` | `python3 tools/re-survey/bounce_kit.py make`, bounce in each DAW per `PROTOCOL.md`, then `analyse <dir> ...` | Export offset, gain, null residual, response, THD+N, silence floor/dither, centre pan law, MIDI click offset/jitter, tempo-map handling |
| `host_audit.py` | `python3 tools/re-survey/host_audit.py run [--filter fabfilter] [--formats au,vst3]` | Every installed AU/VST3 loaded in Infinite's host, one process each: crash (with the .ips culprit matched by pid), hang, fail, code signature, silent/NaN/clip; load time; VST3 out-of-process scan; Apple `auval`; AU vs VST3 twins |
| `au_oop.py` | `python3 tools/re-survey/au_oop.py run ValhallaDelay "Pro-L 2" [--frames 64,128,256]` | AU in process vs out of process (Apple's hosting service): instantiate time, render-call median/p99/max vs deadline, CPU incl. the service, reported latency |
| `load_bench.py` | `python3 tools/re-survey/load_bench.py run --tracks 8,32,64,128 --track node:Wavetable+node:Reverb` | N tracks of synth + effect on held chords, rendered offline: audio-thread load as % of one core, ms per track per second, the 70 % ceiling; `midi out.mid` writes the same chords for the DAW templates |
| `stretch_kit.py` | `python3 tools/re-survey/stretch_kit.py make`, stretch in each DAW per `PROTOCOL.md`; `infinite --dir <dir>` renders Infinite's own through arrangement clips (`--timeline`); then `analyse <dir> ... --out results.md` | Drums, vowel, tone and sweep at 0.5x/0.8x/1.25x/2x: length error, hit timing (pre-echo shows early), missed and extra onsets, transient smear, crest loss, pitch, flutter, non-harmonic artefacts, sweep tracking |
| `builtins_kit.py` | `python3 tools/re-survey/builtins_kit.py make`, bounce each DAW's built-ins per `PROTOCOL.md`; `infinite --dir <dir>` renders Infinite's synth and effect nodes; then `analyse <dir> ... --out results.md` | DAW-only instruments and effects at their defaults: tuning, octave, aliasing at MIDI 96/108, attack, release, velocity span; effect latency after compensation, gain, THD, alias, flatness, tail, RT60 |
| `render_bench.py` | `python3 tools/re-survey/render_bench.py infinite`, then `blender` (headless, `render_bench_blender.py`, public bpy only); `analyse <dir> ... --out results.md`; `td-prep` + paste one line in TouchDesigner's Textport (`render_bench_td.py`, TD has no headless mode), then `td`; `sync <movie>` reads any flash+click movie | Movie render fps (render + encode, slope of two lengths) for 10k instanced cubes and a 4-blur scene at 720p/1080p/4K (TD 720p only), H264 and ProRes 4444; H264 PSNR/SSIM and bitrate against each app's own lossless frames; 10-minute AV sync: offset, drift, spread. Movies read by `video_read.swift` (AVFoundation) |
| `blender_bench.py` | `python3 tools/re-survey/blender_bench.py blender` (headless, `blender_bench_blender.py`, public bpy only), `infinite`, `analyse <dir> ... --out results.md` | Geometry-node instancing (10k), subdivide+displace, cloth stepping: ms per frame. Blender = depsgraph evaluation per frame, nothing drawn (its eval fps is a headless proxy, true viewport fps needs the GUI); Infinite = matched patch, `--render` slope 2 s vs 8 s net of a Cube baseline. QUALITY `geo.*`, `sim.cloth_ms` |
| `av_bench.py` | `python3 tools/re-survey/av_bench.py infinite`; `td-prep [--mode av\|scene]` + paste one line in TouchDesigner's Textport (`av_bench_td.py`), then `td`; `movie <mov>`, `frames <json>`, `analyse` | Audio→picture latency, jitter, beat-to-frame lock and drift from a looped 128 BPM click-and-flash movie (each app's own audio track vs its picture); Infinite reactive (Audio Analyze), clock, and the file-audio regression probe; TD audio-reactive 10k-instance scene frame times (p50/p95/p99, drops). Live camera variant: `docs/plans/re-survey/PROTOCOL-av.md`. QUALITY `av.*`, `live.*` |
| `project_bench.py` | `python3 tools/re-survey/project_bench.py infinite [--sizes 10,100,1000,4000]` / `history [--all]` / `library` / `formats` | Project scaling: file size and headless load / load+write time for generated N-node patches; every `.inf` shipped in each release tag (or ever committed) opened by today's build; factory presets, samples, clips and templates per app by kind, Infinite's in-code presets included; the other apps' project and preset containers on this machine (gzip XML, zip, package dir, binary) from the first bytes only |
| `workflow_cost.py` | `python3 tools/re-survey/workflow_cost.py table [--out f.md]` / `check` | Ten common tasks (instrument to export) per app: step count and Keystroke-Level Model seconds; Infinite steps cite `path::token` and `check` fails when one goes stale; DAW steps from their manuals, confirmed in the timed sitting (`PROTOCOL-workflow.md`) |
| `latency_probe.py` | `python3 tools/re-survey/latency_probe.py run "Live 128"` | real round-trip latency and jitter of any app through BlackHole (the app monitors input to output); clicks in, echo gap out (`PROTOCOL-latency.md`) |
| `readers.py` | `python3 tools/re-survey/readers.py cables --fetch` / `als song.als` / `amxd dev.amxd` / `fcpxml x.fcpxml` / `toe x.toe` / `blender --demo` | Structure of each format: op catalog, devices/clips/automation, timeline lanes/roles, operator families/wires, node trees/domains |
| `diff.py` | `python3 tools/re-survey/diff.py new C8 "Bitwig Studio"` / `lint` / `report` | Dossier scaffold, clean-room + outcome lint, capability diff (`docs/plans/re-survey/capability-diff.md`), 5-quest cap |
| `storage.py` | `python3 tools/re-survey/storage.py status` / `compress` / `clean-tmp` / `check-repo` | `~/re-output` sizes, gzip big files, delete temps, no artefacts in the repo |
| `selftest.py` | `python3 tools/re-survey/selftest.py [--quick]` | Runs every tool's `--self-test` |

`blender_dump.py` runs inside Blender (`readers.py blender` drives it); `common.py` is shared helpers.

Exit codes: 0 ok, 1 found a problem / self-test failed, 2 usage or tool error.

## Known gaps

- `plugin_probe`: AU and VST3 effects (VST3 needs a build with 9f185449); instruments go to `synth_probe`.
  Settings and sweeps use the host's ranges (`plugin_probe.py params X`): AU in the plugin's own units,
  VST3 always normalised 0-1. The 16-bit headless WAV puts the floor near -87 dB THD+N.
  The CPU column is the render-time slope, net of the dry rig; treat differences under ~1 ms/s as noise.
- `synth_probe`: the default patch decides most columns (Diva's sits an octave down, Serum's and Vital's ignore
  velocity), so compare like with like or set the patch with `@settings`. Times have one-cycle resolution.
- `ui_map`: needs the host trusted for Accessibility. Logic and Live 12 expose their windows; TouchDesigner only its
  menus; Bitwig nothing at all (use its Controller API docs via `capability_map` instead). It launches an app that is not running and quits it after.
- `capability_map`: domains are keyword-sorted; counts are a shape, not a score. Pages are cached in ~/re-output.
- `readers.py toe` needs TouchDesigner installed (it uses the bundled `toeexpand`); `blender` needs Blender.
- Clean room: nothing here reads GPL/AGPL source. Blender is driven through its public `bpy` API only, never
  its bundled scripts. `diff.py lint` fails a dossier that links copyleft source or pastes long code.
