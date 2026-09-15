# Categorization Matrix & System Taxonomy

The Categorization Matrix formalizes the structural boundaries, domain-rate transfers, and lifecycle contracts across Infinite.

---

## 1. Universal Node Categorization Taxonomy

Every node in Infinite strictly belongs to one of the following architectural archetypes:

```
                               ┌────────────────────────────────┐
                               │       INFINITE NODE TYPES      │
                               └───────────────┬────────────────┘
          ┌─────────────────┬──────────────────┴─────────────────┬─────────────────┐
          ▼                 ▼                                    ▼                 ▼
   [1. SOURCES]      [2. MODIFIERS / FX]                 [3. MODULATORS]    [4. TERMINALS]
   - Image Generators - Image FX (FilterDef / GLSL)      - LFO / Envelope   - Output / Viewport
   - 3D Primitives    - Mesh Operators (IGeometrySource) - Macros / Pattern - Syphon / Spout
   - Audio Synth/Osc  - Audio DSP Effects                - Math / CV        - Recorder
```

### Archetype Contracts & Invariants:

| Archetype | Inputs | Outputs | State Persistence | Primary Invariant |
| :--- | :--- | :--- | :--- | :--- |
| **Source** | 0 or Modulation | Image, Geometry, Audio | Frame-rate or stateless | Must respect Transport clock; zero CPU burn when canvas idle |
| **Modifier / Effect** | 1+ Primary Data + Mod | Same data type | Single-frame or Ping-Pong | Bypass must pass input bit-for-bit; no buffer mutation |
| **Modulator** | Control signals / Clock | Normalized float [0..1] or bipolar [-1..1] | Phase / Envelope state | `Value01()` must be idempotent within a single frame |
| **Terminal** | Primary Data | Window, OS IPC, File | Framebuffers / Muxers | Clean teardown without corrupting master OpenGL/Metal context |

---

## 2. Multi-Rate Domain Hierarchy

Field & Engine compute across 5 strictly ordered rate domains:

```
[Graph Rate]   (Once on topology change / node spawn)
     │
     ▼
[Frame Rate]   (60-120 Hz: Canvas UI, node cook orchestration, matrix modulation)
     │
     ▼
[Element Rate] (Per-vertex, per-instance, per-particle: SIMD / compute loops)
     │
     ▼
[Pixel Rate]   (GPU Fragment shaders: millions of invocations / frame)
     │
     ▼
[Sample Rate]  (44.1 kHz - 96 kHz: Realtime Audio DSP callback)
```

### Domain Crossing Invariants:
1. **Never Poll Down-Domain**: High-rate domains (Sample / Pixel) must never block or wait on low-rate domains (Frame / Graph).
2. **Implicit Broadcast vs. Explicit Reduce**:
   - Transferring from slow domain to fast domain (e.g. Frame $\to$ Pixel) is an **implicit broadcast** (zero cost).
   - Transferring from fast domain to slow domain (e.g. Sample $\to$ Frame) requires an **explicit reduce or analysis operator** (e.g. RMS envelope, FFT spectrum, Peak meter).

---

## 3. Connective Tissue & Registration Invariants

When any new node or subsystem is introduced, it must register across all 4 hand-maintained connective wiring chains:
1. **Factory / Registry**: `SpawnNode()` instantiation table and name catalog.
2. **Pin / Wire Matrix**: Pin type declaration (`CABLE_IMAGE`, `CABLE_GEOM`, `CABLE_AUDIO`, `CABLE_NOTE`, `CABLE_MOD`).
3. **Modulation Binder**: `VisitParams()` exposing modulatable controls via `ParamRef`.
4. **Serialization Grammar**: Patch save/load token grammar (`SAVE_PROP`, `LOAD_PROP`) with UID stability.
