# Linux Platform Inventory

The checklist. Every `Platform::` function, every `#if` outside
`src/platform/`, and every build-system site, each with its Linux strategy
and the phase that owns it. Tick items off in the phase's commit messages.
Re-grep before editing, because line numbers drift.

Legend: **S** = stub in P0 (fill `outError` if it has one, return
false/empty/0). **Impl Pn** = real implementation lands in phase n.

## Linux file layout

```
src/platform/linux/
  PlatformLinux.cpp        misc desktop: app nap, trackpad, dialogs, crash, log, fatal, url, http, docs, window
  TextLinux.cpp            fonts + GetTextOutlines + text raster (FreeType + fontconfig)
  AudioDeviceLinux.cpp     miniaudio: output, input capture, analyze, device list, recovery
  MidiLinux.cpp            ALSA sequencer
  MediaLinux.cpp           FFmpeg: video decode, video audio track, recorder, InspectMovie
  CameraLinux.cpp          V4L2
  PluginHostLinux.cpp      AU stubs + VST3 facade dispatch (mirrors win/PluginHostWin.cpp)
  PluginVST3Linux.cpp      VST3 host (P4)
  SyphonLinux.cpp          stubs
src/platform/common/       code shared by Windows + Linux (extracted from win/, Windows behaviour unchanged)
  MediaDecodePortable.cpp  image/HDR/EXR/model/audio-file decode (from win/MediaDecodeWin.cpp) — P1
  SubjectMaskOnnx.cpp      u2netp via ONNX Runtime (from win/PlatformWin.cpp), EP registration hook — P1
  PathOpen.h               UTF-8 path → FILE*/ifstream (wide on Windows, plain on POSIX)
src/scanner_main_linux.cpp VST3 scanner helper entry (P4)
```

## Platform.h functions (~137)

### Desktop / app (PlatformLinux.cpp)

| Function(s) | Linux strategy | Phase |
|---|---|---|
| `PreventAppNap` | no-op (no App Nap equivalent affecting GLFW) | S, final |
| `PollTrackpadMagnificationDelta` | return 0.0 (GLFW exposes no gestures), like Windows | S, final |
| `InstallCrashHandler` | `sigaction` for SEGV/BUS/ILL/FPE/ABRT on an alternate signal stack; write `AppSupportDir()/crash/<ts>.txt` with `backtrace()`/`backtrace_symbols_fd` (async-signal-safe fd writes only), then re-raise | Impl P1 |
| `AppendLogLine` | append to `AppSupportDir()/log.txt`; also stderr | Impl P1 |
| `ShowFatalError` | stderr + `AppendLogLine` + `tinyfd_messageBox` (skip the box when `INFINITE_EXITAFTER`/headless) | Impl P1 |
| `OpenImageDialog`, `OpenHdrDialog`, `OpenModelDialog`, `OpenPatchDialog`, `SavePatchDialog`, `OpenDeviceDialog`, `SaveDeviceDialog`, `OpenVideoDialog`, `OpenAudioDialog`, `OpenFolderDialog` | tinyfiledialogs with the same filters as `PlatformWin.cpp`; `""` on cancel. Save dialogs append the extension if the user omitted it | S → Impl P1 |
| `OpenExternalUrl` | validate `http(s)://` exactly as the Windows version does, then `posix_spawnp("xdg-open")`, detached; never through a shell | Impl P1 |
| `HttpGet` | `dlopen("libcurl.so.4")`; resolve `curl_easy_*`; enforce timeout + size cap as documented; false + reason if libcurl is absent | Impl P1 |
| `InitDocumentHandlingPreGlfw`, `InitDocumentHandlingPostGlfw` | no-op | S, final |
| `PollPendingOpenFile` | once: return the first existing file path from `/proc/self/cmdline` ending in `.infinite`/`.inf`/`.field` (the `.desktop` file launches `Infinite %f`); false after | Impl P5 |
| `ExecutablePath` | `readlink("/proc/self/exe")` | Impl P0 (needed for Resources lookup) |
| `ScannerExecutablePath` | `dirname(ExecutablePath()) + "/infinite-vst3-scanner"` | Impl P4 |
| `SuppressAppUIForHeadlessProcess` | no-op | S, final |

### Images, models, text

| Function(s) | Linux strategy | Phase |
|---|---|---|
| `LoadImageRGBA`, `LoadImageRGBAFromMemory`, `LoadImageFloatRGB`, `LoadModel` | shared `common/MediaDecodePortable.cpp` (extracted from `win/MediaDecodeWin.cpp`: stb_image, tinyexr, OBJ/PLY/STL) | Impl P1 |
| `DecodeAudioFileToBuffer` | same shared file (dr_wav/mp3/flac + AIFF); **P3 adds an FFmpeg fallback** for m4a/alac/ogg/opus that dr_libs can't read | Impl P1, extend P3 |
| `AvailableFontFamilies` | fontconfig `FcFontList` families, sorted, deduped, cached | Impl P1 |
| `GetTextOutlines` | FreeType `FT_Outline_Decompose`, flattening conics/cubics the same way `Platform.mm` does. Normalise so cap height ≈ 1 using the **character** `H` (see the windows-parity §3.4 trap; don't repeat it). Keep winding as-is | Impl P1 |

### Background removal

| Function(s) | Linux strategy | Phase |
|---|---|---|
| `SubjectMask` | shared `common/SubjectMaskOnnx.cpp`; CPU EP only on Linux; model at `dirname(exe)/assets/models/u2netp.onnx`. `MattingMode::Person` behaves as Windows does | Impl P1 |
| `MattingBackend` | `"CPU (ONNX Runtime)"` | Impl P1 |

### Audio (AudioDeviceLinux.cpp — miniaudio)

| Function(s) | Linux strategy | Phase |
|---|---|---|
| `AudioDeviceOpen`, `AudioDeviceClose`, `AudioDeviceBufferFrames` | `ma_device` playback (duplex when input capture is wanted), `ma_format_f32`, deinterleave into the planar callback. Honour requested rate/frames as hints and report what was negotiated. Teardown: `joinable()` rule (windows-parity §3.1) | Impl P2 |
| `AudioListDevices` | `ma_context_get_devices`; `deviceId` = 1-based index into the cached list (the same scheme as `AudioDeviceWin.cpp`) | Impl P2 |
| `AudioDeviceConfigDidChange`, `AudioWillSleep`, `AudioDidWake`, `AudioDeviceDebugSimulateConfigChange` | latch atomics from miniaudio's `notificationCallback` (rerouted/stopped/interruption). Sleep/wake: latch on `ma_device_notification_type_interruption_*`; logind D-Bus is out of scope | Impl P2 |
| `AudioPcmConversionSelfTest` | print `AUDIOPCMTEST OK`, return true (miniaudio converts) | S, final |
| `AudioStart/Stop/IsRunning/DeviceName/Read/SetSmoothing/SetGain` (Audio Analyze) | separate `ma_device` capture + the same band/onset analysis Windows uses. Read `AudioDeviceWin.cpp` and share the analysis math if it is not already shared | Impl P2 |
| `AudioInputCapture*` (AddRef/RemoveRef/SetDevice/GetDevice/Pump/IsRunning/Read×2) | lock-free ring fed by the capture side, per-reader cursors, same semantics as the Windows implementation | Impl P2 |
| `AudioSpikeStart/Stop/GetStats` | stub, like Windows (throwaway P0 API) | S, final |

### MIDI (MidiLinux.cpp — ALSA sequencer)

| Function(s) | Linux strategy | Phase |
|---|---|---|
| `MidiStart/Stop/IsRunning/DeviceSummary/DeviceName` | open a seq client, create one input port, subscribe to every readable hardware/software port (skip our own and `System`), and re-subscribe on `SND_SEQ_EVENT_PORT_START/EXIT` (hotplug). One reader thread | Impl P2 |
| `MidiRead`, `MidiPollLastTouched`, `MidiNoteHitCount`, `MidiChannelLastNote` | same tables and locking as macOS | Impl P2 |
| `MidiReadNotesSince`, `MidiNoteStreamPosition` | lock-free ring, single producer (one reader thread, so the MPMC trap from windows-parity §3.3 doesn't apply) | Impl P2 |
| `MidiClockIsPresent`, `MidiClockBpm` | handle `SND_SEQ_EVENT_CLOCK/START/STOP` as their own event types (ALSA decodes them for you, so there's no status-byte masking trap) | Impl P2 |
| `MidiDeviceId` | stable id = hash of `client:port` name (not the numeric address, which changes across reboots). Document the choice | Impl P2 |

### Video, recorder, camera

| Function(s) | Linux strategy | Phase |
|---|---|---|
| `VideoOpen/Close/Width/Height/Duration/FrameAt/DecodeIsCatchingUp` | libavformat + libavcodec (threaded decode) + swscale → RGBA, row-flipped. Choose synchronous (like macOS, `DecodeIsCatchingUp` = false) or a worker thread (like Windows); **match whichever `RunArrange*`/video fixtures assume** | Impl P3 |
| `DecodeVideoAudioTrackToBuffer` | libavformat + swresample → planar float; return the exact string `"no audio track in this file"` when there is none | Impl P3 |
| `Recorder*` (Start, Append×2, SetInputIsBgra, AcquireFrameBuffer, Pending/DroppedFrameCount, SetTestQueueByteBudget, AppendAudio, Stop, Cancel, QueueHasRoom, FlushPendingAudio, KickEncoder, FinishAudioInput, DebugState, FrameCount) | encoder worker thread with the same queue/byte-budget/pool design as `MediaWin.cpp`; BGRA bottom-up → swscale → yuv420p → libx264 (H.264) + AAC in `.mp4`, matching Windows' output codecs. `FlushPendingAudio`/`KickEncoder` may be no-ops if audio is written synchronously (as on Windows) | Impl P3 |
| `InspectMovie` | libavformat stream durations + frame count | Impl P3 |
| `CameraListDevices/Open/Close/IsRunning/SetMirror/SetResolution/ReadFrame` | V4L2: enumerate `/dev/video*` with `VIDIOC_QUERYCAP` (capture-capable only). Capture thread with mmap buffers; YUYV → RGBA, MJPEG → `stbi_load_from_memory`; mirror + flip on copy | Impl P3 |

### Plugins (PluginHostLinux.cpp / PluginVST3Linux.cpp)

| Function(s) | Linux strategy | Phase |
|---|---|---|
| `EnumerateAudioUnits`, `DescribeAudioUnitBundle` | empty / false, like Windows | S, final |
| `EnumerateVST3Plugins`, `DescribeVST3Bundle`, `CacheVST3BundlePath`, `SetVST3SearchFolders`, `VST3Blocklist`, `ClearVST3Blocklist`, `VST3ScanFailures`, `UnsupportedPluginsSeen` | mirror `win/PluginVST3Win.cpp` structure: an out-of-process scan via `infinite-vst3-scanner`, a blocklist + crash sentinel under `AppSupportDir()`. Module loading via `dlopen` of `<bundle>.vst3/Contents/x86_64-linux/<name>.so` + `ModuleEntry`/`ModuleExit` (see the SDK's `public.sdk/source/vst/hosting/module_linux.cpp`). Flag top-level `.so` files as unsupported (VST2) | S → Impl P4 |
| `PluginCreate/Poll/Prepare/Destroy/DescriptionOf/LatencySamples/Render/ScheduleMIDIEvent/Parameter*/SetParameter/GetParameter/BeginLearn/EndLearn/PollLearned/SaveState/RestoreState` | port from `PluginVST3Win.cpp`; the real-time rules are identical | S → Impl P4 |
| `PluginOpenEditor/CloseEditor/EditorIsOpen`, `AnyPluginEditorOpen`, `PumpPluginEditorEvents` | own Xlib top-level window, `IPlugView::attached(xid, kPlatformTypeX11EmbedWindowID)`. One process-wide `Steinberg::Linux::IRunLoop` (fd handlers + timers), exposed via `IPlugFrame` **and** `IPluginFactory3::setHostContext`. All callbacks on the main thread (JUCE requires it). `PumpPluginEditorEvents` services it every frame **even with no editor open**, with `poll()` + `XPending`. Needs X11 (XWayland on Wayland desktops). See phase-04 §4.3 | S → Impl P4 |

### Syphon (SyphonLinux.cpp)

| Function(s) | Linux strategy | Phase |
|---|---|---|
| `SyphonServer*`, `SyphonGetAvailableServers`, `SyphonClient*` | stubs: null handles, empty lists, false. The nodes are hidden from the Add menu on Linux (see main.cpp items) | S, final |

### Windows-only block (`#if defined(_WIN32)` at the end of Platform.h)

`ConfigureOutputWindow`, `ReassertOutputWindowTopmost`,
`SetWindowIconFromResource`: **don't define these on Linux.** Linux uses
`main.cpp`'s non-Windows GLFW path. Window icon: P1 calls `glfwSetWindowIcon`
from the bundled icon PNG in portable code (not behind `_WIN32`); X11 honours
it, and on Wayland the `.desktop` file supplies it.

---

## `#if` sites outside src/platform (captured on 2026-09-13; re-grep `__APPLE__|_WIN32`)

| Site | Today | Linux change | Phase |
|---|---|---|---|
| `src/core/gl3.h` | `__APPLE__` → OpenGL/gl3.h, else glad | none | — |
| `src/platform/AppPaths.h` `AppSupportDir()` | `#else` = `~/Library/Application Support` (**macOS**) | new `__linux__` branch: `$XDG_CONFIG_HOME/Infinite`, else `~/.config/Infinite`. Also check `DesktopDir`-style helpers (fall back to `xdg-user-dir DESKTOP`, else `$HOME`) | P0 |
| `src/platform/NetCompat.h` | POSIX default | none | — |
| `src/nodes/TextNode.cpp` (includes, `Rasterize`, font list, BGRA flip) | `#else` = **GDI+ (Windows)** | move rasterisation behind a new `Platform::RasterizeText(...)` (and the node's font list onto the existing `Platform::AvailableFontFamilies`). Move the CoreText code verbatim into `Platform.mm`, the GDI+ code verbatim into `win/`, and write the FreeType version in `linux/TextLinux.cpp`. Keep the pixel format each side returns explicit in the signature. Net effect: zero platform `#if` left in TextNode | P1 (P0: compile it out on Linux with a temporary `Rasterize` that clears to transparent, **inside `linux/`**, not in the node) |
| `src/nodes/RemoveBgNode.cpp` `kModeNames` | `_WIN32` → GPU label; else macOS labels | flip polarity: `__APPLE__` → macOS labels, else `{ "Salient subject" }` (the Windows label wording can drop "(GPU)" when the backend is CPU; derive the suffix from `MattingBackend()` at draw time instead) | P1 |
| `src/nodes/ImageSpectralSynthNode.cpp` | `#else <GL/gl.h>` | include `gl3.h` unconditionally | P0 |
| `src/nodes/AnalyzeNodes.cpp`, `PaulStretchNode.cpp`, `src/audio/dsp/MolderDsp.cpp` | Accelerate vs `PortableFft` | none (portable default) | — |
| `src/audio/AudioFileWriter.cpp` | `_stat64`/`localtime_s` vs POSIX | none | — |
| `src/audio/PluginScanner.cpp` VST3 folders | Windows folders; `#else` = macOS folders? **verify** | Linux: `~/.vst3`, `/usr/lib/vst3`, `/usr/local/lib/vst3` (the VST3 spec's Linux locations) | P4 |
| `src/core/UpdateCheck.cpp` `ExpectedAssetName()` | Apple / Win(x64/ARM64) / else `{}` | add `__linux__` → `"Infinite-x86_64.AppImage"` (and make the updater only *point* at the download; it must not self-replace the AppImage) | P5 |
| `main.cpp` top: CoreFoundation include, `malloc_zone_statistics` test (≈L4, ≈L47590) | Apple-only; the test's `#else` path | confirm the `#else` compiles and skips cleanly (optional: `mallinfo2()` on glibc) | P0 |
| `main.cpp` `<fcntl.h>/<io.h>` (≈L44), `_setmode` in scanner child (≈L52909) | Windows-only | none | — |
| `main.cpp` `MODKEY` (≈L52) | `_WIN32` "Ctrl" else "Cmd" | flip: `__APPLE__` "Cmd" else "Ctrl". Shortcut handling already accepts `KeyCtrl || KeySuper` | P0 |
| `main.cpp` Syphon display names + "no servers" text + node descriptions (≈L509, L6827, L30981, L31527) | `_WIN32` Spout text, else macOS text | three-way via `__APPLE__` / `_WIN32` / else "not available on Linux". **Hide Syphon In/Out from the Add menu and search on Linux** (keep the factory registration so patches still load, and show an "unavailable on Linux" body) | P1 |
| `main.cpp` sample-rate/buffer combos disabled (≈L34425–34470) | Windows shared mode only | none; Linux keeps them enabled (miniaudio honours them) | — |
| `main.cpp` `kPatchExtension` (≈L36626) | `_WIN32` ".infinite" else ".inf" | flip: `__APPLE__` ".inf" else ".infinite" | P0 |
| `main.cpp` output-window fullscreen (≈L36856, L36906, L75654) + `SetWindowIconFromResource` (≈L37050, L53003) | Windows `Platform::` calls; else GLFW attribs | Linux uses the GLFW path. P1 checks it on X11 via an Xvfb fixture; on Wayland, fullscreen uses `glfwSetWindowMonitor` since positioning is ignored | P1 |
| `main.cpp` `SPOUTLOOPTEST` (≈L41137) | `!_WIN32` → SKIP | none | — |
| `main.cpp` resource dir (≈L52736) | Apple bundle; else `exeDir/Resources` | none: the AppImage lays out `usr/bin/Infinite` + `usr/bin/Resources/` + `usr/bin/assets/` | — |
| `main.cpp` glad load (≈L53008 `#if !defined(__APPLE__)`) | glad on non-Apple | none (verify the log line prints the Mesa version) | P0 |
| `main.cpp` `glfwInitHint(GLFW_COCOA_MENUBAR…)` (≈L52960) | Cocoa hint | add the portable X11-preference hint described in README decisions (call `glfwPlatformSupported` first) | P0 |

After P1, this must print nothing:
`grep -rnE "__linux__|_WIN32" src/nodes/`

## CMakeLists.txt

| Site | Change | Phase |
|---|---|---|
| `enable_language` block | nothing for Linux | — |
| `FetchContent` | add FreeType (static, no brotli/harfbuzz/png/zlib/bzip2) behind `if(LINUX)`; FLAC is currently `if(WIN32)`: widen to `if(WIN32 OR LINUX)` if `AudioFileWriter.cpp` is used on Linux | P0/P1 |
| `INFINITE_ENABLE_VST3 AND NOT APPLE AND NOT WIN32` FATAL_ERROR | P0: on Linux, **force VST3 OFF with a status message** instead of failing (plugin functions stub). P4: remove the guard and wire the Linux VST3 sources | P0 → P4 |
| new `LINUX_SOURCES` list + `if(LINUX)` (CMake ≥ 3.25 defines `LINUX`; otherwise use `CMAKE_SYSTEM_NAME STREQUAL "Linux"`) | `src/platform/linux/*.cpp`, `src/platform/common/*.cpp`, `src/audio/AudioFileWriter.cpp`, `external/glad/src/gl.c`, `external/miniz.c`, vendored `tinyfiledialogs.c` | P0 (grows per phase) |
| link | `Threads::Threads dl m`, `fontconfig`, `asound` (P2), FFmpeg (P3), `X11` (P4), ONNX Runtime (P1). **Not** libcurl (dlopen'd) | per phase |
| defines | `_USE_MATH_DEFINES` not needed; keep `IMGUI_*` (the existing `if(NOT WIN32)` block covers it) | — |
| POST_BUILD | copy `Resources/fonts`, `Resources/icons`, `assets/models/u2netp.onnx`, `libonnxruntime.so*` next to the binary (the same as the Windows POST_BUILD block) | P0 (fonts/icons), P1 (onnx) |
| RPATH | `set_target_properties(Infinite PROPERTIES BUILD_RPATH_USE_ORIGIN ON INSTALL_RPATH "$ORIGIN:$ORIGIN/../lib")` so bundled `.so` files resolve inside the AppImage | P1 |
| compile flags | Clang/GCC: `-Wall` as on macOS; don't add `-Werror` globally. If GCC OOMs or is too slow on `main.cpp`, try `-O1` for that one file on GCC only, documented like the MSVC `/Od` note | P0 |
