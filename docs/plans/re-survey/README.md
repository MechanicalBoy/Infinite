# re-survey: deconstruct competitors, one by one

Prompt for a new session. Status: draft, not yet started. Written 2026-10-12.

## 1. Goal

Build `tools/re-survey`, a repeatable toolkit, and use it to deconstruct one competitor at a time. Each
deconstruction ends in a short dossier (section 7) that tells Infinite what to build, measure or ignore.

Infinite is an MIT-licensed live instrument and AV workstation: global modulation, learned (prediction)
modulators, the Field language, a node graph, timeline/arrangement, plugin hosting, 3D and compositing.
Nothing in this survey is general reverse engineering. If a finding does not map to a pillar below, drop it.

## 2. Pillars (what findings must map to)

| # | Pillar | One line |
|---|---|---|
| P1 | Live AV workstation | Audio and visuals in one patch, played live |
| P2 | Global modulation | Anything can modulate anything, one routing model |
| P3 | Learns with you | Prediction modulators (the green family) |
| P4 | Field | Customizable language for pixels, geometry, modifiers |
| P5 | Audio quality and hosting | Own DSP plus VST3/AU hosting |
| P6 | Timeline and arrangement | Clips, lanes, stretch, export |
| P7 | 3D, compositing, output | Geometry, 2D effects, Syphon/Spout/NDI, projection |
| P8 | Performance | Audio first, then projector, canvas, previews |

## 3. Rules (non-negotiable)

- Follow `AGENTS.md`. Load the matching skills first: `tool-first`, `git-branch-workflow`,
  `codebase-navigation`, `infinite-patch-authoring` (plugin probe), `semi-brain` (before architecture calls).
- Clean room. Infinite is MIT. Never open, read, grep or reference GPL/AGPL source: Bespoke, VCV Rack, Vital,
  OBS, VLC, SuperCollider, Kronos, Cmajor, **and Blender**. Blender is GPL, so its bundled Python scripts and
  its source are off limits too. For Blender use only its public manual, its public Python API docs, and its
  observable behavior (what the UI and nodes do when used).
- Findings are BEHAVIOR NOTES ("how X routes a modulator"), never copied or decompiled code. Never
  re-implement from decompiled output.
- The owner accepts the EULA risk for education on proprietary apps. Still never commit or redistribute
  competitor binaries, decompiled code or raw analysis dumps.
- No debugging or analysis tools in shipped builds.
- Prefer what macOS ships (`otool`, `nm`, `codesign`, `plutil`, `strings`, `lipo`) and Infinite's own plugin host.
  Do NOT install Ghidra, Hopper or Homebrew bottles (see section 8, dead ends).
- Storage: big outputs go to `~/re-output` (outside the repo), compressed, never committed. Remove temporary
  downloads when done. Check `du -sh ~/re-output` at the end of each target.
- No "Generated with Claude Code" or Co-Authored-By lines anywhere. Feature branch, commit per step, merge
  straight back, no PR. One decision per message when you need me, and never re-ask a recorded answer.
- Keep the quest board minimal: 5 or fewer open quests, release-bound only.

## 4. Competitor registry

"On Mac" = installed here now. Method column says how to learn without reading code.

### Tier 1: direct (node-based AV)

| ID | Competitor | Pillars | Learn | Method | On Mac |
|---|---|---|---|---|---|
| C1 | TouchDesigner | P1 P4 P7 P8 | Operator families, cook model, GPU instancing, perf ceiling | Docs, `.toe`/`.tox` structure, own timing | Yes |
| C2 | cables.gl | P1 P2 P4 | Op catalog, port types, patch JSON, export-to-web | Saved analysis + public ops docs | Yes |
| C3 | Max/MSP/Jitter + Max for Live | P1 P2 P5 | Patcher paradigms, `.amxd` JSON, modulation conventions | Docs + JSON format | No |
| C4 | vvvv gamma | P1 P4 | Dataflow typing, live recompile | Docs, node browser | No |
| C5 | Notch | P7 P8 | Real-time quality, GPU effect set | Docs, demos | No |

### Tier 2: live performance

| ID | Competitor | Pillars | Learn | On Mac |
|---|---|---|---|---|
| C6 | Resolume (Arena/Avenue) | P1 P7 | Clip launching, effect chains, latency expectations | No |
| C7 | MadMapper / Isadora | P7 | Projection mapping UX, show control | No |

### Tier 3: DAWs, editors and 3D (modulation, arrangement, geometry)

| ID | Competitor | Pillars | Learn | On Mac |
|---|---|---|---|---|
| C8 | Bitwig Studio | P2 P6 | Closest model to global modulation: routing UI, per-voice vs global, arrangement clip behavior | Yes |
| C9 | Ableton Live | P6 P5 | Warping, clip model, `.als` format, Live Object Model | No |
| C10 | Final Cut Pro | P6 | Arrangement view reference: magnetic timeline, roles, compound clips, retiming, trim and ripple behavior | Yes (Final Cut Pro Creator Studio) |
| C11 | Blender (Geometry Nodes and 3D) | P4 P7 | Geometry Nodes: fields, attributes, instances, domain model, simulation zones. Also modifiers, shader nodes, viewport, import/export formats. GPL: docs and behavior only | Yes |

### Tier 4: modular and creative coding

| ID | Competitor | Learn | Licensing |
|---|---|---|---|
| C12 | VCV Rack, Bespoke Synth | Modular UX, cabling | GPL: behavior only |
| C13 | Pure Data, SuperCollider | Dataflow semantics | SuperCollider GPL: never read source |
| C14 | Reaktor | Sound-design ecosystem benchmark | Proprietary: docs and behavior |
| C15 | Hydra, Strudel, Shadertoy | Live-coded visuals and music | Hydra and Strudel are AGPL-3.0: docs and behavior only. Shadertoy: per-shader licences, docs and behavior |
| C16 | Faust, Kronos | Ideas behind Field | Faust compiler is GPL: docs and papers only. Kronos: published paper only. Cmajor: off limits |

### Tier 5: quality benchmarks (the bar, not competitors)

| ID | Benchmark | Measure |
|---|---|---|
| B1 | FabFilter (Pro-Q 4, Pro-L 2, Saturn 2, Pro-C 2, Pro-R 2, Timeless 3) | EQ, dynamics, saturation, reverb accuracy |
| B2 | Serum 2, Phase Plant, Diva, Vital | Aliasing, filter behavior, modulation depth and rate limits (Vital is GPL: probe only, never source) |
| B3 | Valhalla (Plate, FutureVerb, Delay, FreqEcho) | Reverb and delay character |

Not competitors: Premiere and DaVinci (only as a second view on C10), Unreal and Unity (game engines).

## 5. What to learn (priority order)

| # | Question | Source | Output |
|---|---|---|---|
| Q1 | How do the best tools bind and route modulation (C8, C3, C1 CHOP exports, C2)? | Docs + own use | Gaps vs Infinite's modulation matrix |
| Q2 | How fast are they, and why (C1 cook model, C6 latency)? | Own timing | Perf targets for P8 |
| Q3 | Which sound-quality metrics beat ours (aliasing, THD, latency, CPU)? | Plugin probe | Per-node table vs a benchmark plugin |
| Q4 | How does C10 handle arrangement (magnetic timeline, roles, compound clips, retime) vs `src/arrange/`? Read `timeline-arrangement-architecture` first | Own use + docs | Arrangement gaps |
| Q5 | How do C11's geometry nodes model fields, attributes and instances vs Infinite's geometry nodes and Field Modifier? Read `new-geometry-node` and `field-domains` first | Public manual + own use | Geometry and domain gaps |
| Q6 | What features exist elsewhere that Infinite lacks (MIDI out, cables FX presets are already on the list)? | Op catalogs, feature lists | At most 5 quests |
| Q7 | How do others do learned or adaptive modulation? (little direct competition; nearest are Wekinator, Magenta Studio) | Docs | Positioning, not a copy |

## 6. Deconstruction order (one by one)

Stop after each target and show me the dossier. Do not start the next one until I say so.

| Step | Target | Why this order | Deliverables used |
|---|---|---|---|
| 1 | C2 cables.gl | Op catalog is one command (`readers.py cables --fetch`); the REA dump covers only the Electron shell | Op-catalog table, patch-JSON notes |
| 2 | B1-B3 plugin probe | Directly improves Infinite's audio quality | Probe tool + per-plugin tables |
| 3 | C8 Bitwig | Closest to P2 | Modulation routing dossier |
| 4 | C1 TouchDesigner | Biggest AV rival | Cook model and perf dossier |
| 5 | C10 Final Cut | Arrangement reference | Timeline behavior dossier |
| 6 | C11 Blender | 3D and geometry reference | Geometry model dossier (behavior and docs only) |
| 7 | C3, C9 (if installed or trial) | Format readers (built) | `.amxd`, `.als` readers |

## 7. Dossier template (one per target, in `docs/plans/re-survey/dossiers/<id>.md`)

Scaffold with `python3 tools/re-survey/diff.py new <ID> "<Name>"` (from `dossiers/TEMPLATE.md`); `diff.py lint` enforces the parts below.

1. What it is, version, how we got access, licence status (GPL, proprietary, permissive).
2. Method used and what was NOT done (no source read, no decompiled code kept).
3. Pillar map: findings per pillar P1-P8, each with evidence (screenshot path, command, doc link).
4. Comparison table: Pillar | Their feature | Infinite equivalent (file path) | Status (gap, lead, parity) | Outcome | Evidence.
5. Measurements (if any): metric, method, numbers, units, setup. Reproducible command line.
6. Outcome per finding: new quest, perf target, quality gap, or ignore (with one-line reason).
7. Storage: what was written to `~/re-output`, its size, what was deleted.

## 8. Tooling (build in this order)

1. `tools/re-survey/inventory.py`: bundle layout, linked frameworks, exported symbols, plugin formats, safe
   strings summary, Info.plist facts. Markdown report per app. Uses only macOS-shipped tools.
2. `tools/re-survey/plugin_probe`: loads a plugin through Infinite's own host, records parameter list,
   impulse and sweep response, THD, latency, CPU. Table output comparable between plugins.
3. Format readers: cables op catalog, `.amxd` (JSON), `.als` (gzipped XML), Blender and Final Cut public
   export formats where documented.
4. `tools/re-survey/diff.py`: turns dossier tables into a capability-diff report for the roadmap board.

Each tool runs headless, gets a line in the `tool-first` inventory, and has a self-test.

All built: see `tools/re-survey/README.md`. `python3 tools/re-survey/selftest.py` runs every self-test.

### State and dead ends (do not repeat)

- REA (npm `rea-agents` 6.4.0) is installed globally. Its JS/Electron analysis works.
- `~/re-output/cables-app-rea-analysis.json.gz` holds the cables.app analysis (99 MB compressed). It covers
  the Electron shell only (11 IPC calls, 2 native addons), not the ops catalog.
- Native analysis: Ghidra 12.1.4 ships no macOS arm64 decompiler. Hopper's headless bridge timed out, even
  after the demo dialog. Homebrew bottle installs are killed by the sandbox (casks work). Cutter's DMG failed
  to download. All of these were removed. If deep native analysis is ever needed, building Ghidra's decompiler
  from its Apache-2.0 source is the real fix (about 1 to 2 hours); ask me first.
- Bitwig, TouchDesigner and the plugins are native; use the inventory and black-box methods, not decompiling.
- VST3 plugins pass audio through unchanged in headless renders (`AudioPluginNode::ReloadFromIdentity` leaves
  `desc.path` empty, no warning). The probe uses the AU build and refuses `vst3:` targets until that is fixed.
- Headless `--audio-summary --wav` writes 16-bit, so THD+N bottoms out near -87 dB. Anything at the dry floor
  reads as "at floor", not a number.
- `Infinite --describe` with no type aborts (macOS privacy kill via CoreMotion). Always pass a type.
- The probe measures default plugin state only (`plugin_state` is an opaque blob) and effects only; B2 synths
  need a notes stimulus first.
- TouchDesigner ships `toeexpand`: `readers.py toe` reads `.toe`/`.tox` structure without decompiling.
- Never use the `bespoke` MCP server or the `bespoke-viz` skill for this work: both sit on BespokeSynth (GPL).
- re-survey findings are growth work. Under the quest-board rule (release-bound only) they land in the
  capability diff, not on the board, unless the owner promotes one.

## 9. Done means

- Each tool runs headless and has a one-line usage plus a self-test.
- Each dossier is readable without opening any competitor's code and ends in outcomes, not notes.
- At most 5 open quests added. Storage is clean (`~/re-output` listed, temp files removed).
- Report what failed, not just what worked.
