# Prior Art — What Other Linux Ports Taught Us

Research done on 2026-09-13 before these docs were finalised. Each lesson is
already folded into a phase file; this page says **why** a rule exists. If
you're tempted to break a rule, read its source first.

| Lesson | Source | Where it's applied |
|---|---|---|
| Real audio/MIDI apps ship **x86_64 only** on Linux | Bespoke (x64 tarball), Blender (x86_64 official builds) | README decisions |
| Build on the **oldest** supported base; glibc/libstdc++ are forward-compatible only. The "GLIBC_2.xx not found" reports come from building too new | [VCV Rack build docs](https://vcvrack.com/manual/Building), VCV community | README (Ubuntu 22.04 base), phase-05 §5.1 |
| Linking GLVND `libOpenGL.so.0` kills the AppImage on minimal installs | [audacity#12093](https://github.com/audacity/audacity/issues/12093) (Audacity 4.0, Ubuntu 26.04 minimal) | validation.md L3, phase-00 §0.2, phase-05 §5.2 |
| GL, ALSA, Pulse, JACK and X11 libs must come from the host, never be bundled | [AppImage excludelist](https://github.com/AppImage/pkg2appimage/blob/master/excludelist) | phase-05 §5.2 |
| The new static AppImage runtime removes the `libfuse2` requirement | [AppImage/type2-runtime](https://github.com/AppImage/type2-runtime) | phase-05 §5.2–5.3 |
| GitHub runner kernels have **no sound modules** (`snd-dummy`, `snd-aloop` "not found") | [runner-images#8295](https://github.com/actions/runner-images/issues/8295), [#1114](https://github.com/actions/virtual-environments/issues/1114) | validation.md L2, phase-02 §2.5 (parser test is primary) |
| The VST3 host must provide `Linux::IRunLoop` via the frame **and** the factory host context | [Steinberg: Provide a Runloop on Linux](https://steinbergmedia.github.io/vst3_dev_portal/pages/Technical+Documentation/Provide+A+Runloop+On+Linux/Index.html) | phase-04 §4.3 |
| JUCE plugins assume run-loop callbacks on the **main/UI thread** | [Steinberg forum: IRunLoop clarification](https://forums.steinberg.net/t/doc-clarification-on-irunloop/916726) | phase-04 §4.3 |
| Some JUCE editors flood events; per-frame caps make them sluggish | [yabridge CHANGELOG](https://github.com/robbert-vdh/yabridge/blob/master/CHANGELOG.md) | phase-04 §4.3 (time budget, not count cap) |
| JUCE's own Linux VST3 hosting landed as one self-contained platform commit (run loop + X11 embedding together) | [JUCE commit de712ca](https://github.com/juce-framework/JUCE/commit/de712ca02e2bca8a7b66e1f4c99ff246dd6a7c47) | phase-04 keeps host + editor + run loop in one phase |
| GLFW 3.4 selects X11/Wayland at runtime via `glfwInitHint(GLFW_PLATFORM, …)` | [GLFW 3.4 intro](https://www.glfw.org/docs/3.4/intro.html) | README decisions, phase-00 §0.4 |
| PipeWire is the default server on all major distros; the Pulse compatibility layer reportedly adds latency | general 2025–26 coverage | phase-02 §2.1 (check miniaudio for native PipeWire) |
| ImGui+GLFW apps (ImHex) ship Linux via a Docker-built AppImage in CI | [ImHex build.yml](https://github.com/WerWolv/ImHex/blob/master/.github/workflows/build.yml) | phase-05 (Dockerfile.release) — read ImHex's workflow as a template |
| Surge XT publishes pinned Linux x86_64 tarballs with VST3 (~330 MB) | [surge-synthesizer/releases-xt](https://github.com/surge-synthesizer/releases-xt/releases) | phase-04 §4.4 |

## Commit-shape pattern observed

The ports above land in this order: **platform layer → CI → packaging →
user-reported packaging fixes**. Post-release bug trackers are dominated by
*packaging* problems (missing `.so`, glibc, FUSE, GL libs), not by the
platform code. That's why L3's multi-distro and minimal-install smoke
exists, and why the beta (L4) comes before the release, not after.

## Not researched (known gaps)

- How other ImGui apps handle HiDPI on X11 (fractional scaling). Check
  GLFW's content-scale docs in P1 if screenshots from beta testers look
  wrong.
- LV2 hosting (out of scope by decision).
- Flatpak/Flathub packaging. That's a possible follow-up after the AppImage,
  since many Fedora/Steam Deck users prefer it. Not in this plan.
