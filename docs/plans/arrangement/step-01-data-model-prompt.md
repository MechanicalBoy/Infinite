# Arrangement Timeline — Step 1: data model + serialization

Paste this whole file into a fresh Claude Code session on Infinite.

---

You are implementing **Step 1 of 8** of the Arrangement Timeline feature in
Infinite (C++/ImGui node compositor). Repo root: **`/Users/namansoni/infinte`**
(that spelling is correct).

The spec is `~/Downloads/README.md`; this step commits it into the repo as
`docs/plans/arrangement/README.md`. This prompt covers **only Step 1**. No UI,
no audio, no compositing, no render work.

Every line number below was verified at commit `f5aa88c`. If `main` has moved,
re-grep the **symbol** named next to each number before editing.

## Goal

Streams and clips exist in the patch data model and survive save, load, undo,
redo, autosave, node deletion and File→New — with **no UI**. The exit
criterion is a passing self-test, not a visible feature.

## Design decisions already made (don't re-litigate)

| Decision | Choice | Why |
|---|---|---|
| Shape | `StreamRecord` **owns** `std::vector<ClipRecord> clips` | Exactly the `PerfRecord::targets` shape. Reorder/delete a stream → its clips move with it; no `streamIndex` in memory to go stale |
| On disk | `stream …` lines; `clip <streamIdx> …` back-references like `perftarget <perfIdx> …` | Existing parent/child convention |
| Seconds | `double`, written with the existing `DoubleToString` (`%.17g`, `Patch.cpp:50`) | Abutting clips must stay exactly equal after reload; overlap checks (Step 3) compare edges |
| Node ref | `srcIndex` + `srcOutput` | `VideoSourceNode` has image and audio on separate outputs; `FieldPixelNode` has an aux image output. Same meaning as `CableRecord::srcOutput` |
| Version | Do **not** bump `Patch::kVersion` | Unknown tags are ignored by older builds; bumping would lock them out |
| Malformed stream line | Keep it (sanitized), never drop | Dropping would shift every later `clip` back-reference onto the wrong stream |
| Malformed clip line | Drop it | Same as `perftarget` with a bad index |
| Canvas resolution / arrangement settings | **Not in this step** | Later phases add an `arrange` tag; the format is forward-compatible |

## Branch

```bash
cd /Users/namansoni/infinte && git checkout main && git checkout -b feature/arrange-step-01-data-model
```

```bash
mkdir -p docs/plans/arrangement && cp ~/Downloads/README.md docs/plans/arrangement/README.md && cp ~/Downloads/step-01-data-model-prompt.md docs/plans/arrangement/
```

## 1. Records — `src/core/Patch.h`

Add after `GestureRecord` (ends `Patch.h:226`), before `struct Data`:

```cpp
   // Arrangement timeline (docs/plans/arrangement/README.md). A stream is one
   // lane; it owns its clips, same parent/child shape as PerfRecord::targets,
   // so reordering or deleting a stream can never leave a clip on the wrong
   // lane. Clips within one stream never overlap - enforced by the editor,
   // not here.
   enum StreamType { kStreamVideo = 0, kStreamAudio = 1 };

   struct ClipRecord
   {
      double startSeconds  = 0.0;   // >= 0
      double lengthSeconds = 1.0;   // > 0
      int    srcIndex      = -1;    // node index - remapped by ApplyPatchData's resolve()
      int    srcOutput     = 0;     // which output of srcIndex, as CableRecord::srcOutput
      int    triggerMode   = 0;     // 0 = continuous, 1 = retrigger
      float  fadeInSec     = 0.0f;
      float  fadeOutSec    = 0.0f;
      float  gainDb        = 0.0f;
      float  speed         = 1.0f;  // > 0
      bool   loop          = false;
   };

   struct StreamRecord
   {
      int   type      = kStreamVideo;
      int   blendMode = 0;      // video only; index into BlendModes::Names() (0-31)
      float opacity   = 1.0f;   // video only, 0..1
      float gainDb    = 0.0f;   // audio only
      float pan       = 0.0f;   // audio only, -1..1
      std::string name;         // empty = auto ("V1", "A2", ...) - label derived by the UI
      std::vector<ClipRecord> clips;
   };
```

Add to `Patch::Data` (`Patch.h:228-243`), after `gestures`:

```cpp
      std::vector<StreamRecord> streams; // arrangement timeline, clips nested
```

Extend the grammar comment (after the `gesture` entry, ~`Patch.h:59`):

```
//   stream <type> <blendMode> <opacity> <gainDb> <pan> <name to end of line>
//   clip <streamIndex> <start> <length> <srcIndex> <srcOutput> <triggerMode> <fadeIn> <fadeOut> <gainDb> <speed> <loop>
//     Arrangement timeline (docs/plans/arrangement/README.md). A clip
//     back-references the stream line it belongs to by position, like
//     perftarget -> perf. start/length use %.17g so abutting clip edges
//     reload exactly equal. A clip with an out-of-range stream index, a
//     non-finite or negative start, or a length <= 0 is dropped; a malformed
//     stream line is kept with defaults so later clip indices still line up.
```

## 2. Write and read — `src/core/Patch.cpp`

**Write** — in `Patch::Write`, after the `gesture` loop (ends `Patch.cpp:313`):

```cpp
   for (size_t i = 0; i < data.streams.size(); i++)
   {
      const StreamRecord& s = data.streams[i];
      file << "stream " << s.type << " " << s.blendMode << " " << FloatToString(s.opacity) << " "
           << FloatToString(s.gainDb) << " " << FloatToString(s.pan) << " " << EscapeLine(s.name) << "\n";
      for (const ClipRecord& c : s.clips)
         file << "clip " << i << " " << DoubleToString(c.startSeconds) << " " << DoubleToString(c.lengthSeconds) << " "
              << c.srcIndex << " " << c.srcOutput << " " << c.triggerMode << " "
              << FloatToString(c.fadeInSec) << " " << FloatToString(c.fadeOutSec) << " "
              << FloatToString(c.gainDb) << " " << FloatToString(c.speed) << " " << (c.loop ? 1 : 0) << "\n";
   }
```

**Read** — two new branches in the `Patch::Read` tag chain, before the
`// Anything else is from a newer version` comment (`Patch.cpp:649`):

```cpp
      else if (tag == "stream")
      {
         // Always pushed, even when malformed: a clip line refers to its
         // stream by position, so dropping one would shift every later clip
         // onto the wrong lane. Missing/garbage tokens leave defaults.
         StreamRecord s;
         in >> s.type >> s.blendMode >> s.opacity >> s.gainDb >> s.pan;
         std::string raw;
         std::getline(in, raw);
         if (!raw.empty() && raw[0] == ' ')
            raw.erase(0, 1);
         s.name = UnescapeLine(raw);
         if (s.type != kStreamVideo && s.type != kStreamAudio) s.type = kStreamVideo;
         if (s.blendMode < 0 || s.blendMode > 31) s.blendMode = 0;
         if (!std::isfinite(s.opacity)) s.opacity = 1.0f;
         s.opacity = std::clamp(s.opacity, 0.0f, 1.0f);
         if (!std::isfinite(s.gainDb)) s.gainDb = 0.0f;
         if (!std::isfinite(s.pan)) s.pan = 0.0f;
         s.pan = std::clamp(s.pan, -1.0f, 1.0f);
         outData.streams.push_back(std::move(s));
      }
      else if (tag == "clip")
      {
         int streamIdx = -1;
         ClipRecord c;
         if (in >> streamIdx >> c.startSeconds >> c.lengthSeconds >> c.srcIndex &&
             streamIdx >= 0 && streamIdx < (int)outData.streams.size() &&
             std::isfinite(c.startSeconds) && std::isfinite(c.lengthSeconds) &&
             c.startSeconds >= 0.0 && c.lengthSeconds > 0.0)
         {
            // Trailing settings: missing tokens keep ClipRecord's defaults;
            // a garbage token reads as 0, so each is sanitized below.
            int loop = 0;
            in >> c.srcOutput >> c.triggerMode >> c.fadeInSec >> c.fadeOutSec >> c.gainDb >> c.speed >> loop;
            c.loop = loop != 0;
            if (c.srcOutput < 0) c.srcOutput = 0;
            if (c.triggerMode != 0 && c.triggerMode != 1) c.triggerMode = 0;
            const float len = (float)c.lengthSeconds;
            if (!std::isfinite(c.fadeInSec)) c.fadeInSec = 0.0f;
            if (!std::isfinite(c.fadeOutSec)) c.fadeOutSec = 0.0f;
            c.fadeInSec = std::clamp(c.fadeInSec, 0.0f, len);
            c.fadeOutSec = std::clamp(c.fadeOutSec, 0.0f, len);
            if (!std::isfinite(c.gainDb)) c.gainDb = 0.0f;
            if (!std::isfinite(c.speed) || c.speed <= 0.0f) c.speed = 1.0f;
            outData.streams[streamIdx].clips.push_back(c);
         }
      }
```

`std::clamp` needs `<algorithm>` (already included). `std::isfinite` is
already used in this file; add `#include <cmath>` if the compiler asks.

## 3. `PatchJson` parity — `src/core/PatchJson.cpp`

After the `performance` block (before `return out;`, line 109), add a
`"streams"` array: one object per stream with `type, blendMode, opacity,
gainDb, pan, name` and a nested `"clips"` array with every `ClipRecord` field.
Same style as the `performance`/`targets` nesting just above.

## 4. Live state + graph wiring — `src/main.cpp`

Four sites. All four are required — the first two alone leave stale clips
pointing at reused node indices.

**4a. Global** — directly after `std::vector<Patch::PerfRecord> gPerfElements;`
(`main.cpp:1024`):

```cpp
   // Arrangement timeline (docs/plans/arrangement/README.md). Same record
   // type the patch stores - no separate runtime class. Clip srcIndex is a
   // live node index: rewritten by ApplyPatchData, pruned by
   // RemoveNodeByIndex, cleared by NewPatch.
   std::vector<Patch::StreamRecord> gArrangeStreams;
```

**4b. `BuildPatchData()`** — after `data.perfLayout = gPerfLayout;` (`main.cpp:30382`):

```cpp
      data.streams = gArrangeStreams;
```

**4c. `ApplyPatchData()`** — after the `gPerfLayout` clamps (`main.cpp:32145-32148`),
before `RebuildAudioTopology()`:

```cpp
      // A clip whose node didn't survive (deleted at this point in history,
      // or an unknown type in this build) is dropped, exactly like a cable.
      // The stream itself is always kept, even if it ends up empty.
      gArrangeStreams.clear();
      for (const Patch::StreamRecord& s : data.streams)
      {
         Patch::StreamRecord mapped = s;
         mapped.clips.clear();
         for (const Patch::ClipRecord& c : s.clips)
         {
            GraphNode* src = resolve(c.srcIndex);
            if (src == nullptr)
               continue;
            Patch::ClipRecord mc = c;
            mc.srcIndex = src->index;
            mapped.clips.push_back(mc);
         }
         gArrangeStreams.push_back(std::move(mapped));
      }
```

**4d. `RemoveNodeByIndex()`** — directly after
`GestureRecorder::Instance().ClearForNode(index);` (`main.cpp:29680`). The
`PushUndoCheckpoint()` at the top of the function already captured the clip,
so undo brings it back:

```cpp
      // Fourth, same reason: a clip is keyed by node index too, and indices
      // are reused (NewPatch / every Undo respawns from 1).
      for (Patch::StreamRecord& s : gArrangeStreams)
         s.clips.erase(std::remove_if(s.clips.begin(), s.clips.end(),
                                      [index](const Patch::ClipRecord& c) { return c.srcIndex == index; }),
                       s.clips.end());
```

**4e. `NewPatch()`** — next to `GestureRecorder::Instance().Clear();`
(`main.cpp:30898`), **unconditionally** (not inside the
`!gSuppressUndoCheckpoints` block — `ApplyPatchData` repopulates right after):

```cpp
      gArrangeStreams.clear();
```

Do not add a resolved-`INode*` cache. Do not "fix" the fact that
`gPerfElements` lacks 4d/4e — separate bug, separate branch.

## 5. Self-test — `INFINITE_ARRANGETEST`

**Where:** a new `if (getenv("INFINITE_ARRANGETEST") != nullptr && frameId == 4)`
block in the frame loop, directly after the `INFINITE_UNDOTEST` block
(starts `main.cpp:55331`; copy its style). It must be a frame-loop fixture,
not an early-exit one like `RunPerfPanelSelfTest` (`main.cpp:48872`, dispatched
before `glfwInit()` at `main.cpp:49532`) — assertions B–D need `SpawnNode`.

Start with `NewPatch();`. Write temp files with `TmpPath("arrange_selftest.inf")`
(`main.cpp:62`), remove them afterwards. Every check prints one line ending in
`OK` or containing `FAIL` (the driver greps exactly that); end with a summary
line `arrange test: all  OK` / `FAIL`.

Gotchas the test must respect:
- `Patch::Read` **fails on a file with no `node` record** (`Patch.cpp:672`).
  Every hand-built `Patch::Data` / hand-written file needs at least one node
  (e.g. a `NodeRecord` with `typeName = "Cube"`, `category = "3D"`).
- **Undo/Redo change node indices** (ApplyPatchData respawns from 1). After
  any `Undo()`/`Redo()`, check a clip by resolving `FindNodeByIndex(c.srcIndex)`
  and comparing `typeName`, never by comparing the raw index to a saved one.
- Floats/doubles compare with `==` — `%.9g`/`%.17g` round-trip exactly.

Assertions:

- **A. Round trip.** `Patch::Data` with 1 node, 3 streams (video, audio, video;
  names `"Main Lane"`, `""`, and `"a\\b"` with a backslash), 5 clips split 2/2/1,
  **every field non-default** (`srcOutput 1`, `triggerMode 1`, `loop true`,
  `speed 0.5`, etc.). Clip 2 starts at exactly `clip1.start + clip1.length`
  with non-representable values (e.g. start `0.1`, length `0.2`). Write, read,
  compare every field of every stream and clip; also assert
  `c2.startSeconds == c1.startSeconds + c1.lengthSeconds` after reload.
- **B. Undo/redo, live.** Spawn `Cube`; set `gArrangeStreams` to one audio
  stream with one clip on the cube (`startSeconds = 2.0`); `PushUndoCheckpoint()`;
  set `startSeconds = 5.0`; `Undo()` → `2.0` and clip resolves to a `Cube`;
  `Redo()` → `5.0` and still resolves to a `Cube`.
- **C. Deletion, live.** Spawn `Sphere`, add a second clip on it,
  `RemoveNodeByIndex(sphere)` → that clip is gone **immediately**, the cube's
  clip and the stream remain. `Undo()` → sphere clip is back and resolves to a
  `Sphere`. Also: `ApplyPatchData` on a `Data` whose clip `srcIndex` names no
  node → clip dropped, stream kept, no crash.
- **D. File→New.** With clips present, `NewPatch()` → `gArrangeStreams.empty()`.
- **E. Forward compatibility.** Hand-write a file: header, one Cube node block,
  `stream 1 0 1 0 0 A`, `arrangefuture 1 2 3`, `clip 0 1 2 -1 0 0 0 0 0 1 0`.
  Reads OK with 1 stream / 1 clip.
- **F. Malformed input.** One file containing: `stream 1` (truncated),
  `stream 0 0 1 0 0 V`, then clips `clip 7 0 1 -1` (bad stream → dropped),
  `clip 0 0 0 -1` (length 0 → dropped), `clip 0 -1 1 -1` (negative start →
  dropped), `clip 0 0 1 -1` (truncated after srcIndex → kept, trailing
  defaults), `clip 1 0 1 -1 0 0 0 0 0 abc 0` (garbage speed → `1.0`).
  Assert: 2 streams; stream 0 is `type 1` with default opacity/gain/pan/name;
  stream 0 has 1 clip, stream 1 has 1 clip with `speed == 1.0f` (proves the
  truncated stream line didn't shift indices).
- **G. JSON.** `PatchJson::ToJson(BuildPatchData())` has a `"streams"` array
  whose clip count matches `gArrangeStreams`.

## 6. Register the fixture

- `.claude/skills/run-infinite-hygiene/driver.sh`: add `"ARRANGETEST:10"` to
  `TIER1_CHECKS` (after `"UNDOTEST:10"`) and to `FULL_TESTS` (after `"UNDOTEST:10"`).
- `.claude/skills/run-infinite-hygiene/SKILL.md`: add `ARRANGETEST` to the
  "Core engine (undo, patch format)" row.

## 7. Build and verify

```bash
cmake --build build -j"$(sysctl -n hw.ncpu)"
```

Clean build, no new warnings. Then:

```bash
INFINITE_ARRANGETEST=1 INFINITE_EXITAFTER=10 ./build/Infinite.app/Contents/MacOS/Infinite
```

```bash
.claude/skills/run-infinite-hygiene/driver.sh --auto --skip-build
```

`--auto` escalates to the full suite because `Patch.cpp` changed — that's
expected and wanted (PATCHTEST, ROUNDTRIPTEST, AUTOSAVETEST, UNDOPERFTEST all
exercise this path). Anything listed in `known-test-failures.txt` is not yours.

Finally, open a real patch saved before this change and confirm it loads
unchanged, then save it and confirm no `stream`/`clip` lines were written
(empty arrangement writes nothing).

## Out of scope — do not touch

- Any UI: panel, drawing, menu item, shortcut (Step 2).
- `Transport` (Seek is Step 2), `AudioEngine`, `ParamMailbox`,
  `RebuildAudioTopology` (Step 5).
- `BlendModes`, `LayerStackNode`, shaders (Step 4). `OutputNode`, offline pump (Step 7).
- `Seek`/`Retrigger` virtuals (Step 6).
- The `gPerfElements` NewPatch/RemoveNodeByIndex gap (separate bugfix branch).
- Windows: nothing platform-specific here; no `src/platform/` changes.

## Definition of done

Clean build; all ARRANGETEST lines `OK`; hygiene driver green; one commit on
`feature/arrange-step-01-data-model` containing the code, the fixture
registration and `docs/plans/arrangement/`; merged to `main` per
`git-branch-workflow`. The app looks and behaves **exactly** as before.
