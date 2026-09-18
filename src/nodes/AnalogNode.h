#pragma once

#include <memory>
#include <string>
#include <vector>

#include "audio/SynthModes.h"
#include "core/AudioCable.h"
#include "core/INode.h"
#include "core/NoteCable.h"

class AudioAnalogNode;

enum AnalogFilterType
{
   kAFilterOff = 0,
   kAFilterLadder,   // ZDF nonlinear Moog ladder
   kAFilterSvfLP,    // 12 dB SVF Lowpass
   kAFilterSvfHP,    // 12 dB SVF Highpass
   kAFilterSvfBP,    // 12 dB SVF Bandpass
   kAFilterSvfNotch, // 12 dB SVF Notch
   kNumAFilterTypes
};

enum AnalogWaveform
{
   kAWaveSaw = 0,
   kAWaveSquare,
   kAWaveTriangle,
   kNumAWaveforms
};

inline const std::vector<std::string>& AnalogWaveformList()
{
   static const std::vector<std::string> kList = { "saw", "square", "triangle" };
   return kList;
}

inline const std::vector<std::string>& AnalogFilterTypeList()
{
   static const std::vector<std::string> kList = {
      "off",
      "ladder lp",
      SynthModes::FilterName(SynthModes::kFilterLP12),
      SynthModes::FilterName(SynthModes::kFilterHP12),
      SynthModes::FilterName(SynthModes::kFilterBP12),
      SynthModes::FilterName(SynthModes::kFilterNotch12)
   };
   return kList;
}

struct AnalogSynthParams
{
   float volume = 0.8f;
   float freq = 220.0f;
   float glide = 0.0f;
   float pitchBend = 0.0f;
   float pw1 = 0.5f;
   float voices = 1.0f;
   float spread = 0.2f;
   float osc2Tune = 0.0f;
   float osc2Detune = 0.0f;
   float oscMix = 0.0f;
   float sub = 0.0f;
   float noise = 0.0f;
   float cutoff = 8000.0f;
   float resonance = 0.0f;
   float drive = 0.0f;
   float keyTrack = 0.0f;
   float attack = 5.0f;     // ms
   float decay = 300.0f;    // ms
   float sustain = 0.75f;   // 0..1
   float release = 250.0f;  // ms

   int wave1 = kAWaveSaw;
   int wave2 = kAWaveSaw;
   int filterType = kAFilterLadder;
   bool sync = false;
   bool analog = true;
};

class AnalogNode : public INode, public IAudioSource
{
public:
   static constexpr int kMaxVoices = 8;
   static constexpr int kMaxUnison = 7;

   static INode* Create() { return new AnalogNode(); }
   AnalogNode();
   ~AnalogNode() override;

   unsigned int GetOutputTexture() override { return 0; }
   int GetOutputWidth() const override { return 0; }
   int GetOutputHeight() const override { return 0; }
   void CookIfNeeded(int frameId) override;
   void VisitParams(ParamVisitor& v) override;

   AudioNode* GetAudioNode() override;

   AudioCable* AudioInputSlot(int /*slot*/) override { return nullptr; }
   NoteCable* NoteInputSlot(int slot) override { return slot == 0 ? &noteInput : nullptr; }
   const char* InputLabel(int slot) const override
   {
      return slot == 0 ? "notes" : nullptr;
   }

   int ReadScope(float* out, int capacity);
   int ActiveVoices() const;
   double DebugMailboxSampleRate() const;

   // 19 smoothed floats
   float volume = 0.8f;
   float freq = 220.0f;
   float glide = 0.0f;
   float pitchBend = 0.0f;
   float pw1 = 0.5f;
   float voices = 1.0f;
   float spread = 0.2f;
   float osc2Tune = 0.0f;
   float osc2Detune = 0.0f;
   float oscMix = 0.0f;
   float sub = 0.0f;
   float noise = 0.0f;
   float cutoff = 8000.0f;
   float resonance = 0.0f;
   float drive = 0.0f;
   float keyTrack = 0.0f;
   float attack = 5.0f;     // ms
   float decay = 300.0f;    // ms
   float sustain = 0.75f;   // 0..1
   float release = 250.0f;  // ms

   // Discrete settings
   int wave1 = kAWaveSaw;
   int wave2 = kAWaveSaw;
   int filterType = kAFilterLadder;
   bool sync = false;
   bool analog = true;

   NoteCable noteInput;

private:
   std::unique_ptr<AudioAnalogNode> mAudioNode;
   int mLastCookFrame = -1;
};
