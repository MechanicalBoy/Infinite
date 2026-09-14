# Lens 1 — Structure

**Question:** What exists, how is it wired together, and what is actually
reachable?

**Not this lens:** what the wired thing *does* when it runs (→ 2 Execution),
whether its data survives save/undo (→ 3 Data & State).

## Trigger questions
Any "yes" means this lens is at least Touched.

- Does the change add, remove, rename or re-home a class, file, node type, pin or cable?
- Does it add a new implementer of an interface (`INode`, `IAudioSource`, `IGeometrySource`, `IModulator`, `IEffectKernel`)?
- Does it need an entry in a hand-maintained table (registration, cable chain, extension allowlist, `EffectDef`)?
- Does it add a source file, a target, or an external dependency to `CMakeLists.txt`?
- Does it move a responsibility across a module boundary (`nodes/` ↔ `core/` ↔ `audio/` ↔ `platform/`)?

## Sub-lenses

### 1a Object model
The shapes that code is allowed to take.
- **Anchors:** `class INode` (`src/core/INode.h`), `class IAudioSource`,
  `class IGeometrySource` (both in `INode.h`, geometry extended in
  `src/nodes/Geometry3DNodes.h`), `class IModulator` / `struct ParamRef`
  (`src/core/Modulation.h`), `GraphNode` (`src/core/GraphNode.h`),
  `IEffectKernel` (`src/audio/dsp/IEffectKernel.h`).
- **Rules:** audio nodes follow the two-object rule (an `INode` main-thread half
  plus an `AudioNode` audio half). The three-object exception exists only for
  plugin hosting (`AudioPluginNode`). Don't invent a fourth shape
  (`docs/CODE_STANDARDS.md` §7).
- **Owning skills:** the matching `new-*-node` skill, `field-integration` for Field nodes.

### 1b Registration & wiring
Having a class does not make it reachable.
- **Anchors:** `RegisterNodes` / `NodeFactory` (`src/core/NodeFactory.*`),
  `struct EffectDef` table (`src/audio/EffectDefs.*`), `InputCountFor`,
  `CableFor(`, `ConnectGeometrySlot`, `QueryNewLink`, `DisplayName`,
  drop allowlists (`kModelExt`, `kGltfExt`), and the four cable-wiring
  chains (see `cable-logic-sweep`). All are in `src/main.cpp` unless noted.
- **Owning skills:** `cable-logic-sweep`, `codebase-navigation` (living map), `new-*-node`.
- **Known traps:**
  - A pin declared in a header does nothing without its cable chain.
  - A `GraphNode*` returned by `SpawnNode` dangles after the next spawn.
  - `IsAudioOutputIndex` exists because `VideoSourceNode` has two outputs.

### 1c Module boundaries
- **Anchors:** directory layout `src/nodes`, `src/audio` (+`dsp/`),
  `src/core` (+`field/`), `src/platform` (+`win/`). `Platform.h` is the only
  door to native code.
- **Rules:** `src/nodes/` and `src/audio/` stay pure C++. Objective-C and
  `_WIN32` stay behind `Platform::`. A new top-level directory for one node
  is a finding.
- **Owning skills:** `windows-parity` (the one-abstraction rule).

### 1d Graph topology
Infinite has several graphs, not one.
- **Image / geometry DAG:** `ImageCable` (`src/core/ImageCable.h`), `IGeometrySource`, pulled through `CookIfNeeded`.
- **Audio / note DAG:** `AudioCable.h`, `NoteCable.h`, and `AudioEngine::SetTopology`, rebuilt as a whole topology and swapped with retire-one-generation.
- **Modulation network:** `ParamRef` bindings (`Modulation.h`), and colour bindings (`Palette.h`).
- **Field graph:** `src/core/field/FieldGraph*` (host, ownership, reconciler).
- **Owning skills:** `cable-logic-sweep`, `modulation-sweep`, `field-integration`.
- **Known trap:** blurring the image and audio DAGs, for example touching audio state from the param UI (`CODE_STANDARDS.md` §3).

### 1e Dependencies & licensing
- **Anchors:** `CMakeLists.txt`, `external/`, `cmake/`.
- **Rules:** match the existing vendoring tier: single-header libraries go in
  `external/`, mid-size libraries use `FetchContent`, huge binaries are zips,
  and VST3 is a submodule (see `codebase-navigation`).
- **Licensing:** Infinite is MIT. Never read GPL sources (BespokeSynth,
  Kronos, Cmajor, SuperCollider). VST3 stays behind `INFINITE_ENABLE_VST3`.
- **Owning skills:** `infinite-code-review` (the clean-room check).

## Zoom guide
| Zoom | For Structure it means |
|---|---|
| L1 | Which graph(s) X belongs to, and which module directory owns it |
| L2 | The interfaces X implements, plus the registration tables it appears in |
| L3 | Link map: class → factory entry → cable chain → consumers |
| L4 | The exact table rows / `case` arms / `if (dynamic_cast<…>)` dispatch lines |
