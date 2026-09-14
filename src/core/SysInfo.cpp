#include "SysInfo.h"
#include "core/gl3.h"
#include "platform/Platform.h"

#define GLFW_INCLUDE_NONE
#include <GLFW/glfw3.h>

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

#if defined(_WIN32)
   #include <windows.h>
#else
   #include <sys/utsname.h>
#endif

#ifndef INFINITE_VERSION_STRING
   #define INFINITE_VERSION_STRING "dev"
#endif

#if defined(__linux__)
namespace Platform { extern bool HasGuiDialogHelper(); }
#endif

namespace SysInfo
{
   void PrintAndExit(GLFWwindow* /*window*/)
   {
      std::printf("================ Infinite System Info ================\n");
      std::printf("Infinite version: %s\n", INFINITE_VERSION_STRING);

#if defined(_WIN32)
      std::printf("OS: Windows\n");
#else
      struct utsname un {};
      if (uname(&un) == 0)
      {
         std::printf("OS: %s %s %s (%s)\n", un.sysname, un.release, un.version, un.machine);
      }
      else
      {
         std::printf("OS: POSIX (uname failed)\n");
      }
#endif

      int platform = glfwGetPlatform();
      const char* platformName = "Unknown";
      if (platform == GLFW_PLATFORM_WIN32) platformName = "Win32";
      else if (platform == GLFW_PLATFORM_COCOA) platformName = "Cocoa (macOS)";
      else if (platform == GLFW_PLATFORM_WAYLAND) platformName = "Wayland";
      else if (platform == GLFW_PLATFORM_X11) platformName = "X11";
      else if (platform == GLFW_PLATFORM_NULL) platformName = "Null";
      std::printf("GLFW Platform: %s\n", platformName);

      const GLubyte* vendor = glGetString(GL_VENDOR);
      const GLubyte* renderer = glGetString(GL_RENDERER);
      const GLubyte* version = glGetString(GL_VERSION);
      const GLubyte* glslVersion = glGetString(GL_SHADING_LANGUAGE_VERSION);

      std::printf("GL Vendor:    %s\n", vendor ? (const char*)vendor : "null");
      std::printf("GL Renderer:  %s\n", renderer ? (const char*)renderer : "null");
      std::printf("GL Version:   %s\n", version ? (const char*)version : "null");
      std::printf("GLSL Version: %s\n", glslVersion ? (const char*)glslVersion : "null");
#if defined(__linux__)
      std::printf("Dialog helper: %s\n", Platform::HasGuiDialogHelper() ? "yes" : "no (zenity/kdialog missing)");
#endif

      // Audio backend/device and MIDI port enumeration - portable, since
      // AudioListDevices/MidiStart/MidiDeviceSummary are already implemented
      // on all three platforms (docs/plans/linux/phase-02-audio-midi.md
      // 2.5.3). This is diagnostics only: MidiStart's device list here comes
      // from whatever was already running, or a short-lived probe start/stop
      // if nothing was, so INFINITE_SYSINFO stays a read-only snapshot.
      const std::vector<Platform::AudioDeviceInfo> audioDevices = Platform::AudioListDevices();
      std::printf("Audio devices: %d\n", (int)audioDevices.size());
      for (const auto& dev : audioDevices)
      {
         std::printf("  [%u] %s%s%s (in=%d out=%d)\n", dev.deviceId, dev.name.c_str(),
                     dev.isInput ? " [input]" : "", dev.isOutput ? " [output]" : "",
                     dev.inputChannels, dev.outputChannels);
      }

      const bool midiWasRunning = Platform::MidiIsRunning();
      std::string midiError;
      if (!midiWasRunning)
         Platform::MidiStart(midiError);
      std::printf("MIDI ports: %s\n", Platform::MidiDeviceSummary().c_str());
      if (!midiWasRunning)
         Platform::MidiStop();

      std::printf("======================================================\n");
      std::fflush(stdout);
      std::exit(0);
   }

   void CrashTest()
   {
      volatile int* bad = nullptr;
      *bad = 42;
   }
}
