# B Load, latency and routing (Live, Logic, Bitwig): dossier

Status: done 2026-10-12 for Infinite's side; the three DAW sittings are pending (protocols below). Lint: `python3 tools/re-survey/diff.py lint docs/plans/re-survey/dossiers/B.md`

## 1. What it is

- Block B of `coverage.md`: areas 6 (performance under load), 7 (real-time latency) and 14 (mixing and routing).
- Reference apps: Ableton Live 12 Suite, Logic Pro and Bitwig Studio, all installed. Licence: all three are proprietary, so only behaviour and their manuals were used.
- Infinite was measured headless through its own host. The DAW side needs a person at the keyboard (a template per DAW, a BlackHole loopback sitting); exact steps are in `PROTOCOL-load.md` and `PROTOCOL-latency.md`.

## 2. Method

- Load: `python3 tools/re-survey/load_bench.py run --track "node:Wavetable+node:Reverb" --tracks 8,32,64,128` and the same for `node:Analog+node:EQ`.
  - Each track is a synth plus an effect playing held 4-note chords at 120 BPM, 48 kHz, offline.
  - Load is audio-thread time per second of audio, from the slope between a 4 s and a 24 s render, so setup cost cancels.
- Latency: `python3 tools/re-survey/latency_probe.py --self-test` (tool ready; the round trip needs the sitting in `PROTOCOL-latency.md`).
- PDC: AUPeakLimiter (`au:aufx:lmtr:appl`), whose latency equals its Attack Time, in `INFINITE_PLUGINNODETEST`; Pro-Q 4 linear phase and Pro-L 2 as AU and VST3 alongside a dry path.
- Routing: headless renders of Mixer, fan-out send and Dynamics sidechain patches, read back as WAV (numbers in section 5).
- Not done: no DAW source read, no decompiled code kept, no binaries or dumps committed.

## 3. Pillar map

- P5: Plugin delay compensation missed latency changes after load.
  - The audio topology snapshots each plugin's latency once. VST3 `restartComponent(kLatencyChanged)` was ignored and AU `latency` was never re-read, so a plugin whose latency moves with a parameter (AUPeakLimiter Attack, AUNewTimePitch, linear-phase EQ modes) went out of alignment with every other path until the graph was rebuilt.
  - Shipped since ba6576e8 (2026-08-21, in every release from v0.2-preview on): needs a release-notes line.
  - Fixed and merged (6d8376ef): VST3 hosts on all three platforms note the flag and re-read `getLatencySamples()`; AU re-reads `latency`; the headless loop now polls like the UI frame pump.
  - Evidence: `INFINITE_PLUGINNODETEST` latency case, 96 → 1440 samples after Attack 2 → 30 ms; with the fix removed it stays 96 (fails). Windows and Linux read from source, not built.
- P8: Infinite renders its audio graph on one thread.
  - Wavetable + Reverb costs 18 ms of audio-thread time per track per second at 8 tracks and 34 ms at 128: the cost per track grows with the track count. One core is full at about 42 tracks, and a live device (70 % of a core) holds about 32.
  - Analog + EQ costs 52–69 ms per track per second: a live device holds about 13 tracks.
  - DAWs spread tracks across cores; the DAW sitting gives their ceiling for the same chords.
  - Evidence: `~/re-output/load-bench/wt-reverb.md`, `analog-eq.md`.
- P5: Mixer summing and pan law are exact.
  - 1, 4, 8, 12 identical inputs sum to +0.00, +12.04, +18.06, +21.58 dB, matching 20·log10(N) to 0.01 dB.
  - Pan is equal power scaled by √2: centre is unity, hard pan gives +3.01 dB on one side and silence on the other, −0.5 gives +2.32 / −5.33 dB.
- P5: Sends work by fan-out.
  - One source cabled to a Mixer input and to a Reverb whose return is muted leaves the dry path untouched (−1.939 dB, exactly the Audio File's 0.8 volume).
  - The Mixer is the only summing node; there are no named buses, only Mixers feeding Mixers.
- P5: Dynamics sidechain works.
  - Steady sine through Dynamics (threshold −30, ratio 10) with a kick on the sidechain: external on ducks by 19.0 dB peak to trough; external off, or nothing wired, the level is flat.
  - The parameter sweep cannot see this switch (its rig feeds the same tone to both pins), so this check is the only test of it.
- P5: Plugins get no sidechain.
  - The Plugin node has one audio input (`in`); VST3 aux buses are left inactive. A FabFilter Pro-C or Pro-G cannot be keyed from another track, which all three DAWs offer.
- P5: The patch checker rejected Mixer slot names past the default 8.
  - A Mixer saved with `channels 12` accepted `in_9`..`in_12` by number but not by name (`E_BAD_REF`), because names were matched against the type's default schema only.
  - Fixed and merged (1d08bcb0); fixture `tests/headless/topology/g14_mixer12_by_name.inf` gives `E_BAD_REF 'in_9'` on the old binary and validates clean now. Headless authoring only: saved patches use numbers.
- P5: A Keyboard fed only 8 synths; the 9th and later stayed silent.
  - `NoteEventQueue::kMaxConsumers` was 8. Each note consumer gets a read cursor; the 9th got cursor −1 with no warning (`AudioTopology.cpp`), so a Keyboard cabled to 12 synths played 8.
  - Shipped since 457a2b9d (2026-08-17, every release from v0.2-preview on): needs a release-notes line. Portable C++, so all three platforms. Nothing bad is saved; reopening a patch on the fixed build plays every synth.
  - Fixed and merged (0c4e50d8): the cap is 64 (cursors are walked only up to the registered count, so it costs memory, not time), and `--validate` raises `W_NOTE_FANOUT` past it. Smoke checks "the 12th synth on one Keyboard gets notes" and "65 consumers raise W_NOTE_FANOUT" both fail on the old binary.
  - It also made the first load numbers above 8 tracks wrong (only 8 synths sounded); section 5 is the rerun.
- P8: Headless runs could abort on macOS when a Spatial Mixer was in head-track mode.
  - CoreMotion's headphone-motion request is checked against the process that started it. From a terminal that is the terminal, so the request aborted the run (SIGABRT). `--describe` of every type hit it, so describe-all never ran and the patch-authoring skill went stale.
  - Shipped in v0.5.0 (23a4e507); macOS only (Windows and Linux use the stub).
  - Fixed and merged (0c4e50d8): head tracking is off in headless runs (`HeadTracker::Disable`, all three sides). Smoke's describe-all checks pass again; the skill is regenerated.
- P5: Audio Out clips a sum over full scale in a 24-bit render (12 sines at 0.2 peak read +16 dB instead of +21.6 dB). Expected for a fixed-point file.

## 4. Comparison

| Pillar | Their feature | Infinite equivalent | Status | Outcome | Evidence |
|---|---|---|---|---|---|
| P5 | Delay compensation follows a plugin's latency change live (all three) | `src/app/graph/AudioTopology.cpp` | parity | ignore: fixed in this block, needs a release-notes line | `INFINITE_PLUGINNODETEST` |
| P8 | Multicore audio graph: tracks spread over cores (all three) | `src/app/graph/AudioTopology.cpp` | gap | perf-target: one-thread ceiling about 32 light or 13 heavy tracks; parallelise independent chains | `load_bench.py` |
| P5 | Summing and constant-power pan (all three) | `src/nodes/AudioNodes.h` | parity | ignore: exact to 0.01 dB; 12 inputs per Mixer, chain Mixers for more | section 5 |
| P5 | Sends and return tracks (Live returns, Logic aux, Bitwig FX tracks) | `src/nodes/AudioNodes.h` | parity | ignore: fan-out cables are sends, the dry path is untouched | section 5 |
| P5 | Built-in compressor sidechain (all three) | `src/audio/dsp/DynamicsKernel.cpp` | parity | ignore: 19 dB ducking measured | section 5 |
| P5 | Plugin sidechain input (all three) | `src/nodes/AudioPluginNode.cpp` | gap | quality-gap: one audio input, VST3 aux bus never activated | section 3 |
| P8 | Round-trip latency at 64/128/256 frames | `src/platform/Platform.mm` | gap | ignore: unmeasured until the BlackHole sitting; tool ready | `PROTOCOL-latency.md` |

## 5. Measurements

Load, % of one core, `load_bench.py` (48 kHz, offline, slope of a 4 s and a 24 s render):

| Tracks | Wavetable + Reverb | Analog + EQ |
|---|---|---|
| 8 | 14.5 | 41.8 |
| 32 | 69.9 | 183.7 |
| 64 | 169.5 | 383.0 |
| 128 | 436.1 | 883.3 |

- Ceiling at 70 % of a core (interpolated between rows): Wavetable + Reverb about 32 tracks; Analog + EQ about 13.
- Per-track cost rises with the track count (Wavetable 18 → 34 ms, Analog 52 → 69 ms per track per second), so doubling tracks more than doubles load.
- Runs that overlapped another session's build were discarded (one read 794 %), as were runs before the fan-out fix.
- `load_bench.py` first estimated the ceiling from the last row's per-track cost, which undercounts when cost grows; it now interpolates (self-test case added).

Routing, headless renders at 48 kHz, 1 kHz sine, levels in dB:

| Check | Result |
|---|---|
| Mixer sum, 1/4/8/12 inputs | +0.00 / +12.04 / +18.06 / +21.58 (want 20·log10 N) |
| Pan −1 / −0.5 / 0 (L, R, relative to centre; positive mirrors) | +3.01, −∞ / +2.32, −5.33 / 0, 0 |
| Fan-out send, return muted | dry unchanged to 0.001 dB |
| Dynamics sidechain, kick keyed | 19.0 dB ducking; 0.0 dB with external off |
| PDC, AUPeakLimiter Attack 2 → 30 ms | latency 96 → 1440 samples picked up |

Latency: none yet (tool ready, sitting pending).

## 6. Outcomes

- Quests: none. Four Infinite bugs found, all fixed and merged with regression checks:
  - latency changes ignored by PDC: `INFINITE_PLUGINNODETEST`;
  - Mixer slot names past 8 rejected: topology fixture g14;
  - a note source fed only 8 synths: smoke fan-out checks;
  - headless runs aborted by head tracking on macOS: smoke describe-all checks.
- Release notes need lines for PDC, the note fan-out and head tracking (all shipped).
- Perf targets: multicore audio graph. Independent synth-to-effect chains that meet only at a Mixer can render on worker threads; the bar is the DAW ceiling from the load sitting. Until then, about 32 light or 13 heavy tracks per machine.
- Quality gaps: plugin sidechain. Add a `sidechain` audio slot to the Plugin node and activate the plugin's first aux input bus (VST3 `activateBus(kAudio, kInput, 1)`, AU input element 1) when one is cabled. Three platforms: VST3 hosts on all three, AU on macOS only.
- Ignored, with reason:
  - named buses: Mixers feeding Mixers already do it, and a second routing model would break P2's "one routing model";
  - 24-bit clipping over full scale: expected for a fixed-point file;
  - round-trip latency: waits on the sitting, nothing to decide yet.
- Owner sittings needed: the load template per DAW (`PROTOCOL-load.md`) and the latency loopback (`PROTOCOL-latency.md`).

## 7. Storage

- Written to ~/re-output: `load-bench/` (results tables and `chords-30s.mid`).
- Deleted: scratch WAVs and patches from the routing checks.
