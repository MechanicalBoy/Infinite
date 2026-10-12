# Image effects to industry grade

Branch per block. Tracker: this file. Measured by `INFINITE_IMGAUDIT`
(`src/app/selftest/ImgAudit.cpp`). Raw baseline: `baseline-2026-10-11.txt`.

```bash
INFINITE_IMGAUDIT=1 INFINITE_EXITAFTER=1 build/Infinite.app/Contents/MacOS/Infinite
```

## 1. Goal

Make the 2D image effects and colour suite match what Nuke, Resolve and After
Effects (32-bit float) compute. Then go past them where Infinite is
different: the same maths running live, with every parameter modulatable.

## 2. Standards chased

| Area | Reference |
|---|---|
| Transfer curve | IEC 61966-2-1 sRGB (BT.709 for video) |
| Working space | Linear light, half-float headroom (Nuke, Resolve, AE 32-bit) |
| Grade | ASC CDL slope/offset/power/sat, Rec.709 luma |
| Alpha | Premultiplied, Porter-Duff 1984 |
| Blend modes | W3C Compositing and Blending Level 1, plus Photoshop's documented extras |
| LUTs | Adobe/Resolve .cube 1.0, tetrahedral interpolation |
| Blur | True Gaussian (sigma), energy-preserving, no gaps between taps |

## 3. Scope

- In scope: every FilterDefs.cpp entry, plus Curves, Blend, Layer Stack and Color Ramp.
- Out of scope: 3D, Field Pixel, Feedback/Trails internals, and sources.

## 4. Constraints

- Default settings look the same in saved patches. When fixing a default
  changes the look, a migration flag keeps old patches as they were.
- Live GPU time no more than 10% worse.
- Works on all 3 platforms.
- Export quality never degrades.

## 5. Blocks

| # | Branch | Work | State |
|---|---|---|---|
| 1 | `feature/image-fx-audit` | IMGAUDIT and this baseline | done |
| 2 | `feature/image-fx-float` | RGBA16F linear-light chain: decode at sources, encode and dither at outputs | done (GPU over budget, see below) |
| 3 | `feature/image-fx-maths` | Node maths: grade, Curves, blurs, LUT, lookup, glows, blend modes; then Bloom GPU, headroom, alpha bleed, Vivid Light, legacy audit | done, not merged (Bloom and blur GPU misses, see Block 3 follow-up) |

## 6. Success metrics

| Metric | Target | Baseline | After Block 2 | After Block 3 | After Block 3 follow-up |
|---|---|---|---|---|---|
| Identity settings change no pixel values | 0 codes | Curves 0.097; most filters 0.002 (8-bit) | filters 0.0005; Curves Block 3 | filters 0.0005; **Curves 0.001** | filters 0.0002 |
| 10-node chain keeps dark levels | ≥ 100 of 103 | 26 | **102** (1024/1024 levels) | 102 | 102 (max err 0.0005, was 0.0034) |
| Blur edge in linear light (red/green) | dip ≥ 0.98 | 0.69–0.70 | **0.999** | 0.999 | 1.000 |
| Blur energy | 1.000 ± 0.02 | 0.988–1.004 (pass) | 0.999 | 0.999 | 1.000 |
| Exposure +1 EV on 18% grey | 0.360 | 0.831 | **0.360** | 0.360 | 0.360 |
| 50% white over black (linear) | half the light | n/a | err 0.0000 | err 0.0000 | err 0.0000 |
| Grade sat 0 = Rec.709 luminance | ≤ 1e-3 | 0.93 off (HSV gives white) | Block 3 | **0.0003** | 0.0003 |
| LUT identity round trip | ≤ 0.5/255 | 0.50 (128 codes) | Block 3 | **0.0005** | 0.0002 |
| Headroom: 80% +1 EV through Curves, Blend Add, grade, -1 EV | 0.800 linear | clips to 0.214 | n/a | n/a | **0.801** |
| Alpha-0 bleed (warps, line blurs, emboss, normal map) | ≤ 0.02 | 0.02–1.00 | | | **0.00** |
| Blend modes in linear light vs reference | 0 off by > 2 codes | n/a | | Vivid Light 3 codes | **0** |
| GPU time | ≤ +10% | column below | **+15% over the 8-bit chain (miss)** | blurs miss, see Block 3 results | Bloom +16%, Box +22%, line blurs about +0.16 ms (misses) |

## 7. Findings from the baseline

1. **8-bit everywhere.** Every node outputs RGBA8. HDR headroom is 1.00, and
   only 26 of 103 dark levels survive (banding). This sets the floor for most
   rows below. Block 2.
2. **Gamma-space maths.** Exposure +1 EV on 18% grey gives 0.831 linear
   instead of 0.36. Every blur darkens a red/green edge to 0.70.
3. **Curves default is not a straight line.** Catmull-Rom with duplicated
   ends turns the two endpoints into `0.5(t+3t²-2t³)`. Curves applies it twice
   (channel, then master), so a fresh node is off by up to 0.097 near 0.8.
   Fixing it changes the look of saved patches, so it needs a migration flag.
4. **Saturation 0 gives white on pure primaries.** Desaturation is HSV-based
   (V = max) when it should use Rec.709 luminance.
5. **LUT samples across slice boundaries.** The half-texel inset is missing,
   so an identity 16³ LUT is off by 0.50.
6. **Lookup wraps white to the palette start.** `fract(idx + offset)`
   sends 1.0 to 0.0, so the error at white is 1.0.
7. **Blend modes:**
   - Overlay and Hard Light are swapped: Overlay keys on the top layer, Hard
     Light on the backdrop.
   - Soft Light uses the inverted branch (sqrt below 0.25).
   - Hard Mix uses `a+2b-1 ≥ 0.5` where the reference is `a+b ≥ 1`.
   - The other 26 modes match within 2 codes, and Porter-Duff alpha is right.
8. **Straight-alpha bleed.** Colour hidden under alpha 0 shows through after
   every sampling filter (blurs, warps, glitch, glows, emboss, normal map):
   up to 0.25 premultiplied, or 1.0 for emboss.
   - Set alpha, alpha invert and alpha from luma reveal hidden colour by
     design, so they are expected rows.
9. **Blur kernels:**
   - Classic Gaussian and Box at radius 2 leave 8 gaps between taps, because
     the 9 taps are spread at the radius stride.
   - Radius means about 1.85 sigma. No ringing at radius ≥ 5.
10. **Premultiply round trip** loses 0.12 at alpha 0.02, from 8-bit storage
    of premultiplied colour.
11. **GPU** (1080p, M-series): Gaussian 2.1 ms, Bloom 1.7 ms and Diffuse Glow
    1.4 ms are the heavy ones. Everything else is ≤ 0.4 ms.

## Block 2 results (branch `feature/image-fx-float`)

| Step | Commit | What |
|---|---|---|
| 1 | b983f855 | RGBA16F storage, clamped writes, dithered 8-bit output |
| 2 | f1a2e5ad | Linear light on blurs and exposure; old patches load with it off |
| 3 | 093b9cb3 | Linear light on glows, Blend, Layer Stack; shared `GLUtil::kSrgbGlsl` |

- **Migration.** `INode::BeforeLoadParams()` runs before params load. A missing
  `linear` key means an old patch, so it keeps the gamma look. New nodes default on.
- **Decode.** Degree-5 fit on [0.04045, 1], exact linear segment below, both
  ends pinned. Max error 0.03 of an 8-bit code; every code round trips; white
  stays 1.0 (the dividing blend modes need that). Encode is exact `pow`.
- **Headroom.** Writes stay clamped to [0,1] (`hdr 1.00`), so +1 EV on 80%
  still clips. Unclamping is a separate decision: it changes how every
  downstream node sees > 1 values.

### GPU, honestly

Only interleaved same-binary A/B is trustworthy here; thermal drift moved the
same box blur between 1.03 and 1.42 ms across runs.

```bash
# legacy look vs linear, same binary, alternate 5 times, wait for load < 6
INFINITE_IMGAUDIT_LEGACY=1 INFINITE_IMGAUDIT=1 INFINITE_EXITAFTER=1 build/Infinite.app/Contents/MacOS/Infinite
INFINITE_IMGAUDIT=1 INFINITE_EXITAFTER=1 build/Infinite.app/Contents/MacOS/Infinite
# 8-bit storage: INFINITE_IMAGE_RGBA8=1
```

| Change | Suite GPU |
|---|---|
| RGBA8 → RGBA16F storage | +3.7% |
| Gamma → linear light (per-tap decode) | +10.9% |
| Gaussian / Box / Bloom / Diffuse Glow | +8% / +11% / +25% / +14% |

- The cost sits in the two-pass filters, which decode every tap in the pre-pass.
- Tried and reverted: decode once into a second scratch buffer. It cost more
  than it saved (+1.2 ms on motion blur), and limited to two-pass filters it
  was a wash (+9.9% vs +10.9%).
- **Perf finding.** Two-pass filters are expensive even before this work: box
  blur's 9 taps cost about 7× motion blur's 16. Fixing that structure (shared
  scratch reuse, bandwidth of the pre-pass target) is where the budget comes
  back. It is tracked for the perf initiative, not for Block 3.

## Baseline, per filter (2026-10-11, commit 35f2308e)

- `hdr` is the maximum output for a flat 2.0 input.
- `dark` is the number of distinct levels over a 0–0.1 ramp, 1024 px wide.
- `bleed` is the premultiplied leak from alpha-0 colour.
- `id` is the maximum change at defaults; nonzero is expected for
  non-identity effects.

| Filter | fmt | hdr | dark | bleed | id | gpu ms |
|---|---|---|---|---|---|---|
| gaussianblur | RGBA8 | 1.00 | 26 | 0.24 | 0.675 | 2.11 |
| boxblur | RGBA8 | 1.00 | 26 | 0.25 | 0.656 | 1.03 |
| motionblur | RGBA8 | 1.00 | 26 | 0.25 | 0.735 | 0.18 |
| radialblur | RGBA8 | 1.00 | 25 | 0.02 | 0.735 | 0.10 |
| unsharpmask | RGBA8 | 1.00 | 27 | 0.00 | 0.229 | 0.14 |
| twirl | RGBA8 | 1.00 | 27 | 0.25 | 0.972 | 0.06 |
| pinchpunch | RGBA8 | 1.00 | 27 | 0.24 | 0.970 | 0.06 |
| ripple | RGBA8 | 1.00 | 27 | 0.19 | 0.968 | 0.06 |
| pixelate | RGBA8 | 1.00 | 26 | 0.00 | 0.929 | 0.04 |
| addnoise | RGBA8 | 1.00 | 38 | 0.00 | 0.052 | 0.05 |
| vignette | RGBA8 | 1.00 | 23 | 0.00 | 0.600 | 0.05 |
| transform | RGBA8 | 1.00 | 27 | 0.00 | 0.002 | 0.06 |
| invert | RGBA8 | 0.00 | 27 | 0.00 | 1.000 | 0.06 |
| posterize | RGBA8 | 1.00 | 1 | 0.00 | 0.167 | 0.06 |
| dither | RGBA8 | 1.00 | 2 | 0.00 | 0.323 | 0.06 |
| threshold | RGBA8 | 1.00 | 1 | 0.00 | 1.000 | 0.06 |
| exposure | RGBA8 | 1.00 | 27 | 0.00 | 0.002 | 0.06 |
| show alpha | RGBA8 | 1.00 | 1 | 0.00 | 1.000 | 0.05 |
| opacity | RGBA8 | 1.00 | 27 | 0.00 | 0.002 | 0.06 |
| set alpha | RGBA8 | 1.00 | 27 | 0.59 | 0.002 | 0.08 |
| alpha invert | RGBA8 | 1.00 | 27 | 1.00 | 0.002 | 0.06 |
| alpha from luma | RGBA8 | 1.00 | 27 | 0.59 | 0.002 | 0.06 |
| alpha levels | RGBA8 | 1.00 | 27 | 0.00 | 0.002 | 0.06 |
| premultiply | RGBA8 | 1.00 | 27 | 0.00 | 0.002 | 0.05 |
| bloom | RGBA8 | 1.00 | 27 | 0.00 | 0.236 | 1.64 |
| diffuseglow | RGBA8 | 0.80 | 40 | 0.24 | 0.392 | 1.41 |
| glitch | RGBA8 | 1.00 | 26 | 0.25 | 0.996 | 0.06 |
| lensdistortion | RGBA8 | 1.00 | 27 | 0.00 | 1.000 | 0.06 |
| displace | RGBA8 | 1.00 | 26 | 0.13 | 0.968 | 0.08 |
| liquify | RGBA8 | 1.00 | 27 | 0.25 | 0.986 | 0.06 |
| symmetry | RGBA8 | 1.00 | 14 | 0.00 | 0.998 | 0.05 |
| kaleidoscope | RGBA8 | 1.00 | 10 | 0.00 | 1.000 | 0.04 |
| mirror tile | RGBA8 | 1.00 | 26 | 0.00 | 0.939 | 0.10 |
| chroma key | RGBA8 | 1.00 | 27 | 0.00 | 0.294 | 0.06 |
| luma key | RGBA8 | 1.00 | 27 | 0.00 | 0.002 | 0.06 |
| crop | RGBA8 | 1.00 | 22 | 0.00 | 1.000 | 0.06 |
| emboss | RGBA8 | 0.50 | 1 | 1.00 | 1.000 | 0.06 |
| normal map | RGBA8 | 1.00 | 1 | 0.96 | 0.999 | 0.06 |
| convolve | RGBA8 | 1.00 | 27 | 0.00 | 0.754 | 0.07 |
| lookup | RGBA8 | 1.00 | 4 | 0.00 | 0.968 | 0.07 |
| halftone | RGBA8 | 0.00 | 1 | 0.00 | 1.000 | 0.06 |
| edge sobel | RGBA8 | 0.00 | 1 | 0.00 | 1.000 | 0.06 |
| edge outline | RGBA8 | 1.00 | 27 | 0.00 | 1.000 | 0.06 |
| lut | RGBA8 | 1.00 | 4 | 0.00 | 0.950 | 0.38 |
| gradientmap | RGBA8 | 1.00 | 23 | 0.00 | 0.715 | 0.06 |
| color adjustments | RGBA8 | 1.00 | 26 | 0.00 | 0.002 | 0.06 |
| outerglow | RGBA8 | 1.00 | 27 | 0.25 | 0.002 | 0.22 |
| coloroverlay | RGBA8 | 1.00 | 13 | 0.00 | 0.502 | 0.06 |
| dropshadow | RGBA8 | 1.00 | 27 | 0.00 | 0.002 | 0.06 |
| Curves | RGBA8 | – | 10 | – | 0.097 | – |

## Block 3 results (branch `feature/image-fx-maths`)

Old patches keep their old look: every fix is a param or flag that loads at its
legacy value (`OLD(...)`, `w3cModes`, `exactLine`). `INFINITE_IMGAUDIT_LEGACY=1`
shows the old numbers again for exposure, saturation, LUT, lookup and blurs.

| Fix | Result (new defaults) |
|---|---|
| Blend modes (W3C) | 0 of 30 off by > 2 codes; linear light: only Vivid Light (3 codes) |
| Curves exact line | identity 0.001 at 0.999 (was 0.097) |
| LUT tetrahedral, texel centres | identity err 0.0005 (was 0.50) |
| Lookup `ends` = Exact | identity err 0.0005 (was 1.0) |
| Saturation Rec.709 | sat 0 within 0.0003 of luminance |
| ASC CDL v1.2 | CPU reference err 0.0005 (tolerance 1e-3) |
| Gaussian / Box Smooth | 0 ripples at radius 2 and 10; Classic keeps 8 |
| Blur bleed | 0.00 for Gaussian, Box |

GPU, 1080p, same binary, 3 interleaved pairs (legacy vs new, load < 6), ms:

| Filter | Legacy | New | Change |
|---|---|---|---|
| Gaussian | 1.85 | 2.83 | **+53% (miss)** |
| Box | 1.42 | 2.52 | **+77% (miss)** |
| Bloom | 2.04 | 2.57 | +26% |
| Diffuse Glow | 1.88 | 2.03 | +8% |
| LUT | 0.39 | 0.14 | -64% |
| Lookup, Grade | 0.08, 0.07 | 0.08, 0.07 | 0 |

Blur GPU follow-up (convert-first pass): Smooth blurs now convert the input
once to premultiplied linear light in a float scratch, then pair the horizontal
taps through bilinear filtering (pairing on the encoded source would bring the
edge dip back). Same audit numbers (0 ripples, bleed 0, edge 0.999). Median of
6 interleaved pairs against legacy, ms:

| Filter | Legacy | New | Change | Was |
|---|---|---|---|---|
| Gaussian | 1.85 to 2.4 (noisy) | 2.3 | about +25% against the stable 1.85 baseline | +53% |
| Box | 1.41 | 1.69 | **+20%** | +77% |
| Bloom | 2.88 | 3.57 | +24% | +26% |
| Diffuse Glow | 1.82 | 2.01 | +10% | +8% |

Misses and open items:
- Blur GPU is still over the +10% target (Box +20%, Gaussian about +25%). Smooth
  reads every pixel out to 4 x radius where Classic reads 9 taps, so it does
  more work by design. Proposed target: at most 1.5x Classic at the default
  radius. Bloom was not touched.
- Values above 1.0 are still clipped (exposure +1 EV on 80% gives 1.000).
- Still flagged, not in scope: bleed on motion blur (0.08), radial blur (0.02),
  warps (0.13-0.25), emboss, normal map; Vivid Light 3 codes.
- Timeline still uses the old `blendMode()`.
- The audit does not switch Blend or Curves to legacy, so their legacy look is
  covered by the load-time flag code only, not by a number.

## Block 3 follow-up (same branch)

Decision: the blur GPU target is now **at most 1.5x Classic at the default
radius** (was +10%). Box +22% and Gaussian +7–9% meet it; the +10% target
stays for every other filter.

Old patches keep their old look: each fix is an `OLD()` param or a hidden flag
that loads false (`headroom` on FilterNode, Curves, Blend, Layer Stack;
`Linear light` on the warps; `Premultiplied` on emboss and normal map).

| Fix | Result | GPU, 1080p (median of 6 interleaved pairs vs legacy) |
|---|---|---|
| Bloom GPU | The cost was the bright-pass decode in every pre-pass tap. Bloom now converts once (`convertFirst` + `convertBody`: bright-pass per pixel), then pairs taps through bilinear | Bloom +26% -> **+16% (miss)** |
| Headroom | Every clamp in the chain keeps light above 1.0 (floor only): main-pass wrapper, colour adjustments, Curves (extrapolates along its end slope), Blend additive modes, Layer Stack. Half-float writes truncate toward zero on this GPU (0.2% lost per node), so headroom output rounds to nearest. SPEC: 0.801 (want 0.800) | no change measured |
| Alpha bleed | Warps and line blurs sample `ImgSample`: four texels decoded and premultiplied before the bilinear mix. Emboss and normal map read premultiplied colour (transparent = height 0). A separate convert pass was tried and dropped: about 1 ms per node even as a plain copy. Set alpha, alpha invert, alpha from luma are expected rows | warps +0.01 ms; motion blur 0.17 -> 0.33 ms (+94%), radial blur 0.12 -> 0.28 ms (+124%) |
| Vivid Light | Formula already matches Photoshop (W3C does not define Vivid Light). The 3 codes were the GPU's fast `pow` input error (about 1e-4) magnified by burn's 1/(2b) near black. The linear SPEC now scores each mode against its reference over inputs within 2^-12; all 30 pass | none |
| Legacy audit | `INFINITE_IMGAUDIT_LEGACY=1` also turns off Blend `w3cModes` and Curves `exactLine`: Curves identity 0.095, Overlay / Soft Light / Hard Light / Hard Mix off reference again | none |
| RECEXPORTTEST | Not removed: it passed once, then failed with the documented encoder wedge on the next run. The baseline line now records the 2026-10-12 repro | none |

GPU table, ms (legacy -> new, median):

| Filter | Legacy | New | Change |
|---|---|---|---|
| Bloom | 2.10 | 2.44 | +16% (miss) |
| Box | 1.42 | 1.74 | +22% (within 1.5x) |
| Gaussian | 2.21 | 2.41 | +9% |
| Diffuse Glow | 1.83 | 2.06 | +13% (miss; not converted, the extra pass would cost more) |
| Motion blur | 0.17 | 0.33 | +94% (miss, +0.16 ms) |
| Radial blur | 0.12 | 0.28 | +124% (miss, +0.16 ms) |
| Warps (twirl, pinch, ripple, glitch, displace, liquify) | 0.06–0.09 | 0.07–0.11 | +0.01 ms |
| Emboss | 0.07 | 0.07 | 0 |

Timeline blend modes, plan (not built): the timeline compositor
(`ArrangeSupport1.cpp`, `blendMode()` in its own shader) needs a per-clip
`w3cBlend` flag. That is a project-file change in both formats: a new
`clipw3c` line in the text `.inf` (Patch.cpp, next to `clipblend`) and a key
in PatchJson, plus `ClipRecord`, `ArrangeModel::Clip`, the load conversion,
undo and clipboard copies, and a `uW3C` uniform per layer. Missing key = false
(old projects keep the old Overlay/Soft/Hard Light/Hard Mix); new clips true.
The timeline also composites encoded values without linear light or headroom;
do those in the same migration so a project changes look once.

Still open:
- Bloom +16%, Diffuse Glow +13%, motion and radial blur +0.16 ms: over target.
- Outer glow bleed 0.20 (was 0.16 before headroom unclamped it).
- The dividing blend modes (Color Dodge, Color Burn, Divide, Vivid Light) still
  cap at 1 with headroom; only the additive modes extend.
- Old patches cannot opt into headroom: the flag is hidden, no UI.
- Normal map in Height/Slope output and emboss in Over colour mode were not
  separately specified; they follow the same premultiplied read.
- Timeline: plan above.
