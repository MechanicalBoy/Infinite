#include "platform/Platform.h"

#include <string>

namespace Platform
{
   bool MidiStart(std::string& outError)
   {
      outError = "not yet implemented on Linux (P2)";
      return false;
   }

   void MidiStop()
   {
   }

   bool MidiIsRunning()
   {
      return false;
   }

   std::string MidiDeviceSummary()
   {
      return "No MIDI devices (Linux P2)";
   }

   std::string MidiDeviceName(MidiDeviceId /*device*/)
   {
      return "";
   }

   bool MidiRead(MidiDeviceId /*device*/, int /*channel*/, int /*controller*/, bool /*isNote*/, float& outValue01)
   {
      outValue01 = 0.0f;
      return false;
   }

   bool MidiPollLastTouched(MidiCCValue& /*outLast*/)
   {
      return false;
   }

   unsigned int MidiNoteHitCount(MidiDeviceId /*device*/, int /*channel*/, int /*note*/)
   {
      return 0;
   }

   bool MidiChannelLastNote(MidiDeviceId /*device*/, int /*channel*/, MidiLastNote& /*out*/)
   {
      return false;
   }

   int MidiReadNotesSince(unsigned long long& /*cursor*/, MidiNoteMessage* /*out*/, int /*maxCount*/)
   {
      return 0;
   }

   unsigned long long MidiNoteStreamPosition()
   {
      return 0;
   }

   bool MidiClockIsPresent()
   {
      return false;
   }

   float MidiClockBpm()
   {
      return 0.0f;
   }
}
