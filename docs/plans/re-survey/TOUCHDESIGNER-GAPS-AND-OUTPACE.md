# Outpacing TouchDesigner: Visual & AV Gaps & Roadmap

Companion document to `docs/plans/re-survey/dossiers/H.md` and `docs/plans/re-survey/README.md`.  
Generated from the extraction of TouchDesigner 2025.32820 (`tools/re-survey/touchdesigner_map.py`) vs Infinite's node graph.

---

## 1. Executive Census

From `~/re-output/touchdesigner/touchdesigner_map.md`:
- **TouchDesigner Operators Cataloged**: **483 operators** across 7 families:
  - **TOP** (Texture/2D): 93 operators
  - **CHOP** (Channel/Audio/Control): 112 operators
  - **SOP** (3D Surface Geometry): 90 operators
  - **POP** (GPU Point Cloud / Particles): 102 operators
  - **MAT** (Materials / Shading): 7 operators
  - **DAT** (Tables, Text, Python): 51 operators
  - **COMP** (Components, Panels, 3D Scenes): 28 operators
- **Infinite (census, checked 2026-10-13)**: 319 node types: 3D 86, Compositing 37, Source 34, Effects 28, Modulators 30, AudioEffects 25, Notes 24, Synths 17, Utility 18, Macros 9, Prediction 8; plus the **Field language**.

---

## 2. Where Infinite Leads TouchDesigner

1. **Integrated audio (Lead)**:
   - TouchDesigner handles audio as CHOP channels; it is not a production audio engine.
   - Infinite has an audio engine on its own thread with latency compensation, 17 synths, 28 audio effects and VST3/AU hosting.
2. **User Programmability & Shaders (Field Language Lead)**:
   - In TouchDesigner, writing custom shaders (GLSL TOP) requires boilerplate code, setting up custom uniform bindings, and writing separate scripts.
   - In Infinite, the **Field language** (`FieldPixel`, `Field Modifier`, `Field Primitive`) is plain text with modulation inputs and no uniform wiring.
3. **Instancing (measured against Blender only)**:
   - Dossier D: 10,000 instanced cubes at 4K, up to 263 fps render+encode, about 300x Blender. No TouchDesigner instancing measurement yet.
4. **Resolution Paywall vs Openness**:
   - TouchDesigner Non-Commercial caps resolution at **1280x720** (commercial licenses cost $600 to $2,200).
   - Infinite is MIT and free, with no resolution cap; exports ProRes 4444 (with alpha) and H264. AV sync is measured by `av-sync-sweep`.

---

## 3. The 5 Key Gaps to Outpace TouchDesigner

To beat TouchDesigner across complex AV stage productions and interactive installations:

### Gap 1: Optical Flow GPU Motion Vectors (TOP)
* **TouchDesigner**: `OpticalFlow TOP` computes real-time 2D motion vector fields ($dx, dy$) from incoming live video frames on the GPU.
* **Why it matters**: Allows artists to move particles, smoke, and distortion based on human movement on camera.
* **Action for Infinite**: add a new `OpticalFlowNode` (Lucas-Kanade or Horn-Schunck GPU pass) following `new-compositing-node`.

### Gap 2: Time Machine / Temporal Pixel Mapping (TOP)
* **TouchDesigner**: `TimeMachine TOP` maintains a 30–60 frame texture ring buffer and scrubs the delay time of each individual pixel based on a grayscale control texture.
* **Why it matters**: Creates slit-scan video effects, fluid time displacement, and audio-reactive scanline time warps.
* **Action for Infinite**: add a new `TimeMachineNode` over a texture history ring (Trails/Feedback already keep one frame).

### Gap 3: Point Cloud Neighbor Search & Proximity (POP)
* **TouchDesigner**: POP operators calculate nearest-neighbor distances between points on the GPU, enabling proximity lines, flocking, and particle mesh triangulation.
* **Why it matters**: Essential for modern Plexus-style visual designs.
* **Action for Infinite**: add a new `ProximityLinesNode` with spatial hashing, following `new-geometry-node`.

### Gap 4: Curve Sweeping & Lathe (SOP)
* **TouchDesigner**: `Sweep SOP` and `Revolve SOP` turn 2D curves into 3D pipes, cables, and turned vases.
* **Action for Infinite**: add new `SweepAlongCurveNode` and `LatheNode` nodes, following `new-geometry-node` (Screw exists and covers part of lathe).

### Gap 5: Stage Lighting & Hardware Protocols (CHOP)
* **TouchDesigner**: Industry-standard DMX512, Art-Net, and sACN support for controlling stage lighting rigs.
* **Action for Infinite**: add a new `DMXOutputNode` over UDP Art-Net, next to OSC Send in `src/nodes/OscNodes.cpp`.
