#include "SysInfo.h"
#include "core/gl3.h"

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
#include "platform/Platform.h"
extern "C"
{
#include <libavcodec/avcodec.h>
#include <libavutil/avutil.h>
}
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
      std::printf("FFmpeg (libavutil): %s\n", av_version_info());
#if defined(INFINITE_ENABLE_GPL_CODECS)
      std::printf("H.264 encoder: %s\n", avcodec_find_encoder_by_name("libx264") != nullptr
                                             ? "libx264 (present)" : "libx264 (MISSING)");
#else
      std::printf("H.264 encoder: none (INFINITE_ENABLE_GPL_CODECS=OFF)\n");
#endif
      std::printf("AAC encoder: %s\n", avcodec_find_encoder(AV_CODEC_ID_AAC) != nullptr
                                          ? "present" : "MISSING");
      {
         const std::vector<Platform::CameraDeviceInfo> cams = Platform::CameraListDevices();
         std::printf("Cameras found: %zu\n", cams.size());
         for (const auto& cam : cams)
            std::printf("  - %s (%s)%s\n", cam.localizedName.c_str(), cam.uniqueId.c_str(),
                       cam.isDefault ? " [default]" : "");
      }
#endif
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
