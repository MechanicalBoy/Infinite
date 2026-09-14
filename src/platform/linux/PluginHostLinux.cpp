#include "platform/Platform.h"

#include <string>
#include <vector>

namespace Platform
{
   void EnumerateAudioUnits(std::vector<PluginDesc>& out)
   {
      out.clear();
   }

   bool DescribeAudioUnitBundle(const std::string& /*bundlePath*/, std::vector<PluginDesc>& out)
   {
      out.clear();
      return false;
   }

   void EnumerateVST3Plugins(const std::vector<std::string>& /*folders*/, std::vector<PluginDesc>& out)
   {
      out.clear();
   }

   bool DescribeVST3Bundle(const std::string& /*bundlePath*/, std::vector<PluginDesc>& out)
   {
      out.clear();
      return false;
   }

   void CacheVST3BundlePath(const std::string& /*identifier*/, const std::string& /*bundlePath*/)
   {
   }

   void SetVST3SearchFolders(const std::vector<std::string>& /*folders*/)
   {
   }

   std::vector<std::string> VST3Blocklist()
   {
      return {};
   }

   void ClearVST3Blocklist()
   {
   }

   std::vector<std::string> VST3ScanFailures()
   {
      return {};
   }

   std::vector<std::string> UnsupportedPluginsSeen()
   {
      return {};
   }

   struct PluginHandle
   {
   };

   PluginHandle* PluginCreate(const PluginDesc& /*desc*/, double /*sampleRate*/, int /*maxBlockFrames*/)
   {
      return nullptr;
   }

   PluginLoadState PluginPoll(PluginHandle* /*handle*/, std::string& outError)
   {
      outError = "plugins not yet supported on Linux (P4)";
      return PluginLoadState::Failed;
   }

   bool PluginPrepare(PluginHandle* /*handle*/, double /*sampleRate*/, int /*maxBlockFrames*/, std::string& outError)
   {
      outError = "plugins not yet supported on Linux (P4)";
      return false;
   }

   void PluginDestroy(PluginHandle* handle)
   {
      delete handle;
   }

   PluginDesc PluginDescriptionOf(PluginHandle* /*handle*/)
   {
      return PluginDesc{};
   }

   int PluginLatencySamples(PluginHandle* /*handle*/)
   {
      return 0;
   }

   void PluginRender(PluginHandle* /*handle*/, const float* const* /*in*/, int /*inChannels*/,
                     float* const* out, int outChannels, int numFrames)
   {
      if (out != nullptr)
      {
         for (int ch = 0; ch < outChannels; ch++)
         {
            if (out[ch] != nullptr && numFrames > 0)
            {
               std::fill(out[ch], out[ch] + numFrames, 0.0f);
            }
         }
      }
   }

   void PluginScheduleMIDIEvent(PluginHandle* /*handle*/, int /*frameOffset*/,
                                const unsigned char* /*bytes*/, int /*byteCount*/)
   {
   }

   int PluginParameterCount(PluginHandle* /*handle*/)
   {
      return 0;
   }

   bool PluginParameterInfo(PluginHandle* /*handle*/, int /*index*/, PluginParamInfo& /*out*/)
   {
      return false;
   }

   bool PluginParameterInfoByAddress(PluginHandle* /*handle*/, unsigned long long /*address*/,
                                     PluginParamInfo& /*out*/)
   {
      return false;
   }

   void PluginSetParameter(PluginHandle* /*handle*/, unsigned long long /*address*/, float /*value*/)
   {
   }

   bool PluginGetParameter(PluginHandle* /*handle*/, unsigned long long /*address*/, float& /*outValue*/)
   {
      return false;
   }

   void PluginBeginLearn(PluginHandle* /*handle*/)
   {
   }

   void PluginEndLearn(PluginHandle* /*handle*/)
   {
   }

   bool PluginPollLearned(PluginHandle* /*handle*/, unsigned long long& /*outAddress*/)
   {
      return false;
   }

   bool PluginOpenEditor(PluginHandle* /*handle*/, std::string& outError)
   {
      outError = "plugin editors not yet supported on Linux (P4)";
      return false;
   }

   void PluginCloseEditor(PluginHandle* /*handle*/)
   {
   }

   bool PluginEditorIsOpen(PluginHandle* /*handle*/)
   {
      return false;
   }

   bool AnyPluginEditorOpen()
   {
      return false;
   }

   bool PumpPluginEditorEvents()
   {
      return false;
   }

   bool PluginSaveState(PluginHandle* /*handle*/, std::string& /*outBase64*/)
   {
      return false;
   }

   bool PluginRestoreState(PluginHandle* /*handle*/, const std::string& /*base64*/)
   {
      return false;
   }
}
