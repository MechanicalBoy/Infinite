#include "platform/Platform.h"

#include <string>
#include <vector>

namespace Platform
{
   struct CameraHandle
   {
   };

   std::vector<CameraDeviceInfo> CameraListDevices()
   {
      return {};
   }

   CameraHandle* CameraOpen(const std::string& /*deviceId*/, CameraResolution /*res*/, bool /*mirrorX*/, std::string& outError)
   {
      outError = "not yet implemented on Linux (P3)";
      return nullptr;
   }

   void CameraClose(CameraHandle* handle)
   {
      delete handle;
   }

   bool CameraIsRunning(CameraHandle* /*handle*/)
   {
      return false;
   }

   void CameraSetMirror(CameraHandle* /*handle*/, bool /*mirrorX*/)
   {
   }

   void CameraSetResolution(CameraHandle* /*handle*/, CameraResolution /*res*/)
   {
   }

   bool CameraReadFrame(CameraHandle* /*handle*/, std::vector<unsigned char>& /*outPixels*/,
                        int& /*outWidth*/, int& /*outHeight*/, unsigned long long& /*outFrameSeq*/)
   {
      return false;
   }
}
