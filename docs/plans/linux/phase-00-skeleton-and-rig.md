# Phase 0 — Skeleton + Validation Rig

**Outcome:** Linux builds in CI (Clang + GCC), the headless tests pass, and
the node canvas renders under Xvfb, with a screenshot to prove it. Every
`Platform::` function exists on Linux, mostly as stubs. The full validation
rig from [validation.md](validation.md) exists and runs.

## Start

```bash
cd /Users/namansoni/infinte
git fetch origin && git switch main && git pull --ff-only
git switch -c feature/linux-step-00-skeleton
```

Read first: [README.md](README.md) (all of it), [validation.md](validation.md),
[platform-inventory.md](platform-inventory.md).
Skills: `codebase-navigation`, `windows-parity` (§0, §2, §3.9).

## Tasks (in order, one commit each where sensible)

### 0.1 Local container (L0)

- Create `tools/linux/deps-apt.sh`, `Dockerfile`, `local.sh` and `build.sh`
  as specified in validation.md. Make them `chmod +x`, `set -euo pipefail`.
- Check that `docker info` works (OrbStack). If it doesn't, stop and tell the
  owner to run `brew install --cask orbstack` and open OrbStack once. Don't
  try to install it yourself (macOS App Management blocks it).
- The container build will fail until 0.2–0.4 land. That's expected.

### 0.2 CMake Linux branch

In `CMakeLists.txt` (re-grep `WIN32_SOURCES`, `INFINITE_ENABLE_VST3`):

- Add `LINUX_SOURCES`: `src/platform/linux/*.cpp` (list explicitly, no
  glob), `external/glad/src/gl.c`, `external/miniz.c`,
  `src/audio/AudioFileWriter.cpp`. Check what `AudioFileWriter.cpp` needs
  (FLAC, shine) and widen those `if(WIN32)` FetchContent blocks to include
  Linux.
- Pick sources with `elseif(CMAKE_SYSTEM_NAME STREQUAL "Linux")`.
- VST3: on Linux, replace the FATAL_ERROR with
  `set(INFINITE_ENABLE_VST3 OFF CACHE BOOL "" FORCE)` + `message(STATUS "VST3 on Linux lands in P4")`.
  Make sure every VST3 source/define is already conditional on the option. If
  something compiles VST3 regardless, gate it.
- Link: `Threads::Threads ${CMAKE_DL_LIBS} m`. Add others as you use them
  (fontconfig comes in P1). **Never link `OpenGL::GL`/`libGL`/`libOpenGL`**:
  GLFW loads GL at runtime, and linking it breaks minimal installs (see
  validation.md L3, "Minimal-install trap"). Add the `ldd` GL check to CI now.
- POST_BUILD: copy `Resources/fonts` + `Resources/icons` to
  `$<TARGET_FILE_DIR:Infinite>/Resources/` (mirror the Windows block).
- GLFW: make sure the GLFW FetchContent builds both X11 and Wayland
  (`GLFW_BUILD_X11 ON`, `GLFW_BUILD_WAYLAND ON`).

### 0.3 `src/platform/linux/` stubs

Create the files listed in the platform-inventory layout. Every function in
`Platform.h` (outside the `_WIN32` block) gets a definition:

- **Real in P0:** `ExecutablePath` (`/proc/self/exe`), `AppendLogLine`
  (append + stderr), `ShowFatalError` (stderr only for now).
- **Everything else:** a stub per the inventory: fill `outError`
  (`"not yet implemented on Linux (P<n>)"`), return false/empty/0/nullptr.
  Include the phase number in the message so the stub is traceable.
- Copy the exact declarations from `Platform.h`. **Don't retype them.**
  Default arguments stay in the header only.
- The link is the check. An unresolved symbol means a missing stub.

Tip: grep the Windows side for the full list, since it has already solved
"every function defined":
`grep -hoE "^[A-Za-z].*Platform::[A-Za-z0-9_]+\(" src/platform/win/*.cpp | sort -u`
(or scan for `^\s*[^/].*\b(\w+)\(` inside `namespace Platform {` in
`Platform.h`).

### 0.4 Portable fixes (see the inventory's `#if` table for each)

| Change | File |
|---|---|
| XDG `AppSupportDir()` (`$XDG_CONFIG_HOME/Infinite` or `~/.config/Infinite`) | `src/platform/AppPaths.h` |
| Flip `MODKEY` to `__APPLE__` "Cmd" / else "Ctrl" | `src/main.cpp` |
| Flip `kPatchExtension` to `__APPLE__` ".inf" / else ".infinite" | `src/main.cpp` |
| Include `gl3.h` instead of `<GL/gl.h>` | `src/nodes/ImageSpectralSynthNode.cpp` |
| GLFW X11 preference: before `glfwInit`, if `getenv("INFINITE_WAYLAND")` is unset and `getenv("DISPLAY")` is set, `glfwInitHint(GLFW_PLATFORM, GLFW_PLATFORM_X11)`. Guard it with `#if !defined(__APPLE__) && !defined(_WIN32)` next to the existing Cocoa hint, or better, a `Platform::` pre-init hook if you add one to all three sides | `src/main.cpp` |
| TextNode: it won't compile (GDI+ in `#else`). **Minimal P0 fix:** add `Platform::RasterizeText` (the P1 contract, see phase-01 §1.4) with a Linux stub that returns an empty image, and move the GDI+ body into `win/` and the CoreText body into `Platform.mm` now. If that's too big for P0, do it anyway: there's no other way to compile TextNode on Linux without breaking rule 3 | `src/nodes/TextNode.cpp`, `Platform.h`, `Platform.mm`, `win/` |
| Anything else that fails to compile: fix it in the portable direction, and add a row to platform-inventory.md | — |

After each flip: `.claude/skills/run-infinite-hygiene/driver.sh --fast` on
macOS must stay green.

### 0.5 Make the harness OS-aware

- `.claude/skills/run-infinite-hygiene/driver.sh`: `BIN` defaults by `uname -s`
  (`Darwin` → the `.app` path, `Linux` → `build-linux/Infinite`), with an
  env override `INFINITE_BIN`. Known-failures file: `known-test-failures-linux.txt`
  on Linux. Skip the macOS `cmake --build build` step on Linux; call
  `tools/linux/build.sh` instead.
- Create `known-test-failures-linux.txt`. Run the fast tier and add **every**
  failure caused by a stub, each with a reason and a phase
  (`NAME|stubbed: MIDI (P2)`). Anything that fails for a reason that is *not*
  a stub is a real bug. Fix it or raise it with the owner. Don't baseline it.
- `.github/scripts/headless-tests.sh`: add the `Linux` branch. Any test that
  needs a stubbed subsystem prints `SKIP (Linux P<n>)` rather than failing.

### 0.6 `INFINITE_SYSINFO`

- New TU `src/core/SysInfo.cpp` + `.h` (add it to `COMMON_SOURCES`). When
  `INFINITE_SYSINFO=1`: create a hidden GLFW window, print `GL_VENDOR`,
  `GL_RENDERER`, `GL_VERSION`, the GLSL version, the GLFW platform
  (`glfwGetPlatform()`), OS (`uname`), and the app version. Then exit 0.
- Hook it in `main.cpp` where the other early env-var modes dispatch (keep it
  to a single call line).
- It works on all three OSes. Later phases append their subsystems.

### 0.7 CI (L1 + L2)

- Add `tools/linux/xvfb-harness.sh` (steps 1, 2, 5, 6 from validation.md;
  steps 3–4 arrive in P2, but land the MIDI spike below now).
- Add the `linux` job to `.github/workflows/build.yml` per the sketch, and
  wire it into the `detect` job's path filters the same way macos/windows are.
- **Spikes. Record the answers in validation.md, replacing "known unknown":**
  1. Kernel MIDI on `ubuntu-24.04`. Public reports say the runner's azure
     kernel has **no** sound modules (see validation.md L2 step 4), so
     expect failure. Spend at most 30 minutes on it:
     `sudo apt-get install -y linux-modules-extra-$(uname -r); sudo modprobe snd-seq snd-virmidi; ls /dev/snd/seq`.
     Try it in the OrbStack container too. Record the result. Either way,
     P2's primary MIDI proof is the parser unit test.
  2. GCC peak RSS on `main.cpp` (`/usr/bin/time -v`) and build time on the
     runner. If the runner OOMs, apply the per-file `-O1` fallback from the
     inventory and document it.
  3. How long the fast tier takes under llvmpipe. Set the job timeout to ~2×
     that.

### 0.8 Push + prove

```bash
git push -u origin feature/linux-step-00-skeleton
gh run watch            # or: gh run list --branch feature/linux-step-00-skeleton
```

Iterate until green. Also run `tools/linux/local.sh build && tools/linux/local.sh test --fast`
once locally (arm64) to prove L0 works for later phases.

## Exit criteria

- [ ] `linux (clang)` and `linux (gcc)` CI jobs green; macOS and Windows jobs still green
- [ ] `headless-tests.sh` passes on Linux (SKIPs allowed only for stubbed subsystems)
- [ ] `xvfb-harness.sh --fast` passes against `known-test-failures-linux.txt`
- [ ] Artifact contains a canvas screenshot (`INFINITE_SHOWCASE=1` + `IMAGERESYNTH_SCREENSHOT`) that is not black and shows nodes
- [ ] `INFINITE_SYSINFO=1` output in the CI log shows `llvmpipe` and GL ≥ 3.2 and `X11`
- [ ] `grep -rnE "__linux__|_WIN32" src/nodes/` prints nothing
- [ ] macOS `driver.sh --fast` green
- [ ] Spike answers written into validation.md
- [ ] README status row updated

## Stays unverified after P0

Everything user-facing: no dialogs, no audio, no MIDI, no video, no plugins,
and no real GPU has ever run it. Say so in the phase report.
