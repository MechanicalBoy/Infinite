# Linux Validation Rig

How a port gets verified by someone with no Linux machine. Phase 0 builds all
of this. Every later phase adds fixtures to it and must leave proof in it.

```
                   ┌───────────────────────── same scripts, same package list ─────────────────────────┐
 owner's Mac       │                                                                                     │
 ├─ OrbStack ─► L0 local container (arm64, Ubuntu 24.04) ── fast loop: build + L1 + L2 in minutes       │
 └─ git push ──► GitHub Actions ubuntu runners (x86_64)                                                  │
                  ├─ L1 build (Clang primary, GCC secondary) + headless-tests.sh                         │
                  ├─ L2 full harness under Xvfb + Mesa llvmpipe                                          │
                  │     ├─ audio: miniaudio null backend + PulseAudio null sink                          │
                  │     ├─ MIDI: ALSA virtual port (snd-seq / snd-virmidi)                               │
                  │     └─ artifacts: logs, screenshots, a screen recording  ◄── the owner looks here    │
                  ├─ L3 AppImage on Ubuntu 22.04/24.04, Debian 12, Fedora, Arch (+ Wayland smoke)        │
                  └──────────────────────────────────────────────────────────────────────────────────────┘
 beta testers ───► L4 real hardware: GPUs, audio interfaces, MIDI, cameras, VST editors, desktops
```

## What each layer can and cannot prove

| Claim | L0/L1 | L2 | L3 | L4 |
|---|:-:|:-:|:-:|:-:|
| Compiles and links, no platform-layer crash | ✅ | | | |
| Rendering correct (software GL, strict Mesa GLSL) | | ✅ | | ✅ real GPUs |
| Undo, save/load, 167-node round trip, fixtures | | ✅ | | |
| Audio graph and device lifecycle logic | | ✅ virtual devices | | ✅ |
| MIDI parsing and note stream | | ✅ if a virtual port loads | | ✅ |
| Video decode/encode, A/V sync | | ✅ | | |
| Missing `.so` files / glibc too new on other distros | | | ✅ | |
| Latency, xruns, real interfaces, JACK setups | ❌ | ❌ | ❌ | ✅ only |
| Cameras, VST editors on KDE/GNOME, NVIDIA/AMD drivers, HiDPI, Wayland desktops | ❌ | partial | partial | ✅ only |

Report every phase against this table: say what was proven and at which
layer, and list what stays unproven.

---

## Files to create (Phase 0)

```
tools/linux/
  deps-apt.sh          # the ONE apt package list, used by the Dockerfile and CI
  Dockerfile           # FROM ubuntu:24.04 (dev/test), RUN deps-apt.sh
  Dockerfile.release   # FROM ubuntu:22.04 (AppImage build base, glibc floor) — P5
  local.sh             # owner-Mac wrapper: build image once, run any script inside it
  build.sh             # cmake configure+build into build-linux/ (Clang default, CC/CXX override)
  xvfb-harness.sh      # L2: start Xvfb + audio/MIDI fakes, run the harness, collect artifacts
  record.sh            # L2: screen-record a showcase run via ffmpeg x11grab
  distro-smoke.sh      # L3: run an AppImage in N distro containers — P5
.github/workflows/build.yml     # + linux jobs (see below)
.claude/skills/run-infinite-hygiene/driver.sh   # made OS-aware (BIN path, known-failures file)
.claude/skills/run-infinite-hygiene/known-test-failures-linux.txt
```

Add `build-linux/` and `artifacts-linux/` to `.gitignore`.

### deps-apt.sh (starting list; trim/extend as phases land)

```
build:   build-essential clang lld cmake ninja-build pkg-config git ccache
glfw:    libx11-dev libxrandr-dev libxinerama-dev libxcursor-dev libxi-dev
         libxkbcommon-dev libwayland-dev wayland-protocols
gl:      libgl-dev libegl-dev mesa-utils libgl1-mesa-dri
text:    libfontconfig-dev            (FreeType comes via FetchContent)
midi:    libasound2-dev
test:    xvfb xauth ffmpeg pulseaudio pulseaudio-utils alsa-utils weston
         kmod file imagemagick
```

FFmpeg *dev* headers are **not** apt packages. P3 pins a prebuilt shared
FFmpeg (see phase-03). The `ffmpeg` binary above is only for `record.sh`.

---

## L0 — local container on the owner's Mac

The owner has installed OrbStack (it provides `docker`). Memory is tight: set
OrbStack Settings → System → Memory limit to about 5–6 GB, and build
`main.cpp` with `-j1` if the compiler gets OOM-killed.

```bash
tools/linux/local.sh build                 # configure + build into build-linux/ (arm64)
tools/linux/local.sh test --fast           # L1 + L2 fast tier under Xvfb
tools/linux/local.sh test --group audio    # any driver.sh tier/group
tools/linux/local.sh shell                 # interactive shell in the container
```

`local.sh` mounts the repo at `/src`, reuses a named volume for `ccache`, and
never writes into `build/` (the macOS build dir). The container is **arm64**:
it proves the code compiles and runs on Linux, not that the x86_64 release
works. CI is authoritative.

## L1 — build + headless (CI)

- Runner `ubuntu-24.04`, x86_64. Matrix: `clang` (gating) and `gcc` (gating
  compile, tests optional). Both must compile. GCC often catches things
  Clang/MSVC accept.
- `cmake -S . -B build-linux -G Ninja -DCMAKE_BUILD_TYPE=Release`
- `.github/scripts/headless-tests.sh build-linux/Infinite`. It already
  handles non-Darwin. Add the `Linux` cases it needs (e.g. `RECEXPORTTEST`
  is gated from P3 on).
- Upload `build-linux/Infinite` as an artifact (`Infinite-linux-x86_64-bin`).

## L2 — full harness under a virtual display

`xvfb-harness.sh` must:

1. Export `LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=llvmpipe
   INFINITE_NO_UPDATE_CHECK=1 XDG_RUNTIME_DIR=$(mktemp -d)`.
2. Start `Xvfb :99 -screen 0 1920x1080x24 &` and export `DISPLAY=:99`. Print
   `glxinfo -B` so the log shows the GL version. It must report ≥ 3.2 core.
3. Audio (from P2 on): start `pulseaudio --daemonize --exit-idle-time=-1`,
   `pactl load-module module-null-sink sink_name=infnull`, and the
   `module-null-source` equivalent for capture. Separately run the audio
   group once with `INFINITE_AUDIO_BACKEND=null`, which forces miniaudio's
   null backend (fully deterministic; P2 implements the env var).
4. MIDI (from P2 on): **expect no kernel MIDI on GitHub runners.** The
   runners use an `-azure` kernel that has no sound modules. `modprobe
   snd-dummy`/`snd-aloop` fail with "Module not found"
   ([runner-images#8295](https://github.com/actions/runner-images/issues/8295),
   [#1114](https://github.com/actions/virtual-environments/issues/1114)).
   The ALSA sequencer is kernel-side, and there's no user-space substitute.
   So:
   - **Primary MIDI proof = a parser unit test.** It feeds synthetic
     `snd_seq_event_t` values into `MidiLinux.cpp`'s pure event→table
     function (phase-02 §2.5). It runs everywhere.
   - Still try once (P0 spike):
     `sudo apt-get install -y linux-modules-extra-$(uname -r) && sudo modprobe snd-seq snd-virmidi`.
     If `/dev/snd/seq` appears, run the end-to-end MIDI fixtures in CI.
     Otherwise mark them `SKIP (no ALSA seq on runner)`. Try it in the
     OrbStack container too (it shares OrbStack's kernel). Record both
     answers in this file.
   - Real MIDI gear remains L4.
5. Run `driver.sh --skip-build <tier>` with `BIN=build-linux/Infinite`.
6. Always (even on failure) copy logs + every screenshot to
   `artifacts-linux/` and upload it (`actions/upload-artifact`,
   `if: always()`).

**Screenshots:** the app writes them itself (`IMAGERESYNTH_SCREENSHOT=<png>`
with `INFINITE_SHOWCASE*`), so no window-grabbing tool is needed. Phase 1+
adds a per-category screenshot set: one patch per node category (2D,
3D, audio UI, panels). The owner eyeballs these against the same shots from
macOS. Generate the macOS references with the same env vars and commit them
under `tools/linux/reference-shots/` (small PNGs only).

**Recording:** `record.sh` runs a showcase for ~20 s while
`ffmpeg -f x11grab -video_size 1920x1080 -framerate 30 -i :99` writes
`artifacts-linux/showcase.mp4`. Only on `workflow_dispatch` and on phase-tip
pushes, not every commit.

**Known limits of llvmpipe:** it's slow, so heavy fixtures may need larger
`INFINITE_EXITAFTER` budgets or a longer job timeout. Never "fix" a slow
fixture by loosening its assertion. Precision differs from GPU drivers, so
pixel-exact comparisons against macOS are not valid. Compare by eye, or by
tolerant metrics the fixture already uses.

### Linux baseline file

`known-test-failures-linux.txt` uses the same format as the macOS file. Every
entry needs a one-line reason and the phase that will remove it. Example:
`VST3SCANTEST|stubbed until P4`. The baseline must **shrink** each phase and
be **empty of P0–P4 entries** before P5 ships.

## L3 — AppImage on other distros (from P5; the skeleton lands in P0)

`distro-smoke.sh <AppImage>`: for each image in
`ubuntu:22.04 ubuntu:24.04 debian:12 fedora:latest archlinux:latest`:

```
docker run --rm -v $PWD:/w <image> sh -c '
  <install xvfb + mesa via that distro's package manager>
  cd /w && ./Infinite-x86_64.AppImage --appimage-extract-and-run   # containers have no FUSE
     with INFINITE_EXITAFTER=120 IMAGERESYNTH_SCREENSHOT=/w/artifacts-linux/<distro>.png'
```

Pass means exit 0, a non-black screenshot, and no `error while loading shared
libraries` in the log. Also run `ldd` on the extracted binary and fail on any
`not found`.

**Minimal-install trap (real-world precedent):** Audacity 4.0's AppImage
died on minimal Ubuntu 26.04 with `libOpenGL.so.0: cannot open shared
object file`. Qt linked the GLVND `libOpenGL` unconditionally, and minimal
installs don't ship `libopengl0`
([audacity#12093](https://github.com/audacity/audacity/issues/12093)).
Infinite must not link any GL library at all: GLFW `dlopen`s
`libGL.so.1`/`libEGL.so.1`, and glad loads through `glfwGetProcAddress`.
Add the check `ldd Infinite | grep -E "libOpenGL|libGL\.so|libGLX|libEGL"`,
which must print nothing. Also add a smoke image that has *only* the bare
runtime packages (`ubuntu:24.04` + `libgl1 libegl1 libfontconfig1 libx11-6`
+ Mesa), not the full desktop, to catch "worked because dev packages were
installed".

**Wayland smoke:** in one Ubuntu container, start
`weston --backend=headless --renderer=gl` (fall back to `pixman` if GL isn't
available) and launch with `INFINITE_WAYLAND=1 INFINITE_EXITAFTER=120`. Pass
means a window is created and N frames render without a crash. Best-effort:
report, don't gate, unless it passes reliably.

## L4 — beta testers (P5)

- A GitHub **pre-release** `vX.Y.Z-linux-beta.N` carrying the AppImage.
  Posting to issue #14 and creating the pre-release are **public actions**,
  so draft them and get the owner's explicit yes each time.
- `.github/ISSUE_TEMPLATE/linux-beta-report.md`: distro + version, desktop +
  X11/Wayland, GPU + driver, audio stack (PipeWire/Pulse/JACK), and a
  checklist mirroring the "L4 only" rows above.
- **`INFINITE_SYSINFO=1`**: a headless diagnostic dump the tester pastes into
  the report. It prints the GL vendor/renderer/version, the GLFW platform
  (X11/Wayland), audio backends and devices, MIDI ports, VST3 folders + scan
  count, cameras, fontconfig font count, and ONNX Runtime status. Start it in
  P0 with the GL info, and each phase appends its subsystem. Build it
  cross-platform in its own TU (not `main.cpp`), dispatched like other
  `INFINITE_*` env vars.

---

## CI job sketch (`build.yml`)

```yaml
  linux:
    name: Linux (${{ matrix.cc }})
    runs-on: ubuntu-24.04
    strategy:
      fail-fast: false
      matrix:
        cc: [clang, gcc]
    steps:
      - uses: actions/checkout@v4
        with: { submodules: recursive }
      - run: sudo tools/linux/deps-apt.sh
      - uses: hendrikmuhs/ccache-action@v1        # or actions/cache on ~/.ccache
      - run: CC_FAMILY=${{ matrix.cc }} tools/linux/build.sh
      - run: .github/scripts/headless-tests.sh build-linux/Infinite
      - if: matrix.cc == 'clang'
        run: tools/linux/xvfb-harness.sh --fast   # widen per phase
      - if: always()
        uses: actions/upload-artifact@v4
        with: { name: linux-${{ matrix.cc }}-artifacts, path: artifacts-linux }
```

Phase 5 adds `linux-appimage` (on `ubuntu-22.04`, via `Dockerfile.release`
or directly), then `linux-distro-smoke` (`needs: linux-appimage`).

## Proof each phase must hand back

1. A link to the green CI run on the phase-tip commit.
2. The artifact names and what the owner should open (screenshots/recording).
3. Harness totals (`N passed, 0 failed, K xfail`) for Linux, **and** macOS
   `driver.sh` for anything shared that changed.
4. The updated Linux baseline diff (what was removed).
5. An explicit "unverified — needs L4" list.
