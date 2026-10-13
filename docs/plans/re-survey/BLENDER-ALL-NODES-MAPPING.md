# Blender 5.1.0 — Complete Geometry, Shader, Compositor & Modifier Architecture Mapping

> **Clean Room Invariant**: Extracted exclusively from Blender's public runtime RNA API and headless node tree introspection (`/Applications/Blender.app/Contents/MacOS/Blender --background --python-expr`). Zero binary decompilation or GPL source inspection. Complete machine-readable catalog available in `~/re-output/blender/blender_all_nodes.json` (13 MB) and `~/re-output/blender/blender_all_nodes.md`.

---

> **Infinite side checked 2026-10-13** against the node census (`build/census/census.json`) and src/; run `python3 tools/re-survey/diff.py claims` after editing. Competitor numbers come from `~/re-output/`; competitor prose is hand-written.

## 1. Executive Summary & Inventory Scale

| Metric | Blender 5.1.0 | Infinite Equivalent / Advantage |
|---|---|---|
| **Total Procedural Operators** | **513 Operators** | 319 node types in the census (3D 86, Source 34, Compositing 37, Effects 28, audio/notes/modulation the rest) + Field language |
| **Geometry Nodes** | **245 Nodes** (1,027 data sockets) | Procedural 3D nodes + Field Modifier kernels |
| **Shader Nodes** | **99 Nodes** (BSDFs, Textures, Shaders) | Material node (Principled BSDF) + FieldPixel kernels |
| **Compositor Nodes** | **86 Nodes** (Post-processing & Grading) | 64 Compositing + Effects nodes |
| **Object Modifiers** | **83 Modifiers** (Generate, Deform, Physics) | 3D modifier nodes (Extrude, Subdivide, Solidify, Screw, Twist, Mirror, Array, Cloth, Ocean, Particle System) |
| **Execution Domain** | Offline rendering / animation DCC suite | Real-time live instrument; render+encode 44.5-263 fps on the dossier D bench |
| **Render Speed Benchmark** | Baseline Cycles / EEVEE | **70x to 300x faster renders** (dossier D render bench) |
| **Audio-Visual Interactivity** | Static graph / bake required | Audio and MIDI drive visual params live through modulation (frame-rate values) |

---

## 2. Geometry Nodes Architecture (245 Operators)

Blender's Geometry Nodes system evaluates attributes across mesh/curve domains (Point, Edge, Face, Corner, Spline, Instance). Infinite has procedural C++ geometry nodes and the **Field language** (Field Modifier, Field Primitive); it has no general attribute-domain system.

### 2.1 Mesh Operations (42 Nodes)
- **Topological Operators**: Extrude Mesh, Subdivide Mesh, Triangulate, Dual Mesh, Flip Faces, Mesh to Curve, Mesh to Points, Split Edges, Edge Paths to Selection.
- **Boolean & Surface Ops**: Mesh Boolean (Intersect, Union, Difference), Convex Hull, Separate Geometry, Delete Geometry, Merge by Distance.
- **Infinite**: procedural mesh nodes (`Extrude`, `Subdivide`, `Solidify`, `Array`, `Mirror`, `Decimate`, `Merge by Distance`, `Delaunay Mesh`, `Voronoi Cells`); no Remesh (gap).

### 2.2 Curve & Splines (38 Nodes)
- **Spline Generators & Evaluators**: Curve to Mesh, Resample Curve, Fillet Curve, Trim Curve, Subdivide Curve, Sample Curve, Spline Length, Set Spline Type (Bezier, NURBS, Poly).
- **Infinite**: `Curve`, `Path`, `Tube` and `Helix` nodes; no curve resample/offset/fillet operators (gap).

### 2.3 Points & Cloud Distribution (24 Nodes)
- **Point Clouds**: Distribute Points on Faces (Random, Poisson Disk), Distribute Points in Volume, Distribute Points in Grid, Points to Vertices, Points to Curves, Points to Volume.
- **Infinite Lead**: `Distribute Points in Grid`, `Distribute Points on Faces`, `Image to Points`, and `Mesh to Points` nodes feed directly into Infinite's particle and instancing pipelines.

### 2.4 Instances & Duplication (19 Nodes)
- **Instancing Engine**: Instance on Points, Realize Instances, Rotate Instances, Scale Instances, Translate Instances, Instances to Points, Geometry to Instance.
- **Infinite Lead**: `Instance on Points`; the dossier D bench renders 10,000 instanced cubes at 4K at up to 263 fps (render + encode).

### 2.5 Attribute & Field Transfer (36 Nodes)
- **Attribute Processing**: Capture Attribute, Store Named Attribute, Attribute Statistic, Blur Attribute, Transfer Attribute, Raycast, Sample Index, Sample Nearest.
- **Infinite Lead**: the **Field language** (`Field Primitive`, `Field Modifier`) evaluates bare-name expressions (`P.x`, `P.y`, `N`, `Cd`) per vertex with audio and modulation inputs.

---

## 3. Shader Nodes Architecture (99 Operators)

Blender's material graph compiles into Cycles SVM / OSL and EEVEE GLSL shaders.

### 3.1 Surface Shaders & BSDFs
- **Core Models**: Principled BSDF, Glass BSDF, Glossy BSDF, Subsurface Scattering, Diffuse BSDF, Emission, Hair BSDF, Toon BSDF, Sheen BSDF, Volume Scatter, Volume Absorption.
- **Infinite Parity**: Infinite's unified `Material` node includes the complete Principled BSDF parameter set: Metallic, Roughness, Opacity, Emission, IOR, Transmission, Specular, Clearcoat, Subsurface, Sheen, Iridescence, Anisotropy, Dispersion, and Normal Bump.

### 3.2 Procedural Textures & Patterns
- **Noise & Geometric Generators**: Perlin Noise, Voronoi (F1, F2, Distance to Edge), Musgrave (fBm, Multifractal, Ridged Multifractal), Wave Texture, Brick, Checker, Magic, White Noise, Gradient.
- **Infinite Lead**: Infinite's `Noise`, `Ramp`, `Texture`, `Reaction Diffusion`, and `FieldPixel` nodes evaluate these patterns in real-time GLSL/Metal shaders with direct beat-synchronized phase modulation.

---

## 4. Compositor Nodes Architecture (86 Operators)

Blender's Compositor operates across viewport real-time compositing and offline rendering passes.

### 4.1 Filters & Optical Effects
- **Image Filters**: Glare (Bloom, Streaks, Ghost, Fog Glow), Blur (Fast Gaussian, Bokeh), Bilateral Blur, Lens Distortion, Defocus, Pixelate, Directional Blur.
- **Infinite Parity**: `bloom`, `gaussianblur`, `lensdistortion`, `edge sobel`, `Feedback` and `Trails` nodes.

### 4.2 Color Grading & Correction
- **Color Tools**: Color Balance (Lift, Gamma, Gain / ASC-CDL), Hue/Saturation/Value, RGB Curves, Brightness/Contrast, Exposure, Tone Map, Invert, Posterize.
- **Infinite**: `color adjustments`, `exposure`, `Curves`, `lut` and `lookup` nodes.

### 4.3 Matte & Keying
- **Matte Extraction**: Keying (Chroma/Color Key), Difference Key, Color Spill, Channel Key, Inpaint, Dilate/Erode, Cryptomatte.
- **Infinite Parity**: `chroma key`, `luma key`, `alpha levels` and `Remove Background` nodes for live keying.

---

## 5. Object Modifiers (83 Modifiers)

Blender's stack modifiers represent non-destructive geometry evaluation.

| Category | Count | Key Blender Modifiers | Infinite Equivalent / Advantage |
|---|---|---|---|
| **Generate** | 22 | Array, Bevel, Boolean, Decimate, Mirror, Remesh, Screw, Solidify, Subsurf, Triangulate, Wireframe | `Array`, `Mirror`, `Solidify`, `Screw`, `Subdivide`, `Union`/`Difference`/`Intersect`, `Triangulate`, `Wireframe`, `Decimate`; no Bevel, Remesh |
| **Deform** | 17 | Displace, Curve, Simple Deform (Twist, Bend, Taper, Stretch), Smooth, Shrinkwrap, Warp, Wave | `Displacement`, `Twist`, `Wrap`, `Smooth`, `Audio Displacement`; no Shrinkwrap or Bend/Taper |
| **Physics** | 10 | Cloth, Collision, Dynamic Paint, Fluid, Ocean, Particle System, Soft Body | `Cloth`, `Ocean`, `Particle System`; no fluid, soft body or collision |

---

## 6. Strategic Takeaways for Infinite

1. **Procedural geometry coverage**: Infinite has the common generate/deform modifiers; missing are Bevel, Remesh, Shrinkwrap, curve operators and an attribute-domain system. No percentage was measured.
2. **Real-time vs offline**: dossier D measured 68x-300x higher throughput than Blender on its render bench scenes (render + encode).
3. **The Field advantage**: Field kernels replace node chains with short expressions.
