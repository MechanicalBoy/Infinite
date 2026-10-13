# Pixelmator Pro — Complete 2D Image Effects & Color Grading Architecture Mapping

> **Clean Room Invariant**: Extracted exclusively from public application scripting definitions (`PixelmatorPro.sdef`). Zero binary decompilation or disassembly. Complete machine-readable catalog available in `~/re-output/pixelmator/pixelmator_all_models.json` (26 KB) and `~/re-output/pixelmator/pixelmator_all_models.md` (5.3 KB).

---

> **Infinite side checked 2026-10-13** against the node census (`build/census/census.json`) and src/; run `python3 tools/re-survey/diff.py claims` after editing. Competitor numbers come from `~/re-output/`; competitor prose is hand-written.

## 1. Executive Summary & Inventory Scale

| Metric | Pixelmator Pro | Infinite Equivalent / Advantage |
|---|---|---|
| **Procedural 2D Effects** | **23 Native Effects** | 64 Compositing + Effects nodes |
| **Color Adjustment Controls** | **26 Adjustment Parameters** | `color adjustments`, `exposure`, `Curves`, `lut` nodes |
| **Document Commands** | **81 Automations** | Node graph evaluation pipeline |
| **Execution Domain** | Offline photo editing & raster/vector design | Live AV instrument; 44.5-263 fps render+encode on the dossier D bench |
| **Audio Reactivity** | None (static graphic edits) | Audio and modulators drive effect params (frame-rate values) |

---

## 2. 2D Effect Categories Breakdown

### 2.1 Blur & Optical Focus (8 Effects)
- **Gaussian, Box, Disc Blur**: Standard spatial low-pass filtering.
- **Motion Blur**: Directional blur along an angle vector.
- **Zoom Blur**: Radial expansion blur from a defined focus point.
- **Spin Blur**: Rotational angular blur around a center origin.
- **Tilt Shift & Focus**: Depth-of-field emulation with customizable transition bands.
- **Infinite**: `bloom`, `gaussianblur`, `boxblur`, `motionblur`, `radialblur` nodes run as GPU passes; no defocus/bokeh blur (gap).

### 2.2 Geometric & Spatial Distortion (7 Effects)
- **Bump & Pinch**: Radial lens convex/concave magnification.
- **Circle Splash & Hole**: Radial wave displacement and aperture cutouts.
- **Light Tunnel**: Perspective depth distortion tunnel.
- **Twirl & Vortex**: Rotational angular vortex displacement.
- **Infinite**: `lensdistortion`, `transform`, `displace`, `liquify`, `twirl`, `pinchpunch`, `ripple` and `FieldPixel` warp coordinates on the GPU.

### 2.3 Stylization & Halftone Patterns (5 Effects)
- **Pixelate**: Downsampled block resolution mosaicing.
- **Pointillize & Crystallize**: Voronoi/Delaunay cellular point and polygon mosaic tiles.
- **Checkerboard & Stripes**: Procedural geometric coordinate stripes and grids.
- **Infinite**: `pixelate`, `halftone`, `edge sobel`, `posterize`, `kaleidoscope` nodes, and a Voronoi Cells preset in FieldPixel (`src/nodes/FieldPixelNode.cpp`); no pointillize filter (gap).

### 2.4 Color Grading & Adjustments (26 Parameters)
- **White Balance**: `temperature` (-200..200), `tint` (-200..200).
- **Tone & Light**: `exposure` (-400..400), `contrast` (-200..200), `highlights` (-100..100), `shadows` (-100..100), `brightness` (-200..200), `black point` (-200..200).
- **Color & Vibrance**: `hue` (-100..100), `saturation` (-100..100), `vibrance` (-200..200).
- **Detail & Texture**: `texture` (-100..100), `clarity` (-100..100), `sharpen` (0..100), `sharpen radius` (0..100).
- **Styling**: `fade` (0..200), `sepia`, `invert`, `black and white`, `custom lut` (3D Cube LUT).
- **Film Characteristics**: `grain` (0..100), `grain size` (0..400), `vignette` softness/exposure/black point.
- **Infinite**: `color adjustments`, `exposure`, `Curves` and `lut` nodes.

---

## 3. Strategic Architectural Takeaways

1. **Parameter Ranges & Normalization**: Pixelmator Pro exposes calibrated integer ranges (e.g. exposure -400 to +400, contrast -200 to +200). Infinite's `color adjustments` node uses its own float ranges; a range map is needed if presets are ever imported.
2. **Real-Time Video vs Still Image**: Pixelmator Pro edits stills; Infinite runs the same kinds of adjustment continuously on live video, camera input and 3D renders.
