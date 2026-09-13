# Arrangement Timeline — Overhaul (bugs, architecture, features)

Paste this whole file into a fresh Claude Code session on Infinite.

---

You are overhauling Infinite's **Arrangement Timeline** (C++/ImGui/OpenGL node
compositor). Repo root: **`/Users/namansoni/infinte`** (that spelling is correct).
The spec is `docs/plans/arrangement/README.md`. This prompt **replaces its
phases 3, 4, 5, 7 and 8 as they were built**, and adds features the owner has
asked for. Every design decision below is already made. Don't re-open them
unless the code proves one impossible. If that happens, stop and report.

Line numbers in this file were captured on the WP0 baseline
(`src/main.cpp` = 74,220 lines; it is now ~75k and **every number has drifted**).
Treat them as hints only. Before editing, **re-grep the symbol** named next to
each number.

---

## Status — start here

**WP0-WP4 are built, verified and committed. Start at WP5.**

```
WP0 181e1c1 ──► WP1 2dad7e7 ──► WP2 38443af ──► WP3 4bac3b2 ──► WP4 7220d09 ──► [WP5] ──► [WP6] ──► [WP7] ──► [WP8] ──► verify-gate ──► owner merges
  baseline      model core      transport      audio sched      video          ▲ you are here
```

```bash
cd /Users/namansoni/infinte
git checkout feature/arrange-step-06-video                 # WP4 tip
git checkout -b feature/arrange-step-07-editing            # WP5 branch
cmake --build build -j"$(sysctl -n hw.ncpu)"               # must be clean before you touch anything
```

Last known-good state on the WP4 tip:

| Check | Result |
|---|---|
| Build | clean |
| `.claude/skills/run-infinite-hygiene/driver.sh --skip-build --full` | **73 passed, 0 failed, 3 xfail, exit 0** (72 + ARRANGEVIDEOTEST) |
| `INFINITE_ARRANGEVIDEOTEST` (new, WP4) | 8/8 |
| `INFINITE_ARRANGEAUDIOTEST` | 8/8 |
| `INFINITE_TRANSPORTTEST` | 6/6 |
| `INFINITE_ARRANGETEST` | 9/9 |
| Known xfails (pre-existing, not ours) | `GROUPTEST`, `DRAGTEST`, `PLUGINDRAGTEST` |
| `MOLDERTEST` | fails 3/3, **unbaselined and unrelated** — handled on its own branch, don't fold it into this work |

Before writing WP5 code, read **"As built (WP1-WP3)"** and **"As built (WP4)"**
below. Several things landed differently from the plan text, and WP5-WP8
depend on the as-built shape, not on the original wording.

## Owner's working rules (apply throughout)

- Don't UI-script the ImGui canvas (no "Control your Mac", no osascript
  clicking). Verify with self-test fixtures and code reading. The owner
  checks visuals by hand.
- After every successful build, copy `build/Infinite.app` to `~/Desktop/Infinite.app`.
- Every `Platform::` change needs both sides: `Platform.mm` and `win/PlatformWin.cpp`
  (see the `windows-parity` skill).
- Reports back to the owner use tables, bullets and flow diagrams. No long
  prose. Don't end with obvious next steps.

## Work packages and branches

This is too big for one commit. Do the packages **in order**. Give each one its
own branch, stacked on the previous one:
`feature/arrange-step-NN-<slug>` (see the `git-branch-workflow` skill). At the
end of every package:
1. The build is clean.
2. The package's fixtures pass.
3. The hygiene driver is green.
4. Commit.

**Don't merge to `main`.** The owner merges.

| WP | Branch | Content | Risk | State |
|---|---|---|---|---|
| 0 | `feature/arrange-step-02-panel-shell` | Baseline commit of the WIP panel work | — | **done** `181e1c1` |
| 1 | `feature/arrange-step-03-model-core` | `src/arrange/` model, ticks time base, stable IDs, node UIDs, serialization, arrange-only undo | High | **done** `2dad7e7` |
| 2 | `feature/arrange-step-04-transport` | Tempo-safe beats, `SeekBeats`, loop moved into Transport | Medium | **done** `38443af` |
| 3 | `feature/arrange-step-05-audio-scheduling` | Audio-thread clip scheduling, Timeline/Canvas mode, persistent PDC | **Highest** | **done** `4bac3b2` |
| 4 | `feature/arrange-step-06-video` | Lane order, FBO ownership, geometry cache, compose-after-cook | Medium | **done** `7220d09` |
| 5 | `feature/arrange-step-07-editing` | ID-based selection, multi-drag, groups, enable key `0`, offline clips, lane pick, undo coverage, **deletes the legacy bridge** | **High — largest** | next |
| 6 | `feature/arrange-step-08-time-markers` | Bars/Time display, markers, playhead keys, scrub fix | Low–Med | |
| 7 | `feature/arrange-step-09-export-queue` | Render fixes + export queue + persisted settings | Medium | |
| 8 | `feature/arrange-step-10-thumbs-waves` | Live audio waveforms, video thumbnails | Low–Med | |

Each remaining branch stacks on the previous one's tip.

---

## WP0 — Baseline

> **DONE — `181e1c1`.** Reference only; skip.

```bash
cd /Users/namansoni/infinte && git status --short
cmake --build build -j"$(sysctl -n hw.ncpu)"
```

If the build is clean, commit all current modifications on
`feature/arrange-step-02-panel-shell` as
`arrange: panel shell, clip editing, compositing, timeline audio, render (WIP baseline)`.
If it doesn't compile, stop and report. Don't fix unrelated breakage silently.

---

## WP1 — Model core (the foundation everything else stands on)

> **DONE — `2dad7e7`.** Reference only; skip to *As built* for what differs.

### Why
- Clips are identified by `(stream, clip)` vector indices, which go stale after any reorder, overlap trim, delete or undo.
- Clips point at nodes by **reused** node indices (`RemoveNodeByIndex`, [main.cpp:32127](../../../src/main.cpp) comment: "indices are reused").
- Time is `double` seconds while the grid is beats.
- Every timeline undo respawns the whole graph through `ApplyPatchData`.

### Decisions

| Topic | Decision | Why |
|---|---|---|
| Module | New `src/arrange/ArrangeModel.h/.cpp`, added to CMakeLists. Pure data plus edit ops, **no ImGui, no GL, no audio**. `main.cpp` keeps the UI | Testable headless. Future features (automation, retrigger) extend the model, not the 74k-line file |
| Time base | `using Tick = int64_t; constexpr Tick kPPQ = 960;` for **every** clip time field: start, length, fadeIn, fadeOut, markers, loop, render ranges | Exact grid math, triplets included (960 % 3 == 0). A BPM change keeps clips on the grid. Abutting edges compare equal |
| Conversions | `TicksToBeats`, `TicksToSeconds(t, bpm)`, `SecondsToTicks(s, bpm)`, all in the model header | Single tempo (no tempo map yet); one place to change when a tempo map arrives |
| Clip identity | `uint64_t id`, unique within the model, from `Model::nextId` (persisted) | Selection, drag, rename, assign, clipboard, waveform and thumbnail caches all key on it |
| Node identity | New `uint64_t uid` on `GraphNode`, assigned at spawn from `gNextNodeUid++`. `Patch::NodeRecord` gets `uid` (saved as a new trailing key; absent in old files → fresh uid). `ApplyPatchData` restores a record's uid. **Paste/duplicate always assign fresh uids.** Keep a `std::unordered_map<uint64_t, GraphNode*>` rebuilt on graph change | Clips reference `srcUid`, which survives full undo/redo and reload. Other systems (modulation, gestures) keep using indices. **Out of scope** |
| Clip fields | `id, start, length, srcUid, srcOutput, fadeIn, fadeOut (Tick), gainDb, enabled (bool, default true), groupId (0 = none), name, color` | `enabled` = the `0` key (WP5). `groupId` = groups (WP5) |
| Dead data | **Remove** `triggerMode`, `speed` and `loop` from `ClipRecord` and the ARRANGETEST fixture. The loader still *accepts and ignores* those legacy tokens | Engine never used them. Phase 6 (retrigger) re-adds its field when it's actually built |
| Lane | `id, type, blendMode, opacity, gainDb, pan, name, clips` (clips **always sorted by start, never overlapping**) | Keep blend/opacity/gain/pan in the data. Their UI is deferred (owner decision) |
| Markers | `struct Marker { uint64_t id; Tick pos; std::string name; uint32_t color; }` in `Model::markers`, sorted | WP6 |
| Settings | `Model::settings`: timeDisplay (0 = Bars, 1 = Time), snap division, zoom, scroll, loop {enabled, start, end}, dock side, render defaults (WP7). **Audio mode is NOT in settings and is never saved** | Owner wants loop, zoom and render settings to persist per patch. The app always starts in Canvas mode |
| Invariant | `bool Validate(const Model&, std::string* why)` checks sorted, non-overlapping, length > 0, unique ids, group ids refer to ≥ 2 clips. Called in debug builds after every edit op and in every fixture | Catches regressions immediately |

**Edit ops (free functions; each returns whether the model changed and bumps `revision`):**
- `PlaceOverwrite`: overwrite-style insert that trims or splits neighbours and **keeps the lane sorted**. It replaces `PlaceClipTrimmingOverlap` ([main.cpp:25962](../../../src/main.cpp)), which appends without sorting.
- `MoveClips(ids, deltaTick, laneDelta)`: moved clips never trim each other.
- `TrimEdge(id, edge, tick)`
- `Split(id, tick)`
- `DuplicateBlock(ids)`: copies land after the selection's max end as one block, groups re-created with new groupIds.
- `Delete(ids)`
- `SetEnabled(ids, toggle|value)`
- `Group(ids)`, `Ungroup(groupIds)`, `RemoveFromGroup(ids)`
- `TrimGroupEdge(groupId, edge, tick)`, `ScaleGroup(groupId, edge, tick)` (see WP5)
- Lane ops: add, remove, reorder
- Marker ops: add, move, rename, recolor, delete
- `Find(id) → {lane, index}`

### Wiring
- Replace `std::vector<Patch::StreamRecord> gArrangeStreams` ([main.cpp:1134](../../../src/main.cpp)) with `Arrange::Model gArrange`. Convert to and from `Patch::Data` in `BuildPatchData` (~32835) and `ApplyPatchData` (~34637).
- **Serialization** (`src/core/Patch.cpp/.h`):
  - Keep the `stream`/`clip` line grammar and add tick keys.
  - Add `marker` lines and one `arrange` settings line.
  - Legacy files with seconds → convert to ticks **after** the whole file is parsed, using that file's transport BPM.
  - Don't bump `Patch::kVersion`.
  - Keep `PatchJson` in parity.
- **Undo:**
  - `UndoEntry` ([main.cpp:33280](../../../src/main.cpp)) gains `std::optional<Arrange::Model> arrangeOnly`.
  - Timeline edits push arrange-only entries. `Undo()`/`Redo()` ([main.cpp:35285](../../../src/main.cpp)) swap `gArrange` for those and **never call `ApplyPatchData`** for them.
  - Graph edits still push full entries, which carry the arrangement.
  - Because clips reference uids that full undo restores, both entry kinds coexist without remapping.
  - Add `PushArrangeUndo()`, which marks `gPatchDirty` ([main.cpp:32627](../../../src/main.cpp)).
- `NewPatch` ([main.cpp:33349](../../../src/main.cpp)) resets the model and seeds 4 video + 4 audio lanes. Fix the `SeedDefaultArrangeStreams` comment (~33329), which says 3 + 3.

### Exit
Extend `INFINITE_ARRANGETEST` ([main.cpp:58164](../../../src/main.cpp)):
- **Fuzz:** 2,000 seeded random edit ops, with `Validate` after each.
- **Undo/redo round trip:** undo to the start equals the initial model, and redo returns to the final one, interleaved with node add and delete.
- **Save/load:** round trip, plus a legacy seconds-only fixture string.
- **Uid:** survives a full undo and a reload.

---

## WP2 — Transport

> **DONE — `38443af`.** Reference only.

| Bug | Fix |
|---|---|
| `Beats()` = `beatsOffset + (Seconds − secOffset) × currentBpm` (`Transport.cpp:38-50`), so changing BPM mid-play **jumps** the beat position and every beat-placed clip | `SetTempo` stores a pending tempo. The audio thread applies it in `AdvanceAudioClock` by rebasing (`beatsOffset = Beats()`, `secOffset = Seconds()`, counter reset) before swapping BPM. The fallback `Tick()` path already integrates correctly |
| No beat-addressed seek | Add `SeekBeats(double)`. The timeline playhead is **`Beats()`**, everywhere (panel, audio envelope, compositor, render) |
| Loop wrap runs in the panel draw ([main.cpp:26346](../../../src/main.cpp)), is frame-granular, and overshoots | `Transport::SetLoop(bool, double beatStart, double beatEnd)`, atomics. `AdvanceAudioClock` wraps at the block boundary (≤ 1 audio block, not 1 UI frame); `Tick()` handles it when there is no engine. `SetOfflineMode(true)` suspends the loop and restores it after. Delete the panel-side wrap |

Exit:
- The fixture changes BPM mid-play and checks that `Beats()` is continuous (|Δ| < 1 block).
- With loop on, the playhead never exceeds loop end by more than one block.

---

## WP3 — Audio scheduling (the root bug)

> **DONE — `4bac3b2`.** Reference only; the *As built* section is authoritative where the two disagree.

### Current flow (wrong)

```
UI frame ─► main-loop std::set<int> of active srcIndex (main.cpp ~54856)
          └─ set changed? ─► RebuildAudioTopology() (main thread)
                              └─ one terminal per *currently active* clip,
                                 fade window = that clip only (~31434-31530)
```

Consequences to eliminate:
- The second adjacent clip of the same node plays **silent**, because the set doesn't change and the stale window stays.
- Seeking between two clips of the same node is silent for the same reason.
- Onsets land up to one UI frame late.
- Every boundary resets PDC.
- Nodes freeze between clips.
- Edits aren't heard until the next boundary.

### New flow

```
arrangement edit / mode change ─► gArrange.revision++ ─► RebuildAudioTopology() (≤ once per frame)
                                                          └─ seeds = every node of every ENABLED, ASSIGNED clip
                                                             on every audio lane (whole arrangement)
                                                          └─ one terminal per (laneId, srcUid, srcOutput)
                                                             carrying ALL its clip windows (sorted)
audio thread, per sample ─► beat = blockStartBeat + i·bpm/(60·sr)
                          └─ env = Σ windows covering beat (gain · fades · declick) · laneGain
                          └─ paused ⇒ env = 0
```

### Decisions

| Topic | Decision |
|---|---|
| Mode | Replace `bool gArrangeAudioMode` ([main.cpp:1066](../../../src/main.cpp)) with `enum class AudioMode { Canvas, Timeline }`, **default Canvas and never saved**: it resets to Canvas on app launch, File→New and File→Open (owner decision). Only switching explicitly enters Timeline mode. The timeline "Start Audio" = Timeline mode; the canvas top-bar "Start Audio" = Canvas mode. They are mutually exclusive (owner: they are two different use cases) |
| Mode leak | Strict routing depends **only** on `mode == Timeline`. Remove `gArrangePanelOpen` and `IsPlaying()` from both conditions ([main.cpp:31434](../../../src/main.cpp), [54867](../../../src/main.cpp)). Hiding the panel never changes what you hear. The top bar shows the current mode even when the panel is hidden |
| Paused in Timeline mode | Silence (DAW semantics). Nodes keep processing |
| Canvas Audio Outs in Timeline mode | Bypassed (intended, per owner). Their capture rings aren't fed. That's expected |
| Windows | `struct ClipWindow { double startBeat, endBeat, fadeInBeats, fadeOutBeats; float gain; }`, a main-thread-allocated array owned by the ProcessList and freed with it through the existing retire path (`mRetiring` / `CompletedGeneration`). **No allocation on the audio thread.** Replace `AudioTerminal::fadeClipStartSec/LengthSec/fadeInSec/fadeOutSec` (`AudioEngine.h:84-87`) with `const ClipWindow* windows; int numWindows; float laneGain;` |
| Envelope | Rewrite the block in `AudioEngine.cpp` ~310-345. Keep `blockStartBeat = Beats() − n·bpm/(60·sr)` (valid because `AdvanceAudioClock` runs before `RunTopology`). Track a per-terminal window cursor so the scan is O(1) amortized. Always apply a **2 ms declick ramp** at every window edge on top of the user fade (flag this in the report; it's an owner-visible choice) |
| Nodes between clips | Keep running (they're seeds). This satisfies the spec's "a clip does not freeze its node" |
| PDC | Terminal compensation moves to a main-thread-owned `std::unordered_map<TerminalKey, std::unique_ptr<CompensationDelay>>`, persisted across rebuilds and retired only after `CompletedGeneration` passes the generation that dropped it. Max-latency alignment is computed over **all** timeline terminals, so it's stable |
| Rebuild triggers | `gArrange.revision` change, mode change, node graph change. **Delete** the per-frame set-diff block (`main.cpp` ~54856-54891) and `OfflineRenderState::prevArrangeAudioClips` plus its uses (~54735). Clip boundaries never rebuild |
| Offline render | When the job's audio source is Timeline clips, it uses the same terminals, and the existing offline master-sum path stays. When it's Canvas output, the render uses the canvas Audio Outs regardless of the live mode (WP7 #6b) |

### Exit
New `INFINITE_ARRANGEAUDIOTEST`, deterministic and using offline mode. With a sine oscillator node:
- Two abutting clips of the same node → both regions are non-silent.
- Onset error ≤ 1 sample relative to the declick ramp.
- A disabled clip is silent.
- Paused → silent.
- Seeking from clip A into clip B of the same node → audible.
- After `NewPatch` / `LoadPatchFrom`, the mode is Canvas even if Timeline was active before.
- A rebuild mid-clip (edit another lane) produces no discontinuity above threshold at the rebuild block.

Also run the `audio-pipeline-sweep` and `audio-node-sweep` skills (`AUDIOTEARDOWNSWEEPTEST`, which includes deleting a node referenced by a clip mid-playback).

---

## As built (WP1-WP3) — read this before WP4

Everything below is **already in the tree** on `4bac3b2`. Where it disagrees
with the WP1-WP3 sections above, this section wins.

### New and changed files

| File | What it is |
|---|---|
| `src/arrange/ArrangeModel.h/.cpp` | The model. Ticks, `kPPQ = 960`, `Clip`, `Lane`, `Marker`, `Settings`, `Validate`, and every edit op. No ImGui, no GL, no audio |
| `src/arrange/ArrangeLegacy.h/.cpp` | **Transitional bridge, deleted in WP5.** Read its header comment first |
| `src/core/Patch.cpp/.h` | Tick keys on `clip`, new `marker` lines, one `arrange` settings line. `kVersion` unchanged; legacy seconds convert after the whole file parses |
| `src/core/Transport.h/.cpp` | `SeekBeats`, pending-tempo rebase, `SetLoop` + block-accurate wrap, `BlockStartBeats()` |
| `src/audio/AudioEngine.h/.cpp` | `ClipWindow`, window-array topology, beat-domain per-sample envelope, `externalCompensation` |
| `src/main.cpp` | `gArrange`, `gAudioMode`, node uids, arrange-only undo, the whole-timeline scheduler, `INFINITE_ARRANGEAUDIOTEST` |

### Deviations from the plan text above

| Plan said | Actually built | Why it matters to you |
|---|---|---|
| "Replace `gArrangeStreams` with `Arrange::Model`" | **Both exist.** `gArrange` is the source of truth for save/load/undo/fixtures; the ~190 UI call sites still edit `LegacyArrange::StreamRecord` (seconds + node indices) and are funnelled through `SyncArrangeFromLegacy()` / `SyncLegacyFromArrange()` (`main.cpp:5487`, `:5495`) at each boundary | **WP5 deletes the bridge.** Until then, any new UI you write should prefer `gArrange` and must not assume the legacy array is authoritative |
| Rebuild trigger is `gArrange.revision` | A content **fingerprint**, `ArrangeAudioScheduleHash()` — folds mode, offline-arrange flag, tempo, per-lane id/gain, per-clip `srcUid/srcIndex/srcOutput/enabled/start/length/fades/gain`. The main loop rebuilds when the hash moves | A revision counter was unusable while ~190 call sites mutate the legacy array directly. **When WP5 kills the bridge, switch the trigger back to `revision` and delete the hash** |
| `ClipWindow { startBeat, endBeat, fadeInBeats, fadeOutBeats, gain }` + `const ClipWindow* windows` | Same fields plus `abutsPrev` / `abutsNext`, stored as `AudioTopology::clipWindows` (one flat vector) addressed by `AudioTerminal::windowOffset` + `numWindows` | Indices, not pointers, so the array retires with the ProcessList through the existing `mRetiring` path |
| `blockStartBeat = Beats() − n·bpm/(60·sr)` | `Transport::BlockStartBeats()`, captured **before** the advance and before any loop wrap | The subtraction lands on the *new* lap for the block that crosses a loop end. Use `BlockStartBeats()` anywhere you need a block's start on the pre-wrap axis |
| — | `AudioTerminal::externalCompensation` points into `gArrangeTerminalComp`, a main-thread `unordered_map` keyed by `(laneId, srcUid, srcOutput)`, reaped via `CompletedGeneration()` | Don't free a `CompensationDelay` at rebuild time; it can still be in flight |

### Already built, ahead of its WP — don't rewrite it

The **model layer** for several later packages already exists and is fixture-covered.
Those WPs are now mostly **UI wiring**:

| Later WP needs | Already in `ArrangeModel` |
|---|---|
| WP5 groups | `Group`, `Ungroup`, `RemoveFromGroup`, `ClipsInGroup`, `ExpandSelectionToGroups`, `TrimGroupEdge`, `ScaleGroup` |
| WP5 enable / offline media | `SetEnabled`, `ClearSource(uid)` (sets `srcUid = 0`, never erases clips) |
| WP5 editing | `PlaceOverwrite`, `MoveClips`, `TrimEdge`, `Split`, `DuplicateBlock`, `Delete` |
| WP5 dock, WP6 display/snap, WP7 render defaults | `Model::settings` (`dockSide`, `timeDisplay`, `snapDivision`, `snapTriplet`, `zoom`, `scroll`, `loop`, `render*`) — **already persisted** in the `arrange` patch line |
| WP6 markers | `AddMarker`, `MoveMarker`, `RenameMarker`, `RecolorMarker`, `DeleteMarker` — **already serialized** as `marker` lines |
| WP6 `End` key | `ArrangementEnd(m)` |
| WP5 undo | `PushArrangeUndo()` + `UndoEntry::arrangeOnly`; timeline edits never call `ApplyPatchData` |
| WP5 uid resolution | `GraphNode::uid`, `gNextNodeUid`, `FindNodeByUid(uid)` (linear today — WP5 owes the per-frame map) |

### Invariants later packages must not break

1. **No allocation on the audio thread.** Window arrays are built on the main thread and retire with the ProcessList.
2. **Lanes stay sorted and non-overlapping.** Go through the model edit ops; `Validate` runs after every op in debug and in every fixture.
3. **Audio routing depends on `gAudioMode` and nothing else** — not panel visibility, not `IsPlaying()`. The offline render must not assign to it (WP7 #6).
4. **`gAudioMode` is never persisted** and resets to `Canvas` on launch, `File▸New` and `File▸Open`.
5. **A rebuild must not be triggerable from a clip boundary** — the whole timeline is scheduled once.

### Debts carried forward (fix them in the WP that makes them matter)

| Debt | Where | Due |
|---|---|---|
| `ScaleGroup` deep-copies the whole `Model` per call; `TrimGroupEdge` and `ExpandSelectionToGroups` are O(n²) | `ArrangeModel.cpp` | **WP5**, when they go under a live drag |
| `Lane::pan` is stored, serialized and round-tripped but **read by nothing** — a lane's pan is silently inert | `main.cpp` scheduler | Mixer UI is out of scope; either wire pan into the terminal or tell the owner it is inert |
| `ReapArrangeTerminalCompensation()` only runs from inside `RebuildAudioTopology()`, so a stale `CompensationDelay` survives until the next rebuild | `main.cpp` | Bounded leak, harmless; revisit only if it grows |
| `ApplyPatchData` rebuilds the topology before `SetTempo` lands, so the first frame after a load schedules at the old bpm | `main.cpp` | Self-heals in one frame via the hash; clean up when the bridge dies in WP5 |
| `FindNodeByUid` is a linear scan per clip per frame | `main.cpp:5459` | **WP5** (the per-frame uid → `GraphNode*` map) |

### Fixtures that must stay green

| Env var | Frame | Covers |
|---|---|---|
| `INFINITE_ARRANGETEST` | — | model fuzz + `Validate`, undo/redo round trip, save/load incl. a legacy seconds fixture, uid survival |
| `INFINITE_TRANSPORTTEST` | — | mid-play BPM continuity, `SeekBeats`, loop wrap ≤ 1 block, the lapping block's own start beat |
| `INFINITE_ARRANGEAUDIOTEST` | 4 | abutting clips, onset ≤ 1 sample, disabled silent, paused silent, seek across clips, rebuild mid-clip, mode reset on New/Open |
| `INFINITE_ARRANGEVIDEOTEST` | 4 | top lane frontmost, lane opacity, disabled/unassigned skipped, empty → opaque black, geometry clip 0 FBO allocs over 100 frames on two targets, cache eviction (WP4) |

Run one directly:

```bash
INFINITE_ARRANGEAUDIOTEST=1 INFINITE_EXITAFTER=12 ./build/Infinite.app/Contents/MacOS/Infinite
```

All three are registered in `.claude/skills/run-infinite-hygiene/driver.sh`.
**Register every new fixture there too**, in both tier1 and tier2.

### Environment gotchas

- macOS here has no `timeout`, and the agent harness blocks `sleep N; cmd` chains. Run long things in the background and poll.
- Count hygiene results from the driver's own `== Summary ==` line, never by grepping `[pass]` while it is still running.
- A `[stale-baseline]` entry in `known-test-failures.txt` makes the driver exit 1 even with 0 failures. Delete lines for tests that now pass.

## As built (WP4) — read this before WP5

### What landed (`src/main.cpp` unless noted)

| Symbol | What it is |
|---|---|
| `struct ArrangeCompositeTarget` | Owns `scratch[2]` (ping-pong pair), `result` (stable output for the monitor), `retiredResult` (the pre-resize `result`, kept one composite so the draw list never samples a deleted texture), `requestW/H`, and `slot` (geometry-cache key) |
| `gArrangeMonitorTarget` (slot 0), `gArrangeRenderTarget` (slot 1) | One per consumer. Replace the old shared `static sArrangeScratchFbo` and `static sArrangeMonitorFbo` |
| `CollectArrangeVideoLayers(beat, out)` | **The single place lane order and the skip rules live.** Bottom lane first (top lane frontmost); skips `!enabled`, `srcIndex < 0`, and a missing node. Honours `srcOutput` via `INode::GetOutputTexture(int)` |
| `CountActiveArrangeVideoClips(beat, title)` | Now built on the collector, so the monitor label counts exactly what is composited and names the frontmost node |
| `CompositeArrangeTimelineVideo(target, dest, beat, w, h)` | New signature. `dest == nullptr` → `target.result`. Last pass writes `dest` directly (no copy-back). `frameId` is gone |
| `ArrangeComposeShader()` | Program + uniform locations cached once at build |
| `gArrangeGeomViewports` | `std::map<std::pair<uid, slot>, {NodeViewport, lastUsedFrame}>`; `ReapArrangeGeomViewports()` evicts after 120 unused main-loop frames. `gPanelViewports` is never touched |
| `CompositeArrangeMonitorIfRequested()` | Runs right after the main cook loop (`for (gn : gNodes) CookIfNeeded(frameId)`), then the reaper. The panel only sets `requestW/H` and draws `result.tex`; ImGui renders after the composite, so the monitor shows **this** frame, not the previous one |
| `GLUtil::NoteFboAllocation()` / `FboAllocationCount()` (`src/core/GLUtil.*`) | Diagnostic counter bumped by `GLUtil::EnsureFbo` and `NodeViewport::EnsureFbo` on every real allocation |
| `INFINITE_ARRANGEVIDEOTEST` (frame 4) | Top lane frontmost, lane opacity honoured, disabled skipped, unassigned skipped, nothing active → opaque black, geometry clip 0 FBO allocations over 100 frames on two targets of different size, eviction at 121 unused frames. Registered in `driver.sh` tier1, `GROUP_VIDEO` and full |

### Deviations from the WP4 text

| Plan said | Actually built | Why |
|---|---|---|
| Geometry cache keyed by node uid | Keyed by **(uid, target slot)** | The panel keeps drawing under the render's progress window, so the monitor and the render composite the same geometry clip in the same frame at different sizes. One `NodeViewport` per uid would reallocate twice a frame — the exact bug #3 removes |
| "Prefer reading `gArrange`" (session brief) | The collector reads `gArrangeStreams` (legacy mirror) | Same reason WP3's scheduler does: `gArrange` is only synced at save/undo boundaries, so it would show a live drag one sync late. **WP5: switch `CollectArrangeVideoLayers` to `gArrange` + the uid map when the bridge dies — it is the only reader to change** |
| Playhead | Compositor time is `Transport::Beats()` for both monitor and render (clip seconds × live bpm/60) | The audio envelope's axis. The render's `Beats()` reads the video time just set by `SetOfflineVideoTime`, so picture and sound agree. The panel's drawn playhead still uses `Seconds()` — WP6's to unify |
| — | `srcOutput` is now honoured on video lanes | It was ignored (always output 0). WP5's "Output ▸" menu needs it; an index the node doesn't have yields no layer rather than the wrong image |

### Debts carried forward

| Debt | Where | Due |
|---|---|---|
| Collector reads the legacy mirror and `FindNodeByIndex` per clip per frame | `CollectArrangeVideoLayers` | **WP5** (bridge deletion + per-frame uid map) |
| Render "Match Clips" size detection and `arrangeEndSec` still include disabled/unassigned clips | render popup, `detectedClipW/H` | **WP7** #5 |
| `gNodeCameras` is still index-keyed; the geometry clip's camera follows the node's index | compositor geometry branch | Out of scope (moving other systems to uids) |
| A geometry clip's texture is only ever sampled by the composite pass, which is what makes immediate eviction safe | `ReapArrangeGeomViewports` | **WP8**: if thumbnails blit a geometry clip's texture into a draw list, retire evicted entries one frame first |

### Pre-existing sweep findings (not WP4, not fixed)

Both reproduce identically with WP4's `src/` stashed (WP3 tip `4bac3b2`).

| Fixture | Observation | Cause |
|---|---|---|
| `IMAGERESYNTH_SELFTEST` | `279 node types, 35 failures` — compositing sweep exits 1 | Fixture classification gap, not a render bug: every failure is a texture-less type the fixture has no branch for (Notes nodes, 3D point/field ops, Comment, OSC Send, Audio Texture) and so falls through to the `tex != 0` test (`main.cpp` SELFTEST loop). Hygiene doesn't run it |
| `CACHETEST+SHOWCASE` | `idleStreak=0` for all 24 frames, `work` +1 per frame | One SHOWCASE node re-cooks every frame. Unexamined |


---

## WP4 — Video

> **DONE — `7220d09`.** Reference only; *As built (WP4)* below is authoritative.

| # | Bug | Fix |
|---|---|---|
| 1 | Lane 0 (top) composites first, i.e. **at the back** (`CompositeArrangeTimelineVideo`, ~26040-26210) | Iterate lanes bottom → top so the **top lane is frontmost** (spec §1 and NLE convention). Fix the render comment "topmost track wins" to match |
| 2 | `static GLUtil::Fbo sArrangeScratchFbo` (~26147) is shared by the monitor and the offline render → it resizes twice per frame | Pass a `ArrangeCompositeTarget&` that owns its scratch FBO pair. One instance for the monitor, one for render |
| 3 | Geometry clips borrow `gPanelViewports`, which is erased each frame for nodes not in the Viewport Panel (~56480) → GL alloc/free per frame (4K during render) | Own a cache `gArrangeGeomViewports` keyed by node uid, sized to the target, evicted after 120 frames unused. Never touch `gPanelViewports` |
| 4 | `glGetUniformLocation` runs per pass; `frameId` is unused | Cache the locations when the program is built. Drop the dead parameter |
| 5 | The monitor shows the previous frame's textures (the UI draws before the cook loop, ~73802) | Composite the monitor **after** the cook loop into its target. The panel draws that texture next frame, so clip state and textures are consistent |
| 6 | Disabled and unassigned clips | Skip them |
| 7 | Blend and opacity | Keep honouring model values. **No UI** (owner: compositing UI is deferred) |

Exit:
- Run the `compositing-pipeline-sweep` skill.
- The fixture checks that two lanes with opaque clips show the top lane's pixels.
- A geometry clip causes no FBO allocations across 100 frames (count `EnsureFbo` reallocations).

---

## WP5 — Editing, selection, groups, enable, offline clips

| Area | Decision |
|---|---|
| Selection state | `std::set<uint64_t> gArrangeSel` + anchor id. Drag, rename, assign and context-menu targets become ids. Replace `gArrangeSelectedStream/Clip`, `gArrangeMultiSelectedClips`, `gArrangeDraggingClipStream/Index`, `gArrangeAssigningClip*`. Resolve each frame through `Find`; a missing id clears that state |
| Multi-drag | The whole selection moves: time delta for all, lane delta only if every clip lands on a same-type lane. **Overwrite preview**: the regions of target-lane clips that will be trimmed get a red overlay during the drag. Bounds come from the **target** lane (currently the source lane, ~27330-27340) |
| Hit zones | Trim handle width = `clamp(clipW × 0.25, 2, 6)` px. The middle always moves, so narrow clips stay movable |
| Duplicate | `Cmd+D` → `DuplicateBlock` (fixes the first copy overwriting the second original) |
| Copy/paste | The clipboard holds clips by value plus srcUid, relative offsets and relative lane offsets. Paste goes at the playhead on the anchor lane. **Clear it on New/Open** (patch generation counter) |
| Split | `Cmd+E` at the playhead on the selection (the Ableton key) |
| **Enable key `0`** | Toggles `enabled` on the selection (Ableton convention). Disabled clips draw desaturated with a diagonal hatch and are excluded from audio (WP3), video (WP4), render (WP7) and thumbnail capture (WP8). Undoable |
| **Groups** | `Cmd+G` groups ≥ 2 selected clips (any lanes, video + audio allowed). `Cmd+Shift+G` ungroups the selected groups. Right-click → "Remove from Group" for individual clips. Clicking a grouped clip selects the whole group; **Option/Alt-click** selects a single member. Visual: a thin bar across the top of members in the group colour, plus an outline around the group bounds when selected. Move, copy, paste, duplicate, delete and enable apply to the whole group |
| Group length | Dragging a selected group's bounding-box edge **trims only the clips touching that edge** (default). **Shift-drag scales every member's start and length proportionally** around the opposite edge, snapped. Report this choice to the owner |
| Offline media | `RemoveNodeByIndex` ([main.cpp:32129](../../../src/main.cpp)) must **not** erase clips: set `srcUid = 0`. The UI shows "Unassigned" with a hatch and a tooltip, and the clip is silent and invisible. Undo of the delete restores the link (full entry + uid). The canvas "Assign Node" picker (~71903) assigns by uid |
| Add to Timeline lane pick | `AddNodeToArrangeTimeline` (~26212) uses `IsNodeAudioCompatible`, which is true for `VideoSourceNode` (it's also `IAudioSource`) → wrong lane. Rule: produces an image → video lane; audio only → audio lane. `VideoSourceNode` gets a submenu "Add to Timeline ▸ Video / Audio", with the audio item setting `srcOutput` to its audio output (verify the slot number in `src/nodes/VideoSourceNode.h`). Default length **1 bar** in ticks instead of 4.0 s; start = the lane's last end or the playhead |
| Output choice | For nodes with > 1 output of the lane's type (e.g. `FieldPixelNode` aux image), add a clip context menu "Output ▸" that sets `srcOutput` |
| Undo coverage | One entry per gesture, pushed only if `revision` changed (clicking without moving → **no** entry; today every click pushes, `PushUndoCheckpoint` [main.cpp:34725](../../../src/main.cpp)). Popup DragFloats (Start/End/Fade In/Out/Gain), clip rename and lane rename: snapshot on `IsItemActivated()`, push on `IsItemDeactivatedAfterEdit()` if changed (mirror `gDragStartSnapshot` [main.cpp:34737](../../../src/main.cpp) / 70272-70293). All mark `gPatchDirty` |
| Perf | Build the uid → `GraphNode*` map and cached titles once per frame. No `FindNodeByIndex` linear scan ([main.cpp:5416](../../../src/main.cpp)) per clip per frame |
| Zoom | `Cmd/Ctrl + wheel` zooms around the mouse on **both** platforms (Windows precision-touchpad pinch arrives as Ctrl+wheel). Keep the macOS pinch |
| Dock | `gArrangePanelDock` is `const int 0` ([main.cpp:1008](../../../src/main.cpp)) though the layout handles 4 sides (~56470). Make it a persisted setting. Expose **Bottom / Top** in the panel header menu (the timeline is horizontal; left/right are not offered) |
| Audio buttons | Power and routing are split (owner decision). **Top bar: "Start Audio" / "Stop Audio"** controls engine power only and never changes the mode. While Timeline mode is on, it shows a small "Timeline" badge next to it (visible even when the panel is hidden). **Panel toolbar: "Enable Timeline Audio"** toggles the mode: on = Timeline (starts the engine if it's off), off = Canvas (the engine keeps running). Stop Audio leaves the mode unchanged for the session. The app launch, New and Open reset the mode to Canvas (WP3) |
| Dead code | Remove `clipToDeleteStream` (~27920) and the empty right-click block |

Exit:
- Fixture: select ids → reorder lanes → delete a node → undo → the selection still resolves to the same clips or clears. It never hits a different clip.
- Group move, duplicate and delete keep `Validate` green.
- `0` toggles and undoes.
- Run the `shortcuts-sweep` skill (the new keys must not collide and must be ignored while a text field is active; see the focus guard ~69699).

---

## WP6 — Time display, markers, playhead keys

| Topic | Decision |
|---|---|
| Display | A toolbar toggle **Bars \| Time**, persisted. The ruler shows primary labels in the chosen unit and thin secondary labels in the other. Clip popup fields show in the chosen unit, and the hover tooltip shows both. Storage is always ticks, so the toggle is purely a view |
| Snap | A beat grid in ticks: bar, 1/2, 1/4, 1/8, 1/16, triplets, off. Clip edges and the playhead snap too |
| BPM change | Clips keep bar/beat positions, so their seconds change. The tooltip on the tempo field says so |
| Markers | `M` adds a marker at the playhead (snapped). Markers draw as flags on the ruler: drag moves, double-click renames, right-click → colour / delete. `Option/Alt + ← / →` jumps to the previous/next marker. Undoable; saved in the patch |
| Playhead keys | `← / →` nudge the selection by one grid step, or move the playhead when nothing is selected. `Home` = 0. `End` = arrangement end |
| J/K/L + audio scrub | **Not implemented** (owner deferred to me). Shuttle needs reverse playback, which live procedural nodes can't do. Scrub instead: dragging on the ruler moves a ghost playhead, and `SeekBeats` fires **once on release**. Today every drag frame calls `Seek`, which bumps `mResetEpoch` and resets Field state each frame |

Exit: the fixture checks marker save/load/undo, and that after a BPM change clip ticks are unchanged and seconds are rescaled.

---

## WP7 — Render + export queue

| # | Bug / need | Fix |
|---|---|---|
| 1 | "Include video" (`sArrangeRenderIncludeVideo`, ~26567) never reaches the render | Replace both include checkboxes with the source pickers in #6b. Video None → **audio-only WAV** (use the existing WAV writer behind `AudioCaptureRing`; if `OutputNode::StartOfflineRender` can't do audio-only, add a WAV-only path without the encoder). Audio None → no audio track |
| 2 | Duration is `ceil` to whole seconds | Frames = `ceil(durationSec × fps)` from the exact range end |
| 3 | The loop `Seek` fires mid-render (fractional loop lengths) | Covered by WP2 (loop suspended in offline mode). Assert it in the fixture |
| 4 | Hardware-source refusal skipped for arrange renders | Run `FindHardwareDrivenNode`-style checks over nodes referenced by enabled clips in the job's range. Fail the job with a clear message |
| 5 | "Match Clips" takes the first video clip's size (0 for geometry) | First enabled video clip with a non-zero texture size, else the patch's Output node size, else 1920×1080 |
| 6 | Mode leak: render forces Timeline mode (`gArrangeAudioMode = true`, ~26756) and never restores it | The render **never changes the mode**. It uses the job's sources (below). Delete the forced assignment |
| 6b | Render sources are hard-wired (always timeline audio, always timeline video) | Per-job **Audio source**: Timeline clips · Canvas output · None. **Default follows the monitoring mode**: Timeline Audio on → Timeline clips, off → Canvas output (owner: "render what you hear"; video-only timeline over live canvas music and audio-only timeline over live canvas visuals are both first-class). Per-job **Video source**: Timeline clips · Canvas Output node (a picker when several exist) · None. Default: Timeline clips if the range has ≥ 1 enabled video clip, else the first canvas Output node. The canvas-output paths reuse the existing manual OutputNode render path (its own cable / `forceGraphAudio`); the timeline paths use WP3/WP4. The popup shows a one-line summary, e.g. "Audio: Canvas output · Video: Timeline (5 clips)". Audio None + Video None → Render disabled; Video None → WAV. The hardware refusal (#4) also covers canvas-output sources |
| 7 | Settings are static and lost | Render defaults (w, h, fps, sr, format, source overrides, range kind, last folder) live in `Model::settings` and persist in the patch |
| 8 | No overwrite prompt | At enqueue, if the path exists **or** another queued job has the same path → a modal with Overwrite / Auto-rename (`name (2).mp4`) / Cancel |

### Export queue

```
Render button ─► popup: settings + [Render Now] [Add to Queue]
Queue window  ─► job list ─ status · progress · ETA
                 ├ reorder (drag), duplicate, remove, retry failed
                 ├ [Start Queue] [Cancel Current] [Cancel All]
                 └ done job ─► "Reveal" (existing reveal helper)
runs sequentially on the existing gOfflineRender pump; next job starts only
after the previous finalize completes and state (mode/transport/vsync) is restored
```

| Job field | Values |
|---|---|
| range | Whole arrangement (first clip → last end) · Loop · Marker A → Marker B · Custom (ticks) |
| sources | audio: Timeline clips · Canvas output · None; video: Timeline clips · Canvas Output node (which one) · None |
| output | w, h, fps, sample rate, format (mp4/mov/wav), path |
| status | Queued · Rendering · Finalizing · Done · Failed(msg) · Cancelled |

- While a job runs, **timeline editing is locked**: a read-only overlay reading "Rendering — timeline locked".
- The queue is session-only. Only the render defaults persist.

Exit:
- Run the `av-sync-sweep` skill.
- The fixture queues 4 jobs (whole, loop with a fractional length, marker range, audio-only) and checks frame counts, WAV sample counts ±1 block, and that the live mode is unchanged.
- It also covers the source matrix:
  - Timeline video + Canvas audio: a canvas sine is present in the file.
  - Canvas video + Timeline audio.
  - Default audio source follows the Timeline Audio toggle.

---

## WP8 — Live waveforms + video thumbnails

| Clip type | Decision |
|---|---|
| Audio | **Position-indexed live peak cache.** For each clip window, the audio thread accumulates min/max per bucket of `kPPQ/16` ticks and pushes `(clipId, bucket, min, max)` into a fixed-size lock-free SPSC ring (drop when full; never allocate or lock). The main thread drains it into `unordered_map<clipId, vector<MinMax>>`, sized to the clip's bucket count. Draw inside the clip body: filled buckets as a waveform, unfilled as a flat centre line. Clear a clip's cache when its src, output, start or length changes. Not saved. Offline renders fill it too |
| Video | A 96×54 thumbnail from a small texture pool per clip id. Blit the clip's resolved source texture (already found in `CompositeArrangeTimelineVideo`) on the first composite after activation, every 1 s while active, and once on assign. Draw at the clip's left edge, only if `clipW > thumbW + 16` px. Free when the clip is deleted. Not saved |

Don't refactor the existing per-node `Draw*Waveform` copies (10482-14320). **Out of scope.**

Exit:
- The ring never allocates on the audio thread (review it).
- Playing through a clip fills its waveform.
- Deleting 50 clips frees their thumbnails (pool count back to baseline).

---

## Build and verify (every WP)

```bash
cmake --build build -j"$(sysctl -n hw.ncpu)"
.claude/skills/run-infinite-hygiene/driver.sh
cp -R build/Infinite.app ~/Desktop/Infinite.app
```

- Register `INFINITE_ARRANGETEST` changes and the new `INFINITE_ARRANGEAUDIOTEST` in `.claude/skills/run-infinite-hygiene/driver.sh`.
- Sweeps per WP:

| WP | Sweeps to run | State |
|---|---|---|
| 3 | `audio-pipeline-sweep`, `audio-node-sweep` | done — both clean |
| 4 | `compositing-pipeline-sweep` | done — static 0 problems, BYPASS/PALETTE/REMOVEBG pass; SELFTEST's 35 failures and CACHETEST's 0 idle streak are pre-existing (identical on `4bac3b2`) |
| 5, 6 | `shortcuts-sweep`, `panels-sweep` | |
| 7 | `av-sync-sweep` | |

- Before each commit, run the `invariant-interaction-audit` skill on WP1 (no-overlap invariant) and WP3 (sample-accurate window invariant): check that no sibling path (paste, drop, render, undo) bypasses the model ops.
- Finish with the `verify-gate` agent on the final branch.

## Out of scope (owner decisions, don't build)

- Compositing, mute, solo, pan, lane gain, meters, master bus UI. The data stays; the UI waits for a UX pass.
- Retrigger, per-clip speed, loop-in-clip, transitions, keyframes/automation, nested sequences, J/K/L shuttle.
- Moving other systems (modulation, gestures, viewport panel) to node uids.
- Refactoring the existing per-node waveform drawers.

## Report back (per WP, tables and bullets)

- What changed: file → function → one line each.
- Fixture results, with pass counts.
- Any decision above that the code forced you to change, and why.
- Choices the owner should eyeball by hand:
  - the 2 ms declick — **shipped in WP3, still unverified by ear**
  - silence while paused in Timeline mode — **shipped in WP3, still unverified by ear**
  - the group-edge trim vs Shift-scale behaviour (WP5)
  - the Bottom/Top-only dock (WP5)
  - whether `Lane::pan` should be wired up or declared inert (see *Debts carried forward*)
