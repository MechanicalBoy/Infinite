# WP1 — Model core: implementation plan

> **Historical.** WP1 shipped as `2dad7e7`. Kept for the reasoning behind the
> model's shape. For what the model actually looks like now, see the
> *As built (WP1-WP3)* section of `overhaul-prompt.md`.

Branch: `feature/arrange-step-03-model-core` (already created, stacked on
`feature/arrange-step-02-panel-shell`, which has the WP0 baseline commit
`181e1c1`). Paste this file into a fresh session along with
`docs/plans/arrangement/overhaul-prompt.md` (WP1 section + owner rules) to resume.

Produced by `infinite-planner`, grounded against the current `main.cpp`
(re-verified, not trusting the doc's line numbers).

## Flags to resolve with the owner before/while implementing

1. **`gArrangeStreams` can't be deleted in WP1.** ~186 UI call sites (drag,
   select, assign, popups) read/write it and are explicitly WP5's job. Plan:
   keep `gArrangeStreams` as the live UI's data, add `Arrange::Model gArrange`
   as the real source of truth for save/load + arrange-only undo + fixtures,
   with `FromLegacyStreams`/`ToLegacyStreams` shim functions synced at
   `BuildPatchData`/`ApplyPatchData`/`Undo`/`Redo`. WP5 deletes the shim.
2. **Tick format needs a new tag, not a reinterpreted one.** Old `clip` line
   (seconds, positional fields) can't be read as the new tick format without
   silent corruption. Plan: keep `clip` tag's read branch as-is (feeds a
   transient legacy list), add a new `cliptick` tag for the tick-native
   writer output, convert legacy→ticks after the whole file parses.
3. **`Model::nextId` must persist on disk**, not be recomputed as max+1 (a
   deleted-then-reloaded high id could otherwise collide).
4. **`NodeRecord::uid` needs its own dedicated line** (`uid <uint64>`), not
   the generic `s/f/i/b/c` param path — `FieldGraphNode` already writes an
   unrelated `s uid <hex>` param that would collide.

## New module

`src/arrange/ArrangeModel.h/.cpp` — pure data + edit ops, no ImGui/GL/audio.
Full struct/function list (Tick, kPPQ=960, Model, Lane, Clip, Marker,
Settings, Validate, PlaceOverwrite, MoveClips, TrimEdge, Split,
DuplicateBlock, Delete, SetEnabled, Group/Ungroup/RemoveFromGroup,
TrimGroupEdge/ScaleGroup as WP5 stubs, lane/marker ops, Find,
FromLegacyStreams/ToLegacyStreams) — see full agent output below.

Add to `CMakeLists.txt` next to `src/core/Patch.cpp` (~line 245-246).

## Edit sites (re-verified line numbers on this branch)

| File | Anchor | Change |
|---|---|---|
| `src/core/GraphNode.h:42` | `int index` | add `uint64_t uid = 0;` |
| `src/core/Patch.h:72-84` | `NodeRecord` | add `uint64_t uid = 0;` |
| `src/core/Patch.h:243-257` | `ClipRecord` | tick fields, drop triggerMode/speed/loop, add id/srcUid/enabled/groupId |
| `src/core/Patch.h:259-268` | `StreamRecord` | add `uint64_t id = 0;` |
| `src/core/Patch.h` | new | `MarkerRecord`, `ArrangeSettingsRecord` structs |
| `src/core/Patch.h:270-286` | `Data` | add `markers`, `arrangeSettings` |
| `src/core/Patch.cpp` | Write ~217-219, ~315-327 | write `uid` node line, `cliptick`/`marker`/`arrange` lines |
| `src/core/Patch.cpp` | Read ~418, ~663-724, end ~727 | parse `uid`, keep `clip` as legacy-only, add `cliptick`/`marker`/`arrange`, convert legacy→ticks after full parse |
| `src/core/PatchJson.cpp:95-137` | ToJson | drop dead fields, add new ones, add markers/arrangeSettings (no FromJson exists) |
| `src/main.cpp:110` | includes | `#include "arrange/ArrangeModel.h"` |
| `src/main.cpp:616` | globals | `uint64_t gNextNodeUid = 1;` |
| `src/main.cpp:1134` | globals | add `Arrange::Model gArrange;`, `gUidToNode` map |
| `src/main.cpp:6379-6397` | `SpawnNode` | assign `gn.uid`, insert into `gUidToNode` |
| `src/main.cpp:5416-5424` | near `FindNodeByIndex` | new `FindNodeByUid` |
| `src/main.cpp:32114-32173` | `RemoveNodeByIndex` | erase from `gUidToNode` |
| `src/main.cpp:33320-33410` | `NewPatch`/`SeedDefaultArrangeStreams` | fix stale "3+3" comment, reset `gArrange`, add `SeedDefaultArrangeModel` |
| `src/main.cpp:32660-32835` | `BuildPatchData` | sync `gArrange` from legacy, convert to `Patch::Data` |
| `src/main.cpp:34414-34652` | `ApplyPatchData` | restore/clamp uid, rebuild `gArrange` from `Patch::Data`, sync back to `gArrangeStreams` |
| `src/main.cpp:33280-33284` | `UndoEntry` | add `std::optional<Arrange::Model> arrangeOnly` |
| `src/main.cpp` near 34706-34730 | new | `PushArrangeUndo()` |
| `src/main.cpp:35285-35315` | `Undo`/`Redo` | arrange-only fast path, never call `ApplyPatchData` for it |
| `src/main.cpp:58164-58498` | `INFINITE_ARRANGETEST` | rewrite: fuzz (2000 ops + Validate), undo/redo interleaved with node add/delete, save/load incl. legacy fixture, uid survival |

## Invariants for `invariant-interaction-audit` after implementing

- Lane sorted/non-overlapping — check the legacy shim conversion doesn't let `gArrange` and `gArrangeStreams` disagree.
- `nextId`/`uid` uniqueness — every load path (`LoadPatchFrom`, `Undo`/`Redo` full-entry branch, self-test) must clamp `gNextNodeUid`/`gArrange.nextId`.
- `groupId` refers to ≥2 clips — `Delete`/node-removal pruning must not orphan a singleton group; fuzz harness should catch it.

## Full agent output

The complete file-by-file/function-by-function plan with exact signatures,
line-by-line Patch.cpp read/write changes, and fixture rewrite detail is in
this session's transcript (agent id `a186e304b8ae6d4de`, `infinite-planner`,
prompt: "Plan WP1 arrange model core"). Re-run the same planning prompt in
the new session if the transcript isn't available — it re-greps everything
fresh anyway since line numbers may have shifted.
