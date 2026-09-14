#pragma once

#include "../Platform.h"
#include <string>
#include <vector>

namespace OrtMatting
{
   // Hook called before creating the Ort::Session to register platform-specific
   // execution providers (e.g. DirectML on Windows).
   // outUsedGpuEp should be set to true if a GPU EP registered successfully.
   // Forward-declared as void* to keep Ort::SessionOptions out of the header.
   using ProviderHook = void (*)(void* sessionOptionsPtr, bool& outUsedGpuEp);

   void SetProviderHook(ProviderHook hook);

   // Core implementation of Platform::SubjectMask using u2netp.onnx via ONNX Runtime.
   bool SubjectMask(const std::string& modelPath,
                    const std::vector<unsigned char>& rgbaPixels, int width, int height,
                    Platform::MattingMode mode, std::vector<unsigned char>& outMask,
                    std::string& outError);

   std::string MattingBackend();
   const std::vector<std::string>& MattingModeNames();
}
