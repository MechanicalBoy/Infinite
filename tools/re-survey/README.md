# tools/re-survey

Tools for the competitor survey in `docs/plans/re-survey/README.md`. All of them run headless and use only
macOS-shipped tools plus Infinite's own CLI. Big output goes to `~/re-output` (override with `RE_OUTPUT`) and is never committed.

| Tool | One-line usage | What it gives |
|---|---|---|
| `inventory.py` | `python3 tools/re-survey/inventory.py /Applications/Bitwig\ Studio.app` | Bundle facts: Info.plist, document types, archs, linked/bundled libraries, tech stack, helpers, bundled plugins, symbol namespaces (counts), pillar keyword counts, entitlements |
| `plugin_probe.py` | `python3 tools/re-survey/plugin_probe.py run dry node:Reverb "Pro-L 2"` | Latency, gain, THD/THD+N at -12 and -1 dBFS, HF aliasing, flatness, tail, RT60, CPU, parameter count; one comparable table. `list` shows AU ids |
| `synth_probe.py` | `python3 tools/re-survey/synth_probe.py run Diva "Serum 2" node:Wavetable` | Notes in, audio out: patch octave and pitch error per note (YIN), aliasing at MIDI 96/108, onset, attack, release, velocity span, L/R correlation, determinism, CPU idle and per voice |
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
- `readers.py toe` needs TouchDesigner installed (it uses the bundled `toeexpand`); `blender` needs Blender.
- Clean room: nothing here reads GPL/AGPL source. Blender is driven through its public `bpy` API only, never
  its bundled scripts. `diff.py lint` fails a dossier that links copyleft source or pastes long code.
