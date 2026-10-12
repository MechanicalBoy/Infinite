# A Plugin hosting and stability (Live, Logic, Bitwig): dossier

Status: done 2026-10-12. Lint: `python3 tools/re-survey/diff.py lint docs/plans/re-survey/dossiers/A.md`

## 1. What it is

- Block A of `coverage.md`: areas 5 (plugin hosting) and 21 (stability).
- Compared against Ableton Live 12, Logic Pro and Bitwig Studio, all installed. Every installed AU and VST3 on this Mac was loaded in Infinite's own host.
- Licence status: all three DAWs are proprietary, so only their behaviour and their docs were used. The CLAP SDK is MIT (permissive). Steinberg's VST2 SDK is no longer licensed to new hosts.

## 2. Method

- `python3 tools/re-survey/host_audit.py run`: loads every AU and VST3 headless, one process each, and reads each crash report by pid. Also runs `codesign --verify`, `auval`, and pairs AU and VST3 twins.
- `python3 tools/re-survey/plugin_probe.py run "Saturn 2" "vst3 Saturn 2" --sweep "Band 1 Drive=0,0.2,0.5"`: tells the real default apart from the reported one.
- Transport:
  - a Valhalla Delay echo-spacing render at 90 and 120 BPM, with the impulse at 3 s and Wow, Flutter and ModDepth at 0;
  - Drumazon 2 run through `host_audit.py --filter Drumazon`.
- `python3 tools/re-survey/au_oop.py run AUDelay ValhallaDelay "Pro-Q 4" "Pro-L 2" --frames 64,128,256`: uses Apple's public `AUAudioUnit` API with and without `.loadOutOfProcess`.
- Self-tests:
  - `INFINITE_LIBREFRESHTEST`, `AUTOSAVETEST`, `AUTOSAVEMARKERTEST`, `UNDOPERFTEST`, `UNDOTEST`, `PLUGINNODETEST`, `PLUGINSCANTEST`;
  - plugin folders counted with `find` under `/Library/Audio/Plug-Ins`.
- Not done:
  - no DAW source was read and no decompiled code kept;
  - no binaries or dumps were committed;
  - crash reports were read only for the plugin's identity and its exception.

## 3. Pillar map

- P5: Plugins never saw Infinite's clock.
  - VST3 got a hard-coded "playing, 120 BPM" clock on all three platforms (shipped). AU got no clock at all.
  - Fixed and verified:
    - Valhalla Delay synced to a 1/16 note gives 166.8 ms at 90 BPM and 125.1 ms at 120 BPM, and the triplet setting gives 111.2 ms and 83.5 ms. AU and VST3 agree within 0.1 ms.
    - Drumazon 2 now behaves the same in both formats.
  - Evidence: `INFINITE_PLUGINSCANTEST`.
- P5: The headless VST3 path cache was empty because a self-test erased the real plugin index.
  - `StartScan(folder)` replaced the whole index with one folder's results and saved it to the user's settings. `LIBREFRESHTEST` scans a temp folder.
  - Fixed: a per-folder scan now merges into the index (`MergeScan`).
  - A VST3 load takes 0.23 s with the index seeded. A miss rescans all 83 bundles, taking 0.8–2.2 s. AU takes 0.19 s.
  - Evidence: `INFINITE_LIBREFRESHTEST`, `INFINITE_VST3TRACE=1`.
- P5: Both crashes in the audit are modified binaries. Neither is a host bug.
  - ShaperBox 3 (AU and VST3): the kernel kills it with `SIGKILL (Code Signature Invalid)`. `codesign` reports "code or signature have been modified". No host can load it.
  - RC-20 Retro Color (both formats): segfaults in its own code during instantiation, on the main thread. Its signature is valid, but the signer is not the vendor.
  - `host_audit` now prints a Signature column and blames a crash report only by pid. Before this, it had blamed RC-20's crash on ShaperBox.
  - Evidence: `~/re-output/host-audit/`.
- P5: Saturn 2's VST3 metadata reports Drive default 0, while the AU reports 0.2. The AU is right.
  - Both formats start at 0.2: at default, THD is -40.7 dB in both, the same as setting Drive to 0.2 explicitly. At 0 it is -47.0 dB.
  - Infinite passes `defaultNormalizedValue` through unchanged, and it maps a knob from the live value. Saturn's wrong metadata never reaches the user.
  - Evidence: the `plugin_probe` sweep above, plus `src/nodes/AudioPluginNode.cpp` (map slot).
- P5: Running an AU out of process is affordable for a few plugins, not for every plugin. Measured with `au_oop`; table in section 5.
- P5: Formats.
  - Infinite: AU + VST3. Live: AU + VST3 + VST2. Bitwig: VST3 + VST2 + CLAP. Logic: AU only.
  - On this Mac every one of the 83 VST2 bundles and 23 CLAP bundles has an AU or VST3 twin. The only VST2-only items are FabFilter's mono and sidechain layout variants.
- P1: Stability.
  - Autosave is on by default every 60 s, with a session marker for recovery (`src/app/AppState.cpp`, `src/app/graph/PatchIO.cpp`).
  - Undo keeps up to 200 full snapshots (`src/app/AppShared.h`). A checkpoint on 300 nodes takes 2.5 ms; each one also asks every plugin for its state.
  - A plugin crash during render kills the app (Tier 3). Recovery loses up to 60 s of work and the undo history.

## 4. Comparison

| Pillar | Their feature | Infinite equivalent | Status | Outcome | Evidence |
|---|---|---|---|---|---|
| P5 | Host clock to plugins: tempo, position, play state (all three) | `src/platform/PluginTransportVST3.h` | parity | ignore: fixed in this block, needs a release-notes line | Valhalla Delay echo spacing at 90 and 120 BPM |
| P5 | Fast plugin load from a scan cache (all three) | `src/audio/PluginScanner.cpp` | parity | ignore: fixed in this block (`MergeScan`), VST3 0.23 s vs AU 0.19 s | `INFINITE_LIBREFRESHTEST` |
| P5 | Crash isolation: Bitwig's separate plugin host process; Logic's AU hosting service | `src/platform/Platform.mm` | gap | quality-gap: crash-only fallback (section 6); full sandboxing costs 2–4.5× CPU per plugin | `au_oop` table |
| P5 | Out-of-process scanning (all three) | `src/platform/PluginVST3.mm` | parity | ignore: already ships (`--vst3-scan-bundle`) | `host_audit` VST3 scan column |
| P5 | VST2 hosting (Live, Bitwig) | none | gap | ignore: SDK closed to new hosts; 0 VST2-only plugins here apart from mono and sidechain layouts | plugin folder count |
| P5 | CLAP hosting (Bitwig) | none | gap | ignore: every CLAP here has a twin; revisit when per-note modulation is a feature target | plugin folder count |
| P1 | Autosave and crash recovery (Live: recovery prompt; Logic: autosave; Bitwig: autosave) | `src/app/graph/PatchIO.cpp` | parity | ignore: 60 s autosave plus a recovery marker, tests pass | `AUTOSAVETEST`, `AUTOSAVEMARKERTEST` |
| P1 | Undo depth and speed | `src/app/AppShared.h` | parity | perf-target: checkpoint cost with many plugins loaded is unmeasured (`getState` runs on every edit) | `UNDOPERFTEST` |
| P1 | Survive a plugin crash mid-render (Bitwig: yes; Logic: AU service only; Live: no) | `src/nodes/AudioPluginNode.cpp` | gap | quality-gap: same as crash isolation; on the next launch the plugin loads out of process | plugin-host-hardening Tier 3 |

## 5. Measurements

AU in process vs out of process. `au_oop.py`, best of 3 runs by p99, at 48 kHz on a -12 dBFS 1 kHz sine. The machine was under build load, so overrun counts are left out as unreliable. Full table: `~/re-output/au-oop/table.md`.

| Measure | In process → out of process |
|---|---|
| Median render call | 2–4× slower (+10 to +160 µs per block) |
| CPU per plugin | +1.0 to +3.4 % of a core (2–4.5×), e.g. Pro-L 2 2.4 → 5.6 % |
| Instantiate | 0.02–0.06 s → 0.27–0.36 s |
| Reported latency | unchanged |

Other numbers:
- Plugin load, headless: AU median 0.19 s. VST3 0.23 s with the index seeded, 0.8–2.2 s on a miss (it rescans all bundles).
- Transport: echo spacing is within 0.1 ms of the musical value at both tempos, in both formats.
- Undo (`UNDOPERFTEST`, 249 nodes):

  | Action | Time |
  |---|---|
  | `BuildPatchData` on 300 nodes | 2.47 ms (ceiling 50 ms) |
  | click | 2.5 ms |
  | delete | 3.3 ms |
  | group delete of 50 | 27.8 ms |
  | undo | 6.7 ms |
  | redo | 4.5 ms |

- Self-tests, macOS:

  | Test | Result |
  |---|---|
  | `AUTOSAVETEST` | OK, 128 s |
  | `AUTOSAVEMARKERTEST` | OK |
  | `UNDOPERFTEST` | OK |
  | `UNDOTEST` | OK |
  | `PLUGINNODETEST` | OK (300 re-prepares, 1808 blocks) |
  | `LIBREFRESHTEST` | OK |

## 6. Outcomes

- Quests: none. The two Infinite bugs found are fixed and merged with regression checks:
  - plugin clock: `PLUGINSCANTEST`;
  - per-folder scan erasing the index: `LIBREFRESHTEST`.
- Perf targets: an undo checkpoint with 10+ plugins loaded. Measure `BuildPatchData` with real plugin states, aiming for under 50 ms like the 300-node bound.
- Quality gaps, with the decision settled (crash-only fallback, not out of process for everyone):
  1. Around every call into a plugin (render, state, editor), a thread-local records which plugin is running.
  2. A fatal-signal handler writes that plugin's id to a marker file with `write()` (async-signal-safe), then re-raises so the crash report still forms.
  3. On the next launch, after autosave recovery, the marked plugin is flagged "isolate".
     - AU: instantiate with `kAudioComponentInstantiation_LoadOutOfProcess`. This costs 2–4.5× its CPU and 0.3 s more load, for that one plugin only.
     - VST3: there is no OS service, so offer its AU twin or refuse the load with a clear message. Infinite's own child host is a bigger project, worth doing only when VST3-only crashes are reported.
  4. A user can clear the flag in the plugin's menu.
  - Three platforms: the marker and flag are portable code. The signal handler sits behind `Platform::` with POSIX on macOS and Linux and an SEH filter on Windows. The AU path is macOS only.
- Ignored, with reason:
  - VST2: the SDK is closed to new hosts, and no plugin here exists only as VST2.
  - CLAP: no plugin here exists only as CLAP. CLAP's real draw is per-note modulation, which fits P2; revisit it there. The MIT SDK keeps it clean-room safe.
  - ShaperBox and RC-20: modified binaries, so not host bugs.
  - Saturn 2's Drive metadata: the plugin's own metadata is wrong, and Infinite never shows it.
- Owner sitting needed for the behaviour comparison: Live, Logic and Bitwig undo depth, and what each shows after a forced quit. Instructions are in `coverage.md` under Block A.

## 7. Storage

- Written to ~/re-output: `host-audit/` (156 KB), `au-oop/` (20 KB), `bin/au_oop` (the compiled tool).
- Deleted: the scratch WAVs and the fake-HOME index used for the seeding test.
