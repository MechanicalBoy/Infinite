# Lens 3 — Data & State

**Question:** What is remembered, where, and does it survive every round trip
(save/load, undo/redo, copy/paste, duplicate, group, reload)?

**Not this lens:** the file-format *parser's* robustness against bad input
(→ 7c Edges & boundaries), or whether the cached value is *cheap* (→ 6b).

## Trigger questions
- Does the change add or alter a param, a stateful member, or anything the user sets?
- Does it change the patch format, `VisitParams`, or `BuildPatchData` / `ApplyPatchData`?
- Does it hold state between frames (feedback, simulation, sequencer position, Field `state`)?
- Does it introduce or invalidate a cache, revision stamp, or generation counter?
- Must old patches still open, or new patches in older builds?

## Sub-lenses

### 3a Params
- **Anchors:** `VisitParams` (`INode.h`, `Patch.cpp`), `struct ParamRef` and `ModSlider` (`Modulation.h`, `main.cpp`), `DrawDiscreteParamPin`, `docs/node_param_audit.md`.
- **Checks:**
  - Is the param serialised?
  - Is it modulatable (registers a `ParamRef`), or deliberately not?
  - Does it reach the audio thread within one block (→ 2a)?
- **Owning skills:** `node-param-audit`, `audio-node-sweep` (AUDIOPARAMSWEEPTEST), `modulation-sweep`.

### 3b Persistence
- **Anchors:**
  - Line grammar and read/write primitives in `src/core/Patch.h/.cpp`.
  - `PatchJson.*`.
  - `BuildPatchData(`, `ApplyPatchData`, `SavePatchTo`, `LoadPatchFrom` in `main.cpp`.
  - Recents via `NoteRecent`.
  - Preferences: `Infinite.json` / `imgui.ini` under App Support, and the `gTargetFps` prefs line.
- **Rules:** additive changes only, so old patches must load. Unknown keys are skipped, not fatal.
- **Owning skills:** `field-integration` (patch grammar section), `data-accuracy-sweep`.
- **Known trap:** a link that is accepted at runtime but silently lost on save (`cable-logic-sweep`).

### 3c Undo, clipboard, duplicate
- **Anchors:** `PushUndoCheckpoint` / `PushUndoSnapshot`, `Undo()` / `Redo()` (a snapshot through `BuildPatchData`), `CopyParams`, Cmd+C/V, Shift+D, and group ungroup.
- **Checks:**
  - Is a checkpoint pushed once per user gesture, not once per drag frame?
  - Does paste preserve every param and internal link?
- **Owning skills:** `node-ui-sweep` (undo / copy / paste / delete), `data-accuracy-sweep`.

### 3d Caches & revisions
- **Anchors:** `TextureRevision` / `NextTextureRevision` (`INode.h`), `MeshRevision` (`Mesh.h`), `PointCloudRevision`, `CurveStamp`, `BuildSceneSignature` (Render 3D), `class AssetCache` (path + mtime/size key), `AudioDecodeCache`, `FieldProgramCache`.
- **Rule:** a stamp moves **only** when output actually changed (`CODE_STANDARDS.md` §3).
- **Owning skills:** `geometry-transform-sweep` (REVISIONSWEEPTEST), `render-pipeline-sweep` (RENDER3DCACHESWEEPTEST), `data-accuracy-sweep`.
- **Known traps:**
  - `DisplacementNode` bumped its stamp every cook.
  - The XOR-folded scene signature collapsed to 0.
  - `AssetCache` has no sub-asset key.

### 3e Runtime-only state
State that is real while running but deliberately not saved, or that must
reset.
- **Examples:** simulation / feedback buffers, sequencer playheads, Field `state` cells (reset on seek / loop / stop, saved by `(name, type)`), `GestureRecorder` takes, and the arrangement timeline's clip state.
- **Checks:**
  - Is it intentionally unsaved, and documented as such?
  - What resets it?
  - Does hot-reload keep it?
- **Owning skills:** `field-state`, `invariant-interaction-audit`.

## Zoom guide
| Zoom | For Data & State it means |
|---|---|
| L1 | What X remembers, split by where it persists: patch, prefs, cache, or RAM only |
| L2 | Which round trips X's state goes through, and which of them it survives |
| L3 | Field-by-field: runtime member ↔ `VisitParams` key ↔ patch line ↔ undo snapshot |
| L4 | The serialise/deserialise lines and the stamp-bump sites |
