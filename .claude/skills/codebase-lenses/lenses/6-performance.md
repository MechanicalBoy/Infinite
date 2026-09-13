# Lens 6 — Performance

**Question:** What does it cost per frame, per audio block, and per byte, and
does an idle patch stay idle?

**Not this lens:** whether a slow path gives the *right* answer (→ 7), or
*which* thread runs it (→ 2a). This lens asks what running there costs.

## Trigger questions
- Does the change add work to the per-frame tick, `CookIfNeeded`, or the editor draw pass?
- Does it add work, allocation, locking, or logging on the audio thread?
- Does it add a GPU pass, an FBO, a texture upload/readback, or a ping-pong buffer?
- Does it do file I/O, decoding, analysis, or network work on the main thread?
- Does it scale with node count, element count, voice count, or resolution?
- Could it make a static patch re-cook every frame?

## Sub-lenses

### 6a Frame budget
- **Anchors:** `gTargetFps` / vsync and the frame limiter in `main.cpp`, frame-timing display, and the editor's per-frame hit-testing.
- **Owning skills:** `rate-analysis-sweep`.
- **Known trap:** per-frame hit-test cost grows with node count, so big patches stutter even when nothing changes.

### 6b Cook economy
- **Anchors:** `CookIfNeeded(frameId)` memo, `TextureRevision` (downstream skip), Render 3D `BuildSceneSignature`, and idle-frame caching.
- **Rule:** a source that doesn't change must not force a downstream re-render (`new-source-node`).
- **Owning skills:** `rate-analysis-sweep`, `data-accuracy-sweep` (memo under fan-out), `render-pipeline-sweep`.

### 6c Audio budget
- **Anchors:** `AudioEngine::Process`, the audio half's `CookIfNeeded` (a budget of about 5 µs), `ParamMailbox`, `MeterRing`, `AudioCaptureRing`, and `CompensationDelay` (plugin latency).
- **Rules:** no heap allocation, locks, recursion, unbounded loops, or strings on the audio thread. Anything that takes tens of ms goes to a worker (`MolderNode` pattern).
- **Owning skills:** `field-realtime` (the checklist), `audio-pipeline-sweep`, `rate-analysis-sweep` (xruns / jitter).

### 6d GPU cost
- **Anchors:** `GLUtil::Fbo` / `CompileProgram`, pass counts in `FilterDefs`, feedback / reaction-diffusion ping-pong, and Field pixel `state` (an 8 MB ping-pong pair at 1080p per cell), `PixelState`.
- **Owning skills:** `field-state` (memory cost table), `render-pipeline-sweep`, `compositing-pipeline-sweep`.

### 6e Main-thread blocking
- **Known blocking sites:**
  - Synchronous decode on file drop (`ImageSourceNode::Load`, `ModelSourceNode::Load`).
  - Shader compiles.
  - GPU readbacks (`RemoveBgNode` hand-off).
- **Rule:** the only async precedent is the `SampleScanner` worker shape. Reuse it; don't assume a generic job system exists.
- **Owning skills:** `codebase-navigation` (living map entry on sync decode).

### 6f Memory
- **Covers:** growth of `AssetCache` / `AudioDecodeCache`, per-element / per-voice buffers, Field element stores (`ElementStore`), retired generations awaiting free, and texture sizes following resolution.
- **Owning skills:** `field-state`, `field-realtime`.

## Zoom guide
| Zoom | For Performance it means |
|---|---|
| L1 | Which budget X spends (frame, audio block, GPU, RAM) and roughly how much |
| L2 | When X runs: every frame, on change, on load, per block. And whether it can go idle |
| L3 | Hot path: the call chain that runs per frame/block, with allocations and passes marked |
| L4 | The specific loop, allocation, upload, or compile, plus a before/after measurement |

**Evidence rule:** a performance claim needs a number from `rate-analysis-sweep`
or a timed fixture, before and after. Without one it's a hypothesis, and 7d
applies.
