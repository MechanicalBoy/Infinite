# J cables.gl: dossier

Status: done 2026-10-13 from bundled Electron archive `app.asar` in `/Applications/cables.app`. Zero decompilation. Lint: `python3 tools/re-survey/diff.py lint docs/plans/re-survey/dossiers/J.md`

## 1. What it is

- Complete architectural deconstruction of cables.gl desktop standalone application (version bundled in `/Applications/cables.app`).
- Reference app: cables.gl (Tier 1 direct competitor C2 in registry). Proprietary commercial / web creative coding tool.
- Data source: Bundled Electron archive `/Applications/cables.app/Contents/Resources/app.asar` (31,029 files, 8.3 MB JSON directory header).
- Scope: 1,836 active operators (1,687 base operators across 15 core namespaces, plus 149 modern extension operators) and 13,422 dataflow ports.

## 2. Method

- Tools run: `python3 tools/re-survey/cables_extractor.py run` (passes `--self-test`).
- Clean-room invariant: Operator layout JSON and port schema inspection only. No proprietary compiled binary reverse-engineered.
- Output artifacts: Machine dataset `~/re-output/cables/cables_all_ops.json` (2.7 MB) and markdown catalog `~/re-output/cables/cables_all_ops.md` (5.9 KB). Architectural blueprint at `docs/plans/re-survey/CABLES-ALL-OPS-MAPPING.md`.

## 3. Pillar map

- P7: 3D, Shaders & Render Pipeline (`Ops.Gl`: 612 operators). Primitives (Cube, Sphere, Torus, Cylinder, Teapot), procedural shaders (CustomShader, ShaderModifier, PBRMaterial, MatCap), textures (RenderToTexture FBO, Bloom, Blur, Displace, Feedback), and camera matrices. Infinite's 3D and Compositing categories cover these with OpenGL rendering.
- P7: Buffers, Arrays & GPU Instancing (`Ops.Array`: 224 operators). ArrayMath, ArrayFilter, PointArray, and InstancedMesh driving GPU instanced draw calls from flat arrays. Infinite's Instance on Points renders 10,000 instanced cubes and encodes at 60.2 fps 4K H264 (dossier D).
- P2: Global Modulation & Animation (`Ops.Anim`: 99 operators). LFOs (`Ops.Anim.LFO_v3`), Bezier easing curves, smoothers, keyframe tracks. In Infinite any modulator can drive audio, visual and 3D params; values are sampled per frame and ramped per sample (not audio-rate).
- P1: Device I/O & Live Interaction (`Ops.Devices`: 62 operators). MIDI In/Out, Gamepad, WebMidi, Webcam, and Motion sensors. Infinite has MIDI in (MIDI Notes, MIDI CC), MIDI Out, Video In, NDI In/Out and Hand/Face/Pose Track.
- P5: Audio Quality & WebAudio (`Ops.WebAudio`: 37 operators). Basic WebAudio oscillator, filter, and gain nodes. Infinite leads with a native audio engine, 28 audio effects, 17 synths, and VST3/AU plugin hosting.
- P4: Field & Custom Shaders. cables.gl provides `Ops.Gl.Shader.CustomShader` where users write raw GLSL strings. Infinite provides the Field language, which compiles to GLSL for pixels (`src/core/field/GlslBackend.cpp`) and to bytecode for a CPU VM (`src/core/field/FieldVM.cpp`), with audio and geometry inputs.

## 4. Comparison

| Pillar | Their feature | Infinite equivalent | Status | Outcome | Evidence |
|---|---|---|---|---|---|
| P7 | WebGL 3D meshes, procedural shaders & textures (612 ops) | `src/nodes/Geometry3DNodes.h` | parity | ignore: 86 3D nodes, Render 3D, Material; Infinite covers meshes, textures, materials and lighting natively | `src/nodes/Geometry3DNodes.h` |
| P7 | GPU InstancedMesh rendering from flat arrays | none | lead | ignore: Instance on Points; 10,000 instanced cubes render + encode at 60.2 fps 4K H264 (Block D); cables.gl not measured | `dossiers/D.md` |
| P4 | CustomShader (raw GLSL in-browser shader editor) | `src/core/field/GlslBackend.cpp` | lead | ignore: FieldPixel (Field → GLSL; bytecode VM on CPU); one language with audio and modulation inputs across pixels, audio and geometry | `src/core/field/GlslBackend.cpp` |
| P2 | Anim & LFO modulation operators (99 ops) | `src/nodes/ModulatorNodes.h` | parity | ignore: 30 modulators; LFOs, envelopes, smoothing, random, curves covered | `src/nodes/ModulatorNodes.h` |
| P5 | WebAudio synthesis and basic filter nodes (37 ops) | `src/audio/EffectDefs.cpp` | lead | ignore: 28 audio effects, 17 synths, VST3/AU Plugin; a full audio engine against WebAudio basics | `src/audio/EffectDefs.cpp` |
| P7 | Rapier 3D rigid body dynamics extension (16 ops) | none | gap | ignore: Cloth, Particle System; no rigid body solver; revisit on evidence | `~/re-output/cables/cables_all_ops.json` |
| P7 | GPU Particles with vector fields extension (18 ops) | `src/nodes/SimulationNodes.h` | gap | ignore: Particle System: gravity, drag, turbulence; noise turbulence only, no user vector field | `src/nodes/SimulationNodes.h` |
| P1 | Export to Web / Standalone HTML bundle | `src/core/HeadlessJob.cpp` | gap | ignore: Infinite targets native macOS/Windows/Linux AV workstation performance | `docs/plans/re-survey/dossiers/D.md` |

## 5. Measurements

- Total active operators cataloged: 1,836 (1,687 base + 149 extensions).
- Total dataflow ports: 13,422 (9,546 inputs, 3,876 outputs).
- Top namespaces: `Ops.Gl` (612), `Ops.Array` (224), `Ops.Html` (119), `Ops.String` (96), `Ops.Math` (95), `Ops.Graphics` (69), `Ops.Devices` (62), `Ops.WebAudio` (37).
- Reproduce command: `python3 tools/re-survey/cables_extractor.py run --out ~/re-output/cables/cables_all_ops.md`.

## 6. Outcomes

- Quests: none (within 5-quest cap).
- Perf targets: none (cables.gl render speed not measured).
- Quality gaps: none; gaps (rigid body, user vector fields, L-systems) are ignored until a user asks.

## 7. Storage

- Written to ~/re-output:
  - `~/re-output/cables/cables_all_ops.json` (2.7 MB)
  - `~/re-output/cables/cables_all_ops.md` (5.9 KB)
- Deleted: zero temporary files retained; clean-room memory state verified.
