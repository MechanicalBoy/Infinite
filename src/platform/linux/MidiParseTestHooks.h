// Declarations for the INFINITE_MIDIPARSETEST hooks implemented at the
// bottom of MidiLinux.cpp. Linux-only, deliberately not part of Platform.h
// (see that file's trailing comment) - only src/main.cpp includes this, and
// only behind an `#if defined(__linux__)` guard, matching the existing
// precedent for Platform::HasGuiDialogHelper() in src/core/SysInfo.cpp.
#pragma once

#include <alsa/asoundlib.h>
#include <string>

namespace PlatformLinuxTestHooks
{
   void MidiParseTestResetState();
   unsigned int MidiParseTestDeviceId(const std::string& name);
   void MidiParseTestFeedEvent(unsigned int dev, const snd_seq_event_t& ev);
}
