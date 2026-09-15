#pragma once

// Linux-only Platform::PluginHandle. NOT the same type as
// src/platform/PluginHandleInternal.h - that header is AU-shaped and
// unconditionally pulls in Cocoa/AudioToolbox/AVFoundation, so it cannot be
// included here. Linux has no AudioUnit backend at all (macOS-only format),
// so like Windows, every Linux plugin handle is a VST3 handle or nothing.
// Mirrors src/platform/win/PluginHandleInternalWin.h exactly.

#include "../Platform.h"
#include <string>

namespace Platform
{
   // Defined in PluginVST3Linux.cpp alongside the rest of the VST3 hosting
   // machinery (host glue classes, IPtr fields, realtime process data) -
   // mirroring the PluginHandleInternal.h / PluginVST3.mm split on macOS and
   // the PluginHandleInternalWin.h / PluginVST3Win.cpp split on Windows,
   // where PluginVST3State is likewise opaque to everything outside that one
   // translation unit.
   struct PluginVST3State;

   struct PluginHandle
   {
      PluginDesc desc;
      PluginLoadState state = PluginLoadState::Pending;
      std::string loadError;

      double sampleRate = 0.0;
      int maxBlockFrames = 0;

      // Refreshed from IAudioProcessor::getLatencySamples() once
      // setupProcessing/setActive succeed; read by PluginLatencySamples().
      int latencySamples = 0;

      // Null for a handle that failed before ever touching VST3 (e.g. an
      // AU-format PluginDesc, which Linux can't host at all).
      PluginVST3State* vst3 = nullptr;
   };
}
