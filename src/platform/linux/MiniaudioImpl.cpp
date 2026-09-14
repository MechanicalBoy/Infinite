// The one Linux translation unit that compiles miniaudio's implementation.
// Vendored at external/miniaudio/miniaudio.h, pinned to v0.11.25 (see that
// file's own header comment for the exact date/commit). Every other Linux
// platform TU (AudioDeviceLinux.cpp) includes the same header WITHOUT
// MINIAUDIO_IMPLEMENTATION and links against the symbols defined here.
//
// MA_ENABLE_ONLY_SPECIFIC_BACKENDS + the four MA_ENABLE_* below compile in
// only the backends Infinite actually uses on Linux - PulseAudio (also
// covers PipeWire via its Pulse-compat shim; see docs/plans/linux/
// phase-02-audio-midi.md for why there's no native PipeWire backend to
// prefer as of this miniaudio version), ALSA, JACK, and Null (CI/tests).
// Backend selection order and the INFINITE_AUDIO_BACKEND override live in
// AudioDeviceLinux.cpp, not here.
//
// miniaudio dlopen()s each backend's client library (libpulse.so,
// libasound.so, libjack.so) at runtime rather than being linked against it -
// see linux-parity SKILL.md §3.4, "load it, don't link it". So this TU adds
// no new hard .so dependency to the Infinite binary: a system with none of
// these installed still starts, and simply has nothing but the null backend
// available.
#define MINIAUDIO_IMPLEMENTATION
#define MA_ENABLE_ONLY_SPECIFIC_BACKENDS
#define MA_ENABLE_PULSEAUDIO
#define MA_ENABLE_ALSA
#define MA_ENABLE_JACK
#define MA_ENABLE_NULL

#if defined(__GNUC__) || defined(__clang__)
#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wunused-function"
#pragma GCC diagnostic ignored "-Wunused-parameter"
#pragma GCC diagnostic ignored "-Wsign-compare"
#endif

#include "miniaudio.h"

#if defined(__GNUC__) || defined(__clang__)
#pragma GCC diagnostic pop
#endif
