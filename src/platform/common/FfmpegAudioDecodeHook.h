#pragma once

// Seam letting src/platform/linux/MediaLinux.cpp (the only TU in the build
// that links FFmpeg) supply an FFmpeg-based fallback for audio-file
// containers MediaDecodePortable.cpp's dr_libs/AIFF paths cannot read
// (m4a/m4b/caf/ogg/opus) - mirrors SubjectMaskOnnx.cpp's ProviderHook
// pattern (Windows registers DirectML there; here Linux registers an FFmpeg
// decoder into a file shared with Windows, which has no FFmpeg and leaves
// the hook null). Windows keeps reporting these containers unsupported.

#include "../Platform.h"

namespace Platform
{
   using FfmpegAudioDecodeFn = bool (*)(const std::string& path, SampleBuffer& outBuffer,
                                        std::string& outError);

   // Registered once, from a global constructor in MediaLinux.cpp (Linux
   // only). Never called/linked from the Windows build.
   void SetFfmpegAudioDecodeHook(FfmpegAudioDecodeFn fn);
}
