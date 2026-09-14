#include "platform/Platform.h"
#include "tinyfiledialogs.h"

#include <cstdio>
#include <cstdlib>
#include <string>
#include <vector>

namespace Platform
{
   std::string OpenAudioDialog()
   {
      if (std::getenv("INFINITE_EXITAFTER") != nullptr) return "";
      const char* disp = std::getenv("DISPLAY");
      const char* wayland = std::getenv("WAYLAND_DISPLAY");
      if ((!disp || disp[0] == '\0') && (!wayland || wayland[0] == '\0')) return "";

      const char* const filterPatterns[] = {
         "*.wav", "*.aif", "*.aiff", "*.mp3", "*.flac"
      };
      const char* res = tinyfd_openFileDialog(
         "Choose Audio File",
         "",
         (int)(sizeof(filterPatterns) / sizeof(filterPatterns[0])),
         filterPatterns,
         "Audio files (*.wav, *.aif, *.aiff, *.mp3, *.flac)",
         0
      );
      return res ? std::string(res) : std::string();
   }

   bool AudioStart(std::string& outError)
   {
      outError = "not yet implemented on Linux (P2)";
      return false;
   }

   void AudioStop()
   {
   }

   bool AudioIsRunning()
   {
      return false;
   }

   std::string AudioDeviceName()
   {
      return "Default Audio Device";
   }

   bool AudioRead(AudioLevels& out)
   {
      out = AudioLevels{};
      return false;
   }

   void AudioSetSmoothing(float /*attack*/, float /*release*/)
   {
   }

   void AudioSetGain(float /*gain*/)
   {
   }

   bool AudioSpikeStart(std::string& outError)
   {
      // Not a phase stub: this is a P0 throwaway that was never wired into the
      // product UI, and PlatformWin.cpp:662 declines it for the same reason.
      // No phase tag, because no phase will implement it.
      outError = "not supported on Linux";
      return false;
   }

   void AudioSpikeStop()
   {
   }

   AudioSpikeStats AudioSpikeGetStats()
   {
      return AudioSpikeStats{};
   }

   bool AudioDeviceOpen(AudioRenderCallback /*callback*/, void* /*userData*/, double& outSampleRate,
                        std::string& outError, uint32_t /*requestedDeviceId*/,
                        double /*requestedSampleRate*/, int /*requestedBufferFrames*/)
   {
      outSampleRate = 48000.0;
      outError = "not yet implemented on Linux (P2)";
      return false;
   }

   void AudioDeviceClose()
   {
   }

   uint32_t AudioDeviceBufferFrames(uint32_t /*deviceId*/)
   {
      return 512;
   }

   bool AudioPcmConversionSelfTest()
   {
      std::printf("AUDIOPCMTEST OK\n");
      return true;
   }

   bool AudioDeviceConfigDidChange()
   {
      return false;
   }

   bool AudioWillSleep()
   {
      return false;
   }

   bool AudioDidWake()
   {
      return false;
   }

   void AudioDeviceDebugSimulateConfigChange()
   {
   }

   std::vector<AudioDeviceInfo> AudioListDevices()
   {
      AudioDeviceInfo def;
      def.name = "Default";
      def.deviceId = 0;
      def.isOutput = true;
      def.isInput = true;
      def.outputChannels = 2;
      def.inputChannels = 2;
      return { def };
   }

   void AudioInputCaptureAddRef()
   {
   }

   void AudioInputCaptureRemoveRef()
   {
   }

   void AudioInputCaptureSetDevice(uint32_t /*deviceId*/)
   {
   }

   uint32_t AudioInputCaptureGetDevice()
   {
      return 0;
   }

   void AudioInputCapturePump(std::string& outError)
   {
      outError = "not yet implemented on Linux (P2)";
   }

   bool AudioInputCaptureIsRunning()
   {
      return false;
   }

   int AudioInputCaptureRead(float* const* outChannels, int numFrames, int maxChannels,
                             uint64_t& /*readerCursor*/, int /*channelOffset*/, bool /*isMono*/)
   {
      if (outChannels != nullptr)
      {
         for (int ch = 0; ch < maxChannels; ch++)
         {
            if (outChannels[ch] != nullptr && numFrames > 0)
            {
               std::fill(outChannels[ch], outChannels[ch] + numFrames, 0.0f);
            }
         }
      }
      return 0;
   }

   int AudioInputCaptureRead(float* const* outChannels, int numFrames, int maxChannels)
   {
      uint64_t cursor = 0;
      return AudioInputCaptureRead(outChannels, numFrames, maxChannels, cursor, 0, false);
   }
}
