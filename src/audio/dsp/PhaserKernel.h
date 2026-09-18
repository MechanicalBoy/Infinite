#pragma once

#include <algorithm>
#include <atomic>
#include <cmath>

#include "IEffectKernel.h"
#include "AnalogPrimitives.h"
#include "audio/DspMath.h"
#include "audio/MusicTime.h"
#include "audio/ParamMailbox.h"

// Phaser's kernel - cascade of first-order allpass stages with digital and
// analog modes. The cascade is wrapped in a fixed internal feedback loop
// (kFeedbackDigital/kFeedbackAnalog below) - without it the notches the
// allpass chain carves are shallow and the effect reads as a mild EQ sweep
// rather than the resonant "swoosh" every real unit (Phase 90, Small Stone)
// gets by feeding the chain's own output back into its input. No new param:
// same 5 knobs (cutoff, depth, order, spread, rate) + sync + analog + mix
// drive it all, matching how Reverb's FDN redesign stayed on its existing
// controls.
class AudioEffectNode;

struct AllpassStage
{
   float x1 = 0.0f, y1 = 0.0f;

   void Reset() { x1 = y1 = 0.0f; }

   float Process(float x, float a)
   {
      const float y = a * x + x1 - a * y1;
      x1 = x;
      y1 = y;
      return y;
   }
};

class PhaserKernel : public IEffectKernel
{
public:
   static constexpr int kMaxStages = 8;

   enum ParamSlot
   {
      kCutoffHz = 0,
      kRateHz,
      kDepth,
      kSpread,
      kNumSlots
   };

   void PrepareToPlay(double sampleRate, int /*maxBlockSize*/) override
   {
      mSampleRate = sampleRate;
      mMailbox.PrepareToPlay(sampleRate);
      Reset();
   }

   void Reset() override
   {
      for (int i = 0; i < kMaxStages; i++)
      {
         mStagesL[i].Reset();
         mStagesR[i].Reset();
      }
      mPhase = 0.0;
      mDriftLfo.Reset();
      mFbL = mFbR = 0.0f;
   }

   void PushParams(const AudioEffectNode& node, double sampleRate) override;

   void ProcessBlock(const AudioBuffer& in, const AudioBuffer* sidechain, AudioBuffer& out) override;

   int LatencySamples() const override { return 0; }

private:
   // Loop gain around an all-unity-magnitude allpass cascade, so |fb| < 1
   // is unconditionally stable regardless of stage count or cutoff. Analog
   // mode already saturates each stage's output (AsymTanh below), so its
   // loop runs a touch hotter without misbehaving; digital mode has no
   // per-stage saturation, so its feedback stays a bit more conservative.
   static constexpr float kFeedbackDigital = 0.55f;
   static constexpr float kFeedbackAnalog = 0.62f;

   static float AllpassCoeff(float fc, float sampleRate)
   {
      const float clampedFc = std::clamp(fc, 20.0f, sampleRate * 0.45f);
      const float t = tanf((float)M_PI * clampedFc / sampleRate);
      return (t - 1.0f) / (t + 1.0f);
   }

   ParamMailbox mMailbox;
   double mSampleRate = 44100.0;

   std::atomic<int> mStageCount { 4 };
   std::atomic<int> mSync { 0 };
   std::atomic<int> mRateDiv { MusicTime::kQuarter };
   std::atomic<int> mAnalog { 0 };

   AllpassStage mStagesL[kMaxStages];
   AllpassStage mStagesR[kMaxStages];
   double mPhase = 0.0;

   // One-sample feedback tap: each channel's own most recent chain output,
   // fed back into its own next input. Kept per-channel (not summed) so the
   // stereo image the L/R cutoff spread already creates isn't collapsed.
   float mFbL = 0.0f, mFbR = 0.0f;

   // Analog mode components
   AnalogDsp::DriftLfo mDriftLfo;
};
