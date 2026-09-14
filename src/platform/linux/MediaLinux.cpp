#include "platform/Platform.h"
#include "tinyfiledialogs.h"

#include <cstdlib>
#include <string>
#include <vector>

namespace Platform
{
   struct VideoHandle
   {
      int width = 0;
      int height = 0;
      double duration = 0.0;
   };

   std::string OpenVideoDialog()
   {
      if (std::getenv("INFINITE_EXITAFTER") != nullptr) return "";
      const char* disp = std::getenv("DISPLAY");
      const char* wayland = std::getenv("WAYLAND_DISPLAY");
      if ((!disp || disp[0] == '\0') && (!wayland || wayland[0] == '\0')) return "";

      const char* const filterPatterns[] = {
         "*.mp4", "*.mov", "*.m4v", "*.avi", "*.mkv", "*.webm", "*.wmv"
      };
      const char* res = tinyfd_openFileDialog(
         "Choose Video",
         "",
         (int)(sizeof(filterPatterns) / sizeof(filterPatterns[0])),
         filterPatterns,
         "Video files",
         0
      );
      return res ? std::string(res) : std::string();
   }

   VideoHandle* VideoOpen(const std::string& /*path*/, std::string& outError)
   {
      outError = "not yet implemented on Linux (P3)";
      return nullptr;
   }

   void VideoClose(VideoHandle* handle)
   {
      delete handle;
   }

   int VideoWidth(VideoHandle* handle)
   {
      return handle ? handle->width : 0;
   }

   int VideoHeight(VideoHandle* handle)
   {
      return handle ? handle->height : 0;
   }

   double VideoDuration(VideoHandle* handle)
   {
      return handle ? handle->duration : 0.0;
   }

   bool VideoFrameAt(VideoHandle* /*handle*/, double /*seconds*/, std::vector<unsigned char>& /*outPixels*/)
   {
      return false;
   }

   bool VideoDecodeIsCatchingUp(VideoHandle* /*handle*/)
   {
      return false;
   }

   bool DecodeVideoAudioTrackToBuffer(const std::string& /*path*/, SampleBuffer& /*outBuffer*/,
                                      std::string& outError)
   {
      outError = "no audio track in this file";
      return false;
   }

   struct RecorderHandle
   {
   };

   RecorderHandle* RecorderStart(const std::string& /*path*/, int /*width*/, int /*height*/,
                                 int /*fps*/, std::string& outError,
                                 const std::string& /*audioPath*/,
                                 bool /*loopAudio*/,
                                 double /*liveAudioSampleRate*/,
                                 int /*liveAudioChannels*/)
   {
      outError = "not yet implemented on Linux (P3)";
      return nullptr;
   }

   bool RecorderAppend(RecorderHandle* /*handle*/, const std::vector<unsigned char>& /*pixels*/)
   {
      return false;
   }

   void RecorderSetInputIsBgra(RecorderHandle* /*handle*/, bool /*isBgra*/)
   {
   }

   std::vector<unsigned char> RecorderAcquireFrameBuffer(RecorderHandle* /*handle*/)
   {
      return {};
   }

   bool RecorderAppend(RecorderHandle* /*handle*/, std::vector<unsigned char>&& /*pixels*/,
                       int /*repeatCount*/)
   {
      return false;
   }

   int RecorderPendingFrameCount(RecorderHandle* /*handle*/)
   {
      return 0;
   }

   int RecorderDroppedFrameCount(RecorderHandle* /*handle*/)
   {
      return 0;
   }

   void RecorderSetTestQueueByteBudget(RecorderHandle* /*handle*/, size_t /*bytes*/)
   {
   }

   bool RecorderAppendAudio(RecorderHandle* /*handle*/, const float* /*interleavedSamples*/, int /*numFrames*/)
   {
      return false;
   }

   bool RecorderStop(RecorderHandle* handle, std::string& outError,
                     int* outFrameCount, int* outDroppedCount)
   {
      if (outFrameCount != nullptr) *outFrameCount = 0;
      if (outDroppedCount != nullptr) *outDroppedCount = 0;
      outError = "not yet implemented on Linux (P3)";
      delete handle;
      return false;
   }

   void RecorderCancel(RecorderHandle* handle)
   {
      delete handle;
   }

   bool RecorderQueueHasRoom(RecorderHandle* /*handle*/, size_t /*bytes*/)
   {
      return false;
   }

   void RecorderFlushPendingAudio(RecorderHandle* /*handle*/)
   {
   }

   void RecorderKickEncoder(RecorderHandle* /*handle*/)
   {
   }

   void RecorderFinishAudioInput(RecorderHandle* /*handle*/)
   {
   }

   std::string RecorderDebugState(RecorderHandle* /*handle*/)
   {
      return "unimplemented (P3)";
   }

   int RecorderFrameCount(RecorderHandle* /*handle*/)
   {
      return 0;
   }

   MovieInfo InspectMovie(const std::string& /*path*/)
   {
      return MovieInfo{};
   }
}
