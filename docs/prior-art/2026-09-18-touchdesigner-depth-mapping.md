## Problem
How does TouchDesigner handle depth specially in its compositing pipeline, and what does Infinite already have to build a "depth mapping" node on top of?

TD is closed-source; there is no repo to diff, so this report leans on Derivative's own docs/forum plus one public MiDaS integration, cross-checked against Infinite's actual node code.

## Findings by question

### 1. Depth as a render pass/buffer
- Render TOP exposes a **Depth Buffer Format** parameter: `24-Bit Fixed-Point` or `32-Bit Floating-Point`. There's also **Draw Depth Only** (skip color entirely) and **Linear Camera-Space Depth** (only meaningful with the 32-bit float format).
- Default depth is **non-linear projection Z**: 0 at the near plane, 1 at the far plane, "90% of values in the closest 10% of the distance" — a forum expert explicitly calls this "not the camera Z-Depth, it's the projection z-depth." Turning on Linear Camera-Space Depth (float32 only) switches to true linear camera-space distance (0 at camera, increasing outward).
- A separate **Depth TOP** operator pulls the depth buffer out of a Render TOP into an ordinary greyscale TOP (replicated to RGB, alpha=1), at 24-bit fixed or 32-bit float depending on the source format. Precision advice: re-quantize through a Level TOP at 16/32-bit if you need to avoid banding.
- Sources: [Render TOP](https://docs.derivative.ca/Render_TOP), [Depth TOP](https://docs.derivative.ca/Depth_TOP), [forum: Z-Depth? Help?](https://forum.derivative.ca/t/z-depth-help/1047) (read in full).

### 2. Depth-aware compositing
- **There is no dedicated per-pixel depth-test blend mode in TD's Composite TOP.** Verified by fetching the full parameter reference: 42 operations (Add, Atop, Over, Screen, Multiply, Difference, Hue/Saturation/Color/Luminosity, Xor, "Z Film", "Y Film", etc.) — none documented as depth-buffer-driven Z-compare compositing. "Z Film"/"Y Film" read as film-stock-style blend names, not depth ops (unconfirmed meaning, doc gives no description).
- TD's real answer to depth-correct layering is **not a 2D compositing trick — it's 3D**: put multiple pieces of geometry in the *same* Render TOP/scene (same camera, shared depth buffer, hardware depth test via `depthTest`/z-buffer), so draw order doesn't matter, GPU Z-test resolves occlusion per pixel. Cross-Render-TOP "2D over 2D" depth compositing (compare two separately-rendered Depth TOPs with a Switch/Composite mix) is a documented workaround pattern, not a first-class op — the forum thread treats it as DIY (extract Depth TOP from each render, use as an alpha mask into a Composite/Switch), not a built-in mode.
- Sources: [Composite TOP](https://docs.derivative.ca/Composite_TOP) (full op list fetched and read), [forum thread above].

### 3. Depth sensor input nodes
- **Kinect Azure TOP**: depth output = single-channel 32-bit float image, meters from camera. Has a **Point Cloud** output mode: 32-bit float RGBA TOP (512×512 NFOV / 1024×1024 WFOV) where RGB channels directly encode world-space XYZ per pixel — i.e., TD does the unprojection *inside the sensor TOP itself*, not as a separate step. Kinect Azure CHOP pulls skeleton/body tracking off the same depth stream.
- **RealSense TOP**: outputs Color / Depth / Raw Depth / IR. `Depth` is re-ranged 0..1 against a user-set "Max Depth" (meters); `Raw Depth` is the SDK's native units. No native TOP point-cloud output mode documented (unlike Kinect Azure) — community C++ plugins (`DBraun/RealSenseTOP`, `kamindustries/SenseTOP`) exist to add point-cloud output; USB3 required for full resolution.
- Sources: [Kinect Azure TOP](https://docs.derivative.ca/Kinect_Azure_TOP), [Point Clouds guide](https://derivative.ca/UserGuide/Point_Clouds), [RealSense TOP](https://docs.derivative.ca/RealSense_TOP), [DBraun/RealSenseTOP](https://github.com/DBraun/RealSenseTOP).

### 4. Depth-to-geometry
- Two paths, both real and documented:
  - **Point cloud, GPU-only**: sensor TOP (or any depth+color TOP pair) → Point Cloud TOP-style XYZ-in-RGB texture → Render TOP with **instancing** (point-per-instance sprite rendering) — no CPU round trip. `Point Transform TOP` applies 3D transforms/normalization on that XYZ texture before rendering.
  - **SOP path**: `Point File In`/`Point File Select` SOPs import point-cloud formats (PLY/PTS/etc.) as real geometry points, or a manual `SOP to CHOP → CHOP to TOP` bounce turns SOP-domain points into a square XYZ texture for GPU use.
- **The unproject math itself is packaged as a palette component, `depthProjection` COMP**: "uses the given camera intrinsic properties to project a 2D depth map image into a 3D point cloud," output as a float texture for instanced rendering. Exposes: depth interpretation (Z-depth vs. radial distance-to-point, i.e. LiDAR-style), input/output depth range remap, and camera intrinsics either as horizontal-FOV+aspect or explicit normalized focal length (Fx,Fy) + principal point (Cx,Cy) — this is the standard `depth * inverse(K)` / inverse-projection-matrix unproject, exposed as parameters rather than requiring the user to write GLSL.
- Displacement-mapping path (heightmap, not full unproject): Phong MAT height/displacement input takes any TOP (including a Depth TOP) as a per-vertex/per-texel displacement source in a GLSL vertex shader (`TDCreateTBNMatrix()` helper for tangent/bitangent/normal recompute after displacement).
- Sources: [depthProjection COMP](https://docs.derivative.ca/Palette:depthProjection), [Point Clouds guide](https://derivative.ca/UserGuide/Point_Clouds), [Owen Hindley — Depth Scatter Rendering in TD](https://www.owenhindley.co.uk/blogposts/depth-scatter/).

### 5. Monocular ML depth estimation
- No first-party TD depth-estimation TOP exists in the docs indexed. The real-world pattern is third-party: **`Jxke/midas-touchdesigner`**, a public `.tox` component wrapping MiDaS (DPT Hybrid / DPT Swin2 Tiny / MiDaS-small, all `.onnx`) via ONNX Runtime, with an "Install Dependencies" setup step and "Load MiDaS Model" runtime button; input is any video/image TOP, output is a greyscale relative-depth TOP. A PyTorch→ONNX conversion script ships with it for custom models. This is the closest TD analog to Depth Anything-style monocular estimation; it is community-built, not Derivative-shipped.
- Sources: [Jxke/midas-touchdesigner](https://github.com/Jxke/midas-touchdesigner) (README fetched).

### 6. Other special depth handling
- **Depth of field**: documented pattern is Depth TOP → Level TOP (remap near/far range) → drive a **Luma Blur TOP** (blur amount masked by depth) mixed with the sharp render; farther-from-focus pixels get more blur radius. No dedicated "DOF TOP"; it's Depth TOP + Level TOP + Blur TOP + Composite, composed by hand.
- **Fog**: not found as a documented dedicated TOP; typically done as a GLSL MAT/pixel shader term using camera-space depth (same Depth TOP or a custom varying) to fade toward a fog color — inferred from the same Depth TOP building blocks, not independently verified with a doc page.
- **Order-independent transparency / depth peeling**: not documented as a built-in TD feature. TD's transparency story is the ordinary GPU depth-test + manual sort (Geometry COMP render order / disable depth write for transparent passes), the same limitation most real-time engines have; no evidence TD ships OIT/depth-peeling.

## Patterns across sources
- TD's core move: **depth is just another single-channel TOP**, produced once (Render TOP/depth sensor) and consumed by ordinary 2D TOPs (Level, Blur, Composite) or fed back into 3D (Point Cloud, displacement, `depthProjection`). There is no special "depth-typed" pin — it's convention, not a distinct data type.
- **True per-pixel Z-correct compositing only exists inside a single 3D scene** (shared depth buffer + GPU depth test). Cross-layer 2D "Z-compositing" is a DIY pattern (extract two Depth TOPs, threshold/compare by hand), not a built-in Composite TOP mode — this directly answers the user's core question: TD does *not* have a magic "Depth" blend mode; it pushes users back into 3D for correctness.
- Depth sensors normalize on **32-bit float, meters, near/far-driven range remap**, and the better ones (Kinect Azure) do the intrinsics-based unprojection **on-device/in-node**, hiding the math from the user; the RealSense TOP doesn't, leaving point-cloud construction to community plugins.
- ML depth estimation in the TD ecosystem is ONNX-Runtime-based and community-maintained (MiDaS), matching Infinite's own ONNX Runtime dependency (`RemoveBgNode` already proves the pattern: background worker thread, latest-only request queue, GPU readback → inference → texture write-back).

## Infinite codebase pass (what's already there)

| Capability | File(s) | State |
|---|---|---|
| GPU depth buffer in a render node | `src/nodes/Geometry3DNodes.h/.cpp` (`Render3DNode`) | Exists internally: `mDepthBuffer`/`mMsDepth` renderbuffers, `GL_DEPTH_COMPONENT24`, hardware depth test (`depthTest` param), MSAA depth resolve. **Not exposed as an output texture** — `GetOutputTexture()` only returns `mColorTex`; no depth pin, no Depth-TOP equivalent. |
| Shadow depth pass (separate) | `Geometry3DNodes.cpp` (shadow map path, ~line 989-1006) | A second, independent depth-only FBO/texture already exists for shadows (`GL_DEPTH_COMPONENT24`, hardware PCF comparison sampler) — proves the codebase already knows how to build and sample a standalone depth texture; just not wired to the main color output. |
| Camera/projection math | `Render3DNode` params (`fov`, `orthoHeight`, `nearPlane`, `farPlane`, `camDistance`, `camAzimuth/Elevation`, `projection` perspective/ortho) + presumed `CameraNode` | Perspective/ortho projection and near/far already parametrized per-node; the raw projection matrix build is internal (not grepped further) but the inputs `depthProjection` COMP would need (FOV, near/far) already exist as node params. |
| Compositing blend modes | `src/core/BlendModes.h/.cpp`, `src/nodes/BlendNode.h/.cpp`, `src/nodes/LayerStackNode.h/.cpp` | 32 Photoshop-style RGB blend modes (Normal…Anti-Erase) implemented as shared GLSL (`kBlendGLSL`) consumed by `BlendNode` (2-input) and `LayerStackNode` (4-input). **No depth input pin on either — pure RGBA-in/RGBA-out, matching TD's own gap** (no native depth-test Composite mode either). This is the natural hook point for a depth-compare blend mode, following the same `ModeIndex`/GLSL-branch pattern `BlendModes.cpp` already uses. |
| Point cloud data model | `src/nodes/PointDistributionNodes.h/.cpp`, `IGeometrySource::GetPointCloud()`/`PointCloudRevision()` | Real, general point-cloud interface already exists and is already consumed by `Render3DNode` (sprite rendering: `spriteShape` circle/square, `spriteSizeMode` world/screen). A depth-to-point-cloud node would produce a `std::vector<Particle>` and plug straight into this existing consumer — no new rendering path needed, unlike TD where point-cloud instancing has to be hand-wired per network. |
| Texture-driven geometry displacement | Not found | Grep of `Geometry3DNodes.*`/`GeometryOpNodes.*` for a height/displacement-from-texture path came up empty in this pass (not exhaustively swept — flagged as inference, needs `codebase-navigation` follow-up before design). |
| Camera/webcam sensor input node | `src/nodes/VideoInNode.h/.cpp` (+ `src/platform/linux/CameraLinux.cpp`) | Live camera source node exists (`Platform::CameraHandle`, device enumeration, resolution presets, mirror). This is the exact pattern a depth-sensor node (Kinect Azure/RealSense) should mirror: `Platform::` abstraction + device list + `CookIfNeeded` texture upload — but it is RGB-only today, no depth stream, no per-OS depth SDK binding. |
| ONNX inference node pattern | `src/nodes/RemoveBgNode.h/.cpp` | Existing production pattern for GPU-readback → background-thread ONNX/Vision inference → paired-frame texture composite, with a latest-only request queue (exactly what a MiDaS/Depth-Anything monocular depth node would reuse almost verbatim). |

## Comparison table: TD approach → Infinite capability → gap

| # | TD approach | Infinite's current capability | Gap |
|---|---|---|---|
| 1 | Render TOP: depth buffer as 24-bit fixed or 32-bit float, linear or non-linear, pulled out via a Depth TOP | `Render3DNode` builds a real GPU depth buffer (`GL_DEPTH_COMPONENT24`) but never exposes it as a texture output | No "Depth" output pin/mode on `Render3DNode`; no linear-depth conversion utility |
| 2 | No native per-pixel depth-test Composite mode — true Z-correct compositing only happens inside one 3D scene's shared depth buffer; cross-layer 2D depth compositing is DIY | `BlendNode`/`LayerStackNode` have 32 RGBA blend modes, no depth-aware mode; `Render3DNode` already does correct depth-test compositing *for geometry inside one scene* | Same gap TD has for 2D-layer compositing; Infinite is actually ahead for the "geometry in one scene" case since Render3DNode already depth-tests multiple `IGeometrySource` slots correctly |
| 3 | Kinect Azure TOP (depth + on-device point cloud), RealSense TOP (depth + raw depth, no native point cloud) | `VideoInNode` is RGB-only webcam; no depth-sensor SDK binding anywhere in `src/platform` | Full gap — no depth sensor input node or `Platform::` depth camera abstraction exists |
| 4 | `depthProjection` COMP does intrinsics-based unproject to XYZ point-cloud texture; Point Cloud TOP instancing renders it; Phong MAT displacement uses a TOP as heightmap | `IGeometrySource::GetPointCloud()` + `Render3DNode` sprite rendering already consume arbitrary point clouds (`PointDistributionNodes` proves the pattern) | No node computes XYZ-from-depth (the unproject math itself); no found displacement-from-texture path on the mesh/geometry side |
| 5 | Community MiDaS-via-ONNX `.tox`, not Derivative-shipped | `RemoveBgNode` is a proven in-repo ONNX/on-device-segmentation pattern (worker thread, latest-only queue, paired-frame compositing) — the exact scaffold a monocular depth node needs | No depth-estimation model wired in yet; pattern to copy is `RemoveBgNode`, not a new architecture |
| 6 | DOF/fog are hand-composed from Depth TOP + Level TOP + Blur TOP; no OIT/depth-peeling shipped | Infinite has per-node compositing/blur equivalents already (would need to confirm a Blur/Level node exists — not checked this pass) | Same DIY-composition gap as TD; not a priority since TD doesn't solve it natively either |

## Searched, found nothing
- `gh search code`/DeepWiki: not applicable — TouchDesigner is closed-source, no repo to search directly; relied on Derivative's public docs/forum/wiki and one public GitHub MiDaS integration instead.
- WebSearch "TouchDesigner depth peeling order independent transparency" → no dedicated built-in feature found (absence noted in §6, not independently re-verified beyond one search pass).
- Did not verify meaning of Composite TOP's "Z Film"/"Y Film" operations beyond the operation-name list (doc gave no description); flagged as unconfirmed, not claimed as a depth feature.

## Open questions
- Does Infinite have any existing Level/Range-remap TOP-equivalent node, needed to reproduce TD's near/far depth remap step before a depth output is useful downstream? Not checked this pass.
- Does `Render3DNode`'s internal projection-matrix build already expose enough (FOV, near/far, aspect) to implement `depthProjection`-style unproject math directly, or does it need a new camera-intrinsics param set? Not traced past the `VisitParams` param list.
- Is there already a displacement/heightmap-from-texture path anywhere in `GeometryOpNodes.*` that this grep pass missed? Recommend a `codebase-navigation` pass before design if depth-to-mesh (not just depth-to-point-cloud) is in scope.
