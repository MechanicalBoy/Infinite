# cables.gl — Complete Operator Library & Architectural Mapping

> **Clean Room Invariant**: Extracted directly from bundled Electron application archive `/Applications/cables.app/Contents/Resources/app.asar`. Zero binary decompilation. Complete machine-readable catalog available in `~/re-output/cables/cables_all_ops.json` (2.7 MB) and `~/re-output/cables/cables_all_ops.md`.

---

> **Infinite side checked 2026-10-13** against the node census (`build/census/census.json`) and src/; run `python3 tools/re-survey/diff.py claims` after editing. Competitor numbers come from `~/re-output/`; competitor prose is hand-written.

## 1. Executive Summary & Inventory Scale

| Metric | cables.gl Desktop | Infinite Equivalent / Advantage |
|---|---|---|
| **Total Active Operators** | **1,836** (1,687 Base + 149 Modern Extensions) | 319 node types (census) + Field language |
| **Total Dataflow Ports** | **13,422** (9,546 Inputs, 3,876 Outputs) | Typed audio, image, geometry and modulation pins |
| **Primary Domain** | WebGL / WebGPU creative coding & interactive web graphics | Native desktop live AV instrument (macOS, Windows, Linux) |
| **Execution Engine** | JavaScript V8 event loop + WebGL/WebGPU shaders | Native C++ engine, OpenGL/Metal rendering, separate audio thread |
| **Performance Ceiling** | Browser V-Sync | No head-to-head measurement yet (dossier D measured Infinite vs Blender only) |

---

## 2. Operator Families & Architecture Blueprint

### 2.1 3D, Shaders & Render Pipeline (`Ops.Gl`: 612 Operators)
- **Geometry & Meshes**: Primitives (Cube, Sphere, Torus, Cylinder, Plane, Teapot, Lathe, Extrude), custom vertex buffers, and glTF/OBJ loaders.
- **Procedural Shaders & Materials**: BasicMaterial, Lambert, Phong, PBRMaterial, MatCap, CustomShader (with editable vertex/fragment GLSL ports), and ShaderModifier.
- **Textures & Post-Processing**: RenderToTexture (FBO), Blur, Bloom, ColorGrade, Vignette, ChromaticAberration, FeedbackTexture, NormalMap, and DisplaceTexture.
- **Infinite**: native shaders; Field Pixel kernels read modulation inputs without a JS bridge.

### 2.2 Buffers, Point Clouds & Instancing (`Ops.Array`: 224 Operators)
- **InstancedMesh**: GPU hardware instancing driving hundreds of thousands of transforms via flat Float32Arrays.
- **Point Clouds & Particle Arrays**: ArrayMath, ArrayFilter, ArraySort, ArrayInterpolate, and PointArray.
- **Infinite**: `Instance on Points`; 10,000 instanced cubes at 4K up to 263 fps render+encode on the dossier D bench. No cables.gl comparison measured.

### 2.3 Animation & Global Modulation (`Ops.Anim`: 99 Operators)
- **LFOs & Function Generators**: `Ops.Anim.LFO_v3` (Sine, Triangle, Saw, Square, Smooth Random, Perlin Noise with phase, frequency, and min/max clamps).
- **Timeline Curves & Splines**: Keyframe tracks, Bezier easing curves, smoothers, and decay followers.
- **Infinite Lead**: any modulator (LFO, Image Analyze, Prediction family) can drive audio params; values arrive per frame and are ramped per sample.

### 2.4 Device I/O & Sensors (`Ops.Devices`: 62 Operators)
- **MIDI & Gamepad**: MidiInput, MidiOutput, MidiCc, WebMidi, Gamepad, Keyboard, and Mouse.
- **Cameras & Webcams**: Webcam, Microphone, Motion sensors.
- **Infinite**: native MIDI and camera input (`Video In`, `MIDI Notes`, `MIDI CC`); latency not measured.

### 2.5 WebAudio Synthesis & Effects (`Ops.WebAudio`: 37 Operators)
- **Basic WebAudio Nodes**: Oscillator, BiquadFilter, Convolver, Gain, Panner, Analyser, and AudioBuffer.
- **Infinite Lead**: 28 audio effects, 17 synths (census) and VST3/AU hosting; WebAudio cannot host native plugins.

---

## 3. Modern Extension Ecosystem

| Extension Group | Operators | Capabilities | Infinite Strategic Response |
|---|---|---|---|
| **Rapier3d** | 16 | Rigid body physics, collision hulls, forces, impulses, gravity. | Gap: no rigid-body physics (Cloth and Particle System only). |
| **GlParticles** | 18 | GPU particles with noise vector fields, curl noise, and attractors. | Particle System + Field Modifier kernels. |
| **WebGpu** | 24 | WebGPU compute shaders, storage buffers, and compute passes. | Field kernels; no general compute node. |
| **Mediapipe** | 9 | FaceMesh (468 landmarks), hand skeleton, and pose detection. | Parity: Hand Track, Face Track, Pose Track modulators (Apple Vision, on-device). |
| **LSystem** | 3 | Procedural 3D fractal branching and plant generation. | Gap: no L-system node. |
| **SuperShapes** | 3 | Gielis 3D superformula parametric geometric curves and meshes. | Parity: `Supershape` and `Superellipse` nodes. |
| **ReactionDiffusion** | 3 | Gray-Scott chemical reaction-diffusion simulation textures. | Reaction Diffusion 2D compositing node (already native in Infinite). |
