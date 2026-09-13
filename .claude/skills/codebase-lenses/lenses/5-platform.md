# Lens 5 — Platform

**Question:** Does it behave the same on macOS and Windows, and does it build,
package and ship on both?

**Not this lens:** pure-C++ logic with no native call and no input handling. For
that, mark this lens Clear with the evidence ("no `Platform::` call, no
shortcut, no new file type").

## Trigger questions
- Does the change call, add or change a `Platform::` function?
- Does it touch audio devices, MIDI, video, camera, text outlines, model/image decode, Syphon/Spout, or plugin hosting?
- Does it add a key binding, a file path, a file extension, or a file dialog?
- Does it add a source file, a dependency, a GLSL feature, or a build option?
- Will it appear in a release (DMG, Windows zips, website)?

## Sub-lenses

### 5a `Platform::` contract
- **Anchors:** `src/platform/Platform.h` (the surface), `Platform.mm` (macOS), `platform/win/PlatformWin.cpp` plus siblings (Windows), `AppPaths.h`, `NetCompat.h`.
- **Rule:** every `Platform::` function has a two-sided obligation. Read both bodies before claiming a capability exists, and keep `_WIN32` out of the node layer.
- **Owning skills:** `windows-parity`, `pillar-parity-audit`.

### 5b Media & devices
| Capability | macOS | Windows |
|---|---|---|
| Audio device | CoreAudio in `Platform.mm` | `AudioDeviceWin.cpp` (WASAPI) |
| MIDI | `Platform.mm` | `MidiWin.cpp` (WinMM) |
| Video / camera | AVFoundation in `Platform.mm` | `MediaWin.cpp` (Media Foundation) |
| Image / model decode | ImageIO / ModelIO | `MediaDecodeWin.cpp` (hand-rolled OBJ/STL/PLY) |
| Background removal | Vision | ONNX Runtime |
| Text outlines | CoreText | GDI |

- **Owning skills:** `windows-parity` (per-subsystem trap catalogue).
- **Known trap:** a format supported on one side and missing on the other (model loading).

### 5c Interop & hosting
- **Anchors:** Syphon (`SyphonIn/OutNode`, `PlatformWinSyphon.cpp`), Spout (`SpoutGLBridge.*`), plugin hosting (`PluginVST3.*`, `PluginHostWin.cpp`, `PluginVST3Win.cpp`, `PluginHandleInternal*.h`), OSC (`OscNodes`, `OscMessage`), and `RemoteControl`.
- **Owning skills:** `output-projection-sweep`, `plugin-host-hardening`, `new-utility-node`.

### 5d Build & distribution
- **Anchors:** `CMakeLists.txt` (static CRT, `INFINITE_ENABLE_VST3`), `package.sh` / `package.ps1`, `dmg-extras/`, `website/`, `CrashHandlerWin.cpp`, `Infinite.rc.in`.
- **Rules:**
  - GLSL must be strict 330 (Windows drivers reject what macOS allows).
  - Paths must be wide on Windows.
  - Debug tools are compiled out of release builds.
- **Owning skills:** `ship-infinite`, `run-infinite-hygiene`, `windows-parity`.
- **Deploy rule:** after building, copy `build/Infinite.app` to `~/Desktop/Infinite.app`.

## Zoom guide
| Zoom | For Platform it means |
|---|---|
| L1 | Whether X depends on the OS at all, and through which `Platform::` door |
| L2 | A capability matrix: macOS vs Windows, implemented / partial / missing |
| L3 | `Platform.h` declaration → `.mm` body ↔ `*Win.cpp` body → callers in the node layer |
| L4 | The native API calls on each side, and where they diverge |
