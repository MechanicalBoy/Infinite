# Phase 2 — Audio + MIDI

**Outcome:** sound comes out, audio input and Audio Analyze work, and MIDI
arrives. Proven on the miniaudio null backend and a PulseAudio null sink,
plus a virtual ALSA MIDI port if P0's spike found one.

## Start

```bash
git switch main && git pull --ff-only
git switch -c feature/linux-step-02-audio-midi
```

Prereq: P1 merged. Read [README.md](README.md) and the audio/MIDI rows in
[platform-inventory.md](platform-inventory.md).
Skills: `codebase-navigation`, `windows-parity` (§3.1, §3.2, §3.3, §3.6),
`audio-pipeline-sweep` (mandatory before exit).

**Reference implementation:** read `src/platform/win/AudioDeviceWin.cpp` and
`MidiWin.cpp` end to end first. Keep the same semantics, but don't copy their
open bugs.

## Tasks

### 2.1 miniaudio

- Vendor `miniaudio.h` (single header, pin the version in a comment) into
  `external/miniaudio/`, and put `#define MINIAUDIO_IMPLEMENTATION` in exactly
  one Linux TU. Compile only the Linux backends you need:
  `MA_ENABLE_ONLY_SPECIFIC_BACKENDS` + `MA_ENABLE_ALSA`, `MA_ENABLE_PULSEAUDIO`,
  `MA_ENABLE_JACK`, `MA_ENABLE_NULL`. It uses `dlopen`, so no link deps.
- Backend order: PulseAudio (covers PipeWire) → ALSA → JACK. If
  `INFINITE_AUDIO_BACKEND` is `null|alsa|pulse|jack`, force that one.
- PipeWire is now the default sound server on Fedora, Ubuntu, Debian and
  Arch. Its Pulse compatibility layer reportedly adds roughly 10–20 ms and
  may resample. Check whether the miniaudio version you pin has a **native
  PipeWire backend**, and if it does, prefer it before Pulse. Don't
  assume either way; read its changelog. If it doesn't, Pulse compat is
  acceptable for v1, and JACK (served by PipeWire's JACK shim) is the
  low-latency route. Surface it in the audio settings device list as a
  separate backend choice.

### 2.2 Output device (`AudioDeviceLinux.cpp`)

| Rule | Detail |
|---|---|
| Callback format | `ma_format_f32`, interleaved in miniaudio; deinterleave into the engine's planar callback buffer (preallocated in `Open`, never allocated in the callback) |
| Rate / buffer | pass the requested rate + `periodSizeInFrames` as hints, and report the negotiated values via `outSampleRate` / `AudioDeviceBufferFrames()` |
| Device ids | 1-based index into the cached list, same as Windows; 0 = default |
| Recovery | `notificationCallback`: `rerouted`/`stopped` unexpected → latch `ConfigDidChange`; `interruption_began/ended` → WillSleep/DidWake. `AudioDeviceDebugSimulateConfigChange` sets the latch |
| Teardown | `ma_device_uninit` then any own thread: `running=false; if (t.joinable()) t.join();` (windows-parity §3.1) |
| Denormals | no global FTZ (windows-parity §3.6) |
| Real-time safety | no locks, no allocation, no logging in the callback |

### 2.3 Input + analysis

- `AudioInputCapture*`: capture device (or the duplex side) → SPSC ring;
  per-reader read cursors, the same overrun behaviour as Windows.
- `Audio*` (Analyze engine): its own capture `ma_device`; share the analysis
  math with Windows if it's in `AudioDeviceWin.cpp` (extract into `common/`,
  Windows unchanged, same rule as P1).
- `AudioListDevices`: playback + capture lists with names and default flags.

### 2.4 MIDI (`MidiLinux.cpp`, ALSA sequencer)

- Link `asound`, and add `libasound2-dev` to deps (it's already listed).
- `snd_seq_open(SND_SEQ_OPEN_INPUT)`, one app port, subscribe to every
  readable port except our own, `SND_SEQ_CLIENT_SYSTEM` and "Midi Through"
  (unless no hardware exists; then allow Through so tests can use it).
- Hotplug: subscribe to `SND_SEQ_ADDRESS_SUBSCRIBERS` announce events, and
  (re)subscribe on `PORT_START`.
- One reader thread, `poll()` on the seq fds + a wake pipe for stop.
  Event → the same tables and ring as macOS. Clock: handle
  `SND_SEQ_EVENT_CLOCK`, `START`, `STOP`, `CONTINUE` as distinct types.
- `MidiDeviceId` / `MidiDeviceName`: stable across reboots; use client +
  port *names*, not numbers.
- Teardown per §3.1.

### 2.5 Test rig additions (`xvfb-harness.sh`)

Implement steps 3–4 from validation.md:

1. Run the audio group **twice**: `INFINITE_AUDIO_BACKEND=null` (deterministic)
   and PulseAudio with the null sink (proves the real backend path).
2. MIDI, primary: a **parser unit test** (`INFINITE_MIDIPARSETEST=1`) that
   feeds synthetic `snd_seq_event_t`s (note on/off, velocity-0 note-on, CC,
   pitch bend, clock/start/stop, two source ports interleaved) into the
   event → table/ring code, then asserts on `MidiRead`/`MidiReadNotesSince`/
   `MidiClockBpm`. Structure `MidiLinux.cpp` so that function is pure (no
   seq handle). This runs on every CI job, because GitHub runners have no
   kernel sound modules (validation.md L2 step 4).
   Secondary: only if P0's spike found `/dev/snd/seq` (CI or the OrbStack
   container), open a sender client, send notes + clock, and run the MIDI
   fixtures end to end. Otherwise mark them `SKIP (no ALSA seq)`.
3. Extend `INFINITE_SYSINFO` with backend, devices, and MIDI ports.

### 2.6 Sweep

- Run the `audio-pipeline-sweep` skill over the new files and fix what it
  finds.
- Remove P2 entries from `known-test-failures-linux.txt`.

## Exit criteria

- [ ] Audio group green on null backend **and** PulseAudio null sink; `AUDIOPDCTEST`, `DSPTEST`, `AUDIOPARAMSWEEPTEST` pass
- [ ] MIDI fixtures green on a virtual port, **or** SKIPped with the P0-spike reason **plus** the parser unit test green
- [ ] `INFINITE_SYSINFO` lists audio backends/devices + MIDI ports in the CI log
- [ ] audio-pipeline-sweep clean; macOS `--fast` green; Windows CI green
- [ ] Baseline has no P2 entries; README status row updated

## Stays unverified after P2

Latency and xruns at small buffers, real interfaces, PipeWire-native vs
Pulse-compat quirks, JACK, sleep/resume, USB hotplug of real MIDI gear, and
multiple controllers at once. Put all of these on the L4 beta checklist.
