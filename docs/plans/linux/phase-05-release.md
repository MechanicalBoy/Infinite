# Phase 5 — AppImage, Beta, Release

**Outcome:** a portable `Infinite-x86_64.AppImage` that runs on mainstream
distros, is validated by real users in a beta round, and ships through
`ship-infinite` next to the macOS and Windows builds.

## Start

```bash
git switch main && git pull --ff-only
git switch -c feature/linux-step-05-release
```

Prereq: P4 merged, and the Linux baseline has no P0–P4 entries.
Skills: `codebase-navigation`, `ship-infinite` (read all of it before
touching release tooling).

## Tasks

### 5.1 Release build base

- `tools/linux/Dockerfile.release`: `FROM ubuntu:22.04` (glibc 2.35 floor),
  the same `deps-apt.sh`. 22.04's CMake may be older than the project needs;
  install a pinned CMake from Kitware's tarball if so.
- CI job `linux-appimage` on `ubuntu-22.04` (or in that container), x86_64,
  Release, Clang.

### 5.2 AppImage

- Layout (the resource lookup is already `exeDir/Resources`, so keep
  everything next to the binary):

```
AppDir/
  AppRun -> usr/bin/Infinite
  infinite.desktop            Name=Infinite, Exec=Infinite %f, Icon=infinite, Categories=AudioVideo;Audio;Video;, MimeType=application/x-infinite-patch;
  infinite.png                256×256 from the existing app icon
  usr/bin/Infinite
  usr/bin/infinite-vst3-scanner
  usr/bin/Resources/…         fonts, icons
  usr/bin/assets/models/u2netp.onnx
  usr/lib/                    libonnxruntime, FFmpeg libs, anything linuxdeploy collects
  usr/share/mime/packages/infinite.xml    *.infinite (and *.inf) glob
  usr/share/metainfo/infinite.appdata.xml
```

- Use a pinned `linuxdeploy` + `appimagetool` (download with SHA256 in the
  CI step). `linuxdeploy` collects dependencies. **Exclude** the libs that
  must come from the host: libGL/libEGL/libGLX/libOpenGL, libasound,
  libpulse, libjack, libfontconfig, libfreetype (if system),
  libX11/libxcb/libwayland, glibc. Start from the community
  [excludelist](https://github.com/AppImage/pkg2appimage/blob/master/excludelist),
  and keep the final list explicit in the script.
- **Use the new static AppImage runtime**
  ([AppImage/type2-runtime](https://github.com/AppImage/type2-runtime)). It's
  statically linked, so users **don't need `libfuse2`**, which newer distros
  no longer install. Current `appimagetool` releases from
  `AppImage/appimagetool` embed it. Verify this by checking that the runtime
  in the built file has no `libfuse.so.2` dependency. Known caveat: old
  AppImageLauncher versions choke on the new runtime
  ([type2-runtime#121](https://github.com/AppImage/type2-runtime/issues/121));
  mention it in release notes.
- Keep `ldd` free of any GL library (validation.md "Minimal-install trap").
- `PollPendingOpenFile` from argv (inventory P5 row) so `Exec=Infinite %f`
  opens patches.
- `UpdateCheck.cpp`: Linux asset name `Infinite-x86_64.AppImage`; the
  update prompt links to the download and never self-replaces.
- Upload `Infinite-x86_64.AppImage` as the CI artifact.

### 5.3 L3 smoke

- Write `tools/linux/distro-smoke.sh` per validation.md and add the
  `linux-distro-smoke` CI job (`needs: linux-appimage`, matrix over distros).
  Each distro uploads its screenshot + log.
- Also run `INFINITE_SYSINFO=1` in each distro and keep the output.
- Wayland smoke under headless weston (best-effort, reported).
- Fix missing libraries by bundling or excluding (never by requiring users
  to install things, except FUSE; see below).
- Download-page note: `chmod +x Infinite-x86_64.AppImage && ./Infinite-x86_64.AppImage`.
  With the static runtime, no FUSE package is needed. If mounting fails (a
  container, or no `/dev/fuse`), use `--appimage-extract-and-run`.

### 5.4 Beta round (L4) — owner approval required for each public step

1. Add `.github/ISSUE_TEMPLATE/linux-beta-report.md` (validation.md
   contents: distro, desktop, X11/Wayland, GPU/driver, audio stack,
   `INFINITE_SYSINFO=1` paste, and a checklist of every "Stays unverified"
   item from P0–P4).
2. **Draft** (don't publish) the pre-release `vX.Y.Z-linux-beta.1` with the
   AppImage, plus a short comment for issue #14 inviting testers. Show both
   to the owner, and publish only on an explicit yes. No "Generated with
   Claude Code" line.
3. Triage the reports into fixes on this branch (or `feature/linux-step-05b-beta-fixes`).
   Repeat betas as needed, with owner approval each time.
4. Exit the beta when at least 3 testers on at least 2 distro families
   (Debian/Ubuntu + Fedora or Arch), including at least one on Wayland
   desktop and one with a MIDI controller, report core flows working.

### 5.5 Ship integration

- `ship-infinite`: add a `release-linux` step to its `driver.sh release`,
  pulling the CI AppImage onto the GitHub Release the same way it pulls the
  Windows zips. Add Linux to its checklist.
- Website (`website/index.html`): a Linux download button next to
  macOS/Windows, linking to the release asset, with the FUSE note.
  `deploy-pages.yml` publishes on the next push to main (the owner merges).
- `README.md` (repo root): add Linux to the platform list and system
  requirements (x86_64, glibc ≥ 2.35, OpenGL 3.2, X11 or XWayland).

### 5.6 Close out

- The Linux baseline should be empty, or contain only entries the owner
  approved as permanent (for example, a documented llvmpipe precision
  issue).
- Update the status table in [README.md](README.md). Append a
  "Linux-specific known limits" section: no Syphon/Spout, no AU, no LV2,
  no complex-script text shaping, VST editors need X11/XWayland, x86_64
  only.
- Update the memory file `project_linux_port.md` to say it has shipped.

## Exit criteria

- [ ] AppImage built on 22.04; distro smoke green on Ubuntu 22.04/24.04, Debian 12, Fedora, Arch
- [ ] `ldd` clean in every distro; Wayland smoke result recorded
- [ ] Beta exit condition met (5.4.4); all beta blockers fixed
- [ ] `ship-infinite` publishes the AppImage; website button live after the owner merges
- [ ] README status table complete, with verified vs. unverified per phase

## Never do without asking

Publishing a (pre-)release, commenting on #14, merging to `main`, pushing
tags, editing the live website.
