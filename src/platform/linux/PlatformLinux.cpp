#include "platform/Platform.h"
#include "platform/AppPaths.h"

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>
#include <climits>
#include <unistd.h>
#include <sys/types.h>
#include <sys/stat.h>

namespace Platform
{
   void PreventAppNap()
   {
      // No App Nap mechanism on Linux that affects GLFW.
   }

   float PollTrackpadMagnificationDelta()
   {
      // GLFW does not expose trackpad magnification gestures on X11/Wayland.
      return 0.0f;
   }

   void InstallCrashHandler()
   {
      // Real sigaction crash handler lands in Phase 1.
   }

   void AppendLogLine(const std::string& line)
   {
      std::fprintf(stderr, "%s\n", line.c_str());
      std::string dir = AppPaths::AppSupportDir();
      if (!dir.empty())
      {
         std::string logFile = dir + "/log.txt";
         FILE* f = std::fopen(logFile.c_str(), "a");
         if (f != nullptr)
         {
            std::fprintf(f, "%s\n", line.c_str());
            std::fclose(f);
         }
      }
   }

   void ShowFatalError(const std::string& title, const std::string& message)
   {
      std::fprintf(stderr, "[FATAL] %s: %s\n", title.c_str(), message.c_str());
      AppendLogLine(std::string("[FATAL] ") + title + ": " + message);
      // tinyfiledialogs message box arrives in Phase 1.
   }

   std::string OpenImageDialog()
   {
      return "";
   }

   bool LoadImageRGBA(const std::string& /*path*/, std::vector<unsigned char>& /*outPixels*/,
                      int& /*outWidth*/, int& /*outHeight*/, std::string& outError)
   {
      outError = "not yet implemented on Linux (P1)";
      return false;
   }

   bool LoadImageRGBAFromMemory(const std::vector<unsigned char>& /*bytes*/,
                                std::vector<unsigned char>& /*outPixels*/,
                                int& /*outWidth*/, int& /*outHeight*/, std::string& outError)
   {
      outError = "not yet implemented on Linux (P1)";
      return false;
   }

   std::string OpenHdrDialog()
   {
      return "";
   }

   bool LoadImageFloatRGB(const std::string& /*path*/, std::vector<float>& /*outPixels*/,
                          int& /*outWidth*/, int& /*outHeight*/, std::string& outError)
   {
      outError = "not yet implemented on Linux (P1)";
      return false;
   }

   std::string OpenModelDialog()
   {
      return "";
   }

   bool LoadModel(const std::string& /*path*/, std::vector<ModelVertex>& /*outVertices*/,
                  std::vector<unsigned int>& /*outIndices*/, std::string& outError)
   {
      outError = "not yet implemented on Linux (P1)";
      return false;
   }

   std::string OpenPatchDialog()
   {
      return "";
   }

   std::string SavePatchDialog(const std::string& /*suggestedName*/)
   {
      return "";
   }

   std::string OpenDeviceDialog()
   {
      return "";
   }

   std::string SaveDeviceDialog(const std::string& /*suggestedName*/)
   {
      return "";
   }

   std::string OpenFolderDialog(const char* /*title*/, const std::string& /*initialDir*/)
   {
      return "";
   }

   void OpenExternalUrl(const std::string& /*url*/)
   {
   }

   bool HttpGet(const std::string& /*url*/, const std::string& /*userAgent*/,
                std::string& /*outBody*/, std::string& outError,
                int /*timeoutSeconds*/)
   {
      outError = "not yet implemented on Linux (P1)";
      return false;
   }

   void InitDocumentHandlingPreGlfw()
   {
   }

   void InitDocumentHandlingPostGlfw()
   {
   }

   bool PollPendingOpenFile(std::string& /*outPath*/)
   {
      return false;
   }

   std::string ExecutablePath()
   {
      char buf[PATH_MAX];
      ssize_t len = ::readlink("/proc/self/exe", buf, sizeof(buf) - 1);
      if (len > 0)
      {
         buf[len] = '\0';
         return std::string(buf);
      }
      return "";
   }

   std::string ScannerExecutablePath()
   {
      std::string exe = ExecutablePath();
      size_t slash = exe.find_last_of('/');
      std::string dir = (slash != std::string::npos) ? exe.substr(0, slash) : ".";
      return dir + "/infinite-vst3-scanner";
   }

   void SuppressAppUIForHeadlessProcess()
   {
   }

   bool SubjectMask(const std::vector<unsigned char>& /*inputRgba*/, int /*width*/, int /*height*/,
                    MattingMode /*mode*/, std::vector<unsigned char>& /*outAlpha*/,
                    std::string& outError)
   {
      outError = "not yet implemented on Linux (P1)";
      return false;
   }

   std::string MattingBackend()
   {
      return "None (Linux P1)";
   }

   const std::vector<std::string>& MattingModeNames()
   {
      static const std::vector<std::string> kNames = { "Default" };
      return kNames;
   }

   bool DecodeAudioFileToBuffer(const std::string& /*path*/, SampleBuffer& /*outBuffer*/,
                                std::string& outError)
   {
      outError = "not yet implemented on Linux (P1)";
      return false;
   }
}
