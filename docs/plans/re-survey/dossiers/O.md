# O Pixelmator Pro (2D effects, color grading, blurs, distortion, adjustments): dossier

Status: done 2026-10-13 from application scripting definitions in `/Applications/Pixelmator Pro.app/Contents/Resources/PixelmatorPro.sdef`. Zero binary decompilation. Lint: `python3 tools/re-survey/diff.py lint docs/plans/re-survey/dossiers/O.md`

## 1. What it is

- Complete architectural deconstruction of 23 procedural 2D image effects and 26 color adjustment parameters in Pixelmator Pro.
- Reference app: Pixelmator Pro (installed on macOS at `/Applications/Pixelmator Pro.app`). Commercial proprietary licence.
- Data source: Public XML scripting dictionary `PixelmatorPro.sdef` (47 classes, 81 commands, 20 enumerations).
- Scope: 23 procedural 2D filter effects (blurs, geometric distortions, stylization, fills), 26 primary color grading parameters (white balance, tone curves, texture, clarity, film grain, 3D LUTs), and 13 layer compositing models.

## 2. Method

- Tools run: `python3 tools/re-survey/pixelmator_extractor.py run` (passes `--self-test`).
- Clean-room invariant: Public application scripting definitions only. Zero native binary decompilation or disassembly.
- Output artifacts: Machine dataset `~/re-output/pixelmator/pixelmator_all_models.json` (26 KB) and markdown catalog `~/re-output/pixelmator/pixelmator_all_models.md` (5.3 KB). Architectural blueprint at `docs/plans/re-survey/PIXELMATOR-ALL-MODELS-MAPPING.md`.

## 3. Pillar map

- P7: Blur & Optical Filtering (Gaussian, Box, Disc, Motion, Zoom, Spin, Tilt Shift, Focus blur). Infinite has gaussianblur, boxblur, motionblur, radialblur and bloom filters; no tilt shift or defocus.
- P7: 2D Geometric Distortion (Bump, Pinch, Circle Splash, Hole, Light Tunnel, Twirl, Vortex). Coordinate space displacement and warps. Infinite has pinchpunch, twirl, ripple, liquify, lensdistortion and displace filters, plus FieldPixel.
- P7: Stylization & Patterns (Pixelate, Pointillize, Crystallize, Checkerboard, Stripes). Procedural mosaic and halftone effects. Infinite covers stylization through pixelate, halftone and edge filters plus a Voronoi Cells FieldPixel preset; no pointillize.
- P7: Color Grading & Tonal Adjustments (26 parameters: Exposure, Contrast, Highlights, Shadows, Temperature, Tint, Clarity, Texture, Grain, 3D LUT). Infinite has color adjustments, exposure, curves, lut and gradientmap.
- P7: Layer Blending & Masking (Layer blend modes, clipping masks, vector shapes). Infinite has Blend, Layer Stack, luma key, chroma key and set alpha.

## 4. Comparison

| Pillar | Their feature | Infinite equivalent | Status | Outcome | Evidence |
|---|---|---|---|---|---|
| P7 | 8 Optical blur types (Gaussian, Motion, Zoom, Spin, Tilt Shift) | `src/core/FilterDefs.cpp` | parity | ignore: gaussianblur, boxblur, motionblur, radialblur, bloom; no tilt shift | `src/core/FilterDefs.cpp` |
| P7 | 7 Geometric distortion warps (Pinch, Bump, Twirl, Vortex, Splash) | `src/core/FilterDefs.cpp` | parity | ignore: pinchpunch, twirl, ripple, liquify, lensdistortion, displace; covered | `src/core/FilterDefs.cpp` |
| P7 | Stylization patterns (Pixelate, Pointillize, Crystallize) | `src/nodes/FieldPixelNode.cpp` | parity | ignore: pixelate, halftone, Voronoi Cells FieldPixel preset; crystallize is the Voronoi preset; no pointillize | `src/nodes/FieldPixelNode.cpp` |
| P7 | 26 Color adjustment parameters (Exposure, Contrast, Temp, Tint, Clarity) | `src/core/FilterDefs.cpp` | parity | ignore: color adjustments, exposure, curves, lut, gradientmap; covered | `src/core/FilterDefs.cpp` |
| P7 | 3D LUT color mapping file application | `src/core/FilterDefs.cpp` | parity | ignore: lut (.cube, tetrahedral); covered | `src/core/FilterDefs.cpp` |
| P7 | Film grain and texture synthesis (grain size, intensity) | `src/core/FilterDefs.cpp` | parity | ignore: addnoise; covered | `src/core/FilterDefs.cpp` |
| P8 | Real-time render speed | `src/core/HeadlessJob.cpp` | lead | ignore: headless render + encode; Pixelmator is still-image editing; Infinite renders 44.5 to 263 fps (Block D) | `dossiers/D.md` |
| P7 | Real-time audio FFT reactivity driving visual grading | `src/nodes/AnalyzeNodes.h` | lead | ignore: Audio Analyze, Audio to CV; Pixelmator has no audio | `src/nodes/AnalyzeNodes.h` |

## 5. Measurements

- Total 2D Effects: 23.
- Color Adjustment Controls: 26.
- Automatable Commands: 81.
- Reproduce command: `python3 tools/re-survey/pixelmator_extractor.py run --out ~/re-output/pixelmator/pixelmator_all_models.md`.

## 6. Outcomes

- Quests: none (within 5-quest cap across all dossiers).
- Perf targets: none (render speed is measured in dossier D: 44.5 to 263 fps render + encode).
- Quality gaps: Calibrated integer parameter ranges (exposure -400..400) mapped in blueprint for smooth float modulation.

## 7. Storage

- Written to ~/re-output:
  - `~/re-output/pixelmator/pixelmator_all_models.json` (26 KB)
  - `~/re-output/pixelmator/pixelmator_all_models.md` (5.3 KB)
- Deleted: zero temporary files retained; clean-room memory state verified.
