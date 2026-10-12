# re-survey: prompt for the next session (finish blocks A to F)

Paste everything below the line into a fresh Claude Code session in `/Users/namansoni/infinte`. Written 2026-10-12.

---

## What we are building

**Infinite** is an MIT-licensed **live instrument and AV workstation**, built so that audio and visuals live in
one patch and are played live. What makes it different:
- **Global modulation:** anything can modulate anything.
- **Learned modulators:** the green "prediction" family, which learns with the player.
- **Field:** a language for writing your own pixels, geometry and modifiers.
- **Everything else in one app:** a node graph, a timeline/arrangement, VST3/AU plugin hosting, 3D, compositing,
  and output (Syphon/Spout/NDI, projection).

It ships on macOS, Windows and Linux.

**Owner's success ranking:**
1. Income.
2. Reach: many people making art with it.
3. Art and name.
4. Learning.

**Standing rule:** every feature must be grounded in what a real user does. Push back on work that serves the
architecture rather than the player.

## What this work is for (re-survey)

Make Infinite beat the apps people compare it to on quality and speed:
- DAWs: Bitwig, Ableton Live, Logic.
- Visual tools: TouchDesigner, Blender (as a benchmark only), Final Cut.
- Plugins: FabFilter, Valhalla, u-he Diva, Serum, Vital.

The method is **black-box measurement**: stimuli go in, the app plays, renders or bounces them, an analyser
turns the result into numbers, and `app_bench` watches CPU and memory meanwhile. Every area uses this one
harness, grown out of `tools/re-survey/bounce_kit.py`; each area adds stimuli and an analyser, not a new rig.
Each block ends in a dossier table that says what Infinite should build, fix, measure or ignore, and real bugs
found along the way get fixed, not just noted.

**Read first, in this order:**
1. `docs/plans/re-survey/coverage.md`: the area map, owner priorities, block order and results so far. It is
   the source of truth for what is done.
2. `docs/plans/re-survey/README.md`: the rules, the competitor registry, the dossier template, dead ends.
3. `tools/re-survey/README.md`: every tool and how to run it. `python3 tools/re-survey/selftest.py` checks
   them all.
4. `AGENTS.md`, then the skills each block names below.

## Rules (non-negotiable, owner's words where quoted)

**Clean room.** Infinite is MIT.
- Never open, read, grep or reference GPL/AGPL source: Bespoke, VCV Rack, Vital, OBS, VLC, SuperCollider,
  Kronos, Cmajor, and **Blender** (including its bundled Python scripts).
- For Blender use only its public manual, its public Python API docs and its observable behaviour.
- Vital: measure the binary only.
- Never use the `bespoke` MCP server or the `bespoke-viz` skill.

**Findings.**
- Findings are BEHAVIOUR NOTES, never copied or decompiled code.
- No decompiling of competitor binaries at all. This was declined and recorded; do not re-propose it.
- Never commit or redistribute competitor binaries, decompiled code or raw dumps.

**Tools.**
- Use what macOS ships (`otool`, `nm`, `codesign`, `plutil`, `strings`, `lipo`, `footprint`, `auval`) and
  Infinite's own headless host.
- No Ghidra, no Hopper, no Homebrew bottles.
- No debug or analysis tools in shipped builds.

**Storage.** Big outputs go to `~/re-output`, compressed, never committed. Remove temporary downloads.

**Git.**
- Branch per step (`git-branch-workflow`), commit per step, merge straight back to main, no PR.
- **Never push** unless the owner says so.
- No "Generated with Claude Code" or Co-Authored-By lines anywhere.

**Working with the owner.**
- One decision per message, and never re-ask a recorded answer (see coverage.md and the memory notes).
- Answers use tables, bullets and diagrams, never Artifacts or long prose.
- Don't end a reply telling the owner to do obvious next steps.
- Never quit or kill an app the owner opened.
- Never UI-script Infinite's ImGui canvas. Verify headless (`--audio-summary`, `--frame`, `--render`, env
  self-tests) or by reading code.
- Before fixing any bug, run the `bug-blast-radius` nine questions.
- After building Infinite, copy `build/Infinite.app` to `~/Desktop/Infinite.app`.
- Quest board: 5 or fewer open quests, release-bound only. re-survey findings go to the capability diff, not
  the board.
- **Out of scope:** web research on business, pricing, onboarding or distribution. "Measure, don't research."

**Installed here:**
- DAWs: Ableton Live 12 Suite (trial), Logic Pro, Bitwig Studio.
- Visual: TouchDesigner, Final Cut. Blender is behaviour only.
- Plugins: the full FabFilter line, the full Valhalla line, TDR Nova, Diva, Serum 2, Vital.
- Counts: 84 AU and 83 VST3 plugins, plus 42 VST2 and 23 CLAP that Infinite can't load.

## Where things stand (2026-10-12)

**Tools on main:**
- `inventory`, `plugin_probe`, `synth_probe`, `ui_map` (+ `ax_dump.swift`), `capability_map`, `app_bench`,
  `bounce_kit`.
- `host_audit` (every installed AU/VST3 through Infinite's host, graded crash/hang/fail/silent).
- `readers`, `diff`, `storage`.

**Bench results:**
- App bench (idle):
  - Logic: 2.8 % CPU, 224 MB.
  - Live: 41 % CPU, 819 MB.
  - Infinite: 12.7 % CPU, about 225 MB; window in 4.4 s cold, 0.7 s warm.
  - TouchDesigner: 49.7 % CPU, 1400 MB; window in 10.9 s cold, 3.0 s warm.
  - Bitwig: 3.7 % CPU, 1270 MB. Its window time still needs a rerun: detection is fixed, because its window
    belongs to the `--launch` child process.
- Host audit:
  - 163 of 167 plugins clean.
  - RC-20 Retro Color and ShaperBox 3 crash in both formats. auval and Live's scan DB fail them too.
  - Default-patch quirks: Phase Plant is silent, Twin 2 has DC offset, Vital clips.
  - VST3 scan: 82 of 82 ok.

**Fixed in this session (Block A):** plugins never saw Infinite's tempo or transport.
- What was wrong:
  - VST3 got a hard-coded "playing, 120 BPM, 4/4" clock on all three platforms (since `a2a4703b`, shipped).
  - AU got no host clock at all.
- The fix:
  - A shared `Platform::PluginTransport` snapshot, filled per block from `Transport` in `AudioPluginNode`.
  - One VST3 mapping, `src/platform/PluginTransportVST3.h`, used by the macOS, Windows and Linux hosts.
  - AU `musicalContextBlock` and `transportStateBlock` in `Platform.mm`.
- The check: `Platform::PluginHostClockSeen`, asserted in `INFINITE_PLUGINSCANTEST`.
- Status: merged to main, macOS verified (`INFINITE_PLUGINSCANTEST`, `PLUGINNODETEST`, Drumazon in both formats); Windows and Linux checked by reading the code only.
  Release notes need a line for it.

## What to do: finish blocks A to F, one block at a time

Each block ends in a dossier table (`docs/plans/re-survey/dossiers/`), a results line in coverage.md, and
fixes for any real Infinite bug it finds. Ask the owner only when a block needs their hands. Batch that into
one sitting per app.

### Block A: plugin hosting and stability (finish)

Skills: `plugin-host-hardening`, `bug-blast-radius`, `windows-parity`, `linux-parity`.
1. **Verify the transport fix end to end.** `host_audit.py run --filter Drumazon` should show the VST3
   silent with no notes. Then render a patch with Valhalla Delay synced at 90 BPM: the echo spacing must
   follow 90 BPM, not 120.
2. **Fix `host_audit.crash_culprit`.** Accept only `.ips` reports newer than the run's start time and not
   seen before. It attributed RC-20's report to ShaperBox. Then read ShaperBox's own crash report and name
   the faulting frame.
3. **Fix the headless VST3 path cache.** A headless render never seeds `gVST3BundleMap` (see
   `PluginVST3.mm:154-170`), so every VST3 load rescans all folders: 3.6 s cold, 0.7 s warm. Seed it from the
   saved plugin index the app already writes. Target: VST3 load median close to AU's 0.19 s.
4. **Plugin crash isolation.** Bitwig hosts plugins out of process; Logic uses macOS's AU hosting service.
   Measure what `loadOutOfProcess` costs for AU (CPU and latency per block) using host_audit plus
   app_bench. Decide on a crash-only fallback (run a plugin out of process after it has crashed once)
   rather than the cost for every plugin. Settle the design yourself; the owner prefers decisions to
   questions.
5. **Stability tests.** Recovery after a crash (autosave), undo depth and speed, and what happens to the
   patch and audio when a plugin crashes mid-render. Compare with Live, Logic and Bitwig by behaviour.
6. **Missing formats.** The owner reports users with VST3 crash and not-loading problems. Write a short
   CLAP and VST2 decision note covering what users lose today and the effort, with no code.
7. Open item: the Saturn 2 VST3 default Drive reads 0, the AU reads 0.2. Find out which one is wrong.

### Block B: load, latency, routing (owner priority: important, "makes it professional")

Skills: `audio-pipeline-sweep`, `rate-analysis-sweep`, `run-infinite-hygiene`.
1. **Performance under load.** N-track templates (8, 32, 64, 128 tracks of synth plus effect) in each DAW
   and in Infinite. While playing, `app_bench` records CPU, dropouts and memory. Measure the ceiling where
   dropouts start, and multicore scaling.
2. **Real-time latency.** Round trip from audio in to audio out on the interface (loopback cable, or
   loopback device if none), at 64, 128 and 256 buffer sizes: measured latency vs. reported latency, and
   jitter. Plus PDC correctness with latent plugins (FabFilter linear phase).
3. **Mixing and routing.** Sends, sidechain, buses and channel limits. Pan law and summing go through the
   bounce harness.

The owner builds one template per DAW. Prepare exact instructions plus stimuli first.

### Block C: built-in instruments and effects, time-stretch, engine accuracy (owner: "cover others' built-ins")

Skills: `audio-node-sweep`, `param-truth-audit`, `new-audio-node` #5 (minimalism).
1. The bounce kit is ready at `~/re-output/bounce-kit/kit`, with `PROTOCOL.md`. It waits on the owner's DAW
   bounces. Afterwards run `bounce_kit.py analyse`.
2. **Built-in instruments** (Live Wavetable, Operator, Drift; Logic Alchemy, ES2; Bitwig Polymer, Phase-4):
   `synth_probe` metrics (pitch, aliasing, envelope, velocity, voices, CPU) from MIDI stimuli, compared with
   Infinite's own synths.
3. **Built-in effects** (Live Echo, Roar, Reverb; Logic ChromaVerb, Compressor; Bitwig): gain, response,
   THD, tail and CPU from the sweep stimuli. Compare with `INFINITE_FXAUDIT`.
4. **Time-stretch and pitch-shift quality** (Live warp, Logic Flex, Bitwig): stretch stimuli (drums, vocal,
   sine sweep) at 0.5x, 0.8x, 1.25x and 2x, then transient smear, pitch error and artefacts. Write a new
   stretch analyser in the harness.

### Block D: video and export (TouchDesigner and Blender are the bar)

Skills: `render-pipeline-sweep`, `av-sync-sweep`, `output-projection-sweep`.
1. Matched scenes (instanced geometry, feedback, blur chain, 4K compositing) in TouchDesigner (TD Python),
   Blender (CLI, public API only) and Infinite. Measure FPS, frame-time spread, GPU memory and the resolution
   ceiling.
2. **Export:** offline render speed, codecs and formats, AV sync drift over 10 minutes, and quality (PSNR or
   SSIM against an uncompressed reference). Compare with TD movie out, Blender and Final Cut. Owner:
   "important for user to get good export."

### Block E: projects and library

Skills: `infinite-patch-authoring`.
1. **Projects:** save and load time against project size, file size, whether the format is open, opening
   files from old versions, and autosave/recovery behaviour, across all apps.
2. **Library:** audit Infinite's existing library (presets, samples, templates, browser search speed)
   against what Live, Logic and Bitwig ship. Report coverage gaps users would feel, not raw counts.

### Block F: Final Cut UX, workflow cost, visual design

Skills: `timeline-arrangement-architecture`, `infinite-design-system`, `node-ui-pillars`.
1. **Final Cut:** `ui_map` of its timeline, mapping clip operations, magnetic timeline behaviour and
   shortcuts. Then match its timeline performance: scrub, zoom and many-clip responsiveness against
   Infinite's arrangement. Owner: "not much, but refer to Final Cut's UI/UX and match its performance."
2. **Workflow cost:** step counts and times for the 10 most common tasks (load a plugin, add an effect,
   automate a parameter, map a modulator, export) per app. Owner: "common tasks should perform well."
3. **Visual design:** screenshot metrics for density, contrast (`tools/design/contrast.py`), HiDPI and
   themes. Improve through grounded ImGui enhancements only; the "Dot & Current" design language was
   rejected.

## Done means

- Every area in coverage.md is marked done or parked, with a results line.
- Each block has a dossier ending in outcomes.
- Every real bug found is fixed with a regression check and merged to main. Nothing is pushed without the
  owner's word.
- Each new tool has a self-test, a line in the `tools/re-survey/README.md` table and in the `tool-first`
  inventory.
- `~/re-output` is listed and temporary files are removed.
