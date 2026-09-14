## Problem
AppImage fails to start on minimal distro installs with a missing shared library.

| # | Source (link) | Similarity — why | Status | Their fix (1–2 lines) | Applies to Infinite at | Confidence |
|---|---|---|---|---|---|---|
| 1 | [audacity#12093](https://github.com/audacity/audacity/issues/12093) | AppImage crashes on minimal Ubuntu install (`error while loading shared libraries: libOpenGL.so.0`) | Open / Workaround verified | Avoid linking GLVND `libOpenGL.so.0` directly; link against legacy `libGL.so.1` or bundle `libOpenGL.so.0` under a lazy `fallback/` path | `docs/plans/linux/phase-05-release.md` §5.2 & `phase-00-skeleton-and-rig.md` §0.2 | High |
| 2 | [AppImage excludelist](https://github.com/AppImage/pkg2appimage/blob/master/excludelist) | Standard rules for libraries that must NEVER be bundled in portable Linux packages | Solved / Standardized | Exclude `libGL.so.1`, `libGLdispatch.so.0`, `libGLX.so.0`, `libX11.so.6`, `libasound.so.2` so the host driver stack and display servers remain uncorrupted | `docs/plans/linux/phase-05-release.md` §5.2 (bundle configuration) | High |
| 3 | [AppImage/type2-runtime](https://github.com/AppImage/type2-runtime) | AppImage fails to mount on modern minimal distros lacking `libfuse.so.2` (Ubuntu 24.04, Fedora) | Solved / Released | Statically link musl libc and libfuse2 into the AppImage runtime header, eliminating the external `libfuse2` package requirement | `docs/plans/linux/phase-05-release.md` §5.2–5.3 (runtime binary selection) | High |
| 4 | [MuseScore make_appimage.sh](https://github.com/musescore/MuseScore) | Gracefully handles optional runtime system libraries (`libjack.so.0`, `libOpenGL.so.0`) | Solved | Store fallback libraries in `AppDir/fallback/` and conditionally prepend to `LD_LIBRARY_PATH` in `AppRun` only when the host system lacks them | `docs/plans/linux/phase-05-release.md` §5.2 (`AppRun` wrapper logic) | High |
| 5 | [ImHex build.yml](https://github.com/WerWolv/ImHex/blob/master/.github/workflows/build.yml) | ImGui + GLFW desktop application packaging reproducible AppImages across distributions | Solved | Compile in an older baseline Docker container (Ubuntu 22.04) to prevent high-water `GLIBC_2.xx` symbol requirements | `docs/plans/linux/phase-05-release.md` §5.1 (CI build container image) | High |

## Patterns across sources
- **The GLVND trap:** Modern build systems looking for OpenGL often link against `libOpenGL.so.0` by default. While standard full desktop installs have this, minimal and cloud installs only provide `libGL.so.1` or `libEGL.so.1`. Linking with `OpenGL::GL` (`libGL.so.1`) instead of `OpenGL::OpenGL` prevents missing library errors on minimal installs.
- **Strict library exclusion:** Bundling graphics driver libraries (`libGLX`, `libGLdispatch`, Mesa `swrast`) causes driver mismatch crashes (`libGL error: failed to load driver`). They must always be supplied by the host.
- **Conditional fallback loading:** For libraries that *might* be missing on minimal installs (like `libOpenGL.so.0` or `libjack.so.0`), packaging them in a `fallback/` directory and having `AppRun` test-load before adding to `LD_LIBRARY_PATH` gives the best compatibility without breaking systems that have proper hardware drivers.
- **Static AppImage runtime:** Always use the newer `type2-runtime` release that embeds static FUSE to avoid the common `libfuse.so.2: cannot open shared object file` failure on Ubuntu 22.04+ and 24.04+.

## Searched, found nothing
- `gh search issues "libOpenGL.so.0" --repo BespokeSynth/BespokeSynth` → 0 hits (Bespoke distributes as tarball rather than AppImage)
- `gh search issues "type2-runtime" --repo WerWolv/ImHex` → 0 hits (ImHex bundles runtime through direct release download in workflow)

## Open questions
- Should the Infinite AppImage include `libpipewire-0.3.so.0` as a fallback or assume modern distros have PipeWire preinstalled?
- Does Ubuntu 24.04 minimal need extra font packages (`fonts-dejavu-core`) for ImGui fallback font rendering?
