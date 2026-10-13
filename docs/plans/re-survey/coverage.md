# re-survey coverage: every area of the software

The map of what we benchmark against competitors, what is done, and what the owner decided. Written 2026-10-12.
Rules, competitor registry and tooling live in `README.md`; this file owns the area list and the order.

## The method (owner's call, 2026-10-12)

One harness for every area, measured from outside:

```
stimulus files (WAV, MIDI, video, project template)
        │
        ▼
the app plays/renders/bounces them  ◄── app_bench watches CPU, memory, threads, dropouts
        │
        ▼
analyser (numbers out) ──► comparison table ──► dossier outcome
```

- Works for built-in devices that can't load outside their DAW (Live Wavetable, Logic Alchemy, Bitwig Polymer...).
- Grow the bounce kit (`tools/re-survey/bounce_kit.py`) into this harness instead of writing one tool per area:
  each area adds stimuli + an analyser, not a new rig.
- Setup the owner does by hand happens once per app, batched into one sitting (one template per DAW).

## Area map

✅ done · 🟡 partial · ⏳ running · ❌ not started · ⏸ parked by owner

| # | Area | What it covers | Reference apps | Status | Owner priority |
|---|---|---|---|---|---|
| 1 | Audio engine accuracy | Summing, pan law, timing, PDC, resampling, noise floor | Live, Logic, Bitwig | 🟡 Infinite side done 2026-10-12 (`--timeline` fixed); DAW bounce sitting pending, dossier `dossiers/C.md` | — |
| 2 | Built-in instruments | Pitch, aliasing, velocity, envelope, voices, CPU | Live (Wavetable, Operator, Drift), Logic (Alchemy, ES2), Bitwig (Polymer, Phase-4) | 🟡 Infinite side done 2026-10-12 (Field Synth release fixed); DAW bounce sitting pending (`builtins_kit.py`), dossier `dossiers/C.md` | **cover others' built-ins** |
| 3 | Built-in effects | Gain, response, THD, tail, CPU | Live (Echo, Roar, Reverb), Logic (ChromaVerb, Compressor), Bitwig | 🟡 Infinite side done 2026-10-12; DAW bounce sitting pending (`builtins_kit.py`), dossier `dossiers/C.md` | **cover others' built-ins** |
| 4 | Third-party plugins | Sound + CPU per plugin | FabFilter, Valhalla, Diva, Serum, Vital | ✅ in Infinite's host | — |
| 5 | Plugin hosting | Formats, scan time, load success rate, crash isolation, PDC, host CPU overhead | Live, Logic, Bitwig (sandboxing) | ✅ done 2026-10-12, dossier `dossiers/A.md` | **important: users report VST3 crashes / not loading** |
| 6 | Performance under load | Track and voice ceiling, multicore scaling, dropouts | Live, Logic, Bitwig | 🟡 Infinite side done 2026-10-12, DAW sitting pending (`PROTOCOL-load.md`), dossier `dossiers/B.md` | **needed** |
| 7 | Real-time latency | Audio in→out round trip, buffer sizes, jitter | Live, Logic, Bitwig | 🟡 tool ready and PDC fixed 2026-10-12; loopback sitting pending (`PROTOCOL-latency.md`), dossier `dossiers/B.md` | **important: makes it professional** |
| 8 | Startup and footprint | Launch time, idle CPU, memory, bundle size | all | ⏳ `app_bench` | — |
| 9 | Video and visual engine | FPS, frame-time spread, GPU memory, resolution ceiling | **TouchDesigner, Blender** (behaviour only) | 🟡 Infinite and Blender done 2026-10-13; TouchDesigner row waits on one Textport paste; GPU memory, 8K and a feedback scene not measured, dossier `dossiers/D.md` | **use TD + Blender as the bar** |
| 10 | Export and render | Offline speed, formats/codecs, AV sync, quality | TouchDesigner, Blender, Final Cut, DAWs | 🟡 Infinite and Blender done 2026-10-13 (speed, H264 quality, 10-min sync); TouchDesigner pending; Final Cut and DAW export not measured, dossier `dossiers/D.md` | **important: users need good export** |
| 11 | Modulation | Sources, destinations, per-voice, rate | Bitwig | 🟡 API docs only | — |
| 12 | Sequencing and arrangement | Clips, MIDI edit, automation, quantize | **Final Cut** (UI/UX map + match its timeline performance) | 🟡 Final Cut's command map done 2026-10-13 (menus only: its window is not exposed); timeline scrub/zoom speed not measured, dossier `dossiers/F.md` | light: Final Cut UX + perf |
| 13 | Sampling and audio editing | Time-stretch / pitch-shift quality, slicing, pitch detection | Live warp, Logic Flex, Bitwig | 🟡 Infinite side done 2026-10-12 (`stretch_kit.py`); DAW bounce sitting pending, dossier `dossiers/C.md` | **important** |
| 14 | Mixing and routing | Sends, sidechain, buses, channel limits | Live, Logic, Bitwig | ✅ done 2026-10-12, dossier `dossiers/B.md` | **important** |
| 15 | MIDI, hardware, sync | MPE, MIDI out, controller scripts, OSC, Link | Bitwig, Live | 🟡 API docs only | — |
| 16 | Scripting / extensibility | Public API size by domain | Bitwig, Live, TD, Logic | ✅ `capability_map` | — |
| 17 | UI structure | Menus, shortcuts, AX tree | all | 🟡 `ui_map` (Bitwig exposes nothing) | — |
| 18 | Workflow cost | Steps and time for common tasks | all | 🟡 ten tasks traced and timed by KLM 2026-10-13; DAW steps manual-derived until the timed sitting (`PROTOCOL-workflow.md`), dossier `dossiers/F.md` | **important: common tasks must be fast** |
| 19 | Visual design | Density, contrast, zoom/HiDPI, themes | all | 🟡 contrast measured and fixed in seven themes 2026-10-13; density and HiDPI not measured, dossier `dossiers/F.md` | **important** |
| 20 | Projects and files | Save/load time, size, open format, old-version compat, autosave/recovery | all | 🟡 headless scaling, old-file compatibility and formats done 2026-10-13; GUI save/open time pending (`PROTOCOL-projects.md`), dossier `dossiers/E.md` | **important** |
| 21 | Stability | Crash recovery, plugin-crash handling, undo depth | all | ✅ done 2026-10-12 (DAW side: owner sitting below), dossier `dossiers/A.md` | **important** |
| 22 | Content and library | Presets, samples, templates, browser search speed | all | 🟡 library counted per app 2026-10-13; browser search time pending (`PROTOCOL-projects.md`), dossier `dossiers/E.md` | **check against Infinite's existing library** |
| 24 | Accessibility | Screen-reader exposure | all | 🟡 seen in `ui_map` | — |
| 25 | Collaboration and cloud | Sharing, sync, co-editing | — | ⏸ | not important now |

## Order

Owner priorities: income > reach. Blocks run one at a time; each ends in a dossier table.
Out of scope (owner, 2026-10-12): web research on business, onboarding and distribution; measure, don't research.

| Block | Areas | How | Owner time |
|---|---|---|---|
| A | 5 plugin hosting, 21 stability | Infinite's own host vs DAW scan logs; load every installed VST3/AU headless, count failures and crashes; crash-a-plugin test | none |
| B | 6 load, 7 latency, 14 routing | Harness: N-track templates per DAW, app_bench under playback; loopback latency on the interface | one template per DAW |
| C | 2, 3 built-ins, 13 stretch, 1 engine | Harness: MIDI/audio stimuli → DAW bounces → `synth_probe` / sweep / stretch analysers | one bounce sitting per DAW |
| D | 9 video, 10 export | TouchDesigner + Blender scenes vs Infinite render; fps, frame times, export speed, codec quality, AV sync | none (TD Python, Blender CLI) |
| E | 20 projects, 22 library | Save/load timing, file formats, autosave; Infinite library vs competitors' presets/templates | none |
| F | 12 Final Cut, 18 workflow, 19 visual design | `ui_map` on Final Cut, task step counts, screenshot metrics (contrast, density) | short |

## Results so far

- Synth probe, effects sweeps, capability map, UI map: see section 8 of `README.md` and `~/re-output/`.
- App bench 2026-10-12 (idle): Logic 2.8 % CPU / 224 MB; Live 41 % / 819 MB; Infinite 12.7 % / 220–227 MB,
  window in 4.4 s cold, 0.7 s warm; Bitwig 3.7 % / 1268 MB (window detection missed it: Java child process).
- Startup/idle, final: TouchDesigner window 10.9 s cold / 3.0 s warm, 49.7 % idle CPU, 1400 MB. Bitwig rerun pending
  (window detection fixed: its window belongs to the `--launch` child process).
- Host audit 2026-10-12 (`host_audit.py`, 84 AU + 83 VST3): 163 clean. Crash in both formats: RC-20 Retro Color,
  ShaperBox 3 (auval fails both too; Live's scan DB marks the same two failed). AU-only silence: Drumazon 2 (only
  AU/VST3 asymmetry, host-bug candidate). Default-patch quirks: Phase Plant silent, Twin 2 DC, Vital clips.
  AU load median 0.19 s; VST3 0.67 s, mostly a full rescan: headless never seeds the VST3 path cache from the index.
- Formats: Infinite AU + VST3; Live AU + VST3 + VST2; Bitwig VST3 + VST2 + CLAP (+ Intel plugin host); Logic AU only.
  Installed here: 42 VST2, 23 CLAP Infinite cannot see.
- Isolation: Bitwig runs plugins in a separate host process; Live in-process (like Infinite); Logic uses macOS's AU
  hosting service, which any host can request (`loadOutOfProcess` at AU instantiation).
- Transport fix 2026-10-12 (Block A): plugins never saw Infinite's clock (VST3 hard-coded "playing, 120 BPM" on all
  three platforms since a2a4703b, shipped; AU got none). Now fed per block from Transport; the AU path is verified
  by INFINITE_PLUGINSCANTEST (tempo, beat, bar, meter, play, cycle read back) and PLUGINNODETEST passes. Drumazon 2
  now behaves the same as AU and VST3. Windows/Linux: same shared mapping, checked by reading the code only. Needs a release-notes line.
- Block A done 2026-10-12 (`dossiers/A.md`):
  - Fixed and merged:
    - The plugin clock, verified: Valhalla Delay 1/16 is 166.8 ms at 90 BPM and 125.1 ms at 120 BPM, with AU and VST3 within 0.1 ms.
    - A per-folder plugin scan no longer erases the real index (`MergeScan`, `LIBREFRESHTEST`). VST3 load 0.23 s vs AU 0.19 s.
  - `host_audit`: crash reports are matched by pid, and there is a new Signature column.
    - ShaperBox 3 has a broken code signature.
    - RC-20 is signed by someone other than the vendor.
    - Neither is a host bug.
  - Saturn 2: the VST3 metadata default is wrong (0); the real start value is 0.2 in both formats. Infinite is unaffected.
  - AU out of process (`au_oop`): 2–4.5× CPU per plugin and +0.3 s load, latency unchanged. Decision: run a plugin out of process only after it has crashed once.
  - VST2 and CLAP: ignored, since every one installed has an AU or VST3 twin.
  - Self-tests pass: autosave every 60 s plus recovery marker, 200 undo steps, `BuildPatchData` 2.5 ms on 300 nodes.
  - Owner sitting (one per DAW, about 5 min each):
    1. Make 3 edits.
    2. Undo until it stops, and count the steps.
    3. Force-quit with `kill -9`.
    4. Reopen, and note whether it offers recovery and how much work came back.
- Block B done 2026-10-12 for Infinite's side (`dossiers/B.md`):
  - Fixed and merged, each with a regression check: PDC ignored plugin latency changes (`PLUGINNODETEST`); Mixer slot names past 8 rejected (fixture g14); one note output fed only 8 synths (cap 64, `W_NOTE_FANOUT`); headless runs aborted by head tracking on macOS.
  - Load, one thread: Wavetable + Reverb 14.5 / 69.9 / 169.5 / 436.1 % of a core at 8 / 32 / 64 / 128 tracks; Analog + EQ 41.8 / 183.7 / 383.0 / 883.3 %. Live ceiling about 32 light or 13 heavy tracks. Perf target: multicore graph.
  - Routing: Mixer sum and equal-power pan exact to 0.01 dB; fan-out sends leave the dry path untouched; Dynamics sidechain ducks 19 dB. Gap: the Plugin node has no sidechain input.
  - Owner sittings: load template per DAW (`PROTOCOL-load.md`), latency loopback (`PROTOCOL-latency.md`).
- Next-session prompt for blocks A to F: `NEXT-SESSION.md`.
- Block C 2026-10-12 (`dossiers/C.md`): Field Synth cut every preset 30 ms after note-off (shipped since v0.3.0); fixed,
  with four dead preset dampers. Headless `--timeline` added for arrangement renders. Stretch keeps pitch exactly but
  flams drums (10–14 extra onsets). Default oscillators are clean to C8. Export does not shift back an effect's
  latency (Drive 1.5 ms). DAW bounce sittings pending.
- Block D 2026-10-13 (`dossiers/D.md`): Infinite renders 44.5–263 fps against Blender EEVEE's 0.2–1.6 on matched scenes
  (about 70–300×; a real-time engine against an offline renderer). H264 at each app's default bitrate scores 35.5–51.8 dB
  in Infinite and 28.8–46.1 dB in Blender against their own lossless frames. A 10-minute export keeps sound and picture
  within 0.04 ms in both, no drift. Fixed and merged: macOS Audio File export hung on long files and crashed on 88.2 kHz+
  (01059f67, shipped since v0.3.3). Found, not fixed: `--validate` and `--explain` accept a Field kernel that calls an
  unknown function and `--frame` blames the cable (quality-gap). TouchDesigner row, GPU memory and a feedback scene pending.
- Block E 2026-10-13 (`dossiers/E.md`): load time is flat at 0.76 s from 10 to 4000 nodes (headless); every `.inf` shipped in
  27 release tags still opens, and 102 of 109 ever-committed files load (the 7 failures are 6 negative fixtures and 1 never
  released). `.inf` is plain text; Live is the only other open format. Fixed and merged: Save truncated the file in place
  since v0.1 (fc683464, now write-then-rename). Gap: no factory presets for the audio nodes (263 in-code presets, all visual
  and Field) and 8 samples against thousands. GUI save/open and browser search timing pending.
- Block F 2026-10-13 (`dossiers/F.md`): first sound takes 12 steps in Infinite against 3–4 in the DAWs (quest); Infinite is
  fastest at automate, modulate, tempo, save and export. Final Cut's 226 shortcuts map to Infinite's cutting commands; gaps
  are ripple/magnetic edit, keyboard trim, zoom-to-fit and retime. Fixed and merged: hint and typed text on the field well
  was under 4.5:1 in 7 of 10 themes (e90f84fe).

## App × dimension grid (owner, 2026-10-13)

Every app is judged on every dimension it has, not one app per block. ✅ measured · ⏳ protocol pending (owner sitting or
paste) · ❌ not measured · — not applicable. Infinite is the measured subject in the last column.

| Dimension | Live | Logic | Bitwig | TouchDesigner | Blender | Final Cut | Infinite |
|---|---|---|---|---|---|---|---|
| Audio engine (summing, pan, PDC, latency) | ⏳ bounce, loopback | ⏳ bounce, loopback | ⏳ bounce, loopback | ❌ | — | — | ✅ |
| Visual / 3D engine (fps, frame times, ceiling) | — | — | — | ⏳ Textport paste | ✅ render speed; ❌ viewport, geometry nodes, simulation | ❌ | ✅ (GPU memory ❌) |
| AV integration (export sync, audio→picture latency, beat-to-frame lock) | ❌ | ❌ | ❌ | ⏳ export sync; ❌ live latency | ✅ export sync | ❌ | ✅ export sync; ❌ live latency |
| Built-in modules (synths, effects, stretch) | ⏳ bounce | ⏳ bounce | ⏳ bounce | ❌ | ❌ | ❌ | ✅ |
| UX: workflow cost and design | ⏳ KLM from manual; ✅ command map | ⏳ KLM; ✅ command map | ⏳ KLM; ❌ command map (exposes nothing) | ✅ command map | ❌ | ✅ command map | ✅ |
| Efficiency (startup, idle, load ceiling) | ✅ idle; ⏳ load | ✅ idle; ⏳ load | ✅ idle (window time ⏳); ⏳ load | ✅ idle | ❌ | ❌ | ✅ |
| Robustness (crash, kill mid-save, plugin crash, long run) | ⏳ recovery sitting | ⏳ recovery sitting | ⏳ recovery sitting | ❌ | ❌ | ❌ | 🟡 host audit, autosave, undo; ❌ stress kit |
| Export (speed, codecs, quality) | ❌ | ❌ | ❌ | ⏳ | ✅ | ❌ | ✅ |
| Projects and library | ✅ formats, library; ⏳ GUI timing | ✅ formats, library; ⏳ GUI timing | ✅ formats, library; ⏳ GUI timing | ✅ formats | ✅ formats | ❌ | ✅ |
| Extensibility (public API by domain) | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ |

Biggest holes, in the owner's order:

| Hole | What fills it |
|---|---|
| Robustness for every app | a stress kit: a 4000-module project, device unplug, kill mid-save then reopen, a crashing plugin, a long run; run through `app_bench` |
| Blender beyond render | geometry nodes, simulation and viewport fps from its public Python API and CLI |
| TouchDesigner as the bar for audio-reactive visuals and live frame timing | the Textport paste for render speed, then an audio-reactive scene with frame times from its own Python |
| AV integration bench | audio→picture latency and beat-to-frame lock, measured on a looped click-and-flash patch in each app that can play one |

Tools are reused across apps wherever possible; each hole above adds a stimulus and an analyser to the same harness.
