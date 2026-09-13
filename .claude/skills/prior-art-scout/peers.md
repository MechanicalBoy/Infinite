# Peer Repositories for Prior Art Search

Curated peer repos grouped by domain. Consult this list first when searching for how other projects solved platform, architectural, audio, visual, or packaging problems before widening to global search.

## Node-based Realtime Visuals

- `tooll3/t3` (redirects to `tixl3d/tixl`): ImGui + node graph + realtime GPU pipeline; closest architectural peer to Infinite in stack and paradigm.
- `cables-gl/cables`: WebGL node-based visual programming environment; real-world dataflow and operator graph conventions.
- `hydra-synth/hydra`: Live-coding modular video synth; signal-driven visuals and GLSL generative pipeline.
- `thedmd/imgui-node-editor`: Reference ImGui node canvas, link routing, multi-selection, and pin interaction patterns.
- `Nelarius/imnodes`: Minimalist ImGui node editor; clean link state management and pin interaction model.

## Modular & Audio Applications

- `BespokeSynth/BespokeSynth`: Realtime modular synthesizer and node environment. (Note: Clean room / MIT invariant — read architecture/commit history for concepts only; never copy GPL code).
- `VCVRack/Rack`: Modular virtual Eurorack; lock-free audio thread scheduling, cable/port patching, and module lifecycle.
- `DISTRHO/Cardinal`: Virtual modular synthesizer plugin and standalone (Carla/Rack integration and cross-platform builds).
- `surge-synthesizer/surge`: Modern open-source hybrid synth; cross-platform DSP/SIMD, packaging, and CI workflows.
- `LMMS/lmms`: Open-source DAW; ALSA/Pulse/JACK audio driver backends and multi-format plugin hosting.
- `Ardour/ardour`: Professional digital audio workstation; realtime Linux audio/MIDI latency, thread isolation, and engine design.
- `zrythm/zrythm`: Modern DAW; PipeWire/JACK integration, desktop environment integration, and audio scheduling.
- `mtytel/vital`: Modern visual wavetable synth; OpenGL rendering inside audio plugins and Linux display compatibility.

## Plugin Hosting

- `falkTX/Carla`: Production multi-format plugin host (VST2/VST3/LV2/CLAP/AU); Linux X11/Wayland window embedding and bridge architecture.
- `robbert-vdh/yabridge`: Modern Linux Wine/native VST bridge; authoritative reference on Linux VST3 run loops, X11 event dispatch, and throttling.
- `juce-framework/JUCE`: De-facto standard audio framework; reference Linux VST3 host and client implementation, X11 event loop integration.
- `steinbergmedia/vst3sdk`: Official VST3 SDK; module loading (`ModuleEntry`/`GetPluginFactory`), Linux `IRunLoop`, and host contracts.
- `Tracktion/tracktion_engine`: Real-world production DAW engine; plugin host lifecycle, scan/sandboxing, and audio graph processing.

## Cross-Platform Shipping & Packaging

- `audacity/audacity`: Multi-platform audio editor; Linux AppImage packaging, GLVND/OpenGL runtime dependencies, and audio backends.
- `musescore/MuseScore`: Large-scale desktop app; multi-distro AppImage packaging, font rendering, and platform abstraction.
- `obsproject/obs-studio`: Production realtime video/audio capture; Wayland/PipeWire/OpenGL/X11 platform layers and CI builds.
- `WerWolv/ImHex`: ImGui + GLFW desktop hex editor; modern Docker-based AppImage packaging and multi-distro release workflows.
- `blender/blender`: Production 3D/GL application; Linux ABI compatibility, static bundling conventions, and GL context handling.

## Video, Capture & OpenGL

- `mpv-player/mpv`: High-performance video player; Linux display backends (X11/Wayland), GL/EGL context management, and frame pacing.
- `glfw/glfw`: Windowing and input library used by Infinite; X11/Wayland backend differences, cursor/scaling/event contracts.
- `ocornut/imgui`: Core UI library used by Infinite; docking, viewport management, and keyboard/mouse event dispatch.
- `Syphon/Syphon-Framework`: macOS inter-app frame sharing protocol implemented by Infinite.
- `leadedge/Spout2`: Windows inter-app texture sharing protocol implemented by Infinite.

## Core Libraries Used by Infinite

- `mackron/miniaudio`: Audio playback and capture engine used by Infinite; ALSA, PulseAudio, JACK, WASAPI, and CoreAudio backends.
- `nothings/stb`: Single-file image loading and writing libraries used across Infinite's asset pipeline.
- `syoyo/tinyexr`: HDR OpenEXR loading and saving library used in Infinite's image pipeline.
- `microsoft/onnxruntime`: Machine learning runtime used by Infinite's neural network and inference nodes.
