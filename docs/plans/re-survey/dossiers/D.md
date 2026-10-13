# D Video, render and export (TouchDesigner, Blender): dossier

Status: done 2026-10-13 for Infinite and Blender; the TouchDesigner row waits on one owner paste (below). Lint: `python3 tools/re-survey/diff.py lint docs/plans/re-survey/dossiers/D.md`

## 1. What it is

- Block D of `coverage.md`: areas 9 (video and visual engine) and 10 (export and render).
- Reference apps: Blender (offline renderer, behaviour only: its public manual, public Python API and its output; its source and bundled scripts were never opened) and TouchDesigner (non-commercial licence, 1280×720 render cap). Both installed. Licence: Blender is GPL, TouchDesigner proprietary.
- A real-time engine against an offline renderer is not a like-for-like contest. The table says what a user waits for, not which renderer is better.

## 2. Method

- `python3 tools/re-survey/render_bench.py infinite`, then `blender`, then `analyse ~/re-output/render-bench/Infinite ~/re-output/render-bench/Blender --out ~/re-output/render-bench/results.md`.
- Two scenes at 720p, 1080p and 4K, 60 fps, H264 and ProRes 4444:
  - instanced: 10,000 cubes on a 100×100 grid, spinning (Infinite: Distribute Points in Grid → Instance on Points → Transform → Render 3D; Blender: geometry nodes, EEVEE);
  - blur: 900 cubes plus four Gaussian blurs of radius 20 (Blender: compositor).
- Speed: fps of a full movie render (render and encode), as the slope between a 1 s and a 3 s render so startup does not count.
- Quality: PSNR and SSIM (luma) of each app's own H264 against its own lossless frames of the same frames, at each app's default bitrate (not matched).
- AV sync: a flash every second with a 5 ms click under it, 10 minutes, H264 + AAC; every flash and click is read back out of the file with AVFoundation (`video_read.swift`).
- TouchDesigner has no headless mode: `render_bench.py td-prep` writes the click track and prints one line to paste in its Textport (`render_bench_td.py`).
- Not done: no source read, no decompiled code kept, no binaries or dumps committed.

## 3. Pillar map

- P8: Infinite renders 70–300 times faster than Blender's EEVEE on matched scenes.
  - Infinite 44.5–263 fps (render + encode), Blender 0.2–1.6 fps. The lowest ratio is blur 1080p (about 68×), the highest instanced 4K H264 (about 300×).
  - Both columns are real: Infinite is a real-time engine, EEVEE is a path built for single frames. A user wanting a film-quality still takes Blender; a user wanting 4K at 60 fps of an audio-reactive scene takes Infinite.
  - Blender's cost per still without encoding: 0.66 s (blur 720p) to 5.1 s (instanced 4K).
  - Evidence: `~/re-output/render-bench/results.md`.
- P6: Infinite's H264 is better looking at its default settings, on one scene by a wide margin.
  - Instanced: Infinite 35.5–37.1 dB (SSIM 0.990–0.992) at 17–82 Mbit/s; Blender 28.8–32.2 dB (SSIM 0.958–0.967) at 26–127 Mbit/s. Blender spends more bits and still scores 5–7 dB lower.
  - Blur: Infinite 50.6–51.8 dB at 5–11 Mbit/s; Blender 44.3–46.1 dB at 2.5–17.7 Mbit/s.
  - Caveat: bitrates are each app's own default, the scenes are matched in content and cost rather than pixel for pixel, and PSNR is measured against each app's own lossless frames. It ranks encoder settings, not renderers.
- P6: Audio and picture stay locked over a 10-minute export in both apps.
  - Infinite: offset 0.04 ms, drift 0.000 ms/min, spread 0.00 ms, 600 of 600 flash/click pairs found, audio and video the same length.
  - Blender: offset 0.02 ms, drift 0.000 ms/min, spread 0.02 ms, 600 of 600 pairs, same length.
  - Both are well inside one frame (33 ms at 30 fps).
- P6: Infinite's macOS export stalled or crashed on some Audio File takes (shipped since v0.3.3, fixed 01059f67 on main).
  - A 600 s file under a 120 s take hung at frame ~1350 for good; under load 12 of 36 short takes hung; 88.2/96/192 kHz files killed the app and files under 32 kHz failed to encode.
  - Fixed with a one-second audio lead, a finished-track mark and a rate and bit rate the AAC encoder accepts. Regression: `headless_smoke.sh` renders a long file under a short take plus 8 kHz and 96 kHz files.
  - Needs a release-notes line (written in the commit).
- P4: `--validate` and `--explain` accept a Field kernel that calls a function that does not exist.
  - Reproduced 2026-10-13 on `tests/render/field_pixel.inf` with `sin(` replaced by `bogusfn(`: `--validate` returns ok with no warnings, `--explain` prints the graph, and only `--frame` fails, with "the Output produced no image (is its input connected?)". The kernel's own error (`unknown function 'bogusfn'`, raised in `FieldIR.cpp`) never reaches the user, and the hint points at the wrong thing.
  - Matters to anyone writing patches headless or with an agent: the checking step says yes and the render blames the cable.
- P6: H264 `.mp4` carries no alpha channel. A user who needs transparent video has to pick ProRes 4444, which `render_bench` renders and measures alongside (44.5–170 fps at 720p–4K in Infinite).
- P8: Blender's white flash decodes at about 0.77 luma (its default view transform dims white). The sync reader thresholds at the midpoint of each movie's own range, so the measurement does not depend on it.

## 4. Comparison

| Pillar | Their feature | Infinite equivalent | Status | Outcome | Evidence |
|---|---|---|---|---|---|
| P8 | Render speed (Blender EEVEE: 0.2–1.6 fps on the same scenes) | `src/platform/Platform.mm` | lead | ignore: 70–300× ahead; engines differ in kind, nothing to build | `render_bench.py` |
| P6 | H264 quality at default settings (Blender) | `src/platform/Platform.mm` | lead | ignore: higher PSNR and SSIM at every size, fewer bits on four of six scenes | `render_bench.py analyse` |
| P6 | AV sync over a long export (Blender, TouchDesigner) | `src/platform/Platform.mm` | parity | ignore: both within 0.04 ms, no drift; TouchDesigner row pending | `render_bench.py sync` |
| P6 | Export with long or unusual-rate audio (Blender, Final Cut) | `src/platform/Platform.mm` | parity | ignore: fixed in this block (01059f67), needs a release-notes line | `headless_smoke.sh` |
| P4 | A node's own compile error shown at check time, before a render | `src/core/field/BackendRegister.cpp` | gap | quality-gap: `--validate` and `--explain` must compile every Field kernel and report its message; the bar is `bogusfn(` failing `--validate` with `unknown function` | reproduction in section 3 |
| P7 | Resolution ceiling (TouchDesigner non-commercial: 1280×720) | `src/core/HeadlessJob.cpp` | lead | ignore: Infinite renders 4K, ceiling above 4K untested | `render_bench.py` sizes |

## 5. Measurements

Render speed, fps (render + encode, slope 1 s → 3 s at 60 fps). `~/re-output/render-bench/results.md`:

| Scene / codec | Infinite | Blender |
|---|---|---|
| blur 720p H264 | 263.4 | 1.6 |
| blur 720p ProRes 4444 | 170.3 | 1.6 |
| blur 1080p H264 | 81.0 | 1.2 |
| blur 1080p ProRes 4444 | 81.4 | 1.2 |
| blur 4K H264 | 50.0 | 0.4 |
| blur 4K ProRes 4444 | 44.5 | 0.5 |
| instanced 720p H264 | 200.7 | 0.9 |
| instanced 720p ProRes 4444 | 128.3 | 0.9 |
| instanced 1080p H264 | 73.2 | 0.6 |
| instanced 1080p ProRes 4444 | 80.2 | 0.7 |
| instanced 4K H264 | 60.2 | 0.2 |
| instanced 4K ProRes 4444 | 56.8 | 0.2 |

H264 quality against the app's own lossless frames (luma):

| Scene | Infinite PSNR dB / SSIM / Mbit/s | Blender PSNR dB / SSIM / Mbit/s |
|---|---|---|
| blur 720p | 50.6 / 0.9915 / 5.1 | 46.1 / 0.9872 / 2.5 |
| blur 1080p | 51.8 / 0.9937 / 10.5 | 44.3 / 0.9871 / 7.0 |
| blur 4K | 51.5 / 0.9944 / 11.0 | 44.9 / 0.9889 / 17.7 |
| instanced 720p | 35.5 / 0.9899 / 16.9 | 28.8 / 0.9674 / 26.1 |
| instanced 1080p | 36.4 / 0.9919 / 37.6 | 29.7 / 0.9577 / 48.4 |
| instanced 4K | 37.1 / 0.9917 / 81.9 | 32.2 / 0.9589 / 126.7 |

Not measured:

| Item | Why | What it needs |
|---|---|---|
| TouchDesigner row | no headless mode | owner pastes the one Textport line from `render_bench.py td-prep`, then `render_bench.py td` |
| GPU memory | no portable counter without a profiler | a Metal capture or `powermetrics` run, owner's call |
| Resolution ceiling above 4K | scenes stop at 4K | add 8K sizes to `SIZES` in `render_bench.py` |
| Feedback scene | not built | a feedback-loop scene in each app, same harness |

## 6. Outcomes

- Quests: none.
- Quality gaps:
  - Field compile errors reach `--validate` and `--explain`. The bar: `bogusfn(` in a kernel makes `--validate` fail and name the function, and `--frame` no longer blames the cable.
- Bug fixed with a regression check: macOS Audio File export (01059f67, merged). Needs a release-notes line ("Fixed (macOS): exporting a video with an Audio File no longer hangs on long files or crashes on 88.2 kHz and higher files; 8–24 kHz files now export.").
- Ignored, with reason: render speed and H264 quality (Infinite leads, engines differ in kind); resolution ceiling (4K works, nothing asks for more).
- Owner sittings needed: one Textport paste for TouchDesigner at 720p.

## 7. Storage

- Written to ~/re-output: `render-bench/` (`results.md`, run logs, and the renders: 2.7 GB Infinite, 3.0 GB Blender).
- Kept, not deleted: the renders, because `render_bench.py analyse` reads them and Blender takes hours to re-render. Delete `Infinite/` and `Blender/` once the numbers are final; `results.md` and the logs stay.
- Deleted: `~/re-output/tmp` (`storage.py clean-tmp`).
