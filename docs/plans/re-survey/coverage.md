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
| 5 | Plugin hosting | Formats, scan time, load success rate, crash isolation, PDC, host CPU overhead | Live, Logic, Bitwig (sandboxing) | ❌ | **important: users report VST3 crashes / not loading** |
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
| 21 | Stability | Crash recovery, plugin-crash handling, undo depth | all | ❌ | **important** |
| 22 | Content and library | Presets, samples, templates, browser search speed | all | ❌ | **check against Infinite's existing library** |
| 23 | Learning and onboarding | First run, help, tutorials | all | ❌ | — |
| 24 | Accessibility | Screen-reader exposure | all | 🟡 seen in `ui_map` | — |
| 25 | Collaboration and cloud | Sharing, sync, co-editing | — | ⏸ | not important now |
| 26 | Platforms and distribution | OS support, installer, updates, licensing | all | 🟡 bundle size only | — |
| 27 | Business | Price, tiers, trial, upgrade path, community | all | ❌ | — |

## Order

Owner priorities: income > reach. Blocks run one at a time; each ends in a dossier table.

| Block | Areas | How | Owner time |
|---|---|---|---|
| A | 5 plugin hosting, 21 stability | Infinite's own host vs DAW scan logs; load every installed VST3/AU headless, count failures and crashes; crash-a-plugin test | none |
| B | 6 load, 7 latency, 14 routing | Harness: N-track templates per DAW, app_bench under playback; loopback latency on the interface | one template per DAW |
| C | 2, 3 built-ins, 13 stretch, 1 engine | Harness: MIDI/audio stimuli → DAW bounces → `synth_probe` / sweep / stretch analysers | one bounce sitting per DAW |
| D | 9 video, 10 export | TouchDesigner + Blender scenes vs Infinite render; fps, frame times, export speed, codec quality, AV sync | none (TD Python, Blender CLI) |
| E | 20 projects, 22 library | Save/load timing, file formats, autosave; Infinite library vs competitors' presets/templates | none |
| F | 12 Final Cut, 18 workflow, 19 visual design | `ui_map` on Final Cut, task step counts, screenshot metrics (contrast, density) | short |
| G | 23, 26, 27 | Public pages and docs | none |

## Results so far

- Synth probe, effects sweeps, capability map, UI map: see section 8 of `README.md` and `~/re-output/`.
- App bench 2026-10-12 (idle): Logic 2.8 % CPU / 224 MB; Live 41 % / 819 MB; Infinite 12.7 % / 220–227 MB,
  window in 4.4 s cold, 0.7 s warm; Bitwig 3.7 % / 1268 MB (window detection missed it: Java child process).
