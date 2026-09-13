# Lens 2 — Execution

**Question:** What actually runs, on which thread, in what order, and what does
it do? This is the "frontline" lens: the feature's real behaviour.

**Not this lens:** how fast it runs (→ 6 Performance), whether its output is
mathematically right (→ 7 Correctness).

## Trigger questions
- Does a value cross between threads (main ↔ audio, main ↔ worker, main ↔ GL context)?
- Does it change what happens inside `CookIfNeeded`, an audio `Process`, a kernel, a shader, or a Field backend?
- Does it depend on `Transport` (play / pause / seek / loop / BPM) or on musical time?
- Does it change spawn / connect / disconnect / delete / teardown order?
- Does it change the order in which the per-frame tick does things?

## Sub-lenses

### 2a Threads & ownership
| Thread | Where it lives | May touch |
|---|---|---|
| Main (UI + GL) | `int main()` loop in `src/main.cpp` | Everything GL, all `INode` state, `ImGui` |
| Audio callback | `AudioEngine::Process` (`src/audio/AudioEngine.*`), device side in `Platform.mm` / `platform/win/AudioDeviceWin.cpp` | Only `AudioNode` halves, the mailbox, atomics, pre-allocated buffers |
| Workers | `SampleScanner`, `PluginScanner`, `MolderNode`, `GrainMolderNode`, `SlicerNode`, `RemoveBgNode`, `OutputNode` (recorder), `OscNodes`, `RemoteControl`, `UpdateCheck`, `platform/win/MediaWin.cpp` (grep `std::thread`) | Their own job buffers. **Never GL**, never live node state |

- **Handoff patterns** (reuse these, never invent one):
  - `ParamMailbox` (`src/audio/ParamMailbox.h`) is the only main→audio param path.
  - `SampleSlot` (`src/audio/SampleSlot.h`) is the pending/active/retire ring for buffers.
  - `std::atomic<T*>` plus retire-one-generation is used by `AudioPluginNode` and `SetTopology`.
  - A single `mResultReady` atomic flip is the worker→main result handoff (`MolderNode`).
  - Latest-only request slots are used by `RemoveBgNode`.
- **Owning skills:** `audio-pipeline-sweep`, `field-realtime`, `new-audio-node`.
- **Known traps:**
  - Plugin params deliberately bypass the mailbox. That is documented, not a bug.
  - A worker must be aborted and joined in the destructor before any member is freed.

### 2b The frame tick
The order of one main-loop frame, as it stands today:
```
poll events → Transport::Tick → apply modulation into params
  → CookIfNeeded(frameId) per terminal (Output / Render / Viewport)
      → pull upstream, memoised per frameId
  → draw editor (nodes, panels, links) → ImGui::Render → present → frame limiter
```
- **Anchors:** `CookIfNeeded` (`INode.h`), `frameId`, `Transport::Tick`, the modulation apply loop and `gTargetFps` in `main.cpp`.
- **Owning skills:** `data-accuracy-sweep` (memo under fan-out), `rate-analysis-sweep`.
- **Known trap:** reading `ed::GetNodePosition` / `GetNodeSize` in the same frame a node was spawned returns stale values (see `codebase-navigation`).

### 2c Time & clock
- **Anchors:** `class Transport` (`src/core/Transport.*`, including the audio-clock freeze on pause), `src/audio/MusicTime.h`, the arrangement timeline (`StreamRecord` in `Patch.h`, `docs/plans/arrangement/`), `GestureRecorder`.
- **Rules:** anything animated reads the `Transport` clock, never wall time. Tempo-sync options come only from `MusicTime.h`.
- **Owning skills:** `rhythmic-quantization-standard`, `av-sync-sweep`, `new-source-node` (clock rule).
- **Known traps:**
  - A node that animates while paused.
  - A looping recording that doesn't freeze on spacebar pause (fixed in `0eb00b5`).

### 2d Behaviour logic
The feature itself: node math, DSP kernels (`src/audio/dsp/*Kernel.*`),
shader pass strings, `FilterDefs`, Field backends (`FieldVM`, `GlslBackend`,
`ElementBackend`, `SampleRuntime`), and mesh operators.
- **Owning skills:** the matching `new-*-node` skill; the `field-*` skills for Field; `field-pixel-presets` / `field-modifier-presets`.
- **Pair with 7a:** every behaviour change raises a "is the math right" question.

### 2e Lifecycle
- **Anchors:** `SpawnNode`, `RemoveNodeByIndex`, `DisconnectLinkById`, `DisconnectAllTo`, `ReloadDerivedState`, destructors of two- and three-object nodes, and `AudioEngine::SetTopology`'s retire ring.
- **Owning skills:** `audio-node-sweep` (AUDIOTEARDOWNSWEEPTEST), `plugin-host-hardening`.
- **Known traps:**
  - Deleting mid-playback while the audio half still reads the node.
  - Tearing down the recorder mid-take.
  - GL resources outliving their projector-window context (`output-projection-sweep`).

## Zoom guide
| Zoom | For Execution it means |
|---|---|
| L1 | Which threads X runs on, plus where it sits in the frame tick |
| L2 | Handoff pattern(s) used, clock source, and lifecycle events X reacts to |
| L3 | Sequence: who calls X, what X calls, and on which thread each step runs |
| L4 | The actual loop / kernel / atomic load-store lines |
