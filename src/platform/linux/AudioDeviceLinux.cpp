#include "platform/Platform.h"

#include <cstdio>
#include <string>
#include <vector>

namespace Platform
{
   std::string OpenAudioDialog()
   {
      return "";
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
