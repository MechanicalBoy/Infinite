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
| 2 | — | RGBA16F linear-light chain: decode at sources, encode and dither at outputs | next |
| 3 | — | Node maths: grade, Curves, blurs, LUT, lookup, glows, blend modes | |

## 6. Success metrics

| Metric | Target | Baseline |
|---|---|---|
| Identity settings change no pixel values | 0 codes | Curves 0.097; most filters 0.002 (8-bit) |
| 10-node chain keeps dark levels | ≥ 100 of 103 | 26 |
| Blur edge in linear light (red/green) | dip ≥ 0.98 | 0.69–0.70 |
| Blur energy | 1.000 ± 0.02 | 0.988–1.004 (pass) |
| Grade sat 0 = Rec.709 luminance | ≤ 1e-3 | 0.93 off (HSV gives white) |
| LUT identity round trip | ≤ 0.5/255 | 0.50 (128 codes) |
| GPU time | ≤ +10% | column below |

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
