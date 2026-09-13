#include "platform/Platform.h"

#include <cstring>
#include <string>
#include <vector>

namespace Platform
{
   const std::vector<std::string>& AvailableFontFamilies()
   {
      static const std::vector<std::string> sDefaultFonts = {
         "DejaVu Sans", "DejaVu Serif", "Sans", "Serif", "Monospace"
      };
      return sDefaultFonts;
   }

   bool GetTextOutlines(const std::string& /*text*/, const std::string& /*fontName*/,
                        float /*letterSpacing*/, std::vector<TextContour>& outContours,
                        std::string& outError)
   {
      outContours.clear();
      outError = "not yet implemented on Linux (P1)";
      return false;
   }

   void RasterizeText(const TextRasterRequest& req, int width, int height,
                      unsigned char* outPixelsRGBA, float& outFittedSize)
   {
      if (outPixelsRGBA != nullptr && width > 0 && height > 0)
      {
         std::memset(outPixelsRGBA, 0, (size_t)width * height * 4);
      }
      outFittedSize = req.fontSize;
   }
}
