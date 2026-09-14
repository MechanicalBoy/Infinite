# Phase 3 — Video, Recorder, Camera

**Outcome:** video files play, including their audio tracks. The recorder
exports H.264/AAC `.mp4` with correct A/V sync. Webcams work via V4L2.

## Licence decision — SETTLED 2026-09-14

**Option (a): GPL FFmpeg + libx264, behind a build gate.** The gate was
resolved by the owner; it is no longer a blocker on starting P3. Three
conditions below are part of the decision, not optional polish.

### Why (a)

The question conflated two independent things. Separated:

**Copyright/GPL — a non-issue.** The default build already links the
Steinberg VST3 SDK under GPLv3, so the distributed binary is *already*
GPLv3 (see the repo `LICENSE`). FFmpeg `--enable-gpl` and x264 are both
GPL-v2-**or-later**, which flows upward into GPLv3 cleanly. Adding them
imposes no obligation the project has not already taken on. Every other
bundled component is GPL-compatible (ONNX Runtime MIT, FLAC BSD, GLFW and
tinyfiledialogs zlib, miniz MIT, u2netp weights Apache-2.0 — the last is
GPLv3-compatible but *not* GPLv2-compatible, which is one more reason the
combined work must be v3 and not v2).

**Patents — the real exposure, and it is Linux-specific.** macOS encodes
H.264 through AVAssetWriter and Windows through IMFSinkWriter: in both
cases the OS vendor supplies the encoder and has paid the AVC pool.
Linux has no OS encoder, so bundling x264 makes *this project* the
distributor of an H.264 encoder for the first time. That is a genuine
change in posture, not a formality.

It is still the right call: Infinite is free and open source, distributed
at no charge, far below any pool threshold that has ever been enforced,
and this is precisely what OBS, Kdenlive, Shotcut, HandBrake, Blender and
every mainstream distro's FFmpeg already do. Against that, option (b)
would make Linux silently record a *different and worse* file than macOS
and Windows — a user-visible platform inconsistency, which is the exact
class of defect this port exists to avoid.

### Condition 1 — gate it, do not hardwire it

Add `INFINITE_ENABLE_GPL_CODECS`, default **ON** on Linux. When OFF: LGPL
FFmpeg, no x264, no `--enable-gpl`.

This is required, not defensive. The repo `LICENSE` makes an explicit
promise: "Building with `-DINFINITE_ENABLE_VST3=OFF` excludes the VST3 SDK
and the resulting binary remains under the plain MIT terms." Linking GPL
FFmpeg unconditionally on Linux would silently break that promise — a
VST3-OFF build would still be GPL, for a reason the LICENSE never states.
It also matters practically: Fedora and RHEL cannot ship H.264 at all, and
Flathub's main repo has the same constraint, so a build that works without
x264 is what any future distro packaging will need.

Note the ordering wrinkle: P1 forces `INFINITE_ENABLE_VST3 OFF` on Linux
until P4. So between P3 and P4 the Linux binary becomes GPLv3 because of
FFmpeg *before* it would have from VST3. Harmless, but the LICENSE must
say so rather than leaving a window where the stated reason is wrong.

### Condition 2 — the source offer is ours, and the current plan gets it wrong

§3.1 proposes shipping a prebuilt BtbN `-gpl-shared` FFmpeg. GPL §6 puts
the obligation to provide *corresponding source* on whoever distributes
the binary — us, not BtbN. Publishing an AppImage containing someone
else's prebuilt GPL binaries without being able to produce their matching
source is the single most common way projects fall out of compliance.

So: pin the exact upstream FFmpeg and x264 source tarball URLs **plus
SHA256** in-repo, and either build them in the release container or
archive those exact tarballs as release assets beside the AppImage. Ship
FFmpeg's `COPYING.GPLv2`/`COPYING.GPLv3` and x264's `COPYING` inside the
AppImage, and state the written offer in the release notes.

### Condition 3 — LICENSE and notices land in the same commit as the link

Not as a follow-up. The moment a GPL-linked Linux binary is publishable,
the licence text describing it must already be correct. Add a
`THIRD_PARTY_NOTICES` file while doing this — there is currently only
`assets/models/NOTICE.txt`, which will not scale past P3.

### Worth doing, but not a P3 gate

Prefer **VA-API** hardware encode when the machine has it, with x264 as
the software fallback. Hardware encode puts Linux back in the same
structural position as macOS and Windows — the patent licence for the
silicon was paid by the GPU vendor — and it is faster. It cannot be
verified in the llvmpipe container or in CI, so it belongs in P5 with real
hardware, not in P3's exit criteria.

## Start

```bash
git switch main && git pull --ff-only
git switch -c feature/linux-step-03-media
```

Prereq: P2 merged. Skills: `codebase-navigation`, `windows-parity` (§3.1,
§3.5 stride rule applies to swscale too), `av-sync-sweep` (mandatory before
exit). Reference: `src/platform/win/MediaWin.cpp` (queue, byte budget,
pool, cancel) and the video parts of `Platform.mm` (decode semantics).

## Tasks

### 3.1 FFmpeg dependency

- Pin a prebuilt shared FFmpeg (e.g. BtbN `ffmpeg-n7.1-latest-linux64-gpl-shared-7.1`
  or equivalent; pick an exact release and a SHA256). Download in CMake like
  ONNX Runtime. Link avformat, avcodec, avutil, swscale, swresample. Copy the
  `.so` files to the output dir (RPATH `$ORIGIN`). For the arm64 local
  container, use the linuxarm64 build of the same release.
- Check `ldd` for anything the build pulls from the system that won't exist
  on other distros (P5 smoke will too).
- Add FFmpeg's licence file to the bundle and third-party notices.

### 3.2 Decode (`MediaLinux.cpp`)

- `VideoOpen`: probe, choose the best video stream, open the decoder with
  `thread_count = 0` (auto), and create the swscale context → RGBA.
- **Semantics:** read how callers use `VideoFrameAt` and
  `VideoDecodeIsCatchingUp` (grep in `src/`), and match the macOS contract
  (seek precision, looping, returning the last frame at the end, frame
  timestamps). If Windows differs from macOS, macOS wins; note the Windows
  difference in `docs/WINDOWS_VERIFICATION.md`, don't fix it here.
- Seeking: `av_seek_frame(..., AVSEEK_FLAG_BACKWARD)` + decode forward to the
  target pts. Keep the last decoded frame to avoid re-seeking on small steps.
- Row copy honours `linesize` (never assume `width*4`), and flips to the
  orientation callers expect.
- `DecodeVideoAudioTrackToBuffer`: swresample → planar float at the
  requested rate; the exact `"no audio track in this file"` error string.
- `DecodeAudioFileToBuffer` fallback: if dr_libs fail, try FFmpeg (m4a, ogg,
  opus, alac).
- `InspectMovie`: duration, frame count, stream info.

### 3.3 Recorder

- Mirror `MediaWin.cpp`'s structure: a producer API on the render thread, an
  encoder worker thread, a bounded frame queue with a byte budget
  (`RecorderSetTestQueueByteBudget` for tests), a frame-buffer pool
  (`RecorderAcquireFrameBuffer`), dropped-frame counting, and `Cancel`
  deleting the partial file.
- Video: BGRA or RGBA input (`RecorderSetInputIsBgra`), bottom-up → swscale
  to yuv420p → libx264 (`preset=veryfast`, CRF like the other platforms'
  quality) → mp4, `movflags=+faststart`.
- Audio: AAC (FFmpeg native `aac`) at the session rate. Timestamps come
  from sample counts, never from wall clock.
- Teardown per §3.1; `RecorderStop` flushes both encoders and writes the
  trailer.

### 3.4 Camera (`CameraLinux.cpp`, V4L2)

- Enumerate `/dev/video*`: `VIDIOC_QUERYCAP` with
  `V4L2_CAP_VIDEO_CAPTURE`, skip metadata nodes. Name = `card`.
- Open: `VIDIOC_S_FMT` preferring YUYV, else MJPEG, closest to the requested
  resolution; mmap 4 buffers; capture thread with `poll`.
- Convert YUYV → RGBA (BT.601) and MJPEG → `stbi_load_from_memory`. Mirror on
  copy; latest frame wins (single-slot mailbox).
- CI has no camera. Add a fixture that runs the YUYV/MJPEG converters on
  synthetic buffers. If `v4l2loopback` can be loaded on the runner
  (`modprobe v4l2loopback`, like the MIDI spike), feed it with
  `ffmpeg -f lavfi -i testsrc -f v4l2 /dev/video0`, test end to end, and
  record the result in validation.md.

### 3.5 Tests + sweep

- `headless-tests.sh`: un-gate `RECEXPORTTEST` and `RECSYNCTEST` on Linux.
- Run the video and media groups under Xvfb.
- `record.sh`: now produce `artifacts-linux/showcase.mp4` **with the app's
  own recorder** as well as x11grab, then run `ffprobe` on both in CI and
  print the stream info.
- Run the `av-sync-sweep` skill and fix its findings.
- Extend `INFINITE_SYSINFO` with the FFmpeg version, encoders present, and
  cameras.
- Remove P3 entries from the baseline.

## Exit criteria

- [x] Owner licence decision recorded (see above: GPL + x264 behind `INFINITE_ENABLE_GPL_CODECS`)
- [ ] `INFINITE_ENABLE_GPL_CODECS=OFF` also builds and passes the media group
- [ ] LICENSE, third-party notices and the source offer updated in the same commit as the FFmpeg link
- [ ] `RECEXPORTTEST`, `RECSYNCTEST`, video + media groups green on Linux
- [ ] Artifact: an mp4 made by Infinite's recorder; `ffprobe` shows h264 + aac, matching durations
- [ ] Camera converter tests green (+ v4l2loopback e2e if the runner allows it)
- [ ] av-sync-sweep clean; macOS `--fast` green; Windows CI green
- [ ] Baseline has no P3 entries; README status row updated

## Stays unverified after P3

Real webcams (UVC quirks, formats beyond YUYV/MJPEG), hardware-decoder
paths (none are used), long recordings on slow disks, and the playback
smoothness of 4K files on real CPUs.
