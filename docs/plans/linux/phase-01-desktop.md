# Phase 1 — Desktop Surface

**Outcome:** every visual node works on Linux. Images, HDR, models, text
(2D and 3D), background removal, file dialogs, crash log, update check, and
the output/projector window. Hygiene `--fast` plus the UI, 3D and
compositing groups are green under Xvfb, with per-category screenshots.

## Start

```bash
git switch main && git pull --ff-only
git switch -c feature/linux-step-01-desktop
```

Prereq: P0 merged. Read [README.md](README.md) and the P1 rows in
[platform-inventory.md](platform-inventory.md).
Skills: `codebase-navigation`, `windows-parity` (§3.4, §3.7),
`invariant-interaction-audit` (for the shared-file extraction).

## Tasks

### 1.1 Extract shared decode code (Windows must not change)

- Move the portable body of `src/platform/win/MediaDecodeWin.cpp` into
  `src/platform/common/MediaDecodePortable.cpp`. That covers
  `LoadImageRGBA*`, `LoadImageFloatRGB`, `LoadModel` (OBJ/PLY/STL) and
  `DecodeAudioFileToBuffer` (dr_libs + AIFF).
- Replace `WPATH()` and the bare `std::ifstream(path)` calls with a helper in
  `common/PathOpen.h`: `FILE* OpenFileUtf8(const std::string&, const char* mode)`
  and an `std::ifstream` equivalent. On Windows it's `_wfopen` via
  `Utf8ToWide`; on POSIX it's `fopen`. **This also fixes the open windows-parity
  defect** (the four hand-rolled parsers taking byte paths). Mention that in the
  commit, and update `docs/WINDOWS_VERIFICATION.md`.
- Add the file to both `WIN32_SOURCES` and `LINUX_SOURCES`, and delete the
  moved code from the Windows file.
- Proof that Windows is unchanged: Windows CI green, plus `REMOVEBGTEST` and
  `DSPTEST` still passing on it. State in the commit that Windows ran only CI.

### 1.2 Dialogs

- Vendor `tinyfiledialogs.c/.h` into `external/tinyfiledialogs/` (zlib
  licence). Add it to `LINUX_SOURCES` only, and add the licence to the
  third-party notices file if the repo has one (`grep -ril "stb_image" *.md docs/`).
- Implement every `Open*/Save*Dialog` with the same filter lists as
  `PlatformWin.cpp`. On save, append the extension if it's missing.
- If `INFINITE_EXITAFTER` is set or no `DISPLAY`/`WAYLAND_DISPLAY` exists,
  return `""` immediately (never block CI).
- tinyfiledialogs shells out to `zenity`/`kdialog`/`yad`/`qarma`/`matedialog`.
  Minimal installs and some tiling-WM setups have none of them, and then a
  dialog silently does nothing, which looks like a broken button. At first
  use, check the PATH for any of them. If none exist, show a one-time
  in-app ImGui notice ("Install zenity or kdialog for file dialogs"), log
  it, and add it to `INFINITE_SYSINFO`. An xdg-desktop-portal (D-Bus)
  backend is the proper long-term fix; note it as a follow-up and don't
  build it in P1.
- CI can't click a dialog. Verification is limited to "returns `""` headless
  without hanging". Real use is L4.

### 1.3 Diagnostics

- `InstallCrashHandler`: per the inventory. Write a test that raises SIGSEGV
  in a child process (`INFINITE_CRASHTEST=1` if one exists; otherwise add a
  tiny env-var gated trap in the SysInfo TU, never in release UI) and assert
  the crash file appears. Keep the test's trigger `#ifndef NDEBUG` or
  env-only, and never reachable from UI.
- `ShowFatalError`: add `tinyfd_messageBox` (skipped when headless).

### 1.4 Text (FreeType + fontconfig)

- The `Platform::RasterizeText` contract (introduced in P0) should be:
  UTF-8 text, family, size in px, style flags, and it returns an RGBA8
  premultiplied (or whatever TextNode expects — check) top-down buffer + width/height.
  Make all three implementations return **the same pixel format**, and move
  any per-OS flip/swizzle out of TextNode into each implementation.
- `linux/TextLinux.cpp`:
  - fontconfig: `FcFontList` for `AvailableFontFamilies`; `FcFontMatch` to
    resolve family + bold/italic to a file path; cache `FT_Face` per path.
  - `RasterizeText`: FreeType layout (advance + kerning via `FT_Get_Kerning`;
    no HarfBuzz, so complex scripts won't shape — note that as a known limit),
    render with `FT_RENDER_MODE_NORMAL` into the buffer.
  - `GetTextOutlines`: `FT_Outline_Decompose`. Measure cap height from the
    **character** `'H'` (`FT_Get_Char_Index`), and match the macOS
    normalisation exactly (read `Platform.mm`'s version first).
- Fallback family when the requested one isn't installed: fontconfig's
  default match. Never fail to render.
- CI has few fonts: add `fonts-dejavu-core` to `deps-apt.sh`.
- Proof: TextNode + 3D text fixtures in the harness, and screenshots of a
  Text node and a 3D Text node, compared by eye with the macOS reference shots.

### 1.5 Background removal

- Extract the ONNX session code from `PlatformWin.cpp` (≈L609–700) into
  `common/SubjectMaskOnnx.cpp` with a hook for execution-provider
  registration: Windows registers DirectML, Linux registers nothing (CPU).
  Windows behaviour must be byte-identical.
- CMake Linux: download `onnxruntime-linux-x64-1.20.1.tgz` (same version as
  Windows; there's an aarch64 tarball for the local container) via
  FetchContent/file(DOWNLOAD) with a pinned SHA256. Link it, copy
  `libonnxruntime.so*` + `u2netp.onnx` in POST_BUILD, and set RPATH `$ORIGIN`.
- `RemoveBgNode.cpp`: flip the `kModeNames` polarity (inventory).
- Proof: `REMOVEBGTEST` passes on Linux CI.

### 1.6 Network + URL

- `HttpGet` via dlopen'd libcurl; `OpenExternalUrl` via `xdg-open`
  (inventory). The update check stays off in CI (`INFINITE_NO_UPDATE_CHECK=1`).
  Add a one-off fixture that runs `HttpGet` against
  `https://api.github.com/repos/n1m21n/Infinite/releases/latest` on CI only, to prove
  TLS works via the system libcurl.

### 1.7 Window, menus, Syphon

- The output/projector window: exercise its fixture under Xvfb (grep
  `ConfigureOutputWindow` callers for the fixture name), and write a
  screenshot.
- Window icon: `glfwSetWindowIcon` from a bundled PNG, in portable code.
- Syphon: three-way strings; hide Syphon In/Out from the Add menu and search
  on Linux; keep them registered so old patches load and show an
  "unavailable on Linux" message. Add a fixture: load a patch containing a
  Syphon node on Linux → no crash, node present.

### 1.8 Screenshots set

- Create `tools/linux/shots.sh`: for each category patch (2D, 3D, text,
  compositing, panels), run with `INFINITE_SHOWCASE=1` +
  `IMAGERESYNTH_SCREENSHOT=artifacts-linux/shots/<name>.png`.
- Generate the same set on macOS into `tools/linux/reference-shots/`
  (downscale to ≤ 800 px wide, commit only small PNGs).
- Upload both in the CI artifact so the owner can compare side by side.

### 1.9 Baseline

Remove every P1 entry from `known-test-failures-linux.txt`. Run the UI, 3D
and compositing groups (`driver.sh --group …`) under Xvfb and fix anything
that isn't a known llvmpipe precision issue.

## Exit criteria

- [ ] Linux CI green; `--fast` + UI/3D/compositing groups pass under Xvfb
- [ ] macOS `driver.sh --fast` green; Windows CI green (both arches, CRT scan)
- [ ] `REMOVEBGTEST` passes on Linux
- [ ] Screenshot artifact: category shots + reference shots; owner has looked
- [ ] Baseline has no P1 entries
- [ ] `grep -rnE "__linux__|_WIN32" src/nodes/` prints nothing
- [ ] README status row updated

## Stays unverified after P1

Real dialogs (zenity/kdialog present? blocking correctly?), real fonts on
user systems, NVIDIA/AMD GL drivers, HiDPI scaling, Wayland, and the
projector on a real second monitor.
