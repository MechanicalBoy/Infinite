# E Projects and library (Live, Logic, Bitwig, TouchDesigner, Blender): dossier

Status: done 2026-10-13 for what runs headless; GUI save/load timing and browser search speed wait on a short owner sitting (`PROTOCOL-projects.md`). Lint: `python3 tools/re-survey/diff.py lint docs/plans/re-survey/dossiers/E.md`

## 1. What it is

- Block E of `coverage.md`: areas 20 (projects and files) and 22 (content and library).
- Reference apps: Ableton Live 12 Suite, Logic Pro, Bitwig Studio, TouchDesigner and Blender, all installed. Licence: all proprietary except Blender (GPL, behaviour and file containers only).
- Only what each app installs here is counted. Logic's sound library and Bitwig's packages download on demand, so their totals are larger than the table.

## 2. Method

- `python3 tools/re-survey/project_bench.py infinite --sizes 10,100,1000,4000 --out ~/re-output/project-bench/scaling.md`: generated patches of N nodes (a Shape, N-2 cheap image effects, an Output, an LFO on every tenth node). Load is `--validate --lenient`; load and write is `--canonicalize`; median of 3, headless.
- `project_bench.py history --all`: the first committed version of every `.inf` the repo ever had, opened by today's build, each failure labelled.
- `project_bench.py formats`: the container of each app's project and preset files on this machine, from the first 256 bytes only. Nothing is decoded past the container and nothing is copied.
- `project_bench.py library`: factory presets, samples, clips and templates per app by kind, plus Infinite's in-code presets counted from `src/`.
- Not done: no source read, no decompiled code kept, no binaries or dumps committed.

## 3. Pillar map

- P8: Opening a project costs the same at 10 nodes as at 4000.
  - Load stays at 0.755–0.790 s for every size; the 10-node patch is the floor (process start), and the cost per node above it reads −0.01 to −0.30 ms, below measurement noise.
  - The 4000-node file is 313 KB (8 KB gzip at 1000 nodes, 32.5 KB at 4000).
  - Caveat: headless, cheap nodes, no window or GL setup counted. A 4000-node patch of heavy nodes, or the GUI's first frame, is not measured here.
- P1: Old patches still open.
  - Opened by today's build: every `.inf` shipped in each release tag from v0.1 to v0.5.0 loads (0 failures in 27 tags).
  - Every `.inf` the repo ever committed: 102 of 109 load. The 7 that fail are all explained: six negative test fixtures that must fail (`E_BAD_KEY`, `E_BAD_PARAM`, `E_BAD_SLOT`, `E_SLOT_TAKEN`, `E_NOT_A_MODULATOR`) and one file that never shipped in a release (`E_UNKNOWN_TYPE`).
  - Evidence: `~/re-output/project-bench/history.md` and `history_all.md`.
- P1: Infinite's project format is open text, like Live's; Bitwig, Logic, TouchDesigner and Blender keep theirs closed.
  - Infinite `.inf`: plain text, 0.8 KB median in the shipped examples. Live `.als`: gzip XML (226 KB median). Bitwig presets and devices: binary. Logic `.logicx`: a package directory (2 MB median) with closed contents; its `.aupreset` is XML. TouchDesigner `.toe`: binary (277 KB). Blender `.blend`: zstd.
  - A text format means a patch can be diffed, written by a script and read by an agent. Live is the only other app whose files could be.
  - Evidence: `~/re-output/project-bench/formats.md`.
- P1: Save truncated the user's file in place for every release since v0.1.
  - `Patch::Write` and the Field device writer opened the target and overwrote it. A full disk, a quota or a crash mid-save left a cut-off patch that no longer opened, often the only copy.
  - Fixed on main (fc683464, merged 3bac05c2): the file is written beside the target and renamed over it, so a failed save reports the error and leaves the previous file whole. Windows saves and opens folders with non-ASCII names through the same path. Autosave uses it too.
  - Regression: `headless_smoke.sh` checks a save cut off by a file-size limit (fails, previous file intact, no temp left) and a non-ASCII folder. Needs a release-notes line.
- P1: Autosave, recovery and undo are on by default (from Block A).
  - Autosave every 60 s with a recovery marker (`src/app/graph/PatchIO.cpp`, `src/app/AppState.cpp`), 200 undo steps, 2.5 ms per checkpoint on a 300-node patch; tests pass (`AUTOSAVETEST`, `AUTOSAVEMARKERTEST`, `UNDOPERFTEST`).
- P6: Infinite ships much less starting content than the DAWs, and none for its audio nodes.
  - What a first-run user finds on disk: Live 3,258 presets, 6,135 samples and loops, 350 clips, 25 projects; Logic 21,633 presets, 1,337 samples, 18 clips, 45 projects; Bitwig 2,781 presets, 90 clips. Infinite: 8 samples (one drum kit), no clips, 22 patches (templates and examples), 263 presets in code.
  - Those 263 presets sit in the visual and Field nodes (Field Pixel 40, Field Notes 33, Field Element 30, Formula 26, Field Synth 27, and so on). Analog, Wavetable, Oscillator, Reverb, Delay and the other audio nodes have none.
  - Evidence: `~/re-output/project-bench/library.md`, node counts from `src/nodes/`.

## 4. Comparison

| Pillar | Their feature | Infinite equivalent | Status | Outcome | Evidence |
|---|---|---|---|---|---|
| P8 | Project load time against size (all five) | `src/core/Patch.h` | lead | ignore: flat from 10 to 4000 nodes; GUI first-frame time waits on the sitting | `project_bench.py infinite` |
| P1 | Old projects still open (Live, Logic, Bitwig) | `src/core/Patch.h` | parity | ignore: 0 failures across 27 release tags, 102 of 109 ever-committed files, the 7 failures explained | `project_bench.py history --all` |
| P1 | Open, scriptable project format (Live: gzip XML) | `src/core/Patch.h` | lead | ignore: plain text, ahead of every app but Live | `project_bench.py formats` |
| P1 | A failed save leaves the old file whole (all five) | `src/app/graph/PatchIO.cpp` | parity | ignore: fixed in this block (fc683464), needs a release-notes line | `headless_smoke.sh` |
| P1 | Autosave and crash recovery (Live: recovery prompt; Logic, Bitwig: autosave) | `src/app/graph/PatchIO.cpp` | parity | ignore: 60 s autosave plus a recovery marker, tests pass | `AUTOSAVETEST` |
| P5 | Factory presets for built-in instruments and effects (Live 3,258; Logic 21,633; Bitwig 2,781) | `src/nodes/AnalogNode.cpp` | gap | quality-gap: the audio nodes ship no presets; the bar is a preset list of at least 8 on each of Analog, Wavetable and Oscillator and on Reverb, Delay, EQ and Drive | `project_bench.py library` |
| P6 | Starter samples, loops and MIDI clips (Live 6,135 + 350; Logic 1,337 + 18; Bitwig 90 clips) | `src/core/Patch.h` | gap | ignore: Infinite is a live instrument whose users bring their own material; revisit when onboarding shows an empty browser to be a drop-off | `project_bench.py library` |
| P1 | Templates and demo projects (Live 25, Logic 45) | `src/core/Patch.h` | parity | ignore: 22 shipped patches, the same order of size | `project_bench.py library` |

## 5. Measurements

Project scaling, Infinite (`~/re-output/project-bench/scaling.md`; median of 3, headless, process start included):

| Nodes | File KB (full) | Gzip KB | Load s | Load + write s |
|---|---|---|---|---|
| 10 | 0.8 | 0.3 | 0.790 | 0.135 |
| 100 | 7.4 | 1.0 | 0.762 | 0.780 |
| 1000 | 76.0 | 8.1 | 0.769 | 0.766 |
| 4000 | 313.5 | 32.5 | 0.755 | 0.785 |

Old patches opened by today's build:

| Source | Files | Load | Fail |
|---|---|---|---|
| Shipped in release tags v0.1 to v0.5.0 | 1 to 19 per tag | all | 0 |
| First version of every committed `.inf`, added 2026-08 | 1 | 1 | 0 |
| Added 2026-09 | 40 | 33 | 7 (6 negative fixtures, 1 never released) |
| Added 2026-10 | 68 | 68 | 0 |

Starting content on this machine (`~/re-output/project-bench/library.md`):

| Kind | Live | Logic | Bitwig | Infinite |
|---|---|---|---|---|
| Instrument and effect presets | 3,258 | 21,633 | 2,781 | 263 in code (none for audio nodes) |
| Samples and loops | 6,135 | 1,337 | 0 | 8 |
| Clips and MIDI | 350 | 18 | 90 | 0 |
| Projects, templates, demos | 25 | 45 | 0 | 22 |

Not measured:

| Item | Why | What it needs |
|---|---|---|
| GUI save and open time on a big project, in each app | the GUI canvas is not scripted; the DAWs expose no timing | the sitting in `PROTOCOL-projects.md` |
| Browser search time | same | same sitting |
| Crash recovery in Live, Logic and Bitwig | needs a forced quit and a reopen by hand | the Block A sitting, `dossiers/A.md` |

## 6. Outcomes

- Quests: none.
- Quality gaps:
  - Factory presets for the audio nodes. Start with the three synths and four effects named in the table row; each preset must be a real sound a player would pick, not a parameter sweep. The bar: each of those seven nodes opens a preset list of at least 8. The audio-node minimalism rule (`new-audio-node` #5) governs the DSP, not this: presets change no processing.
- Bug fixed with a regression check: Save truncated the file in place (fc683464, merged). Needs a release-notes line ("Fixed: Save no longer truncates the patch if the disk fills or the app quits mid-save; on Windows, patches and Field devices save and open in folders with non-ASCII names.").
- Ignored, with reason: project load time and old-file compatibility (Infinite leads or ties); starter samples, loops and clips (users bring their own; revisit on evidence); templates (parity).
- Owner sittings needed: one short sitting for GUI save and open time plus browser search time (`PROTOCOL-projects.md`).

## 7. Storage

- Written to ~/re-output: `project-bench/` (`scaling.md`, `history.md`, `history_all.md`, `formats.md`, `library.md`).
- Deleted: the generated N-node patches (written to a temp folder and removed by the tool) and `~/re-output/tmp` (`storage.py clean-tmp`).
