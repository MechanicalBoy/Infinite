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
| 1 | Audio engine accuracy | Summing, pan law, timing, PDC, resampling, noise floor | Live, Logic, Bitwig | 🟡 bounce kit built, needs bounces | — |
| 2 | Built-in instruments | Pitch, aliasing, velocity, envelope, voices, CPU | Live (Wavetable, Operator, Drift), Logic (Alchemy, ES2), Bitwig (Polymer, Phase-4) | 🟡 Infinite's own only | **cover others' built-ins** |
| 3 | Built-in effects | Gain, response, THD, tail, CPU | Live (Echo, Roar, Reverb), Logic (ChromaVerb, Compressor), Bitwig | 🟡 Infinite's own only | **cover others' built-ins** |
| 4 | Third-party plugins | Sound + CPU per plugin | FabFilter, Valhalla, Diva, Serum, Vital | ✅ in Infinite's host | — |
| 5 | Plugin hosting | Formats, scan time, load success rate, crash isolation, PDC, host CPU overhead | Live, Logic, Bitwig (sandboxing) | ✅ done 2026-10-12, dossier `dossiers/A.md` | **important: users report VST3 crashes / not loading** |
| 6 | Performance under load | Track and voice ceiling, multicore scaling, dropouts | Live, Logic, Bitwig | ❌ | **needed** |
| 7 | Real-time latency | Audio in→out round trip, buffer sizes, jitter | Live, Logic, Bitwig | ❌ | **important: makes it professional** |
| 8 | Startup and footprint | Launch time, idle CPU, memory, bundle size | all | ⏳ `app_bench` | — |
| 9 | Video and visual engine | FPS, frame-time spread, GPU memory, resolution ceiling | **TouchDesigner, Blender** (behaviour only) | ❌ | **use TD + Blender as the bar** |
| 10 | Export and render | Offline speed, formats/codecs, AV sync, quality | TouchDesigner, Blender, Final Cut, DAWs | ❌ (Infinite only) | **important: users need good export** |
| 11 | Modulation | Sources, destinations, per-voice, rate | Bitwig | 🟡 API docs only | — |
| 12 | Sequencing and arrangement | Clips, MIDI edit, automation, quantize | **Final Cut** (UI/UX map + match its timeline performance) | ❌ | light: Final Cut UX + perf |
| 13 | Sampling and audio editing | Time-stretch / pitch-shift quality, slicing, pitch detection | Live warp, Logic Flex, Bitwig | ❌ | **important** |
| 14 | Mixing and routing | Sends, sidechain, buses, channel limits | Live, Logic, Bitwig | ❌ | **important** |
| 15 | MIDI, hardware, sync | MPE, MIDI out, controller scripts, OSC, Link | Bitwig, Live | 🟡 API docs only | — |
| 16 | Scripting / extensibility | Public API size by domain | Bitwig, Live, TD, Logic | ✅ `capability_map` | — |
| 17 | UI structure | Menus, shortcuts, AX tree | all | 🟡 `ui_map` (Bitwig exposes nothing) | — |
| 18 | Workflow cost | Steps and time for common tasks | all | ❌ | **important: common tasks must be fast** |
| 19 | Visual design | Density, contrast, zoom/HiDPI, themes | all | ❌ | **important** |
| 20 | Projects and files | Save/load time, size, open format, old-version compat, autosave/recovery | all | ❌ | **important** |
| 21 | Stability | Crash recovery, plugin-crash handling, undo depth | all | ✅ done 2026-10-12 (DAW side: owner sitting below), dossier `dossiers/A.md` | **important** |
| 22 | Content and library | Presets, samples, templates, browser search speed | all | ❌ | **check against Infinite's existing library** |
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
- Next-session prompt for blocks A to F: `NEXT-SESSION.md`.
