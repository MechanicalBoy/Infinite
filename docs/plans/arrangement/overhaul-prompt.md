# Arrangement Timeline — Overhaul (bugs, architecture, features)

Paste this whole file into a fresh Claude Code session on Infinite.

---

You are overhauling Infinite's **Arrangement Timeline** (C++/ImGui/OpenGL node
compositor). Repo root: **`/Users/namansoni/infinte`** (that spelling is correct).
The spec is `docs/plans/arrangement/README.md`. This prompt **replaces its
phases 3, 4, 5, 7 and 8 as they were built**, and adds features the owner has
asked for. Every design decision below is already made. Don't re-open them
unless the code proves one impossible. If that happens, stop and report.

Line numbers were verified on branch `feature/arrange-step-02-panel-shell`
with a large uncommitted diff (`src/main.cpp` = 74,220 lines). Before editing,
**re-grep the symbol** named next to each number.

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

| WP | Branch | Content | Risk |
|---|---|---|---|
| 0 | `feature/arrange-step-02-panel-shell` (existing) | Commit the current uncommitted work as the baseline | — |
| 1 | `…-step-03-model-core` | `src/arrange/` model, ticks time base, stable IDs, node UIDs, serialization, arrange-only undo | High |
| 2 | `…-step-04-transport` | Tempo-safe beats, `SeekBeats`, loop moved into Transport | Medium |
| 3 | `…-step-05-audio-schedule` | Audio-thread clip scheduling, Timeline/Canvas mode, persistent PDC | **Highest** |
| 4 | `…-step-06-video` | Lane order, FBO ownership, geometry cache, compose-after-cook | Medium |
| 5 | `…-step-07-editing` | ID-based selection, multi-drag, groups, enable key `0`, offline clips, lane pick, undo coverage, misc | High |
| 6 | `…-step-08-time-markers` | Bars/Time display, markers, playhead keys, scrub fix | Low–Med |
| 7 | `…-step-09-export-queue` | Render fixes + export queue + persisted settings | Medium |
| 8 | `…-step-10-thumbs-waves` | Live audio waveforms, video thumbnails | Low–Med |

---

## WP0 — Baseline

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

## WP4 — Video

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

| WP | Sweeps to run |
|---|---|
| 3 | `audio-pipeline-sweep`, `audio-node-sweep` |
| 4 | `compositing-pipeline-sweep` |
| 5, 6 | `shortcuts-sweep`, `panels-sweep` |
| 7 | `av-sync-sweep` |

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
  - the 2 ms declick
  - the group-edge trim vs Shift-scale behaviour
  - silence while paused in Timeline mode
  - the Bottom/Top-only dock
