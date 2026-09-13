# Phase 4 — VST3 Plugins

**Outcome:** Linux VST3 plugins are scanned out of process, loaded,
rendered, parameter-automated, saved and restored, and their editors open
in X11 windows.

## Start

```bash
git switch main && git pull --ff-only
git switch -c feature/linux-step-04-vst3
```

Prereq: P3 merged. Skills: `codebase-navigation`, `plugin-host-hardening`
(mandatory before exit), `windows-parity` (§3.1, §3.7).
Reference, in order: `src/platform/win/PluginVST3Win.cpp` (the host: port
its structure), `src/platform/win/PluginHostWin.cpp` (facade + AU stubs),
`src/scanner_main_win.cpp`, and the SDK's
`external/vst3sdk/public.sdk/source/vst/hosting/module_linux.cpp` +
`public.sdk/source/vst/utility/` (run loop helpers, if present).

## Tasks

### 4.1 Build

- In `CMakeLists.txt`, remove the Linux force-OFF from P0. Add
  `PluginHostLinux.cpp`, `PluginVST3Linux.cpp`, and whichever VST3 SDK
  sources Windows compiles (check the Windows list; swap `module_win32.cpp`
  for `module_linux.cpp` if the SDK module loader is used, or write the
  `dlopen` loader directly as Windows does with `LoadLibraryExW`).
- Link `X11` (`libx11-dev` is already in deps) and `${CMAKE_DL_LIBS}`.
- New target `infinite-vst3-scanner` from `src/scanner_main_linux.cpp`
  (mirror the Windows scanner; same child protocol as `--vst3-scan-bundle`
  in `main.cpp`). POST_BUILD places it next to `Infinite`.

### 4.2 Host (`PluginVST3Linux.cpp`)

| Area | Linux detail |
|---|---|
| Bundle layout | `Foo.vst3/Contents/x86_64-linux/Foo.so` (`aarch64-linux` on arm64). A single-file `Foo.vst3` that is itself an `.so` is also valid (old style); support both |
| Load | `dlopen(RTLD_NOW | RTLD_LOCAL)`, call `ModuleEntry(handle)`, then `GetPluginFactory`. On unload: `ModuleExit()` then `dlclose` |
| Folders | `$HOME/.vst3`, `/usr/lib/vst3`, `/usr/local/lib/vst3` (+ user folders from settings); implement in `PluginScanner.cpp` via its per-OS table |
| Scan | out-of-process via `ScannerExecutablePath()`; timeout + crash → blocklist, sentinel under `AppSupportDir()`, same files as Windows |
| Paths | plain UTF-8 `fopen` / `std::filesystem` (no wide-path issue on Linux) |
| VST2 | top-level `.so` in `~/.vst` etc. → `UnsupportedPluginsSeen` only |

Port the rest (process setup, buses, parameter changes, MIDI events,
state streams, latency/PDC) from the Windows host. Where the logic is
identical, prefer extracting it into a shared `common/PluginVST3Common.cpp`
used by both. Windows behaviour must not change (same rule as P1).

### 4.3 Editors (X11)

- `PluginOpenEditor`: `XOpenDisplay` once (on the GLFW X11 display via
  `glfwGetX11Display()` when GLFW is on X11; if GLFW is on Wayland, open
  our own X connection to XWayland, and if there's none, return
  `"plugin editors need X11/XWayland"`).
- Create a top-level window sized from `IPlugView::getSize`, set `WM_NAME`
  + `WM_DELETE_WINDOW`, and `view->attached((void*)xid, kPlatformTypeX11EmbedWindowID)`.
- Implement **one process-wide `Steinberg::Linux::IRunLoop`**
  (`registerEventHandler`/`unregisterEventHandler` with fds,
  `registerTimer`/`unregisterTimer`). Expose it through **both** paths the
  spec requires ([Steinberg: Provide a Runloop on Linux](https://steinbergmedia.github.io/vst3_dev_portal/pages/Technical+Documentation/Provide+A+Runloop+On+Linux/Index.html)):
  1. `queryInterface` on our `IPlugFrame` (passed via `IPlugView::setFrame`), for editors;
  2. the host-context object passed to `IPluginFactory3::setHostContext`,
     so plugins can register timers **with no editor open**.
  Most Linux plugins (JUCE, DPF) won't draw or update without it.
- **Threading:** call every handler and timer on the **main thread**. The
  spec doesn't say so, but JUCE plugins implicitly require it
  ([Steinberg forum](https://forums.steinberg.net/t/doc-clarification-on-irunloop/916726)).
  Never use a background `poll()` thread for this.
- `PumpPluginEditorEvents` (called each frame from `main.cpp`, **whether or
  not an editor is open**, because factory-context timers exist without
  editors; confirm the call site isn't gated on `AnyPluginEditorOpen`):
  `poll()` the registered fds with a 0 timeout → `onFDIsSet`, fire due
  timers → `onTimer`, then drain `XPending` for our windows (close →
  `removed()`, `ConfigureNotify` → `onSize` if resizable).
- Don't cap the handlers serviced per frame too low. yabridge hit sluggish
  JUCE editors that emit thousands of events on GUI changes, and also
  plugins that re-arm forever. Loop until no fd is ready, with a time budget
  (for example 4 ms) as the only cap.
- Scaling: `IPlugViewContentScaleSupport::setContentScaleFactor` from the
  GLFW monitor content scale.
- All editor calls on the main thread only.

### 4.4 CI test with a real plugin

- Download pinned open-source Linux VST3s in CI (via `actions/cache`), pinning
  version + SHA256 in `tools/linux/test-plugins.sh`, and install into
  `$HOME/.vst3`:
  - **Small, every run:** a DPF example plugin (for example from DISTRHO's
    releases, or built from source in a cached step). Fast, and it covers
    the non-JUCE path.
  - **JUCE path, phase-tip runs:** **Surge XT** from
    [surge-synthesizer/releases-xt](https://github.com/surge-synthesizer/releases-xt/releases)
    (`surge-xt-linux-x86_64-<ver>.tar.gz`, ~330 MB, so cache it and only
    extract the `.vst3`). JUCE is the strictest about IRunLoop threading, so
    its editor screenshot is the meaningful one.
- Run the existing VST3 fixtures (grep `VST3` in the driver groups /
  `INFINITE_*VST3*`): scan finds it, load, render non-silent audio,
  parameter set/get, state save → restore round trip, latency reported.
- Editor: a fixture opens the editor under Xvfb, pumps ~120 frames, then
  captures the X window with `import -window <xid>` (ImageMagick is already
  in deps) → `artifacts-linux/vst3-editor.png`. Pass = non-blank image and
  a clean close.
- Scanner crash path: a deliberately broken `.vst3` (an `.so` that calls
  `abort()` in `ModuleEntry`, built in CI from a 5-line C file) must be
  blocklisted, not crash the app.

### 4.5 Sweep

- Run the `plugin-host-hardening` skill on the Linux host and fix what it
  finds.
- Extend `INFINITE_SYSINFO` with the VST3 folders, scan count, and
  blocklist count.
- Remove P4 entries from the baseline. It must now contain nothing from
  P0–P4.

## Exit criteria

- [ ] Scanner finds Surge XT (or the chosen plugin) in CI; load/render/param/state round trip green
- [ ] Editor screenshot artifact under Xvfb, non-blank
- [ ] Broken plugin blocklisted without crashing
- [ ] plugin-host-hardening clean; macOS `--fast` green; Windows CI green
- [ ] Baseline contains no P0–P4 entries; README status row updated

## Stays unverified after P4

Commercial plugins (u-he, Vital, TAL), editors on a real KDE/GNOME
compositor, HiDPI editor scaling, plugins that need extra system libs,
and editors under Wayland-native mode (unsupported by design).
