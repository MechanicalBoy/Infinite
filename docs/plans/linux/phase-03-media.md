# Phase 3 — Video, Recorder, Camera

**Outcome:** video files play, including their audio tracks. The recorder
exports H.264/AAC `.mp4` with correct A/V sync. Webcams work via V4L2.

## ⚠ Owner gate before any code

FFmpeg licensing needs the owner's explicit decision. Ask with
AskUserQuestion, recommending **(a)**:

| Option | What ships | Consequence |
|---|---|---|
| **(a) GPL FFmpeg + libx264** (recommended) | H.264 mp4 exactly like macOS/Windows | Fine because Infinite is already GPLv3 (VST3 SDK); must ship the FFmpeg source offer/licence text |
| (b) LGPL FFmpeg, no x264 | recordings encoded with e.g. `mpeg4` or `libopenh264` (Cisco binary) | No GPL codec; worse quality or extra download logic |

Record the answer in [README.md](README.md) decisions before continuing.

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

- [ ] Owner licence decision recorded
- [ ] `RECEXPORTTEST`, `RECSYNCTEST`, video + media groups green on Linux
- [ ] Artifact: an mp4 made by Infinite's recorder; `ffprobe` shows h264 + aac, matching durations
- [ ] Camera converter tests green (+ v4l2loopback e2e if the runner allows it)
- [ ] av-sync-sweep clean; macOS `--fast` green; Windows CI green
- [ ] Baseline has no P3 entries; README status row updated

## Stays unverified after P3

Real webcams (UVC quirks, formats beyond YUYV/MJPEG), hardware-decoder
paths (none are used), long recordings on slow disks, and the playback
smoothness of 4K files on real CPUs.
